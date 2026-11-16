import assert from 'node:assert/strict'
import { randomUUID } from 'node:crypto'
import { execFileSync, spawnSync, spawn } from 'node:child_process'
import { existsSync, mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { makeHybridBridge } from '../../src/hybrid.ts'
import { optionalPiAdapter } from '../../src/optional-pi.ts'
import { makeFxAdapter } from '../../src/fx.ts'
import { dispatch } from '../../src/server.ts'
import { OwnerManager } from '../../src/owner.ts'
import { ownerJobs, ownerResume } from '../../src/owner-client.ts'
import { codexAvailable } from '../../src/codex.ts'
import { CODEX_TIER_MODELS } from '../../src/policy.ts'
import { workerEnvironment } from '../../src/worker-env.ts'

const root = fileURLToPath(new URL('../../../../', import.meta.url))
const pin = JSON.parse(readFileSync(new URL('./pin.json', import.meta.url), 'utf8'))
const BOUNDS = { max_new_jobs: 6, max_corrections: 2, wall_ms_per_job: 900000, max_model_steps: 20 }
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
      assert.match(String(answer ?? ''), /python\/ledger\.py/i, 'scout answer must cite python/ledger.py')
      assert.match(String(answer ?? ''), /line\s*\d+|:\d+/i, 'scout answer must cite a line number')
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
    verify: allChecks,
    correction: 'The acceptance checks still fail. Finish the settled_balance rename wherever it is incomplete and fix the remaining defects so python unittest, node ts/check.mjs and cargo test all pass. Stay in the same scope.',
  },
]

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
  return { ready: true, secretEnvFiles: { [profile.auth.envName]: tokenPath, LIVE_PROVIDER_SESSION: sessionPath }, refresh, secretDir }
}

function liveBridge(fx, selections) {
  const resolvePolicy = tier => {
    if (tier !== 'scout' && tier !== 'worker') throw new Error('live pilot supports only scout and worker')
    return { kind: 'leaf', target: { executor: 'fx', selection: selections[tier] } }
  }
  return makeHybridBridge(optionalPiAdapter(), undefined, undefined, undefined, resolvePolicy, fx)
}

function codexBridge(selections) {
  const resolvePolicy = tier => {
    if (tier !== 'scout' && tier !== 'worker') throw new Error('live pilot supports only scout and worker')
    const pin = selections[tier]
    return { kind: 'leaf', target: { executor: 'codex', selection: { model: pin.model, effort: pin.effort } } }
  }
  return makeHybridBridge(optionalPiAdapter(), undefined, undefined, undefined, resolvePolicy)
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
  let result
  try { result = await waitJob(bridge, wt, admitted.session_id) }
  finally { clearInterval(poll) }
  const elapsed = performance.now() - started
  let checksPassed = false, checkError = null
  try { task.verify(wt, result.last_assistant_text); checksPassed = true } catch (error) { checkError = String(error).slice(0, 500) }
  const status = execFileSync('git', ['-C', wt, 'status', '--porcelain'], { encoding: 'utf8' })
  return { task: task.key, tier: task.tier, backend: admitted.backend, session_id: admitted.session_id, state: result.state, acceptance_claim: result.acceptance_claim ?? null, last_assistant_text: String(result.last_assistant_text ?? '').slice(0, 2000), elapsed_ms: Math.round(elapsed), sampled_peak_tree_rss_kib: peakRss, parent_checks_passed: checksPassed, check_error: checkError, worktree_changes: status.trim().split('\n').filter(Boolean).slice(0, 50), ...(result.usage ? { usage: result.usage } : {}) }
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
    if (preflight.ready) { selected = { name, profile }; auth = preflight; break }
    unavailable.push({ profile: name, reason: 'authentication unavailable', setup: preflight.setup })
  }
  if (!selected) {
    console.log(JSON.stringify({ status: 'unavailable', jobs_started: 0, profiles: unavailable }))
    return { status: 'unavailable', exitCode: 75, report: { scope: BOUNDS, unavailable } }
  }
  const { name, profile } = selected
  const report = { mode: 'live', profile: name, provider: profile.provider, selections: profile.selections, runtime: pin.version, scope: BOUNDS, production_routing: false, paid_gateway: false, root: runRoot, jobs: [], corrections: [] }
  let owner = null
  try {
    const home = join(runRoot, 'home'), repo = join(home, 'repo')
    mkdirSync(home, { recursive: true })
    const base = provisionRepo(repo)
    const fx = makeFxAdapter({
      binary, binarySha256: pin.binary_sha256, home, provider: profile.provider, connection: profile.connection,
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
    let corrections = 0
    for (const task of TASKS) {
      auth.refresh?.()
      jobs.push({ selection: profile.selections[task.tier], ...(await runBridgeJob(bridge, repo, 'fx-' + task.key, task, base)) })
    }
    const multi = jobs.find(j => j.task === 'multi')
    if (multi?.state === 'succeeded' && multi.parent_checks_passed === false && corrections < BOUNDS.max_corrections) {
      const wt = join(repo, '.work', 'wt', 'fx-multi')
      const job = (await ownerJobs(repo, owner.ownerId)).find(item => item.job_id === multi.session_id)
      if (job) {
        const target = { job_id: job.job_id, run_id: job.run_id, owner_generation: job.owner_generation }
        const command = { target, command_id: 'live-correction-1', feedback: TASKS[2].correction }
        const receipt = await ownerResume(repo, owner.ownerId, command)
        corrections++
        report.corrections.push({ job_id: multi.session_id, receipt: receipt.receipt })
        if (receipt.receipt === 'accepted') {
          const corrected = await waitJob(bridge, wt, multi.session_id)
          let checksPassed = false, checkError = null
          try { TASKS[2].verify(wt); checksPassed = true } catch (error) { checkError = String(error).slice(0, 500) }
          report.corrections.push({ job_id: multi.session_id, state: corrected.state, parent_checks_passed: checksPassed, check_error: checkError })
        }
      }
    }
    if (profile.incumbent === 'bridge-codex' && codexAvailable()) {
      const incumbentBridge = codexBridge(profile.selections)
      for (const task of TASKS) {
        const pin = profile.selections[task.tier]
        jobs.push({ selection: { model: pin.model, effort: pin.effort, provider: 'codex' }, ...(await runBridgeJob(incumbentBridge, repo, 'inc-' + task.key, task, base)) })
      }
    } else if (profile.incumbent === 'pi-cli' && spawnSync('which', ['pi'], { encoding: 'utf8', timeout: 5000 }).status === 0) {
      for (const task of TASKS) jobs.push({ selection: { model: 'deepseek-v4.1-flash', effort: 'high', provider: 'opencode-go' }, ...(await runPiCliJob(repo, 'inc-' + task.key, task, base)) })
    } else {
      report.incumbent = { status: 'unavailable', note: 'incumbent runtime not authenticated on this host' }
    }
    report.incumbent_ran = jobs.some(j => j.backend !== 'fx')
    const output = join(scratch, 'fx-live.json')
    writeFileSync(output, JSON.stringify(report, null, 2))
    console.log(JSON.stringify({ status: 'completed', profile: name, report: output, jobs: jobs.map(j => ({ task: j.task, backend: j.backend, state: j.state, parent_checks_passed: j.parent_checks_passed })) }))
    return { status: 'completed', exitCode: 0, report }
  } catch (error) {
    report.error = String(error).slice(0, 2000)
    writeFileSync(join(scratch, 'fx-live.json'), JSON.stringify(report, null, 2))
    console.log(JSON.stringify({ status: 'failed', profile: name, error: report.error }))
    return { status: 'failed', exitCode: 1, report }
  } finally {
    if (owner) await owner.close().catch(() => {})
    if (auth?.secretDir) rmSync(auth.secretDir, { recursive: true, force: true })
  }
}
