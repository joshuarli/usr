import assert from 'node:assert/strict'
import { randomUUID } from 'node:crypto'
import { execFileSync, spawnSync, spawn } from 'node:child_process'
import { existsSync, mkdirSync, mkdtempSync, readdirSync, readFileSync, rmSync, writeFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { makeHybridBridge } from '../../src/hybrid.ts'
import { optionalPiAdapter } from '../../src/optional-pi.ts'
import { makeFxAdapter } from '../../src/fx.ts'
import { dispatch } from '../../src/server.ts'
import { OwnerManager } from '../../src/owner.ts'
import { ownerJobs, ownerResume } from '../../src/owner-client.ts'
import { codexAvailable } from '../../src/codex.ts'
import { CODEX_TIER_MODELS, ROOT_PLANS } from '../../src/policy.ts'
import { workerEnvironment } from '../../src/worker-env.ts'
import { classifyJobBlock, classifyProbeResponse, pilotVerdict, renameEvidenceOk, scoutFindingOk } from './pilot.ts'

const root = fileURLToPath(new URL('../../../../', import.meta.url))
const pin = JSON.parse(readFileSync(new URL('./pin.json', import.meta.url), 'utf8'))
const BOUNDS = { max_new_jobs: 6, max_continuations: 1, wall_ms_per_job: 900000, max_model_steps: 20 }
const LIVE_BASE = join(root, '.work/tmp/fx-live')
const LOGIN_HOME = join(LIVE_BASE, 'fx-profile')
const FX_BINARY = join(root, '.work/tmp/fx-spike/installed-home/.local/bin/fx')

const fxPin = (model, effort, provider) => ({ model, effort, provider, runtimeVersion: '0.0.17' })

const PROFILES = {
  codex: {
    provider: 'codex',
    connection: null,
    selections: {
      scout: fxPin(CODEX_TIER_MODELS.scout.model, CODEX_TIER_MODELS.scout.effort, 'codex'),
      worker: fxPin(CODEX_TIER_MODELS.worker.model, CODEX_TIER_MODELS.worker.effort, 'codex'),
    },
    incumbent: 'bridge-codex',
    auth: {
      kind: 'fx-login', credential: join(LOGIN_HOME, 'chatgpt-auth.json'),
      setup: `FX_HOME=${LOGIN_HOME} ${FX_BINARY} login codex`,
    },
  },
  'opencode-go': {
    provider: 'opencode-go',
    connection: {
      protocol: 'openai-chat-completions', base_url: 'https://opencode.ai/inference/go/openai/v1',
      auth: { type: 'bearer', env: 'LIVE_PROVIDER_TOKEN' },
      headers: { 'x-opencode-session': { env: 'LIVE_PROVIDER_SESSION' } },
      model_metadata: { 'deepseek-v4.1-flash': { context_window: 1000000, supports_tool_use: true, reasoning_efforts: { high: { reasoning_effort: 'high' } } } },
    },
    selections: {
      scout: fxPin('deepseek-v4.1-flash', 'high', 'opencode-go'),
      worker: fxPin('deepseek-v4.1-flash', 'high', 'opencode-go'),
    },
    incumbent: 'pi-cli',
    auth: { kind: 'opencode-export', envName: 'LIVE_PROVIDER_TOKEN' },
  },
}

function toolchainPath() {
  const dirs = []
  const rustupCargo = spawnSync('rustup', ['which', 'cargo'], { encoding: 'utf8', timeout: 10000 })
  if (rustupCargo.status === 0 && rustupCargo.stdout.trim()) dirs.push(dirname(rustupCargo.stdout.trim().split('\n')[0]))
  for (const tool of ['node', 'python3', 'cargo', 'rustc']) {
    const found = spawnSync('which', [tool], { encoding: 'utf8', timeout: 5000 })
    if (found.status === 0 && found.stdout.trim()) dirs.push(dirname(found.stdout.trim()))
  }
  const unique = [...new Set(dirs.filter(dir => dir.startsWith('/')))]
  return unique.length ? unique.join(':') + ':/usr/bin:/bin' : '/usr/bin:/bin'
}

function provisionRepo(repo) {
  const git = (...args) => execFileSync('git', ['-C', repo, ...args], { encoding: 'utf8', timeout: 10000 }).trim()
  mkdirSync(repo, { recursive: true })
  git('init', '-q'); git('config', 'user.name', 'Live Fixture'); git('config', 'user.email', 'live@example.com')
  mkdirSync(join(repo, 'python'), { recursive: true })
  mkdirSync(join(repo, 'ts'), { recursive: true })
  mkdirSync(join(repo, 'rust', 'src'), { recursive: true })
  writeFileSync(join(repo, 'python', 'ledger.py'), `def balance_after(entries):
    balance = 0
    for entry in entries:
        if entry["kind"] == "credit":
            balance += entry["amount"]
        elif entry["kind"] == "debit":
            balance += entry["amount"]
    return balance


def summarize(entries):
    return {"count": len(entries), "balance": balance_after(entries)}
`)
  writeFileSync(join(repo, 'python', 'report.py'), `from ledger import summarize


def report(entries):
    summary = summarize(entries)
    return "entries=%d balance=%d" % (summary["count"], summary["balance"])
`)
  writeFileSync(join(repo, 'python', 'test_ledger.py'), `import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ledger import balance_after, summarize
from report import report


class LedgerTest(unittest.TestCase):
    def test_balance(self):
        entries = [{"kind": "credit", "amount": 100}, {"kind": "debit", "amount": 30}]
        self.assertEqual(balance_after(entries), 70)

    def test_summarize(self):
        self.assertEqual(summarize([{"kind": "credit", "amount": 5}]), {"count": 1, "balance": 5})

    def test_report(self):
        self.assertEqual(report([{"kind": "credit", "amount": 5}]), "entries=1 balance=5")


if __name__ == "__main__":
    unittest.main()
`)
  writeFileSync(join(repo, 'ts', 'ledger.mjs'), `export function balanceAfter(entries) {
  let balance = 0
  for (const entry of entries) {
    if (entry.kind === 'credit') balance += entry.amount
    else if (entry.kind === 'debit') balance += entry.amount
  }
  return balance
}

export function summarize(entries) {
  return { count: entries.length, balance: balanceAfter(entries) }
}
`)
  writeFileSync(join(repo, 'ts', 'check.mjs'), `import assert from 'node:assert/strict'
import { balanceAfter, summarize } from './ledger.mjs'
assert.equal(balanceAfter([{ kind: 'credit', amount: 100 }, { kind: 'debit', amount: 30 }]), 70)
assert.deepEqual(summarize([{ kind: 'credit', amount: 5 }]), { count: 1, balance: 5 })
console.log('ts check passed')
`)
  writeFileSync(join(repo, 'rust', 'Cargo.toml'), `[package]\nname = "ledger"\nversion = "0.1.0"\nedition = "2021"\n\n[dependencies]\n`)
  writeFileSync(join(repo, 'rust', 'src', 'lib.rs'), `pub fn balance_after(entries: &[(bool, i64)]) -> i64 {
    let mut balance = 0;
    for (is_credit, amount) in entries {
        if *is_credit {
            balance += amount;
        } else {
            balance += amount;
        }
    }
    balance
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn debit_subtracts() {
        assert_eq!(balance_after(&[(true, 100), (false, 30)]), 70);
    }
}
`)
  writeFileSync(join(repo, '.gitignore'), 'target/\n__pycache__/\n.work/\nCargo.lock\n')
  git('add', '.'); git('commit', '-qm', 'live fixture')
  return git('rev-parse', 'HEAD')
}

const PY_CHECK = ['-m', 'unittest', 'discover', '-s', 'python', '-p', 'test_*.py', '-t', 'python']
function pyCheck(wt) { execFileSync('python3', PY_CHECK, { cwd: wt, stdio: 'pipe' }) }
function allChecks(wt) {
  pyCheck(wt)
  execFileSync('node', ['ts/check.mjs'], { cwd: wt, stdio: 'pipe' })
  execFileSync('cargo', ['test', '--manifest-path', 'rust/Cargo.toml'], { cwd: wt, stdio: 'pipe', env: { ...process.env, CARGO_HOME: join(LIVE_BASE, 'cargo-home') } })
}
function cleanTree(wt) {
  const status = execFileSync('git', ['-C', wt, 'status', '--porcelain'], { encoding: 'utf8' })
  assert.equal(status.trim(), '', 'scout worktree must remain unchanged')
}
function testsUntouched(wt) {
  const diff = execFileSync('git', ['-C', wt, 'diff', '--name-only', 'HEAD', '--', 'python/test_ledger.py'], { encoding: 'utf8' })
  assert.equal(diff.trim(), '', 'acceptance tests must not be edited')
}

const TASKS = [
  {
    key: 'scout', tier: 'scout',
    prompt: 'The Python acceptance check fails in this repository. Investigate python/ and report the exact file and line that causes the wrong result, with a one-sentence explanation. Do not modify any files and do not run shell commands.',
    scope: { writable_paths: [], acceptance_proof: 'final answer cites python/ledger.py line evidence; worktree unchanged', attempt_limit: 1, stop_on: 'any file modification or shell use' },
    verify: (wt, answer) => {
      cleanTree(wt)
      assert.ok(scoutFindingOk(String(answer ?? '')), 'scout answer must cite the debit defect at python/ledger.py lines 6-7')
    },
  },
  {
    key: 'fix', tier: 'worker',
    prompt: 'The Python ledger computes the wrong balance for debits in python/ledger.py. Fix the bug so the Python tests pass. Change only files under python/ and run the Python check.',
    scope: { writable_paths: ['python'], acceptance_proof: 'python unittest discover exits zero; test_ledger.py unmodified', attempt_limit: 2, stop_on: 'scope expansion or unavailable proof' },
    verify: (wt) => { pyCheck(wt); testsUntouched(wt) },
  },
  {
    key: 'multi', tier: 'worker',
    prompt: 'Rename the public balance function to settled_balance in all three language ports: python/ledger.py (update python/report.py and python/test_ledger.py callers), ts/ledger.mjs and rust/src/lib.rs consistently. The acceptance checks currently fail; make the Python, Node and Cargo checks all pass.',
    scope: { writable_paths: ['python', 'ts', 'rust'], acceptance_proof: 'python unittest, node ts/check.mjs and cargo test --manifest-path rust/Cargo.toml all exit zero', attempt_limit: 2, stop_on: 'scope expansion or unavailable proof' },
    verify: (wt) => {
      allChecks(wt)
      const files = {
        python: readFileSync(join(wt, 'python', 'ledger.py'), 'utf8'),
        ts: readFileSync(join(wt, 'ts', 'ledger.mjs'), 'utf8'),
        rust: readFileSync(join(wt, 'rust', 'src', 'lib.rs'), 'utf8'),
        'python-report': readFileSync(join(wt, 'python', 'report.py'), 'utf8'),
        'python-test': readFileSync(join(wt, 'python', 'test_ledger.py'), 'utf8'),
        'ts-check': readFileSync(join(wt, 'ts', 'check.mjs'), 'utf8'),
      }
      const problem = renameEvidenceOk(files)
      assert.equal(problem, null, problem ?? undefined)
    },
  },
]

const CONTINUATION_PROMPT = 'Follow-up in the same scope: add the one-line docstring """Net balance across entries.""" as the first statement inside settled_balance in python/ledger.py, then rerun the Python check.'
function continuationVerify(wt) {
  pyCheck(wt)
  assert.match(readFileSync(join(wt, 'python', 'ledger.py'), 'utf8'), /Net balance across entries/, 'continuation docstring missing')
}

function exportOpenCodeToken() {
  try {
    const raw = execFileSync('opencode', ['auth', 'export'], { encoding: 'utf8', timeout: 10000, maxBuffer: 1_000_000, stdio: ['ignore', 'pipe', 'ignore'] })
    const creds = JSON.parse(raw)
    const match = Array.isArray(creds) && creds.find(c => c?.active && c.integrationID === 'opencode' && c.value?.type === 'oauth')
    const token = match?.value?.access
    return typeof token === 'string' && token.length > 0 && token.length < 4096 ? token : null
  } catch { return null }
}

function profileAuth(profile, runRoot) {
  if (profile.auth.kind === 'fx-login') {
    return existsSync(profile.auth.credential) && readFileSync(profile.auth.credential, 'utf8').length > 0
      ? { ready: true } : { ready: false, setup: profile.auth.setup }
  }
  const secretDir = join(runRoot, 'secrets')
  const tokenPath = join(secretDir, 'provider.key')
  const sessionPath = join(secretDir, 'provider-session.key')
  const refresh = () => {
    const token = exportOpenCodeToken()
    if (!token) return false
    mkdirSync(secretDir, { recursive: true })
    writeFileSync(tokenPath, token + '\n', { mode: 0o600 })
    writeFileSync(sessionPath, randomUUID() + '\n', { mode: 0o600 })
    return true
  }
  if (!refresh()) return { ready: false, setup: 'opencode auth login (OpenCode Go subscription), then rerun' }
  const baseUrl = profile.connection?.base_url
  const probe = async () => {
    if (!baseUrl) return 'unknown'
    try {
      const token = readFileSync(tokenPath, 'utf8').trim()
      const session = readFileSync(sessionPath, 'utf8').trim()
      const res = await fetch(baseUrl.replace(/\/$/, '') + '/chat/completions', {
        method: 'POST',
        headers: { authorization: 'Bearer ' + token, 'x-opencode-session': session, 'content-type': 'application/json' },
        body: JSON.stringify({ model: 'deepseek-v4.1-flash', messages: [{ role: 'user', content: 'ping' }], max_tokens: 1, stream: false }),
        signal: AbortSignal.timeout(15000),
      })
      return classifyProbeResponse(res.status, await res.text())
    } catch { return 'unknown' }
  }
  return { ready: true, secretEnvFiles: { [profile.auth.envName]: tokenPath, LIVE_PROVIDER_SESSION: sessionPath }, refresh, secretDir, probe }
}

function liveBridge(fx, selections) {
  const resolvePolicy = tier => {
    if (tier !== 'scout' && tier !== 'worker') throw new Error('live pilot supports only scout and worker')
    const tail = ROOT_PLANS[tier]
    if (tail.kind !== 'fallback') throw new Error('live pilot requires a fallback root plan for ' + tier)
    return { kind: 'fx-fallback', fx: selections[tier], codex: tail.codex, command: tail.command, pi: tail.pi }
  }
  return makeHybridBridge(optionalPiAdapter(), undefined, undefined, resolvePolicy, fx)
}

function codexBridge(selections) {
  const resolvePolicy = tier => {
    if (tier !== 'scout' && tier !== 'worker') throw new Error('live pilot supports only scout and worker')
    const pin = selections[tier]
    return { kind: 'leaf', target: { executor: 'codex', selection: { model: pin.model, effort: pin.effort } } }
  }
  return makeHybridBridge(optionalPiAdapter(), undefined, undefined, resolvePolicy)
}

async function waitJob(bridge, cwd, id, deadlineMs = 960000) {
  const deadline = Date.now() + deadlineMs
  for (;;) {
    const result = await dispatch(bridge, { name: 'status', cwd, session_id: id })
    if (result.state !== 'running') return result
    if (Date.now() > deadline) throw new Error('live job exceeded wall deadline')
    await new Promise(r => setTimeout(r, 500))
  }
}

function descendantRss(rootPid) {
  try {
    const table = execFileSync('ps', ['-axo', 'pid=,ppid=,rss='], { encoding: 'utf8', timeout: 5000 })
      .split('\n').map(line => line.trim().split(/\s+/).map(Number)).filter(row => row.length === 3 && row.every(Number.isFinite))
    const byPid = new Map(table.map(row => [row[0], row]))
    const children = new Map()
    for (const [pid, ppid] of table) { if (!children.has(ppid)) children.set(ppid, []); children.get(ppid).push(pid) }
    let total = 0
    const stack = [rootPid], seen = new Set()
    while (stack.length) {
      const pid = stack.pop()
      if (seen.has(pid)) continue
      seen.add(pid)
      const row = byPid.get(pid)
      if (row) total += row[2]
      for (const child of children.get(pid) ?? []) stack.push(child)
    }
    return total
  } catch { return null }
}

async function waitTerminal(bridge, cwd, id, timeoutMs) {
  const deadline = Date.now() + timeoutMs
  for (;;) {
    const result = await dispatch(bridge, { name: 'status', cwd, session_id: id })
    if (result.state !== 'running') return result
    if (Date.now() > deadline) return null
    await new Promise(r => setTimeout(r, 500))
  }
}

async function runBridgeJob(bridge, repo, wtName, task, base) {
  const wt = join(repo, '.work', 'wt', wtName)
  execFileSync('git', ['-C', repo, 'worktree', 'add', '-qb', wtName, wt, base], { encoding: 'utf8', timeout: 10000 })
  const scope = { base_revision: base, ...task.scope }
  const started = performance.now()
  const admitted = await dispatch(bridge, { name: 'start', cwd: wt, title: task.key, tier: task.tier, scope, brief: task.prompt })
  let rootPid = null
  try {
    const session = JSON.parse(readFileSync(join(repo, '.work', 'worker-bridge', admitted.session_id + '.json'), 'utf8'))
    if (session.execution?.kind === 'process') rootPid = session.execution.run.pid
  } catch {}
  let peakRss = null
  const poll = setInterval(() => { if (rootPid) { const rss = descendantRss(rootPid); if (rss) peakRss = Math.max(peakRss ?? 0, rss) } }, 250)
  let result, timedOut = false, termination = null
  try {
    result = await waitJob(bridge, wt, admitted.session_id)
  } catch (error) {
    if (!String(error).includes('wall deadline')) throw error
    timedOut = true
    try { await dispatch(bridge, { name: 'cancel', cwd: wt, session_id: admitted.session_id }) } catch {}
    termination = await waitTerminal(bridge, wt, admitted.session_id, 60000)
    result = termination ?? { state: 'unknown', last_assistant_text: '' }
  } finally { clearInterval(poll) }
  const elapsed = performance.now() - started
  let checksPassed = false, checkError = null
  if (timedOut && !termination) checkError = 'job exceeded wall deadline and termination could not be verified; parent checks skipped'
  else try { task.verify(wt, result.last_assistant_text); checksPassed = true } catch (error) { checkError = String(error).slice(0, 500) }
  const status = execFileSync('git', ['-C', wt, 'status', '--porcelain'], { encoding: 'utf8' })
  return { task: task.key, tier: task.tier, backend: result.backend ?? admitted.backend, session_id: admitted.session_id, state: result.state, timed_out: timedOut || undefined, termination: timedOut ? (termination ? 'verified' : 'unverified') : undefined, acceptance_claim: result.acceptance_claim ?? null, error: result.error ?? null, fallback_reason: result.fallback_reason ?? null, last_assistant_text: String(result.last_assistant_text ?? '').slice(0, 2000), elapsed_ms: Math.round(elapsed), sampled_peak_tree_rss_kib: peakRss, parent_checks_passed: checksPassed, check_error: checkError, worktree_changes: status.trim().split('\n').filter(Boolean).slice(0, 50), ...(result.usage ? { usage: result.usage } : {}) }
}

async function runPiCliJob(repo, wtName, task, base) {
  const wt = join(repo, '.work', 'wt', wtName)
  execFileSync('git', ['-C', repo, 'worktree', 'add', '-qb', wtName, wt, base], { encoding: 'utf8', timeout: 10000 })
  const started = performance.now()
  const child = spawn('pi', ['-p', '--model', 'opencode-go/deepseek-v4.1-flash:high', '--no-session', '--session-dir', join(repo, '.work', 'pi-sessions'), '--', task.prompt], { cwd: wt, env: { ...workerEnvironment(), PI_TELEMETRY: '0' }, detached: true, stdio: ['ignore', 'pipe', 'pipe'] })
  let stdout = '', stderr = '', timedOut = false
  child.stdout.on('data', b => { stdout += b; if (stdout.length > 1_048_576) child.kill('SIGKILL') })
  child.stderr.on('data', b => { stderr += b; if (stderr.length > 1_048_576) child.kill('SIGKILL') })
  const deadline = setTimeout(() => {
    timedOut = true
    try { process.kill(-child.pid, 'SIGKILL') } catch { try { child.kill('SIGKILL') } catch {} }
  }, BOUNDS.wall_ms_per_job)
  const code = await new Promise(resolve => child.once('close', resolve))
  clearTimeout(deadline)
  const elapsed = performance.now() - started
  let checksPassed = false, checkError = null
  try { task.verify(wt, stdout); checksPassed = true } catch (error) { checkError = String(error).slice(0, 500) }
  const status = execFileSync('git', ['-C', wt, 'status', '--porcelain'], { encoding: 'utf8' })
  return { task: task.key, tier: task.tier, backend: 'pi-cli', state: code === 0 && !timedOut ? 'succeeded' : 'failed', exit_code: code, timed_out: timedOut, last_assistant_text: stdout.slice(-2000), elapsed_ms: Math.round(elapsed), parent_checks_passed: checksPassed, check_error: checkError, worktree_changes: status.trim().split('\n').filter(Boolean).slice(0, 50), stderr_tail: stderr.slice(-500) }
}

function runStderrTail(repo, sessionId, bytes = 8192) {
  try {
    const session = JSON.parse(readFileSync(join(repo, '.work', 'worker-bridge', sessionId + '.json'), 'utf8'))
    const path = session.execution?.run?.errors
    if (!path || !existsSync(path)) return ''
    const text = readFileSync(path, 'utf8')
    return text.slice(-bytes)
  } catch { return '' }
}

function nativeSessionIds(fxHome) {
  try {
    return readdirSync(join(fxHome, 'sessions/v2'), { withFileTypes: true })
      .filter(entry => entry.isDirectory() && entry.name !== '.tmp').map(entry => entry.name)
  } catch { return [] }
}

async function runContinuation(bridge, owner, repo, wt, multi) {
  const record = { attempted: false, nativeSession: false }
  try {
    const sessionPath = join(repo, '.work', 'worker-bridge', multi.session_id + '.json')
    const session = JSON.parse(readFileSync(sessionPath, 'utf8'))
    const origOutput = session.execution?.run?.output
    if (!origOutput || !existsSync(origOutput + '.job.json')) { record.reason = 'no-run-record'; return record }
    const origJob = JSON.parse(readFileSync(origOutput + '.job.json', 'utf8'))
    const ids = nativeSessionIds(origJob.fxHome)
    if (ids.length !== 1) { record.reason = 'no-native-session'; return record }
    const nativeId = ids[0]
    record.nativeSession = true
    record.attempted = true
    const job = (await ownerJobs(repo, owner.ownerId)).find(item => item.job_id === multi.session_id)
    if (!job) { record.reason = 'owner-job-missing'; record.attempted = false; return record }
    const target = { job_id: job.job_id, run_id: job.run_id, owner_generation: job.owner_generation }
    const receipt = await ownerResume(repo, owner.ownerId, { target, command_id: 'live-continuation-1', feedback: CONTINUATION_PROMPT })
    record.receipt = receipt.receipt
    if (receipt.receipt !== 'accepted') { record.accepted = false; return record }
    record.accepted = true
    const resumed = await waitJob(bridge, wt, multi.session_id)
    record.state = resumed.state
    record.last_assistant_text = String(resumed.last_assistant_text ?? '').slice(0, 2000)
    const logDir = dirname(origOutput)
    let identity = false
    for (const name of readdirSync(logDir)) {
      if (!name.endsWith('.fx.json.job.json')) continue
      try {
        const candidate = JSON.parse(readFileSync(join(logDir, name), 'utf8'))
        if (candidate.resume === nativeId && candidate.fxHome === origJob.fxHome) identity = true
      } catch {}
    }
    record.identity_retained = identity
    try { continuationVerify(wt); record.parent_checks_passed = true } catch (error) { record.parent_checks_passed = false; record.check_error = String(error).slice(0, 500) }
    return record
  } catch (error) {
    record.error = String(error).slice(0, 500)
    return record
  }
}

export async function livePilot(binary, scratch, requested) {
  const scopeReport = { mode: 'live', scope: BOUNDS, paid_gateway: false, production_routing: false }
  console.log(JSON.stringify(scopeReport))
  mkdirSync(LIVE_BASE, { recursive: true })
  const names = requested ? [requested] : Object.keys(PROFILES)
  for (const name of names) if (!PROFILES[name]) throw new Error('unknown live profile: ' + name)
  const runRoot = mkdtempSync(join(LIVE_BASE, 'run-'))
  const unavailable = []
  let selected = null, auth = null
  for (const name of names) {
    const profile = PROFILES[name]
    const preflight = profileAuth(profile, runRoot)
    if (!preflight.ready) { unavailable.push({ profile: name, reason: 'authentication unavailable', setup: preflight.setup }); continue }
    if (preflight.probe) {
      // A quota/auth probe result is evidence about the FX lane only. The admitted
      // fx-fallback plan owns failover, so a dead FX provider must not zero the
      // batch; the session-log exhaustion watch surfaces it promptly per job.
      preflight.probe_result = await preflight.probe()
    }
    selected = { name, profile, probe_result: preflight.probe_result }; auth = preflight; break
  }
  if (!selected) {
    console.log(JSON.stringify({ status: 'blocked', jobs_started: 0, profiles: unavailable }))
    return { status: 'blocked', exitCode: 75, report: { verdict: 'blocked', scope: BOUNDS, unavailable } }
  }
  const { name, profile } = selected
  const report = { mode: 'live', profile: name, provider: profile.provider, probe_result: selected.probe_result ?? null, selections: profile.selections, runtime: pin.version, scope: BOUNDS, production_routing: false, paid_gateway: false, root: runRoot, jobs: [] }
  let owner = null
  try {
    const home = join(runRoot, 'home'), repo = join(home, 'repo')
    mkdirSync(home, { recursive: true })
    const base = provisionRepo(repo)
    const fx = makeFxAdapter({
      transport: 'cli', binary, binarySha256: pin.binary_sha256, home, provider: profile.provider, connection: profile.connection,
      allowedCommands: ['python3', 'python3 *', 'node', 'node *', 'cargo', 'cargo *', 'git status*', 'git diff*', 'git log*', 'git show*'],
      wallMs: BOUNDS.wall_ms_per_job, pathEnv: toolchainPath(),
      secretEnvFiles: auth.secretEnvFiles ?? {},
      authFiles: profile.auth.kind === 'fx-login' ? [profile.auth.credential] : [],
      extraEnv: { CARGO_HOME: join(LIVE_BASE, 'cargo-home') },
    })
    const bridge = liveBridge(fx, profile.selections)
    owner = new OwnerManager(bridge)
    await owner.ensureRepo(repo)
    const jobs = []
    report.jobs = jobs
    let providerBlocked = false
    for (const task of TASKS) {
      if (providerBlocked) break
      auth.refresh?.()
      const jobResult = { selection: profile.selections[task.tier], ...(await runBridgeJob(bridge, repo, 'fx-' + task.key, task, base)) }
      jobs.push(jobResult)
      if (jobResult.state !== 'succeeded') {
        const probe = auth.probe ? await auth.probe() : null
        jobResult.provider_block = classifyJobBlock({
          state: jobResult.state, lastText: jobResult.last_assistant_text ?? '', error: jobResult.error,
          elapsedMs: jobResult.elapsed_ms, wallMs: BOUNDS.wall_ms_per_job,
          stderrTail: runStderrTail(repo, jobResult.session_id), probe,
        })
        // Only a block on the FX lane itself should halt the batch: once the
        // admitted ladder has fallen through to another backend, the FX probe
        // result no longer predicts whether the remaining tasks can run.
        if (jobResult.provider_block && (jobResult.backend ?? 'fx') === 'fx') providerBlocked = true
      }
    }
    const multi = jobs.find(j => j.task === 'multi')
    let continuation = null
    if (multi) {
      continuation = providerBlocked
        ? { attempted: false, nativeSession: false, reason: 'provider-blocked' }
        : await runContinuation(bridge, owner, repo, join(repo, '.work', 'wt', 'fx-multi'), multi)
      if (continuation.state !== undefined && continuation.state !== 'succeeded') {
        const probe = auth.probe ? await auth.probe() : null
        continuation.provider_block = classifyJobBlock({ state: continuation.state, lastText: continuation.last_assistant_text ?? '', elapsedMs: 0, wallMs: BOUNDS.wall_ms_per_job, stderrTail: '', probe })
      }
    }
    report.continuation = continuation
    if (profile.incumbent === 'bridge-codex' && codexAvailable()) {
      const incumbentBridge = codexBridge(profile.selections)
      for (const task of TASKS) {
        const pin = profile.selections[task.tier]
        jobs.push({ comparison_class: 'bridge-route', selection: { model: pin.model, effort: pin.effort, provider: 'codex' }, ...(await runBridgeJob(incumbentBridge, repo, 'inc-' + task.key, task, base)) })
      }
    } else if (profile.incumbent === 'pi-cli' && spawnSync('which', ['pi'], { encoding: 'utf8', timeout: 5000 }).status === 0) {
      report.incumbent_note = 'pi-cli exercises the provider route without bridge scope, lease or owner controls; it is provider-diagnostic evidence, not a route-equivalent comparison'
      for (const task of TASKS) jobs.push({ comparison_class: 'provider-diagnostic', selection: { model: 'deepseek-v4.1-flash', effort: 'high', provider: 'opencode-go' }, ...(await runPiCliJob(repo, 'inc-' + task.key, task, base)) })
    } else {
      report.incumbent = { status: 'unavailable', note: 'incumbent runtime not authenticated on this host' }
    }
    report.incumbent_ran = jobs.some(j => j.comparison_class !== undefined)
    // FX-intended jobs are the ones admitted through the fx-fallback plan; incumbent
    // comparisons carry an explicit comparison_class and never count as FX evidence.
    const fxJobs = jobs.filter(j => j.comparison_class === undefined)
    report.provider_failover = fxJobs.filter(j => j.backend !== 'fx')
      .map(j => ({ task: j.task, from: 'fx', to: j.backend, state: j.state, fallback_reason: j.fallback_reason ?? null, parent_checks_passed: j.parent_checks_passed }))
    report.verdict = pilotVerdict({
      tasks: TASKS.map(t => {
        const j = fxJobs.find(x => x.task === t.key)
        return { key: t.key, state: j?.state, checks: j?.parent_checks_passed === true, block: j?.provider_block ?? null, backend: j?.backend }
      }),
      continuation: continuation ? {
        attempted: continuation.attempted === true, accepted: continuation.accepted,
        identity: continuation.identity_retained, checks: continuation.parent_checks_passed,
        block: continuation.provider_block ?? null, nativeSession: continuation.nativeSession === true,
      } : null,
    })
    const output = join(scratch, 'fx-live.json')
    writeFileSync(output, JSON.stringify(report, null, 2))
    console.log(JSON.stringify({ status: 'completed', verdict: report.verdict, profile: name, report: output, jobs: jobs.map(j => ({ task: j.task, backend: j.backend, state: j.state, parent_checks_passed: j.parent_checks_passed })) }))
    return { status: 'completed', exitCode: report.verdict === 'passed' ? 0 : report.verdict === 'blocked' ? 75 : 1, report }
  } catch (error) {
    report.error = String(error).slice(0, 2000)
    report.verdict = 'failed'
    writeFileSync(join(scratch, 'fx-live.json'), JSON.stringify(report, null, 2))
    console.log(JSON.stringify({ status: 'failed', profile: name, error: report.error }))
    return { status: 'failed', exitCode: 1, report }
  } finally {
    if (owner) await owner.close().catch(() => {})
    if (auth?.secretDir) rmSync(auth.secretDir, { recursive: true, force: true })
  }
}
