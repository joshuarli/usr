import assert from 'node:assert/strict'
import { createServer } from 'node:http'
import { execFileSync, spawnSync } from 'node:child_process'
import { existsSync, mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs'
import { join } from 'node:path'
import { qualificationBridge } from './bridge.ts'
import { makeFxAdapter } from '../../src/fx.ts'
import { dispatch } from '../../src/server.ts'
import { OwnerManager } from '../../src/owner.ts'
import { ownerJobs, ownerResume, ownerSteer, ownerInterrupt } from '../../src/owner-client.ts'
import { decodeSession } from '../../src/session.ts'

export async function bridgePilot(binary, scratch, options = {}) {
  const transport = options.transport ?? 'cli'
  const root = mkdtempSync(join(scratch, 'fx-bridge-')), home = join(root, 'home'), repo = join(home, 'repo'), cwd = join(repo, '.work/wt/pilot')
  mkdirSync(repo, { recursive: true })
  const git = (...args) => execFileSync('git', ['-C', repo, ...args], { encoding: 'utf8', timeout: 10000 }).trim()
  git('init', '-q'); git('config', 'user.name', 'Fixture'); git('config', 'user.email', 'fixture@example.com')
  writeFileSync(join(repo, 'arithmetic.py'), 'def add(a, b):\n    return a - b\n')
  writeFileSync(join(repo, 'check.py'), 'import sys\nfrom arithmetic import add\nassert add(2, 3) == 5\nif sys.argv[1] == "strings": assert add("2", "3") == 5\nprint("check passed")\n')
  writeFileSync(join(repo, '.gitignore'), '__pycache__/\n')
  if (transport === 'acp') {
    writeFileSync(join(repo, '.fx.json'), JSON.stringify({ permission_mode: 'full-access', permission: { '*': 'allow' }, max_agent_steps: 0 }))
    writeFileSync(join(repo, '.mcp.json'), JSON.stringify({ mcpServers: { ambient: { command: '/bin/sh', args: ['-c', 'touch ambient-started'] } } }))
  }
  git('add', '.'); git('commit', '-qm', 'fixture'); writeFileSync(join(repo, '.git/info/exclude'), '/.work/\n')
  mkdirSync(join(repo, '.work/wt'), { recursive: true }); git('worktree', 'add', '-qb', 'pilot', cwd)
  let router = null, requestBudget = 20, calls = [], requests = [], final = '', providerError, holdAt = 0, heldResolve = () => {}
  const server = createServer(async (req, res) => {
    try {
      let raw = ''; for await (const chunk of req) { raw += chunk; if (raw.length > 1048576) throw new Error('request too large') }
      const body = JSON.parse(raw); assert.equal(body.model, 'fixture-model'); assert.equal(body.reasoning_effort, 'high')
      requests.push(body); if (requests.length > requestBudget) throw new Error('model-step budget exceeded')
      if (holdAt && requests.length === holdAt) { heldResolve(); return }
      const routed = router ? router(body) : undefined, call = router ? routed.call : calls.shift(), index = requests.length
      const delta = call ? { role: 'assistant', tool_calls: [{ index: 0, id: 'call_' + index, type: 'function', function: { name: call[0], arguments: JSON.stringify(call[1]) } }] } : { role: 'assistant', content: (router ? routed.final : final) + '\nACCEPTANCE: met' }
      res.writeHead(200, { 'content-type': 'text/event-stream' }); res.end('data: ' + JSON.stringify({ id: 'fixture', object: 'chat.completion.chunk', model: 'fixture-model', choices: [{ index: 0, delta, finish_reason: call ? 'tool_calls' : 'stop' }], usage: { prompt_tokens: 10, completion_tokens: 5, total_tokens: 15 } }) + '\n\ndata: [DONE]\n\n')
    } catch (error) { providerError = error; res.writeHead(400); res.end('fixture rejected request') }
  })
  await new Promise(r => server.listen(0, '127.0.0.1', r))
  const connection = { protocol: 'openai-chat-completions', base_url: `http://127.0.0.1:${server.address().port}/v1`, auth: { type: 'none' }, model_metadata: { 'fixture-model': { context_window: 32768, max_output_tokens: 2048, supports_tool_use: true, reasoning_efforts: { high: { reasoning_effort: 'high' } } } } }
  const fx = makeFxAdapter({ transport, binary, binarySha256: JSON.parse(readFileSync(new URL('./pin.json', import.meta.url), 'utf8')).binary_sha256, home, provider: 'fixture', connection, allowedCommands: ['python3 check.py numbers', 'python3 check.py strings'], wallMs: 15000 })
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
  const sessionPath = id => join(repo, '.work/worker-bridge', id + '.json')
  const runOf = id => decodeSession(JSON.parse(readFileSync(sessionPath(id), 'utf8')), cwd, id).execution.run
  const nativeId = id => JSON.parse(readFileSync(runOf(id).output + '.native.json', 'utf8')).session_id
  // git restores same-size sources within one mtime second, so Python would reuse stale bytecode.
  const reset = () => { git('-C', cwd, 'checkout', '--', 'arithmetic.py'); rmSync(join(cwd, '__pycache__'), { recursive: true, force: true }) }
  async function admit(title, tier = 'worker', jobScope = scope, target = bridge) {
    const admitted = await dispatch(target, { name: 'start', cwd, title, tier, scope: jobScope, brief: title })
    ids.push(admitted.session_id); return admitted
  }
  async function settled(id, target = bridge) {
    const deadline = Date.now() + 30000
    while (Date.now() < deadline) {
      if (providerError) throw providerError
      const result = await dispatch(target, { name: 'status', cwd, session_id: id })
      if (result.state !== 'running') return result
      await new Promise(r => setTimeout(r, 25))
    }
    throw new Error('bridge job did not terminate')
  }
  async function childScenario() {
    reset(); requestBudget = 60; requests = []
    const text = message => typeof message.content === 'string' ? message.content : JSON.stringify(message.content ?? '')
    const childIds = messages => messages.filter(m => m.role === 'tool').map(m => /child_id\\?":\\?"([0-9a-f-]{36})/.exec(text(m))?.[1]).filter(Boolean)
    router = body => {
      const all = body.messages.map(text).join('\n'), tools = body.messages.filter(m => m.role === 'tool').length
      if (all.includes('You are a scout child')) return tools === 0 ? { call: ['read_file', { path: 'arithmetic.py' }] } : { final: 'arithmetic.py:2 subtracts b instead of adding it' }
      if (all.includes('You are a worker child')) return [
        { call: ['write_file', { path: 'arithmetic.py', content: 'def add(a, b):\n    return a + b\n' }] },
        { call: ['shell', { action: 'run', command: 'python3 check.py numbers' }] },
      ][tools] ?? { final: 'PROOF: child ran python3 check.py numbers, exit 0' }
      const ids = childIds(body.messages)
      return [
        { call: ['mcp_children_spawn', { tier: 'scout', task: 'Locate the arithmetic error with file and line evidence.', intent_id: 'scout-1' }] },
        { call: ['mcp_children_wait', { child_id: ids[0], timeout_s: 60 }] },
        { call: ['mcp_children_spawn', { tier: 'worker', task: 'Fix arithmetic.add for numbers and run python3 check.py numbers.', intent_id: 'worker-1' }] },
        { call: ['mcp_children_wait', { child_id: ids[2], timeout_s: 60 }] },
        { call: ['mcp_children_spawn', { tier: 'worker', task: 'override', intent_id: 'escape-1', model: 'other-model' }] },
        { call: ['shell', { action: 'run', command: 'python3 check.py numbers' }] },
      ][tools] ?? { final: 'PROOF: scout located arithmetic.py:2; worker child fixed it; root reran python3 check.py numbers, exit 0' }
    }
    const parentFx = makeFxAdapter({ transport, binary, binarySha256: JSON.parse(readFileSync(new URL('./pin.json', import.meta.url), 'utf8')).binary_sha256, home, provider: 'fixture', connection, allowedCommands: ['python3 check.py numbers'], wallMs: 60000, delegation: { maxChildren: 3, maxConcurrent: 2 } })
    const parentBridge = qualificationBridge(parentFx)
    try {
      const root = await admit('Coordinate a scout child and a worker child to fix arithmetic.add; rerun the check yourself.', 'worker', scope, parentBridge)
      const done = await settled(root.session_id, parentBridge)
      assert.equal(done.state, 'succeeded', JSON.stringify(done)); assert.deepEqual(done.children_active, []); assert.deepEqual(done.out_of_scope_paths, [])
      execFileSync('python3', ['check.py', 'numbers'], { cwd })
      assert.equal(git('-C', cwd, 'diff', '--name-only'), 'arithmetic.py')
      const job = JSON.parse(readFileSync(runOf(root.session_id).output + '.job.json', 'utf8'))
      const ledger = JSON.parse(readFileSync(join(job.fxHome, 'children-ledger.json'), 'utf8'))
      assert.deepEqual(ledger.children.map(child => [child.tier, child.spawn]), [['scout', 'started'], ['worker', 'started']])
      const rootCalls = acpToolCalls(runOf(root.session_id))
      assert.deepEqual(rootCalls.map(call => call.status), ['completed', 'completed', 'completed', 'completed', 'failed', 'completed'])
      for (const child of ledger.children) {
        const receipt = JSON.parse(readFileSync(child.run.output, 'utf8'))
        assert.equal(receipt.reason, 'end_turn'); assert.equal(receipt.termination, 'verified')
        const childJob = JSON.parse(readFileSync(child.run.output + '.job.json', 'utf8'))
        assert.deepEqual(childJob.mcp_servers, [], 'children must not receive a controller')
        assert.ok(childJob.deadlineAt <= job.deadlineAt, 'child outlived the root deadline')
      }
      return { root: done.state, children: ledger.children.map(child => child.tier), authority_override: 'refused', grandchildren: 'no controller', combined_check: 'python3 check.py numbers passed' }
    } finally { router = null; requestBudget = 20 }
  }
  async function acpScenarios() {
    const out = {}
    // Wall deadline during a held provider turn, then same-session resume.
    reset(); requests = []; calls = [['read_file', { path: 'arithmetic.py' }]]; holdAt = 2
    const shortFx = makeFxAdapter({ transport, binary, binarySha256: JSON.parse(readFileSync(new URL('./pin.json', import.meta.url), 'utf8')).binary_sha256, home, provider: 'fixture', connection, allowedCommands: ['python3 check.py numbers', 'python3 check.py strings', 'python3 slow.py'], wallMs: 3000 })
    const shortBridge = qualificationBridge(shortFx)
    const timed = await admit('deadline fixture', 'worker', scope, shortBridge)
    const timedOut = await settled(timed.session_id, shortBridge)
    assert.equal(timedOut.state, 'timed_out'); assert.equal(timedOut.run_deadline_ms, 3000); assert.equal(timedOut.run_step_limit, 20)
    const timedNative = nativeId(timed.session_id)
    holdAt = 0; requests = []; calls = [['write_file', { path: 'arithmetic.py', content: 'def add(a, b):\n    return a + b\n' }], ['shell', { action: 'run', command: 'python3 check.py numbers' }]]; final = 'PROOF: resumed after deadline; python3 check.py numbers exited 0'
    assert.equal((await dispatch(shortBridge, { name: 'resume', cwd, session_id: timed.session_id, feedback: 'Continue after the deadline.' })).status, 'admitted')
    const afterDeadline = await settled(timed.session_id, shortBridge)
    assert.equal(afterDeadline.state, 'succeeded'); assert.equal(nativeId(timed.session_id), timedNative)
    assert.ok(requests[0].messages.some(message => message.role === 'tool'), 'deadline resume lost history')
    execFileSync('python3', ['check.py', 'numbers'], { cwd })
    out.deadline_resume = { state: timedOut.state, run_deadline_ms: timedOut.run_deadline_ms, resumed: afterDeadline.state, native_session_preserved: true }
    // Cancellation while a writing tool runs: the tool is killed, termination verified, then the session resumes.
    reset()
    requests = []; calls = [['write_file', { path: 'slow.py', content: 'import os, pathlib, time\npathlib.Path("tool.pid").write_text(str(os.getpid()))\ntime.sleep(60)\npathlib.Path("late-write").write_text("late")\n' }], ['shell', { action: 'run', command: 'python3 slow.py' }]]
    const cancelled = await admit('cancel during tool fixture', 'worker', { ...scope, writable_paths: ['arithmetic.py', 'slow.py', 'tool.pid', 'late-write'] }, shortBridge)
    const toolPidPath = join(cwd, 'tool.pid'), barrier = Date.now() + 15000
    while (!existsSync(toolPidPath) && Date.now() < barrier) await new Promise(r => setTimeout(r, 25))
    const toolPid = Number(readFileSync(toolPidPath, 'utf8'))
    assert.equal((await dispatch(shortBridge, { name: 'cancel', cwd, session_id: cancelled.session_id })).interrupted, true)
    const cancelState = await settled(cancelled.session_id, shortBridge)
    assert.equal(cancelState.state, 'cancelled')
    assert.equal(JSON.parse(readFileSync(runOf(cancelled.session_id).output, 'utf8')).termination, 'verified')
    assert.throws(() => process.kill(toolPid, 0), 'cancelled tool process survived')
    assert.equal(existsSync(join(cwd, 'late-write')), false)
    requests = []; calls = []; final = 'PROOF: resumed after cancellation'
    assert.equal((await dispatch(shortBridge, { name: 'resume', cwd, session_id: cancelled.session_id, feedback: 'Resume after cancellation without rerunning slow.py.' })).status, 'admitted')
    assert.equal((await settled(cancelled.session_id, shortBridge)).state, 'succeeded')
    assert.ok(requests[0].messages.some(message => message.role === 'tool'), 'cancel resume lost history')
    for (const name of ['slow.py', 'tool.pid']) rmSync(join(cwd, name))
    out.cancel_during_tool = { state: cancelState.state, termination: 'verified', tool_process_stopped: true, late_write: false, resumed: 'succeeded' }
    // Failed tool, then recovery within the same turn.
    reset(); requests = []; calls = [['shell', { action: 'run', command: 'python3 check.py numbers' }], ['write_file', { path: 'arithmetic.py', content: 'def add(a, b):\n    return a + b\n' }], ['shell', { action: 'run', command: 'python3 check.py numbers' }]]; final = 'PROOF: python3 check.py numbers exited 0 after the first run failed'
    const recovering = await admit('failed tool recovery fixture')
    const recovered = await settled(recovering.session_id)
    assert.equal(recovered.state, 'succeeded')
    const recoveredCalls = acpToolCalls(runOf(recovering.session_id))
    assert.deepEqual(recoveredCalls.map(call => call.status), ['failed', 'completed', 'completed'])
    execFileSync('python3', ['check.py', 'numbers'], { cwd })
    out.failed_tool_recovery = { tool_statuses: recoveredCalls.map(call => call.status), state: recovered.state }
    // Step budget: the run stops as turn_limit and continues without consuming an attempt.
    reset(); requestBudget = 60; requests = []; calls = Array.from({ length: 25 }, () => ['read_file', { path: 'arithmetic.py' }])
    const looping = await admit('step budget fixture')
    const limited = await settled(looping.session_id)
    assert.equal(limited.state, 'turn_limit'); assert.equal(requests.length, 20)
    calls = []; requests = []; final = 'PROOF: continued after step budget'
    assert.equal((await dispatch(bridge, { name: 'resume', cwd, session_id: looping.session_id, feedback: 'Continue.' })).status, 'admitted')
    const continued = await settled(looping.session_id)
    assert.equal(continued.state, 'succeeded'); assert.equal(continued.continuations, 1)
    assert.equal(decodeSession(JSON.parse(readFileSync(sessionPath(looping.session_id), 'utf8')), cwd, looping.session_id).attempts, 1)
    requestBudget = 20
    out.step_limit = { state: limited.state, provider_requests: 20, continuation: continued.state, attempts_consumed: 1 }
    // Hostile read-only scout with ambient project configuration that tries to widen access.
    reset()
    requests = []; calls = [['write_file', { path: 'forbidden.txt', content: 'x' }], ['edit_file', { path: 'arithmetic.py', old_string: 'a - b', new_string: 'a * b' }], ['shell', { action: 'run', command: 'touch shell-forbidden' }], ['subagent', { action: 'message', agent: 'x', message: 'spawn' }], ['toolbox', { run: 'write_file', arguments: { path: 'alternate-forbidden', content: 'x' } }], ['web_fetch', { url: 'http://127.0.0.1:9/' }]]; final = 'arithmetic.py:2 evidence'
    const hostile = await admit('hostile read-only fixture', 'scout', { ...scope, writable_paths: [], acceptance_proof: 'arithmetic.py:2 evidence' })
    const hostileState = await settled(hostile.session_id)
    assert.equal(hostileState.state, 'failed'); assert.match(hostileState.error, /ungated built-in tool web_fetch/)
    const hostileCalls = acpToolCalls(runOf(hostile.session_id))
    assert.deepEqual(hostileCalls.map(call => call.name), ['write_file', 'edit_file', 'shell', 'subagent', 'write_file', 'web_fetch'])
    assert.ok(hostileCalls.slice(0, 5).every(call => call.status === 'failed'))
    for (const name of ['forbidden.txt', 'shell-forbidden', 'alternate-forbidden', 'ambient-started']) assert.equal(existsSync(join(cwd, name)), false, name)
    assert.match(readFileSync(join(cwd, 'arithmetic.py'), 'utf8'), /a - b/)
    out.hostile_read_only = { tool_statuses: 'write/edit/shell/subagent/toolbox failed', escapes: 0, ambient_mcp_started: false, ungated_web_fetch: 'detected and stopped' }
    // Changed saved configuration refuses continuation before any effect.
    const savedJob = JSON.parse(readFileSync(runOf(recovering.session_id).output + '.job.json', 'utf8'))
    const settingsPath = join(savedJob.fxHome, 'settings.json'), original = readFileSync(settingsPath, 'utf8')
    writeFileSync(settingsPath, original.replace('"max_agent_steps":20', '"max_agent_steps":21'))
    const attemptsBefore = decodeSession(JSON.parse(readFileSync(sessionPath(recovering.session_id), 'utf8')), cwd, recovering.session_id).attempts
    await assert.rejects(() => dispatch(bridge, { name: 'resume', cwd, session_id: recovering.session_id, feedback: 'x' }), /configuration changed/)
    assert.equal(decodeSession(JSON.parse(readFileSync(sessionPath(recovering.session_id), 'utf8')), cwd, recovering.session_id).attempts, attemptsBefore)
    writeFileSync(settingsPath, original)
    out.changed_configuration = 'refused before effects'
    out.children = await childScenario()
    reset()
    return out
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
    verifyNativeCheck(before.execution.run, 'python3 check.py numbers', cwd, transport)
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
    verifyNativeCheck(after.execution.run, 'python3 check.py strings', cwd, transport)
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
    verifyNativeCheck(steeredWire.execution.run, 'python3 check.py strings', cwd, transport)
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
    const acp = transport === 'acp' ? await acpScenarios() : undefined
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
            if (kind === 'adapter') run = fx.start({ directory: cwd, logDirectory: join(repo, '.work/worker-bridge'), prompt: jobPrompt(originalJob), selection: originalJob.selection, access: { kind: 'write' } })
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
            assert.equal(jobPrompt(actualJob), jobPrompt(originalJob), 'benchmark prompts differ')
            verifyNativeCheck(run, 'python3 check.py numbers', cwd, transport)
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
    const report = { transport, acp, benchmark, platform: process.platform + '-' + process.arch, root, capabilities: fx.capabilities, backend: 'fx', deterministic_provider: true, live_provider: false, scout: scout.result, worker: worker.result, correction: corrected, native_session_preserved: true, owner_replay: 'one effect', steering, interruption, partial_write_preserved: true, acceptance_commands: ['python3 check.py numbers', 'python3 check.py strings'] }
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

function jobPrompt(job) { return job.prompt ?? job.args.at(-1) }

function acpToolCalls(run) {
  const calls = new Map()
  for (const line of readFileSync(run.output + '.events.ndjson', 'utf8').split('\n').filter(Boolean)) {
    const { update } = JSON.parse(line)
    if (update.sessionUpdate === 'tool_call') calls.set(update.toolCallId, { name: update.name, input: update.rawInput, status: update.status })
    else if (update.sessionUpdate === 'tool_call_update' && calls.has(update.toolCallId) && update.status) calls.get(update.toolCallId).status = update.status
  }
  return [...calls.values()]
}

function verifyNativeCheck(run, command, cwd, transport) {
  if (transport === 'acp') {
    const receipt = JSON.parse(readFileSync(run.output, 'utf8'))
    assert.equal(receipt.reason, 'end_turn'); assert.equal(receipt.termination, 'verified')
    const calls = acpToolCalls(run)
    assert.ok(calls.every(call => call.status === 'completed'), JSON.stringify(calls))
    assert.ok(calls.some(call => call.name === 'shell' && call.input?.command === command), 'assigned check did not run')
    return
  }
  const receipt = JSON.parse(readFileSync(run.output, 'utf8')), native = JSON.parse(receipt.stdout)
  assert.equal(receipt.code, 0); assert.equal(native.exit_code, 0)
  assert.ok(native.tool_calls.every(call => call.status === 'success'))
  const check = native.tool_calls.find(call => call.name === 'shell')?.command_result
  assert.equal(check?.command, command); assert.equal(check?.cwd, cwd); assert.equal(check?.exit_code, 0)
}
