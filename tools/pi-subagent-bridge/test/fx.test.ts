import test, { type TestContext } from "node:test"
import assert from "node:assert/strict"
import { createHash } from "node:crypto"
import { readFileSync, writeFileSync, mkdirSync, existsSync, watch } from "node:fs"
import { join, dirname } from "node:path"
import { Scratch, git, unusedApi } from "./worker-fixtures.ts"
import { makeFxAdapter, fxResult, type FxSelection } from "../src/fx.ts"
import { makeHybridBridge } from "../src/hybrid.ts"
import { piAdapter } from "../src/pi-adapter.ts"
import { decodeSession, encodeSession, type ExecutionPlan } from "../src/session.ts"
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
const mode=${JSON.stringify(behavior)};
if(mode==='oversized')process.stdout.write('x'.repeat(1100000));
else if(mode!=='hold')console.log(JSON.stringify({exit_code:0,model:'fixture-model',session_id:mode==='mismatch'?'foreign-session':id,final_output:'PROOF fixture\\nACCEPTANCE: met',usage:{input_tokens:1,output_tokens:1}}));
if(mode!=='success'&&mode!=='mismatch')setInterval(()=>{},1000);
`
  writeFileSync(binary, source, { mode: 0o755 })
  const fx = makeFxAdapter({ binary, binarySha256: createHash("sha256").update(source).digest("hex"), home: scratch.path, provider: "fixture", connection: {}, allowedCommands: [], wallMs })
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
    const f = fixture(t, behavior, 200), run = f.fx.start(f.request)
    const result = await ended(run)
    assert.equal(result.state, "failed")
    assert.match(readReceipt(run)!, /deadline|oversized/)
  })
}

test("a mismatched FX native session remains unknown and retains the shared worktree lease", async t => {
  const f = fixture(t, "mismatch"), policy: ExecutionPlan = { kind: "leaf", target: { executor: "fx", selection } }
  const bridge = makeHybridBridge(piAdapter(unusedApi()), undefined, undefined, undefined, () => policy, f.fx)
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
  assert.equal((await ended(run)).state, "interrupted")
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
  const bridge = makeHybridBridge(piAdapter(unusedApi()), undefined, undefined, undefined, () => policy, f.fx)
  const scope = { base_revision: f.repo.base, writable_paths: ["README"], acceptance_proof: "fixture proof", attempt_limit: 2, stop_on: "scope expansion" }
  const admitted = await bridge.start(f.repo.cwd, "fixture", "worker", scope, "task")
  const path = join(f.repo.directory, admitted.session_id + ".json")
  const session = decodeSession(JSON.parse(readFileSync(path, "utf8")), f.repo.cwd, admitted.session_id)
  if (session.execution.kind !== "process") throw new Error("missing process")
  assert.equal((await ended(session.execution.run)).state, "succeeded")
  await bridge.status(f.repo.cwd, admitted.session_id)
  const before = readFileSync(path, "utf8")
  const withoutFx = makeHybridBridge(piAdapter(unusedApi()), undefined, undefined, undefined, () => policy)
  await assert.rejects(() => withoutFx.resume(f.repo.cwd, admitted.session_id, "same scope"), /FX adapter unavailable/)
  assert.equal(readFileSync(path, "utf8"), before)
  await assert.rejects(() => withoutFx.cancel(f.repo.cwd, admitted.session_id), /FX adapter unavailable/)
  assert.equal(readFileSync(path, "utf8"), before)
})
