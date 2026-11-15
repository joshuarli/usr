import assert from 'node:assert/strict'
import { createServer } from 'node:http'
import { execFileSync, spawnSync } from 'node:child_process'
import { mkdirSync, mkdtempSync, readFileSync, writeFileSync } from 'node:fs'
import { join } from 'node:path'
import { qualificationBridge } from './bridge.ts'
import { makeFxAdapter } from '../../src/fx.ts'
import { dispatch } from '../../src/server.ts'
import { OwnerManager } from '../../src/owner.ts'
import { ownerJobs, ownerResume, ownerSteer, ownerInterrupt } from '../../src/owner-client.ts'
import { decodeSession } from '../../src/session.ts'

export async function bridgePilot(binary, scratch, options = {}) {
  const root = mkdtempSync(join(scratch, 'fx-bridge-')), home = join(root, 'home'), repo = join(home, 'repo'), cwd = join(repo, '.work/wt/pilot')
  mkdirSync(repo, { recursive: true })
  const git = (...args) => execFileSync('git', ['-C', repo, ...args], { encoding: 'utf8', timeout: 10000 }).trim()
  git('init', '-q'); git('config', 'user.name', 'Fixture'); git('config', 'user.email', 'fixture@example.com')
  writeFileSync(join(repo, 'arithmetic.py'), 'def add(a, b):\n    return a - b\n')
  writeFileSync(join(repo, 'check.py'), 'import sys\nfrom arithmetic import add\nassert add(2, 3) == 5\nif sys.argv[1] == "strings": assert add("2", "3") == 5\nprint("check passed")\n')
  writeFileSync(join(repo, '.gitignore'), '__pycache__/\n')
  git('add', '.'); git('commit', '-qm', 'fixture'); writeFileSync(join(repo, '.git/info/exclude'), '/.work/\n')
  mkdirSync(join(repo, '.work/wt'), { recursive: true }); git('worktree', 'add', '-qb', 'pilot', cwd)
  let calls = [], requests = [], final = '', providerError, holdAt = 0, heldResolve = () => {}
  const server = createServer(async (req, res) => {
    try {
      let raw = ''; for await (const chunk of req) { raw += chunk; if (raw.length > 1048576) throw new Error('request too large') }
      const body = JSON.parse(raw); assert.equal(body.model, 'fixture-model'); assert.equal(body.reasoning_effort, 'high')
      requests.push(body); if (requests.length > 20) throw new Error('model-step budget exceeded')
      if (holdAt && requests.length === holdAt) { heldResolve(); return }
      const call = calls.shift(), index = requests.length
      const delta = call ? { role: 'assistant', tool_calls: [{ index: 0, id: 'call_' + index, type: 'function', function: { name: call[0], arguments: JSON.stringify(call[1]) } }] } : { role: 'assistant', content: final + '\nACCEPTANCE: met' }
      res.writeHead(200, { 'content-type': 'text/event-stream' }); res.end('data: ' + JSON.stringify({ id: 'fixture', object: 'chat.completion.chunk', model: 'fixture-model', choices: [{ index: 0, delta, finish_reason: call ? 'tool_calls' : 'stop' }], usage: { prompt_tokens: 10, completion_tokens: 5, total_tokens: 15 } }) + '\n\ndata: [DONE]\n\n')
    } catch (error) { providerError = error; res.writeHead(400); res.end('fixture rejected request') }
  })
  await new Promise(r => server.listen(0, '127.0.0.1', r))
  const connection = { protocol: 'openai-chat-completions', base_url: `http://127.0.0.1:${server.address().port}/v1`, auth: { type: 'none' }, model_metadata: { 'fixture-model': { context_window: 32768, max_output_tokens: 2048, supports_tool_use: true, reasoning_efforts: { high: { reasoning_effort: 'high' } } } } }
  const fx = makeFxAdapter({ binary, binarySha256: JSON.parse(readFileSync(new URL('./pin.json', import.meta.url), 'utf8')).binary_sha256, home, provider: 'fixture', connection, allowedCommands: ['python3 check.py numbers', 'python3 check.py strings'], wallMs: 15000 })
  const bridge = qualificationBridge(fx), owner = new OwnerManager(bridge), ids = []
  await owner.ensureRepo(repo)
  const base = git('rev-parse', 'HEAD'), scope = { base_revision: base, writable_paths: ['arithmetic.py'], acceptance_proof: 'python3 check.py numbers exits zero; correction also passes python3 check.py strings', attempt_limit: 2, stop_on: 'scope expansion, unavailable proof or dependencies' }
  async function wait(id) {
    const deadline = Date.now() + 20000
    while (Date.now() < deadline) {
      if (providerError) throw providerError
      const result = await dispatch(bridge, { name: 'status', cwd, session_id: id })
      if (result.state !== 'running') return result
      await new Promise(r => setTimeout(r, 25))
    }
    throw new Error('bridge job did not terminate')
  }
  async function start(title, tier, jobScope) {
    const admitted = await dispatch(bridge, { name: 'start', cwd, title, tier, scope: jobScope, brief: title })
    assert.equal(admitted.backend, 'fx'); ids.push(admitted.session_id)
    const result = await wait(admitted.session_id)
    assert.equal(result.state, 'succeeded'); assert.equal(result.acceptance_claim, 'met'); assert.deepEqual(result.out_of_scope_paths, [])
    return { admitted, result }
  }
  try {
    calls = [['read_file', { path: 'arithmetic.py' }]]; final = 'arithmetic.py:2 subtracts b instead of adding it; add(2,3) returns -1.'
    const scout = await start('Locate the arithmetic error with file and line evidence; do not edit or run shell commands.', 'scout', { ...scope, writable_paths: [], acceptance_proof: 'arithmetic.py:2 evidence' })
    assert.match(scout.result.last_assistant_text, /arithmetic\.py:2/); assert.match(readFileSync(join(cwd, 'arithmetic.py'), 'utf8').split('\n')[1], /a - b/)
    assert.equal(git('-C', cwd, 'status', '--porcelain'), '')
    requests = []; calls = [['read_file', { path: 'arithmetic.py' }], ['write_file', { path: 'arithmetic.py', content: 'def add(a, b):\n    return a + b\n' }], ['shell', { action: 'run', command: 'python3 check.py numbers' }]]; final = 'PROOF: python3 check.py numbers exited 0 with check passed'
    assert.throws(() => execFileSync('python3', ['check.py', 'numbers'], { cwd, stdio: 'pipe' }))
    const worker = await start('Fix arithmetic.add for numeric arguments and run python3 check.py numbers.', 'worker', scope)
    execFileSync('python3', ['check.py', 'numbers'], { cwd }); assert.throws(() => execFileSync('python3', ['check.py', 'strings'], { cwd, stdio: 'pipe' }))
    const savedPath = join(repo, '.work/worker-bridge', worker.admitted.session_id + '.json')
    const before = decodeSession(JSON.parse(readFileSync(savedPath, 'utf8')), cwd, worker.admitted.session_id)
    verifyNativeCheck(before.execution.run, 'python3 check.py numbers', cwd)
    const beforeToken = fx.status(before.execution.run, before.execution.selection).result.sessionId
    const job = (await ownerJobs(repo, owner.ownerId)).find(item => item.job_id === worker.admitted.session_id)
    const target = { job_id: job.job_id, run_id: job.run_id, owner_generation: job.owner_generation }
    requests = []; calls = [['write_file', { path: 'arithmetic.py', content: 'def add(a, b):\n    return int(a) + int(b)\n' }], ['shell', { action: 'run', command: 'python3 check.py strings' }]]; final = 'PROOF: python3 check.py strings exited 0 with check passed'
    const command = { target, command_id: 'fixture-correction', feedback: 'The same function must also accept numeric string arguments. Run python3 check.py strings. Keep the same file scope.' }
    assert.equal((await ownerResume(repo, owner.ownerId, command)).receipt, 'accepted')
    assert.equal((await ownerResume(repo, owner.ownerId, command)).receipt, 'accepted')
    const corrected = await wait(worker.admitted.session_id)
    assert.equal(corrected.state, 'succeeded'); assert.deepEqual(corrected.out_of_scope_paths, [])
    assert.equal(requests.length, 3); assert.ok(requests[0].messages.some(message => message.role === 'tool'))
    execFileSync('python3', ['check.py', 'strings'], { cwd })
    const after = decodeSession(JSON.parse(readFileSync(savedPath, 'utf8')), cwd, worker.admitted.session_id)
    verifyNativeCheck(after.execution.run, 'python3 check.py strings', cwd)
    assert.equal(fx.status(after.execution.run, after.execution.selection).result.sessionId, beforeToken)
    assert.equal(after.attempts, 2); assert.equal(git('-C', cwd, 'rev-parse', 'HEAD'), base)
    assert.equal(git('-C', cwd, 'diff', '--name-only'), 'arithmetic.py')
    git('-C', cwd, 'checkout', '--', 'arithmetic.py')
    requests = []; calls = [['read_file', { path: 'arithmetic.py' }]]; holdAt = 2
    const steeringBarrier = new Promise(r => { heldResolve = r })
    const active = await dispatch(bridge, { name: 'start', cwd, title: 'same-scope steering fixture', tier: 'worker', scope, brief: 'Fix arithmetic.add and run the assigned check.' })
    ids.push(active.session_id)
    await boundedBarrier(steeringBarrier)
    const activeWire = decodeSession(JSON.parse(readFileSync(join(repo, '.work/worker-bridge', active.session_id + '.json'), 'utf8')), cwd, active.session_id)
    const steeringToken = fx.session(activeWire.execution.run, activeWire.execution.selection)
    assert.ok(steeringToken)
    const activeJob = (await ownerJobs(repo, owner.ownerId)).find(item => item.job_id === active.session_id)
    const activeTarget = { job_id: activeJob.job_id, run_id: activeJob.run_id, owner_generation: activeJob.owner_generation }
    holdAt = 0; requests = []; calls = [['write_file', { path: 'arithmetic.py', content: 'def add(a, b):\n    return int(a) + int(b)\n' }], ['shell', { action: 'run', command: 'python3 check.py strings' }]]
    final = 'PROOF: steered python3 check.py strings exited 0'
    const steeringCommand = { target: activeTarget, command_id: 'fixture-steering', note: 'Same scope: support numeric strings and run python3 check.py strings.' }
    assert.equal((await ownerSteer(repo, owner.ownerId, steeringCommand)).receipt, 'accepted')
    assert.equal((await ownerSteer(repo, owner.ownerId, steeringCommand)).receipt, 'accepted')
    const steering = await wait(active.session_id)
    assert.equal(steering.state, 'succeeded'); assert.equal(steering.steers, 1)
    const steeredWire = decodeSession(JSON.parse(readFileSync(join(repo, '.work/worker-bridge', active.session_id + '.json'), 'utf8')), cwd, active.session_id)
    verifyNativeCheck(steeredWire.execution.run, 'python3 check.py strings', cwd)
    assert.equal(steeredWire.attempts, 1); assert.equal(fx.status(steeredWire.execution.run, steeredWire.execution.selection).result.sessionId, steeringToken)
    execFileSync('python3', ['check.py', 'strings'], { cwd })
    git('-C', cwd, 'checkout', '--', 'arithmetic.py')
    requests = []; calls = [['write_file', { path: 'arithmetic.py', content: 'def add(a, b):\n    return a + b\n' }]]; holdAt = 2
    const interruptBarrier = new Promise(r => { heldResolve = r })
    const pending = await dispatch(bridge, { name: 'start', cwd, title: 'interrupt after edit fixture', tier: 'worker', scope, brief: 'Fix arithmetic.add and wait for parent control.' })
    ids.push(pending.session_id)
    await boundedBarrier(interruptBarrier)
    const pendingJob = (await ownerJobs(repo, owner.ownerId)).find(item => item.job_id === pending.session_id)
    const pendingTarget = { job_id: pendingJob.job_id, run_id: pendingJob.run_id, owner_generation: pendingJob.owner_generation }
    assert.equal((await ownerInterrupt(repo, owner.ownerId, { target: pendingTarget, command_id: 'fixture-interrupt' })).receipt, 'accepted')
    const interruption = await wait(pending.session_id)
    assert.equal(interruption.state, 'cancelled')
    assert.match(readFileSync(join(cwd, 'arithmetic.py'), 'utf8'), /a \+ b/)
    await assert.rejects(() => dispatch(bridge, { name: 'start', cwd, title: 'unsafe duplicate', tier: 'worker', scope, brief: 'task' }), /clean/)
    holdAt = 0
    let benchmark
    if (options.benchmark) {
      const gate = spawnSync('perf-gate-ready', [], { encoding: 'utf8', timeout: 60000 })
      if (gate.status !== 0) benchmark = { status: 'deferred', reason: gate.status === 75 ? 'perf gate deferred: host busy' : 'performance gate unavailable', gate_exit: gate.status }
      else {
        const originalJob = JSON.parse(readFileSync(before.execution.run.output + '.job.json', 'utf8'))
        const samples = []
        for (let pair = 0; pair < 5; pair++) {
          for (const kind of pair % 2 === 0 ? ['adapter', 'bridge'] : ['bridge', 'adapter']) {
            git('-C', cwd, 'checkout', '--', 'arithmetic.py')
            requests = []; calls = [['read_file', { path: 'arithmetic.py' }], ['write_file', { path: 'arithmetic.py', content: 'def add(a, b):\n    return a + b\n' }], ['shell', { action: 'run', command: 'python3 check.py numbers' }]]
            final = 'PROOF: python3 check.py numbers exited 0 with check passed'
            let run, jobId, result, sampledPeakRssKiB = null
            const started = performance.now()
            if (kind === 'adapter') run = fx.start({ directory: cwd, logDirectory: join(repo, '.work/worker-bridge'), prompt: originalJob.args.at(-1), selection: originalJob.selection, access: { kind: 'write' } })
            else {
              const admitted = await dispatch(bridge, { name: 'start', cwd, title: 'Fix arithmetic.add for numeric arguments and run python3 check.py numbers.', tier: 'worker', scope, brief: 'Fix arithmetic.add for numeric arguments and run python3 check.py numbers.' })
              jobId = admitted.session_id; ids.push(jobId)
              run = JSON.parse(readFileSync(join(repo, '.work/worker-bridge', jobId + '.json'), 'utf8')).execution.run
            }
            for (;;) {
              result = kind === 'adapter' ? fx.status(run, originalJob.selection) : await dispatch(bridge, { name: 'status', cwd, session_id: jobId })
              try {
                const native = JSON.parse(readFileSync(run.output + '.native.json', 'utf8'))
                const rss = Number(execFileSync('ps', ['-p', String(native.child_pid), '-o', 'rss='], { encoding: 'utf8', stdio: ['ignore', 'pipe', 'ignore'], timeout: 1000 }).trim())
                if (rss > 0) sampledPeakRssKiB = Math.max(sampledPeakRssKiB ?? 0, rss)
              } catch {}
              if (result.state !== 'running') break
              if (performance.now() - started > 20000) throw new Error('benchmark job exceeded fixture deadline')
              await new Promise(r => setTimeout(r, 25))
            }
            assert.equal(result.state, 'succeeded'); assert.equal(requests.length, 4)
            execFileSync('python3', ['check.py', 'numbers'], { cwd })
            const actualJob = JSON.parse(readFileSync(run.output + '.job.json', 'utf8'))
            assert.equal(actualJob.args.at(-1), originalJob.args.at(-1), 'benchmark prompts differ')
            verifyNativeCheck(run, 'python3 check.py numbers', cwd)
            const elapsedMs = performance.now() - started
            samples.push({ kind, elapsed_ms: elapsedMs, sampled_peak_native_rss_kib: sampledPeakRssKiB, usage: kind === 'adapter' ? result.result.usage : result.usage })
          }
        }
        const afterGate = spawnSync('perf-gate-ready', ['-1'], { encoding: 'utf8', timeout: 10000 })
        const summary = kind => {
          const times = samples.filter(sample => sample.kind === kind).map(sample => sample.elapsed_ms).sort((a, b) => a - b)
          return { count: times.length, median_ms: times[2], min_ms: times[0], max_ms: times.at(-1) }
        }
        benchmark = afterGate.status === 0 ? { status: 'measured', verdict: 'inconclusive for live runtime performance', gate_before: gate.status, gate_after: afterGate.status, scope: 'same FX runtime, provider, pins, prompt and read/write/check workload; adapter supervision versus shared bridge admission/observation; process-cold, filesystem-warm', limiter: 'subprocess launch, Python check, synchronous Git/ps observation and 25ms polling; no model inference', adapter: summary('adapter'), bridge: summary('bridge'), samples } : { status: 'deferred', reason: 'perf gate deferred: host busy; contaminated timing samples discarded', gate_after: afterGate.status, memory_samples: samples.map(({ kind, sampled_peak_native_rss_kib }) => ({ kind, sampled_peak_native_rss_kib })) }
      }
    }
    const report = { benchmark, platform: process.platform + '-' + process.arch, root, capabilities: fx.capabilities, backend: 'fx', deterministic_provider: true, live_provider: false, scout: scout.result, worker: worker.result, correction: corrected, native_session_preserved: true, owner_replay: 'one effect', steering, interruption, partial_write_preserved: true, acceptance_commands: ['python3 check.py numbers', 'python3 check.py strings'] }
    writeFileSync(join(root, 'report.json'), JSON.stringify(report, null, 2)); writeFileSync(join(root, 'requests.json'), JSON.stringify(requests, null, 2))
    return report
  } finally {
    for (const id of ids) { try { await dispatch(bridge, { name: 'cancel', cwd, session_id: id }) } catch {} }
    await owner.close(); server.closeAllConnections(); await new Promise(r => server.close(r))
  }
}

async function boundedBarrier(promise) {
  let timer
  try { await Promise.race([promise, new Promise((_, reject) => { timer = setTimeout(() => reject(new Error('FX control barrier timed out')), 15000) })]) }
  finally { clearTimeout(timer) }
}

function verifyNativeCheck(run, command, cwd) {
  const receipt = JSON.parse(readFileSync(run.output, 'utf8')), native = JSON.parse(receipt.stdout)
  assert.equal(receipt.code, 0); assert.equal(native.exit_code, 0)
  assert.ok(native.tool_calls.every(call => call.status === 'success'))
  const check = native.tool_calls.find(call => call.name === 'shell')?.command_result
  assert.equal(check?.command, command); assert.equal(check?.cwd, cwd); assert.equal(check?.exit_code, 0)
}
