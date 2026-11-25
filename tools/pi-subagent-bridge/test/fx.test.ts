import test, { type TestContext } from "node:test"
import assert from "node:assert/strict"
import { createHash } from "node:crypto"
import { readFileSync, writeFileSync, mkdirSync, existsSync, watch, statSync } from "node:fs"
import { spawn } from "node:child_process"
import { join, dirname } from "node:path"
import { Scratch, git, unusedApi } from "./worker-fixtures.ts"
import { makeFxAdapter, fxResult, cancelFxChildren, type FxSelection } from "../src/fx.ts"
import { classifyJobBlock, classifyProbeResponse, pilotVerdict, renameEvidenceOk, scoutFindingOk } from "../experiment/fx/pilot.ts"
import { makeHybridBridge } from "./harness-fixtures.ts"
import { piAdapter } from "../src/pi-adapter.ts"
import { decodeSession, encodeSession, type ExecutionPlan, type FxFallbackPlan } from "../src/session.ts"
import type { CommandRun } from "../src/command.ts"

const selection: FxSelection = { model: "fixture-model", effort: "high", provider: "fixture", runtimeVersion: "0.0.17" }
function fixture(t: TestContext, behavior = "success", wallMs = 5000) {
  const scratch = new Scratch()
  t.after(() => scratch.close())
  const repo = scratch.repo(), binary = join(scratch.path, "fake-fx")
  const source = `#!${process.execPath}
const fs=require('node:fs'),p=require('node:path');
if(process.argv.includes('--version')){console.log('0.0.17');process.exit(0)}
const args=process.argv.slice(2),id='native-fixture',dir=p.join(process.env.FX_HOME,'sessions/v2',id);
fs.mkdirSync(p.join(process.env.FX_HOME,'sessions/v2/.tmp'),{recursive:true});fs.writeFileSync(p.join(process.env.FX_HOME,'sessions/v2/index.jsonl'),'');fs.mkdirSync(dir,{recursive:true});fs.writeFileSync(p.join(dir,'log.jsonl'),JSON.stringify({v:1,kind:'session_created',id,workspace:process.cwd(),role:'root'})+'\\n');
const mode=${JSON.stringify(behavior)}==='hold-once'&&args.includes('--resume')?'success':${JSON.stringify(behavior)}==='hold-once'?'hold':${JSON.stringify(behavior)};
if(mode==='oversized')process.stdout.write('x'.repeat(1100000));
else if(mode==='malformed')process.stdout.write('{\"exit_code\":');
else if(!['hold','exhaust','quotafail','smallretry'].includes(mode))console.log(JSON.stringify({exit_code:0,model:'fixture-model',session_id:mode==='mismatch'?'foreign-session':id,final_output:mode==='empty'?'':'PROOF fixture\\nACCEPTANCE: met',usage:{input_tokens:1,output_tokens:1},tool_calls:mode==='webfetch'?[{name:'web_fetch',status:'success'}]:[]}));
if(['exhaust','quotafail','smallretry'].includes(mode))setTimeout(()=>{
  const rec=mode==='exhaust'?{v:1,seq:2,ts:Date.now(),kind:'item',turn:1,type:'model_call',data:{outcome:'failed',failure:'rate_limited',retry_after_s:999999}}
    :mode==='quotafail'?{v:1,seq:2,ts:Date.now(),kind:'item',turn:1,type:'model_call',data:{outcome:'failed',failure:'quota'}}
    :{v:1,seq:2,ts:Date.now(),kind:'item',turn:1,type:'model_call',data:{outcome:'failed',failure:'rate_limited',retry_after_s:3}};
  fs.appendFileSync(p.join(dir,'log.jsonl'),JSON.stringify(rec)+'\\n');
},300);
if(['hold','oversized','early-json','exhaust','quotafail','smallretry'].includes(mode))setInterval(()=>{},1000);
`
  writeFileSync(binary, source, { mode: 0o755 })
  const fx = makeFxAdapter({ transport: "cli", shell: "/bin/sh", binary, binarySha256: createHash("sha256").update(source).digest("hex"), home: scratch.path, provider: "fixture", connection: {}, allowedCommands: [], wallMs })
  const request = { directory: repo.cwd, logDirectory: repo.directory, prompt: "fixture task", selection, access: { kind: "write" as const } }
  mkdirSync(repo.directory, { recursive: true })
  return { repo, fx, request }
}
async function ended(run: CommandRun) {
  const deadline = Date.now() + 10000
  while (Date.now() < deadline) {
    const result = fxResult(run, selection)
    if (result.state !== "running" && result.state !== "unknown_or_interrupted") return result
    if (result.state === "unknown_or_interrupted" && readReceipt(run)) return result
    await new Promise<void>(resolve => setImmediate(resolve))
  }
  throw new Error("FX fixture did not settle")
}
function readReceipt(run: CommandRun) { try { return readFileSync(run.output, "utf8") } catch { return null } }

test("FX supervision binds final JSON to actual exit and resumes only the recorded worktree and pins", async t => {
  const f = fixture(t), run = f.fx.start(f.request)
  const result = await ended(run)
  assert.equal(result.state, "succeeded")
  const resume = result.result!.sessionId!
  assert.match(resume, /^fx:0\.0\.17:/)
  assert.throws(() => f.fx.start({ ...f.request, directory: f.repo.root, resume }), /worktree\/pin mismatch/)
  assert.throws(() => f.fx.start({ ...f.request, selection: { ...selection, effort: "low" }, resume }), /pin mismatch/)
  const next = f.fx.start({ ...f.request, resume })
  assert.equal((await ended(next)).state, "succeeded")
  assert.equal(f.fx.session(next, selection), resume)
  assert.equal(fxResult(next, { ...selection, model: "foreign-model" }).state, "unknown_or_interrupted")
  const job = JSON.parse(readFileSync(next.output + ".job.json", "utf8"))
  writeFileSync(join(job.fxHome, "settings.json"), JSON.stringify({ permission: { "*": "allow" } }))
  assert.throws(() => f.fx.start({ ...f.request, resume }), /configuration changed/)

})

for (const behavior of ["hold", "oversized", "early-json"] as const) {
  test(`FX ${behavior} cannot turn an unfinished run into success`, async t => {
    const f = fixture(t, behavior, behavior === "oversized" ? 5000 : behavior === "early-json" ? 1000 : 200), run = f.fx.start(f.request)
    const result = await ended(run)
    assert.equal(result.state, behavior === "oversized" ? "failed" : "timed_out")
    const receipt = JSON.parse(readReceipt(run)!)
    assert.equal(receipt.reason, behavior === "oversized" ? "oversized" : "deadline")
    assert.ok(Buffer.byteLength(receipt.stdout) <= 1_048_576)
    if (behavior === "early-json") assert.equal(JSON.parse(receipt.stdout).exit_code, 0)
  })
}

test("a mismatched FX native session remains unknown and retains the shared worktree lease", async t => {
  const f = fixture(t, "mismatch"), policy: ExecutionPlan = { kind: "leaf", target: { executor: "fx", selection } }
  const bridge = makeHybridBridge(piAdapter(unusedApi()), undefined, undefined, () => policy, f.fx)
  const scope = { base_revision: f.repo.base, writable_paths: ["README"], acceptance_proof: "fixture proof", attempt_limit: 2, stop_on: "scope expansion" }
  const admitted = await bridge.start(f.repo.cwd, "fixture", "worker", scope, "task")
  const path = join(f.repo.directory, admitted.session_id + ".json")
  const session = decodeSession(JSON.parse(readFileSync(path, "utf8")), f.repo.cwd, admitted.session_id)
  assert.equal(session.execution.kind, "process")
  if (session.execution.kind !== "process") throw new Error("missing process")
  assert.equal((await ended(session.execution.run)).state, "unknown_or_interrupted")
  assert.equal((await bridge.status(f.repo.cwd, admitted.session_id)).state, "unknown_or_interrupted")
  await assert.rejects(() => bridge.start(f.repo.cwd, "duplicate", "worker", scope, "task"), /active worker/)
  const wire = encodeSession(session)
  assert.equal(wire.schema_version, 3)
  assert.throws(() => decodeSession({ ...wire, schema_version: 2 }, f.repo.cwd, admitted.session_id), /require session schema 3/)
  const bad = structuredClone(wire)
  if (bad.execution.kind !== "process" || bad.execution.executor !== "fx") throw new Error("missing FX")
  const invalid = { ...bad, execution: { ...bad.execution, selection: { ...bad.execution.selection, runtimeVersion: "unknown" } } }
  assert.throws(() => decodeSession(invalid, f.repo.cwd, admitted.session_id), /Unsupported persisted FX version/)
  assert.equal(git(f.repo.cwd, "status", "--porcelain"), "")
})

test("FX cancellation rejects stale process identity and mismatched run ownership before signaling", async t => {
  const f = fixture(t, "hold"), run = f.fx.start(f.request)
  await ready(run.output + ".native.json")
  assert.equal(f.fx.cancel({ ...run, proc_start: "stale-process" }), false)
  assert.equal(f.fx.cancel({ ...run, output: run.output + ".foreign" }), false)
  assert.equal(f.fx.cancel(run), true)
  assert.equal((await ended(run)).state, "cancelled")
})

const recoveryScope = (f: ReturnType<typeof fixture>) => ({ base_revision: f.repo.base, writable_paths: ["README"], acceptance_proof: "fixture proof", attempt_limit: 2, stop_on: "scope expansion" })
async function settledStatus(bridge: ReturnType<typeof makeHybridBridge>, cwd: string, id: string) {
  const deadline = Date.now() + 10000
  while (Date.now() < deadline) {
    const status = await bridge.status(cwd, id)
    if (status.state !== "running") return status
    await new Promise<void>(resolve => setTimeout(resolve, 50))
  }
  throw new Error("FX worker did not settle")
}
function currentRun(f: ReturnType<typeof fixture>, id: string): CommandRun {
  const session = decodeSession(JSON.parse(readFileSync(join(f.repo.directory, id + ".json"), "utf8")), f.repo.cwd, id)
  if (session.execution.kind !== "process") throw new Error("missing process")
  return session.execution.run
}

test("an FX run stopped at its wall deadline reports timed_out with its budget and resumes the same native session", async t => {
  const f = fixture(t, "hold-once", 1000), policy: ExecutionPlan = { kind: "leaf", target: { executor: "fx", selection } }
  const bridge = makeHybridBridge(piAdapter(unusedApi()), undefined, undefined, () => policy, f.fx)
  const admitted = await bridge.start(f.repo.cwd, "fixture", "worker", recoveryScope(f), "task")
  assert.equal(admitted.run_deadline_ms, 1000)
  assert.equal(admitted.run_step_limit, 20)
  const stopped = await settledStatus(bridge, f.repo.cwd, admitted.session_id)
  assert.equal(stopped.state, "timed_out")
  assert.equal(stopped.run_deadline_ms, 1000)
  assert.equal(stopped.run_step_limit, 20)
  assert.equal((await bridge.resume(f.repo.cwd, admitted.session_id, "continue")).status, "admitted")
  const job = JSON.parse(readFileSync(currentRun(f, admitted.session_id).output + ".job.json", "utf8"))
  assert.deepEqual(job.args.slice(job.args.indexOf("--resume"), job.args.indexOf("--resume") + 2), ["--resume", "native-fixture"])
  assert.equal((await settledStatus(bridge, f.repo.cwd, admitted.session_id)).state, "succeeded")
})

test("a verified FX cancellation resumes the same native session without replaying the attempt budget", async t => {
  const f = fixture(t, "hold-once"), policy: ExecutionPlan = { kind: "leaf", target: { executor: "fx", selection } }
  const bridge = makeHybridBridge(piAdapter(unusedApi()), undefined, undefined, () => policy, f.fx)
  const admitted = await bridge.start(f.repo.cwd, "fixture", "worker", recoveryScope(f), "task")
  await ready(currentRun(f, admitted.session_id).output + ".native.json")
  assert.equal((await bridge.cancel(f.repo.cwd, admitted.session_id)).interrupted, true)
  assert.equal((await settledStatus(bridge, f.repo.cwd, admitted.session_id)).state, "cancelled")
  assert.equal((await bridge.resume(f.repo.cwd, admitted.session_id, "continue")).status, "admitted")
  assert.equal((await settledStatus(bridge, f.repo.cwd, admitted.session_id)).state, "succeeded")
  await assert.rejects(() => bridge.resume(f.repo.cwd, admitted.session_id, "again"), /attempt limit/)
})

test("an FX run without a verified termination receipt cannot be resumed", async t => {
  const f = fixture(t, "mismatch"), policy: ExecutionPlan = { kind: "leaf", target: { executor: "fx", selection } }
  const bridge = makeHybridBridge(piAdapter(unusedApi()), undefined, undefined, () => policy, f.fx)
  const admitted = await bridge.start(f.repo.cwd, "fixture", "worker", recoveryScope(f), "task")
  await ended(currentRun(f, admitted.session_id))
  await assert.rejects(() => bridge.resume(f.repo.cwd, admitted.session_id, "continue"), /not known complete/)
})

async function ready(path: string): Promise<void> {
  if (existsSync(path)) return
  await new Promise<void>((resolve, reject) => {
    const watcher = watch(dirname(path), () => { if (existsSync(path)) { clearTimeout(timer); watcher.close(); resolve() } })
    const timer = setTimeout(() => { watcher.close(); reject(new Error("supervisor did not publish process identity")) }, 5000)
    watcher.once("error", error => { clearTimeout(timer); watcher.close(); reject(error) })
    if (existsSync(path)) { clearTimeout(timer); watcher.close(); resolve() }
  })
}

test("missing optional FX composition refuses control before changing attempts or history", async t => {
  const f = fixture(t), policy: ExecutionPlan = { kind: "leaf", target: { executor: "fx", selection } }
  const bridge = makeHybridBridge(piAdapter(unusedApi()), undefined, undefined, () => policy, f.fx)
  const scope = { base_revision: f.repo.base, writable_paths: ["README"], acceptance_proof: "fixture proof", attempt_limit: 2, stop_on: "scope expansion" }
  const admitted = await bridge.start(f.repo.cwd, "fixture", "worker", scope, "task")
  const path = join(f.repo.directory, admitted.session_id + ".json")
  const session = decodeSession(JSON.parse(readFileSync(path, "utf8")), f.repo.cwd, admitted.session_id)
  if (session.execution.kind !== "process") throw new Error("missing process")
  assert.equal((await ended(session.execution.run)).state, "succeeded")
  await bridge.status(f.repo.cwd, admitted.session_id)
  const before = readFileSync(path, "utf8")
  const withoutFx = makeHybridBridge(piAdapter(unusedApi()), undefined, undefined, () => policy)
  await assert.rejects(() => withoutFx.resume(f.repo.cwd, admitted.session_id, "same scope"), /FX adapter unavailable/)
  assert.equal(readFileSync(path, "utf8"), before)
  await assert.rejects(() => withoutFx.cancel(f.repo.cwd, admitted.session_id), /FX adapter unavailable/)
  assert.equal(readFileSync(path, "utf8"), before)
})

for (const behavior of ["malformed", "empty"] as const) {
  test(`FX exit zero with ${behavior} final evidence remains unknown`, async t => {
    const f = fixture(t, behavior), run = f.fx.start(f.request)
    assert.equal((await ended(run)).state, "unknown_or_interrupted")
  })
}

function envProbeFixture(t: TestContext, configure?: (scratch: Scratch) => Partial<Parameters<typeof makeFxAdapter>[0]>) {
  const scratch = new Scratch()
  t.after(() => scratch.close())
  const repo = scratch.repo(), binary = join(scratch.path, "fake-fx")
  const source = `#!${process.execPath}
const fs=require('node:fs'),p=require('node:path');
if(process.argv.includes('--version')){console.log('0.0.17');process.exit(0)}
const id='native-fixture',dir=p.join(process.env.FX_HOME,'sessions/v2',id);
fs.mkdirSync(p.join(process.env.FX_HOME,'sessions/v2/.tmp'),{recursive:true});fs.writeFileSync(p.join(process.env.FX_HOME,'sessions/v2/index.jsonl'),'');fs.mkdirSync(dir,{recursive:true});fs.writeFileSync(p.join(dir,'log.jsonl'),JSON.stringify({v:1,kind:'session_created',id,workspace:process.cwd(),role:'root'})+'\\n');
fs.writeFileSync(p.join(process.env.FX_HOME,'probe.json'),JSON.stringify({path:process.env.PATH,secret:process.env.PILOT_TEST_SECRET??null,scoped:process.env.USR_SCOPED_WORKER??null}));
console.log(JSON.stringify({exit_code:0,model:'fixture-model',session_id:id,final_output:'PROOF fixture\\nACCEPTANCE: met',usage:{input_tokens:1,output_tokens:1}}));
`
  writeFileSync(binary, source, { mode: 0o755 })
  const fx = makeFxAdapter({ transport: "cli", shell: "/bin/sh", binary, binarySha256: createHash("sha256").update(source).digest("hex"), home: scratch.path, provider: "fixture", connection: {}, allowedCommands: [], wallMs: 5000, ...configure?.(scratch) })
  const request = { directory: repo.cwd, logDirectory: repo.directory, prompt: "fixture task", selection, access: { kind: "write" as const } }
  mkdirSync(repo.directory, { recursive: true })
  return { scratch, repo, fx, request }
}

test("FX secret env files reach only the child environment and never the job record", async t => {
  let secret = ""
  const f = envProbeFixture(t, scratch => {
    secret = join(scratch.path, "token.txt")
    writeFileSync(secret, "s3cr3t-value\n", { mode: 0o600 })
    return { secretEnvFiles: { PILOT_TEST_SECRET: secret } }
  })
  const run = f.fx.start(f.request)
  const jobPath = run.output + ".job.json"
  const recorded = readFileSync(jobPath, "utf8")
  assert.ok(!recorded.includes("s3cr3t-value"), "job record must not serialize the secret")
  assert.ok(recorded.includes(secret))
  assert.equal((await ended(run)).state, "succeeded")
  const job = JSON.parse(recorded)
  const probe = JSON.parse(readFileSync(join(job.fxHome, "probe.json"), "utf8"))
  assert.equal(probe.secret, "s3cr3t-value")
})

test("FX secret env file failure produces a failed run, not a hung admission", async t => {
  const f = envProbeFixture(t, scratch => ({ secretEnvFiles: { PILOT_TEST_SECRET: join(scratch.path, "absent.txt") } }))
  const run = f.fx.start(f.request)
  const result = await ended(run)
  assert.equal(result.state, "failed")
  assert.match(String(result.stderr ?? "") + JSON.stringify(result.result ?? {}), /absent|ENOENT|spawn/i)
})

test("FX pathEnv provisions the child toolchain PATH", async t => {
  const f = envProbeFixture(t, () => ({ pathEnv: "/opt/toolchain/bin:/usr/bin:/bin" }))
  const run = f.fx.start(f.request)
  assert.equal((await ended(run)).state, "succeeded")
  const job = JSON.parse(readFileSync(run.output + ".job.json", "utf8"))
  const probe = JSON.parse(readFileSync(join(job.fxHome, "probe.json"), "utf8"))
  assert.equal(probe.path, "/opt/toolchain/bin:/usr/bin:/bin")
  assert.equal(probe.secret, null)
})

test("FX workers carry the scoped-worker marker so coordinator-only hooks stay suppressed", async t => {
  const f = envProbeFixture(t)
  const run = f.fx.start(f.request)
  assert.equal((await ended(run)).state, "succeeded")
  const job = JSON.parse(readFileSync(run.output + ".job.json", "utf8"))
  assert.equal(JSON.parse(readFileSync(join(job.fxHome, "probe.json"), "utf8")).scoped, "1")
})

test("FX reserved env names are refused for secrets and extra environment", t => {
  const scratch = new Scratch()
  t.after(() => scratch.close())
  const binary = join(scratch.path, "fake-fx")
  writeFileSync(binary, "#!/bin/true\n", { mode: 0o755 })
  const sha = createHash("sha256").update(readFileSync(binary)).digest("hex")
  const base = { transport: "cli" as const, shell: "/bin/sh", binary, binarySha256: sha, home: scratch.path, provider: "fixture", connection: {}, allowedCommands: [] }
  for (const name of ["FX_PROVIDER", "FX_PERMISSION_MODE", "LD_PRELOAD", "DYLD_INSERT_LIBRARIES", "GIT_DIR", "BASH_ENV", "PYTHONPATH", "NODE_OPTIONS", "HOME", "USR_SCOPED_WORKER", "lowercase"]) {
    assert.throws(() => makeFxAdapter({ ...base, secretEnvFiles: { [name]: "/tmp/x" } }), /Invalid FX secret env/, name)
    assert.throws(() => makeFxAdapter({ ...base, extraEnv: { [name]: "x" } }), /Invalid FX extra env/, name)
  }
  assert.doesNotThrow(() => makeFxAdapter({ ...base, secretEnvFiles: { PILOT_TOKEN: "/tmp/x" }, extraEnv: { CARGO_HOME: "/tmp/cargo" } }))
})

test("FX auth files seed a fresh profile home and survive resume", async t => {
  let credential = ""
  const f = envProbeFixture(t, scratch => {
    credential = join(scratch.path, "cred.json")
    writeFileSync(credential, JSON.stringify({ token: "auth-fixture" }), { mode: 0o600 })
    return { authFiles: [credential], connection: null }
  })
  const run = f.fx.start(f.request)
  const first = await ended(run)
  assert.equal(first.state, "succeeded")
  const job = JSON.parse(readFileSync(run.output + ".job.json", "utf8"))
  const seeded = join(job.fxHome, "cred.json")
  assert.equal(readFileSync(seeded, "utf8"), JSON.stringify({ token: "auth-fixture" }))
  assert.equal(statSync(seeded).mode & 0o777, 0o600)
  const settings = JSON.parse(readFileSync(join(job.fxHome, "settings.json"), "utf8"))
  assert.equal(settings.providers, undefined)
  assert.equal(settings.provider, "fixture")
  writeFileSync(seeded, JSON.stringify({ token: "refreshed" }))
  const next = f.fx.start({ ...f.request, resume: first.result!.sessionId! })
  assert.equal((await ended(next)).state, "succeeded")
  const nextJob = JSON.parse(readFileSync(next.output + ".job.json", "utf8"))
  assert.equal(nextJob.fxHome, job.fxHome)
  assert.equal(readFileSync(join(nextJob.fxHome, "cred.json"), "utf8"), JSON.stringify({ token: "refreshed" }))
})

test("FX live pilot verdict distinguishes passed, blocked and failed", () => {
  const okTask = { state: "succeeded", checks: true }
  const contOk = { attempted: true, accepted: true, identity: true, checks: true, nativeSession: true }
  const tasks = ["scout", "fix", "multi"].map(key => ({ key, ...okTask }))
  assert.equal(pilotVerdict({ tasks, continuation: contOk }), "passed")
  assert.equal(pilotVerdict({ tasks: tasks.slice(0, 2), continuation: contOk }), "blocked")
  assert.equal(pilotVerdict({ tasks: [{ key: "scout", state: "succeeded", checks: false }, ...tasks.slice(1)], continuation: contOk }), "failed")
  assert.equal(pilotVerdict({ tasks: [{ key: "scout", state: "failed", block: "quota" }, ...tasks.slice(1)], continuation: { attempted: false, nativeSession: false } }), "blocked")
  assert.equal(pilotVerdict({ tasks: [{ key: "scout", state: "failed" }, ...tasks.slice(1)], continuation: contOk }), "failed")
  assert.equal(pilotVerdict({ tasks, continuation: { attempted: true, accepted: true, identity: false, checks: true, nativeSession: true } }), "failed")
  assert.equal(pilotVerdict({ tasks, continuation: { attempted: true, accepted: true, identity: true, checks: false, nativeSession: true } }), "failed")
  assert.equal(pilotVerdict({ tasks, continuation: { attempted: true, accepted: false, nativeSession: true } }), "failed")
  assert.equal(pilotVerdict({ tasks, continuation: { attempted: false, nativeSession: false, reason: "no-native-session" } }), "blocked")
  assert.equal(pilotVerdict({ tasks: tasks.map(t => ({ ...t, block: "quota" as const })), continuation: { attempted: false, nativeSession: false } }), "blocked")
  assert.equal(pilotVerdict({ tasks: tasks.map(t => ({ ...t, backend: "codex" })), continuation: contOk }), "blocked")
  assert.equal(pilotVerdict({ tasks: [{ key: "scout", state: "succeeded", checks: true, backend: "pi" }, ...tasks.slice(1)], continuation: contOk }), "blocked")
})

test("FX live pilot provider classification separates quota, auth and transient stalls", () => {
  assert.equal(classifyProbeResponse(429, '{"type":"GoUsageLimitError","message":"usage limit reached (monthly, resets in 14d)"}'), "quota")
  assert.equal(classifyProbeResponse(429, '{"error":"slow down"}'), "rate-limited")
  assert.equal(classifyProbeResponse(401, "unauthorized"), "auth")
  assert.equal(classifyProbeResponse(200, "{}"), "ok")
  assert.equal(classifyProbeResponse(500, "boom"), "unknown")
  const base = { state: "failed", lastText: "", elapsedMs: 900_000, wallMs: 900_000, stderrTail: "[notice] Rate limited · retrying" }
  assert.equal(classifyJobBlock({ ...base, probe: "quota" }), "quota")
  assert.equal(classifyJobBlock({ ...base, probe: null, stderrTail: "MissingCredentials: run fx login codex" }), "auth")
  assert.equal(classifyJobBlock({ ...base, probe: "rate-limited" }), "provider-stall")
  assert.equal(classifyJobBlock({ ...base, probe: null, elapsedMs: 30_000 }), null)
  assert.equal(classifyJobBlock({ ...base, state: "succeeded", probe: "quota" }), null)
})

test("FX live pilot task evidence rejects citation-shaped and rename-incomplete results", () => {
  assert.equal(scoutFindingOk("The bug is python/ledger.py line 7: the debit branch adds instead of subtracting."), true)
  assert.equal(scoutFindingOk("python/ledger.py:999 — the ledger is correct; there is no debit bug."), false)
  assert.equal(scoutFindingOk("ts/ledger.mjs line 5 has the debit bug"), false)
  assert.equal(scoutFindingOk("python/ledger.py line 7 looks wrong"), false)
  const good = {
    python: "def settled_balance(entries):\n    balance -= entry['amount']\n",
    ts: "export function settled_balance(entries) {\n  balance -= entry.amount\n}\n",
    rust: "pub fn settled_balance(entries: &[(bool, i64)]) -> i64 { 0 }\n",
    "python-report": "from ledger import summarize\n",
    "python-test": "from ledger import settled_balance, summarize\n",
    "ts-check": "import { settled_balance } from './ledger.mjs'\n",
  }
  assert.equal(renameEvidenceOk(good), null)
  assert.match(String(renameEvidenceOk({ ...good, ts: good.ts.replaceAll("settled_balance", "balanceAfter") })), /old name/)
  assert.match(String(renameEvidenceOk({ ...good, rust: good.rust.replace("settled_balance", "balance_after") })), /old name/)
  assert.match(String(renameEvidenceOk({ ...good, "python-test": "from ledger import balance_after\n" })), /old name/)
  assert.match(String(renameEvidenceOk({ ...good, "ts-check": "import { summarize } from './ledger.mjs'\n" })), /lacks settled_balance/)
})

test("FX provider exhaustion surfaces promptly as a quota-classified failure", async t => {
  for (const behavior of ["exhaust", "quotafail"] as const) {
    const f = fixture(t, behavior, 20000), run = f.fx.start(f.request)
    const result = await ended(run)
    assert.equal(result.state, "failed")
    assert.match(String(result.result!.error), /quota exhaustion/)
    assert.equal(JSON.parse(readReceipt(run)!).reason, "exhausted")
  }
})

test("a provider retry hint inside the job bound does not count as exhaustion", async t => {
  const f = fixture(t, "smallretry", 6000), run = f.fx.start(f.request)
  const result = await ended(run)
  assert.equal(result.state, "timed_out")
  assert.equal(JSON.parse(readReceipt(run)!).reason, "deadline")
})

const FX_LADDER: FxFallbackPlan = {
  kind: "fx-fallback",
  fx: selection,
  codex: { model: "gpt-6.1-terra", effort: "high" },
  command: { model: "deepseek/deepseek-v4.1-flash", effort: "high" },
  pi: [{ providerID: "opencode-go", id: "muse-spark-1.3-contributor", variant: "high" }],
}

function commandLane(available = true) {
  const launches: unknown[] = []
  return {
    launches,
    runner: {
      available: () => available,
      start: (request: { selection: { model: string; effort: string } }) => {
        launches.push(request.selection)
        return { pid: 4242, output: "cmd-out", errors: "cmd-err", started_at: "2026-11-15T00:00:00Z" }
      },
      status: () => ({ state: "succeeded" as const, result: { subtype: "success" as const, sessionId: "cmd-session", finalText: "PROOF\nACCEPTANCE: met" }, stderr: null }),
      cancel: () => true,
    },
  }
}

function codexLane(available = false) {
  const launches: unknown[] = []
  return {
    launches,
    runner: {
      available: () => available,
      start: (request: { selection: { model: string; effort: string } }) => {
        launches.push(request.selection)
        return { pid: 4343, output: "codex-out", errors: "codex-err", started_at: "2026-11-15T00:00:00Z" }
      },
      status: () => ({ state: "succeeded" as const, result: { subtype: "success" as const, sessionId: "codex-session", finalText: "PROOF\nACCEPTANCE: met" }, stderr: null }),
      cancel: () => true,
      session: () => "codex-session",
    },
  }
}

async function settle(bridge: ReturnType<typeof makeHybridBridge>, cwd: string, id: string, ms = 30000) {
  const deadline = Date.now() + ms
  for (;;) {
    const status = await bridge.status(cwd, id)
    if (status.state !== "running" && status.state !== "queued") return status
    if (Date.now() > deadline) throw new Error("session did not settle")
    await new Promise(resolve => setTimeout(resolve, 200))
  }
}

function ladderScope(f: ReturnType<typeof fixture>) {
  return { base_revision: f.repo.base, writable_paths: ["README"], acceptance_proof: "fixture proof", attempt_limit: 2, stop_on: "scope expansion" }
}

test("FX quota exhaustion advances exactly once to Command Code on a clean worktree", async t => {
  const f = fixture(t, "exhaust", 20000)
  const cmd = commandLane(), codex = codexLane(false)
  const bridge = makeHybridBridge(piAdapter(unusedApi()), cmd.runner, codex.runner, () => FX_LADDER, f.fx)
  const admitted = await bridge.start(f.repo.cwd, "fx-fallback", "worker", ladderScope(f), "task")
  const status = await settle(bridge, f.repo.cwd, admitted.session_id)
  assert.equal(status.backend, "command-code")
  assert.equal(status.state, "succeeded")
  assert.match(status.fallback_reason ?? "", /FX provider\/model exhausted/)
  assert.equal(cmd.launches.length, 1)
  const session = decodeSession(JSON.parse(readFileSync(join(f.repo.directory, admitted.session_id + ".json"), "utf8")), f.repo.cwd, admitted.session_id)
  assert.equal(session.plan.kind, "fx-fallback")
  assert.equal(encodeSession(session).schema_version, 3)
  await bridge.status(f.repo.cwd, admitted.session_id)
  assert.equal(cmd.launches.length, 1)
})

test("FX exhaustion prefers Codex over Command Code when both lanes are approved", async t => {
  const f = fixture(t, "exhaust", 20000)
  const cmd = commandLane(), codex = codexLane(true)
  const bridge = makeHybridBridge(piAdapter(unusedApi()), cmd.runner, codex.runner, () => FX_LADDER, f.fx)
  const admitted = await bridge.start(f.repo.cwd, "fx-fallback", "worker", ladderScope(f), "task")
  const status = await settle(bridge, f.repo.cwd, admitted.session_id)
  assert.equal(status.backend, "codex")
  assert.equal(status.state, "succeeded")
  assert.equal(codex.launches.length, 1)
  assert.equal(cmd.launches.length, 0)
})

test("FX exhaustion after edits blocks fallback instead of replaying partial work", async t => {
  const f = fixture(t, "exhaust", 20000)
  const cmd = commandLane(), codex = codexLane(true)
  const bridge = makeHybridBridge(piAdapter(unusedApi()), cmd.runner, codex.runner, () => FX_LADDER, f.fx)
  const admitted = await bridge.start(f.repo.cwd, "fx-fallback", "worker", ladderScope(f), "task")
  writeFileSync(join(f.repo.cwd, "README"), "partial\n")
  const status = await settle(bridge, f.repo.cwd, admitted.session_id)
  assert.equal(status.state, "blocked_partial_work")
  assert.equal(cmd.launches.length + codex.launches.length, 0)
})

test("FX exhaustion with every fallback lane unavailable ends blocked, never replayed", async t => {
  const f = fixture(t, "exhaust", 20000)
  const cmd = commandLane(false), codex = codexLane(false)
  const bridge = makeHybridBridge(piAdapter(unusedApi()), cmd.runner, codex.runner, () => FX_LADDER, f.fx)
  const admitted = await bridge.start(f.repo.cwd, "fx-fallback", "worker", ladderScope(f), "task")
  const status = await settle(bridge, f.repo.cwd, admitted.session_id)
  assert.match(status.state, /^blocked_/)
  assert.equal(cmd.launches.length + codex.launches.length, 0)
})

test("an unavailable FX primary admits the next approved lane with a recorded reason", async t => {
  const f = fixture(t, "success")
  const cmd = commandLane(), codex = codexLane(false)
  const foreign: FxSelection = { ...selection, provider: "other-provider" }
  const plan = { ...FX_LADDER, fx: foreign }
  const bridge = makeHybridBridge(piAdapter(unusedApi()), cmd.runner, codex.runner, () => plan, f.fx)
  const admitted = await bridge.start(f.repo.cwd, "fx-fallback", "worker", ladderScope(f), "task")
  assert.match(admitted.fallback_reason ?? "", /FX runtime\/provider unavailable/)
  const status = await settle(bridge, f.repo.cwd, admitted.session_id)
  assert.equal(status.backend, "command-code")
  assert.equal(cmd.launches.length, 1)
})

function acpFixture(t: TestContext, behavior: string, wallMs = 5000, delegation?: { maxChildren: number; maxConcurrent: number }) {
  const scratch = new Scratch()
  t.after(() => scratch.close())
  const repo = scratch.repo(), binary = join(scratch.path, "fake-fx-acp")
  const source = `#!${process.execPath}
const fs=require('node:fs'),p=require('node:path');
if(process.argv.includes('--version')){console.log('0.0.17');process.exit(0)}
const mode=${JSON.stringify(behavior)},home=process.env.FX_HOME,args=process.argv.slice(2);
const model=args[args.indexOf('--model')+1],effort=args[args.indexOf('--effort')+1];
const send=m=>process.stdout.write(JSON.stringify({jsonrpc:'2.0',...m})+'\\n');
let buf='',sid=null;
process.stdin.on('data',d=>{buf+=d;let i;while((i=buf.indexOf('\\n'))>=0){const line=buf.slice(0,i);buf=buf.slice(i+1);if(line.trim())handle(JSON.parse(line))}});
process.stdin.on('end',()=>process.exit(0));
function open(id){sid=id;const dir=p.join(home,'sessions/v2',id);fs.mkdirSync(dir,{recursive:true});if(!fs.existsSync(p.join(dir,'log.jsonl')))fs.writeFileSync(p.join(dir,'log.jsonl'),JSON.stringify({v:1,kind:'session_created',id,workspace:process.cwd(),role:'root'})+'\\n')}
function config(){return[{id:'provider',currentValue:'fixture'},{id:'model',currentValue:mode==='wrong-pin'?'other-model':model},{id:'effort',currentValue:effort}]}
let prompt=null;
function handle(m){
  if(m.method==='initialize')return send({id:m.id,result:{protocolVersion:1,agentInfo:{name:'fx',version:'0.0.17'}}});
  if(m.method==='session/new'){open('acp-native');return send({id:m.id,result:{sessionId:'acp-native',configOptions:config()}})}
  if(m.method==='session/resume'){if(!fs.existsSync(p.join(home,'sessions/v2',m.params.sessionId)))return send({id:m.id,error:{code:-32602,message:'Session not found'}});open(m.params.sessionId);return send({id:m.id,result:{configOptions:config()}})}
  if(m.method==='session/prompt'){prompt=m.id;
    if(mode==='hold'||mode==='hold-once'&&!fs.existsSync(p.join(home,'held'))){fs.writeFileSync(p.join(home,'held'),'');return}
    const child=JSON.stringify(m.params.prompt).includes('child of a bridge-managed worker');
    if(mode==='child-hold'&&child)return;
    if(mode==='child-hold'){const gate=setInterval(()=>{if(fs.existsSync(process.env.FIXTURE_GATE)){clearInterval(gate);send({method:'session/update',params:{sessionId:sid,update:{sessionUpdate:'agent_message_chunk',content:{type:'text',text:'PROOF root\\nACCEPTANCE: met'}}}});send({id:m.id,result:{stopReason:'end_turn'}})}},50);return}
    if(mode==='webfetch')return send({method:'session/update',params:{sessionId:sid,update:{sessionUpdate:'tool_call',toolCallId:'w1',name:'web_fetch',status:'pending'}}});
    if(mode==='permission')return send({id:'perm-1',method:'session/request_permission',params:{sessionId:sid,toolCall:{toolCallId:'t1'},options:[]}});
    if(mode==='steps'){fs.appendFileSync(args[args.indexOf('--log-file')+1],'step limit reached outcome_kind=step_limit\\n');return send({id:m.id,result:{stopReason:'refused'}})}
    send({method:'session/update',params:{sessionId:sid,update:{sessionUpdate:'tool_call',toolCallId:'t0',name:'read_file',status:'pending'}}});
    send({method:'session/update',params:{sessionId:sid,update:{sessionUpdate:'agent_message_chunk',content:{type:'text',text:'PROOF fixture\\nACCEPTANCE: met'}}}});
    return send({id:m.id,result:{stopReason:'end_turn',usage:{inputTokens:1,outputTokens:1}}})}
  if(m.method==='session/cancel'&&prompt!==null)return send({id:prompt,result:{stopReason:'cancelled'}});
  if(m.id==='perm-1')return;
}
`
  writeFileSync(binary, source, { mode: 0o755 })
  const fx = makeFxAdapter({ transport: "acp", shell: "/bin/sh", binary, binarySha256: createHash("sha256").update(source).digest("hex"), home: scratch.path, provider: "fixture", connection: {}, allowedCommands: [], wallMs, ...(delegation ? { delegation, extraEnv: { FIXTURE_GATE: join(scratch.path, "release-root") } } : {}) })
  const request = { directory: repo.cwd, logDirectory: repo.directory, prompt: "fixture task", selection, access: { kind: "write" as const } }
  mkdirSync(repo.directory, { recursive: true })
  const policy: ExecutionPlan = { kind: "leaf", target: { executor: "fx", selection } }
  const resolve = (tier: string): ExecutionPlan => { if (tier === "mechanic") throw new Error("no mechanic route"); return policy }
  const bridge = makeHybridBridge(piAdapter(unusedApi()), undefined, undefined, resolve, fx)
  const scope = { base_revision: repo.base, writable_paths: ["README"], acceptance_proof: "fixture proof", attempt_limit: 2, stop_on: "scope expansion" }
  return { scratch, repo, fx, request, bridge, scope }
}
async function acpSettled(bridge: ReturnType<typeof makeHybridBridge>, cwd: string, id: string) {
  const deadline = Date.now() + 15000
  while (Date.now() < deadline) {
    const status = await bridge.status(cwd, id)
    if (status.state !== "running") return status
    await new Promise<void>(resolve => setTimeout(resolve, 25))
  }
  throw new Error("FX ACP worker did not settle")
}
function acpRun(f: ReturnType<typeof acpFixture>, id: string): CommandRun {
  const session = decodeSession(JSON.parse(readFileSync(join(f.repo.directory, id + ".json"), "utf8")), f.repo.cwd, id)
  if (session.execution.kind !== "process") throw new Error("missing process")
  return session.execution.run
}

test("an ACP worker publishes its exact native session at admission and completes with the streamed final text", async t => {
  const f = acpFixture(t, "success")
  const admitted = await f.bridge.start(f.repo.cwd, "fixture", "worker", f.scope, "task")
  const done = await acpSettled(f.bridge, f.repo.cwd, admitted.session_id)
  assert.equal(done.state, "succeeded")
  assert.equal(done.acceptance_claim, "met")
  const run = acpRun(f, admitted.session_id)
  assert.equal(JSON.parse(readFileSync(run.output + ".native.json", "utf8")).session_id, "acp-native")
  assert.equal(JSON.parse(readFileSync(run.output, "utf8")).termination, "verified")
  const job = JSON.parse(readFileSync(run.output + ".job.json", "utf8"))
  assert.ok(!job.args.includes("--provider"), "the provider is selected through private settings, never the failing CLI override")
})

test("an ACP worker whose effective pins differ from admission stops before prompting and cannot be resumed as success", async t => {
  const f = acpFixture(t, "wrong-pin")
  const admitted = await f.bridge.start(f.repo.cwd, "fixture", "worker", f.scope, "task")
  const done = await acpSettled(f.bridge, f.repo.cwd, admitted.session_id)
  assert.equal(done.state, "failed")
  assert.match(String(done.error), /differed from the admitted pins/)
})

test("an ACP permission request is denied and surfaces as a blocked failure", async t => {
  const f = acpFixture(t, "permission")
  const admitted = await f.bridge.start(f.repo.cwd, "fixture", "worker", f.scope, "task")
  const done = await acpSettled(f.bridge, f.repo.cwd, admitted.session_id)
  assert.equal(done.state, "failed")
  assert.match(String(done.error), /interactive permission/)
  assert.equal(JSON.parse(readFileSync(acpRun(f, admitted.session_id).output, "utf8")).permission_requests, 1)
})

test("ACP step exhaustion reports turn_limit and continues without consuming an attempt", async t => {
  const f = acpFixture(t, "steps")
  const admitted = await f.bridge.start(f.repo.cwd, "fixture", "worker", f.scope, "task")
  const done = await acpSettled(f.bridge, f.repo.cwd, admitted.session_id)
  assert.equal(done.state, "turn_limit")
  assert.equal(done.run_step_limit, 20)
  assert.equal((await f.bridge.resume(f.repo.cwd, admitted.session_id, "continue")).status, "admitted")
  const session = decodeSession(JSON.parse(readFileSync(join(f.repo.directory, admitted.session_id + ".json"), "utf8")), f.repo.cwd, admitted.session_id)
  assert.equal(session.attempts, 1)
  assert.equal(session.continuations, 1)
})

test("a cancelled ACP run resumes the exact native session through session/resume", async t => {
  const f = acpFixture(t, "hold-once")
  const admitted = await f.bridge.start(f.repo.cwd, "fixture", "worker", f.scope, "task")
  await ready(acpRun(f, admitted.session_id).output + ".native.json")
  assert.equal((await f.bridge.cancel(f.repo.cwd, admitted.session_id)).interrupted, true)
  assert.equal((await acpSettled(f.bridge, f.repo.cwd, admitted.session_id)).state, "cancelled")
  assert.equal((await f.bridge.resume(f.repo.cwd, admitted.session_id, "continue")).status, "admitted")
  assert.equal((await acpSettled(f.bridge, f.repo.cwd, admitted.session_id)).state, "succeeded")
  const job = JSON.parse(readFileSync(acpRun(f, admitted.session_id).output + ".job.json", "utf8"))
  assert.equal(job.resume, "acp-native")
})

test("an ACP receipt without verified process-tree termination stays unknown and blocks resumption", async t => {
  const f = acpFixture(t, "success")
  const admitted = await f.bridge.start(f.repo.cwd, "fixture", "worker", f.scope, "task")
  await acpSettled(f.bridge, f.repo.cwd, admitted.session_id)
  const run = acpRun(f, admitted.session_id)
  writeFileSync(run.output, JSON.stringify({ ...JSON.parse(readFileSync(run.output, "utf8")), termination: "unverified" }))
  assert.equal(fxResult(run, selection).state, "unknown_or_interrupted")
  await assert.rejects(() => f.bridge.resume(f.repo.cwd, admitted.session_id, "continue"), /not known complete/)
})

test("a changed saved FX configuration refuses resumption before any attempt or transition is recorded", async t => {
  const f = acpFixture(t, "success")
  const admitted = await f.bridge.start(f.repo.cwd, "fixture", "worker", f.scope, "task")
  await acpSettled(f.bridge, f.repo.cwd, admitted.session_id)
  const job = JSON.parse(readFileSync(acpRun(f, admitted.session_id).output + ".job.json", "utf8"))
  const settings = join(job.fxHome, "settings.json")
  writeFileSync(settings, readFileSync(settings, "utf8").replace('"max_agent_steps":20', '"max_agent_steps":21'))
  const path = join(f.repo.directory, admitted.session_id + ".json"), before = readFileSync(path, "utf8")
  await assert.rejects(() => f.bridge.resume(f.repo.cwd, admitted.session_id, "continue"), /configuration changed/)
  assert.equal(readFileSync(path, "utf8"), before)
})

test("an ACP worker that calls the ungated FX web_fetch built-in is stopped and reported as a detected policy violation", async t => {
  const f = acpFixture(t, "webfetch")
  const admitted = await f.bridge.start(f.repo.cwd, "fixture", "worker", f.scope, "task")
  const done = await acpSettled(f.bridge, f.repo.cwd, admitted.session_id)
  assert.equal(done.state, "failed")
  assert.match(String(done.error), /ungated built-in tool web_fetch.*detection, not prevention/)
  const job = JSON.parse(readFileSync(acpRun(f, admitted.session_id).output + ".job.json", "utf8"))
  assert.deepEqual(JSON.parse(readFileSync(join(job.fxHome, "settings.json"), "utf8")).tool_placement, { web_fetch: "toolbox", web_search: "toolbox" })
})

test("a CLI FX result that used an ungated web built-in is not accepted", async t => {
  const f = fixture(t, "webfetch"), run = f.fx.start(f.request)
  const result = await ended(run)
  assert.equal(result.state, "failed")
  assert.match(JSON.stringify(result.result), /ungated built-in tool web_fetch/)
})

function childController(configPath: string, jobPath: string) {
  const server = spawn(process.execPath, [join(import.meta.dirname, "../src/fx-children-mcp.ts"), configPath, jobPath], { stdio: ["pipe", "pipe", "inherit"] })
  let buffer = "", id = 0
  const pending = new Map<number, (value: Record<string, unknown>) => void>()
  server.stdout.setEncoding("utf8")
  server.stdout.on("data", (chunk: string) => {
    buffer += chunk
    let index: number
    while ((index = buffer.indexOf("\n")) >= 0) {
      const message = JSON.parse(buffer.slice(0, index)) as Record<string, unknown>
      buffer = buffer.slice(index + 1)
      pending.get(message.id as number)?.(message); pending.delete(message.id as number)
    }
  })
  const rpc = (method: string, params: unknown) => new Promise<Record<string, unknown>>(resolve => { const key = ++id; pending.set(key, resolve); server.stdin.write(JSON.stringify({ jsonrpc: "2.0", id: key, method, params }) + "\n") })
  return {
    async tool(name: string, args: Record<string, unknown>): Promise<{ error: boolean; value: any }> {
      const result = (await rpc("tools/call", { name, arguments: args })).result as { isError?: boolean; content: Array<{ text: string }> }
      const text = result.content[0]!.text
      return result.isError ? { error: true, value: text } : { error: false, value: JSON.parse(text) }
    },
    rpc, close: () => { server.stdin.end(); server.kill() },
  }
}

test("controlled FX children obey the admission snapshot, replay one effect and hold the root lease until cancelled", async t => {
  const f = acpFixture(t, "child-hold", 20000, { maxChildren: 3, maxConcurrent: 2 })
  const admitted = await f.bridge.start(f.repo.cwd, "fixture", "worker", f.scope, "task")
  const run = acpRun(f, admitted.session_id)
  await ready(run.output + ".native.json")
  const job = JSON.parse(readFileSync(run.output + ".job.json", "utf8"))
  assert.deepEqual(job.mcp_servers.map((server: { name: string }) => server.name), ["children"])
  const settings = JSON.parse(readFileSync(join(job.fxHome, "settings.json"), "utf8"))
  assert.equal(settings.permission.mcp_children_spawn, "allow")
  const config = JSON.parse(readFileSync(join(job.fxHome, "children.json"), "utf8"))
  assert.deepEqual(Object.keys(config.selections).sort(), ["scout", "worker"])
  const controller = childController(join(job.fxHome, "children.json"), run.output + ".job.json")
  t.after(() => { cancelFxChildren(run); controller.close() })
  const listed = (await controller.rpc("tools/list", {})).result as { tools: Array<{ name: string }> }
  assert.deepEqual(listed.tools.map(tool => tool.name), ["spawn", "status", "wait", "cancel", "steer", "resume"])
  assert.match((await controller.tool("spawn", { tier: "worker", task: "x", intent_id: "a", model: "other" })).value, /cannot set model/)
  assert.match((await controller.tool("spawn", { tier: "worker", task: "x", intent_id: "a", cwd: "/" })).value, /cannot set cwd/)
  assert.match((await controller.tool("spawn", { tier: "mechanic", task: "x", intent_id: "a" })).value, /cannot delegate to mechanic/)
  assert.match((await controller.tool("spawn", { tier: "expert", task: "x", intent_id: "a" })).value, /cannot delegate to expert/)
  const scout = await controller.tool("spawn", { tier: "scout", task: "inspect", intent_id: "scout-1" })
  assert.equal(scout.error, false)
  const replay = await controller.tool("spawn", { tier: "scout", task: "inspect", intent_id: "scout-1" })
  assert.equal(replay.value.child_id, scout.value.child_id); assert.equal(replay.value.replayed, true)
  const worker = await controller.tool("spawn", { tier: "worker", task: "edit", intent_id: "worker-1" })
  assert.equal(worker.error, false)
  assert.match((await controller.tool("spawn", { tier: "worker", task: "edit", intent_id: "worker-2" })).value, /concurrent child limit|another writing child/)
  assert.match((await controller.tool("resume", { child_id: worker.value.child_id, feedback: "more" })).value, /not in a resumable terminal state \(running\)/)
  const workerRun = (JSON.parse(readFileSync(join(job.fxHome, "children-ledger.json"), "utf8")).children as Array<{ child_id: string; run: CommandRun }>).find(child => child.child_id === worker.value.child_id)!.run
  await ready(workerRun.output + ".native.json")
  const steered = await controller.tool("steer", { child_id: worker.value.child_id, note: "same scope: also handle strings" })
  assert.equal(steered.error, false, String(steered.value)); assert.equal(steered.value.steered, true); assert.equal(steered.value.state, "running"); assert.equal(steered.value.resumes, 1)
  const ledger = JSON.parse(readFileSync(join(job.fxHome, "children-ledger.json"), "utf8"))
  assert.equal(ledger.children.length, 2)
  const steeredJob = JSON.parse(readFileSync(ledger.children[1].run.output + ".job.json", "utf8"))
  assert.equal(steeredJob.resume, "acp-native"); assert.match(steeredJob.prompt, /SAME-SCOPE FOLLOW-UP: same scope: also handle strings/)
  writeFileSync(join(f.scratch.path, "release-root"), "")
  const holding = await acpSettled(f.bridge, f.repo.cwd, admitted.session_id)
  assert.equal(holding.state, "succeeded")
  assert.equal(holding.children_active.length, 2)
  await assert.rejects(() => f.bridge.start(f.repo.cwd, "duplicate", "worker", f.scope, "task"), /active worker/)
  assert.equal((await f.bridge.cancel(f.repo.cwd, admitted.session_id)).interrupted, true)
  for (const child of [scout.value.child_id, worker.value.child_id])
    assert.equal((await controller.tool("wait", { child_id: child, timeout_s: 15 })).value.state, "cancelled")
  assert.deepEqual((await f.bridge.status(f.repo.cwd, admitted.session_id)).children_active, [])
  const next = await f.bridge.start(f.repo.cwd, "after children", "worker", f.scope, "task")
  assert.equal((await acpSettled(f.bridge, f.repo.cwd, next.session_id)).state, "succeeded")
})
