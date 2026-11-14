import test, { after } from "node:test"
import assert from "node:assert/strict"
import { existsSync, readFileSync } from "node:fs"
import { join } from "node:path"
import { makeWorkerBridge } from "../src/bridge.ts"
import { processStartTime } from "../src/command.ts"
import { makeHybridBridge } from "../src/hybrid.ts"
import { inspectStored, type Snapshot } from "../src/inspect.ts"
import { piPort } from "../src/pi-port.ts"
import { activeWorktreeOwner, claimWorktree, ensureWorktree } from "../src/worktree-lease.ts"
import {
  PI_MODEL, PI_ID, Scratch, commandLane, commandResultLine, migrate, piSession, piSuccess, realDeps, runFor, toolQueued,
  treeOf, unusedApi, writeLog, writePiChild, writeSession, type Repo,
} from "./worker-fixtures.ts"

const scratch = new Scratch()
after(() => scratch.close())

const receipt = commandResultLine("success", { finalText: "proof\nACCEPTANCE: met" })

async function inspectReadOnly(repo: Repo, id: string): Promise<Snapshot> {
  ensureWorktree(repo.directory, repo.cwd, id)
  const before = treeOf(repo.directory)
  const signals: unknown[] = []
  const kill = process.kill
  process.kill = ((pid: number, signal?: string | number) => {
    signals.push(signal ?? "SIGTERM")
    return kill.call(process, pid, signal)
  }) as typeof process.kill
  const snapshots: Snapshot[] = []
  try {
    for (let attempt = 0; attempt < 3; attempt++) snapshots.push(await inspectStored(repo.directory, id, realDeps(piPort())))
  } finally {
    process.kill = kill
  }
  assert.deepEqual(treeOf(repo.directory), before, "the state directory is byte-identical")
  assert.equal(activeWorktreeOwner(repo.directory, repo.cwd), id, "the lease is unchanged")
  assert.deepEqual(signals.filter((signal) => signal !== 0), [], "no process is signalled")
  assert.deepEqual(snapshots.map((snapshot) => snapshot.execution_state), Array(3).fill(snapshots[0]!.execution_state))
  return snapshots[0]!
}

test("a live Command Code process with a terminal receipt is running", async () => {
  const repo = scratch.repo(), pid = scratch.alive()
  const run = runFor(repo, "lane-1", pid, { proc_start: processStartTime(pid) })
  writeLog(run.output, [toolQueued("Build"), receipt])
  const id = writeSession(repo, 1, { command_run: run })
  const snapshot = await inspectReadOnly(repo, id)
  assert.equal(snapshot.execution_state, "running")
  assert.equal(snapshot.last_assistant_text, null)
  assert.equal(snapshot.last_event, "shell_command: Build")
  assert.equal(snapshot.pid, pid)
})

test("a live Pi host with a terminal receipt is running", async () => {
  const repo = scratch.repo(), pid = scratch.alive()
  writePiChild(repo, pid, piSuccess())
  const id = piSession(repo, 2)
  const snapshot = await inspectReadOnly(repo, id)
  assert.equal(snapshot.execution_state, "running")
  assert.equal(snapshot.pid, pid)
  assert.equal(snapshot.last_event, "pi host log")
})

test("a reused PID with a different start identity is interrupted", async () => {
  const repo = scratch.repo(), pid = scratch.alive()
  const run = { pid, output: join(repo.directory, "reused.ndjson"), errors: join(repo.directory, "reused.stderr"),
    started_at: "2026-11-09T00:00:00.000Z", proc_start: "Thu Jan  1 00:00:00 1970" }
  writeLog(run.output, [toolQueued("Build")])
  const id = writeSession(repo, 3, { command_run: run })
  const snapshot = await inspectReadOnly(repo, id)
  assert.equal(snapshot.execution_state, "interrupted")
  assert.match(String(snapshot.error), /PID identity changed/)
})

test("a missing receipt after the executor exits is interrupted", async () => {
  const repo = scratch.repo()
  const id = commandLane(repo, 4, await scratch.gone(), [toolQueued("Build")])
  assert.equal((await inspectReadOnly(repo, id)).execution_state, "interrupted")
})

test("an interrupted Pi admission is blocked, never running or succeeded", async () => {
  for (const backend of ["pi-transition", "pi-admitting"]) {
    const repo = scratch.repo()
    const id = writeSession(repo, 5, { backend, primary_model: PI_MODEL, pi_candidates: [] })
    const snapshot = await inspectReadOnly(repo, id)
    assert.equal(snapshot.execution_state, "blocked_admission", backend)
    assert.match(String(snapshot.error), /Pi admission interrupted or uncertain/)
  }
})

test("a dead Pi host without a result is not succeeded", async () => {
  const repo = scratch.repo()
  writePiChild(repo, await scratch.gone())
  const id = piSession(repo, 6)
  const snapshot = await inspectReadOnly(repo, id)
  assert.equal(snapshot.execution_state, "unknown_or_interrupted")
  assert.notEqual(snapshot.execution_state, "succeeded")
  assert.equal(snapshot.acceptance_claim, "missing")
})

test("a dead Pi host reports its receipt once it has exited", async () => {
  const repo = scratch.repo(), pid = scratch.alive()
  writePiChild(repo, pid, piSuccess())
  const id = piSession(repo, 7)
  assert.equal((await inspectReadOnly(repo, id)).execution_state, "running")
  await scratch.stop(pid)
  const snapshot = await inspectReadOnly(repo, id)
  assert.equal(snapshot.execution_state, "succeeded")
  assert.equal(snapshot.acceptance_claim, "met")
})

test("a Pi host that is alive is running whatever its receipt says, and its receipt counts after exit", async () => {
  const repo = scratch.repo(), pid = scratch.alive()
  const bridge = makeWorkerBridge(piPort(), PI_MODEL)
  writePiChild(repo, pid, piSuccess())
  assert.equal((await bridge.status(repo.cwd, PI_ID)).state, "running")
  writePiChild(repo, pid, { state: "failed", text: null, error: "boom", usage: null, sessionFile: null, runId: null })
  assert.equal((await bridge.status(repo.cwd, PI_ID)).state, "running")
  await scratch.stop(pid)
  const failed = await bridge.status(repo.cwd, PI_ID)
  assert.equal(failed.state, "failed")
  assert.equal(failed.error, "boom")
  writePiChild(repo, pid, piSuccess())
  assert.equal((await bridge.status(repo.cwd, PI_ID)).state, "succeeded")
  writePiChild(repo, pid)
  assert.equal((await bridge.status(repo.cwd, PI_ID)).state, "unknown_or_interrupted")
})

test("inspecting a repository without a state directory creates nothing", async () => {
  const repo = scratch.repo()
  const missing = join(repo.root, ".work", "no-such-state")
  const snapshot = await inspectStored(missing, "usrw_01234567-89ab-cdef-0123-456789abcdef", realDeps())
  assert.equal(snapshot.execution_state, "unknown")
  assert.match(String(snapshot.reason), /no session record at/)
  assert.equal(existsSync(missing), false)
})

test("worker_status advances and releases a terminal lease, which inspection alone never does", async () => {
  const repo = scratch.repo()
  const id = commandLane(repo, 8, await scratch.gone(), [toolQueued("Build")])
  claimWorktree(repo.directory, repo.cwd, id)
  const snapshot = await inspectStored(repo.directory, id, realDeps())
  assert.equal(snapshot.execution_state, "interrupted")
  assert.equal(activeWorktreeOwner(repo.directory, repo.cwd), id)
  const response = await makeHybridBridge(unusedApi()).status(repo.cwd, id)
  assert.equal(response.state, "interrupted")
  assert.equal(activeWorktreeOwner(repo.directory, repo.cwd), null)
})

test("a record saved in the current format inspects exactly like the v1 record it came from", async () => {
  const strip = ({ observed_at: _at, id: _id, last_activity: _activity, ...rest }: Snapshot) => rest
  const repo = scratch.repo(), pid = scratch.alive()
  const run = runFor(repo, "lane-v2", pid, { proc_start: processStartTime(pid) })
  writeLog(run.output, [toolQueued("Build"), receipt])
  writePiChild(repo, pid, piSuccess())
  const lanes: Array<[string, Record<string, unknown>]> = [
    ["command", { command_run: run }],
    ["codex", { backend: "codex", command_run: run }],
    ["pi", { backend: "pi", pi_id: PI_ID, primary_model: PI_MODEL, pi_candidates: [] }],
    ["pi-transition", { backend: "pi-transition", primary_model: PI_MODEL, pi_candidates: [] }],
    ["command-transition", { backend: "command-transition" }],
  ]
  let n = 40
  for (const [name, fields] of lanes) {
    const before = writeSession(repo, n++, { title: "Same lane", ...fields })
    const after = migrate(repo, writeSession(repo, n++, { title: "Same lane", ...fields }))
    const path = join(repo.directory, after + ".json")
    assert.equal(JSON.parse(readFileSync(path, "utf8")).schema_version, 2, name)
    const old = await inspectStored(repo.directory, before, realDeps(piPort()))
    const current = await inspectStored(repo.directory, after, realDeps(piPort()))
    assert.deepEqual(strip(current), strip(old), name)
  }
})
