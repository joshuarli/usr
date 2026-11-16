import test, { after, before } from "node:test"
import assert from "node:assert/strict"
import { optionalPiAdapter } from "../src/optional-pi.ts"
import { watchSession } from "../src/watch.ts"
import {
  Scratch, collect, commandLane, commandResultLine, migrate, piSession, piSuccess, realDeps, runFor, sessionId,
  toolQueued, writeLog, writePiChild, writeSession, type Repo,
} from "./worker-fixtures.ts"

const scratch = new Scratch()
let repo: Repo, alive: number, gone: number
before(async () => {
  repo = scratch.repo()
  alive = scratch.alive()
  gone = await scratch.gone()
})
after(() => scratch.close())

async function watch(id: string, idleMinutes = 10, stateOnly = false, deps = realDeps()) {
  const out = collect()
  const status = await watchSession(repo.root, id, { idleMinutes, stateOnly, pollMs: 5 }, deps, out.write)
  return { status, text: out.text() }
}
async function expectExit(wanted: number, id: string, needle: string, idleMinutes = 10) {
  const { status, text } = await watch(id, idleMinutes)
  assert.equal(status, wanted, text)
  assert.ok(text.includes(needle), text)
}
async function expectState(id: string, wanted: string) {
  const { status, text } = await watch(id, 10, true)
  assert.equal(status, 0)
  assert.equal(text, wanted + "\n")
}

const queued = toolQueued("Download kernel")

test("a final result record ends the wait", async () => {
  const id = commandLane(repo, 1, gone, [queued, commandResultLine("success", { finalText: "report written" })])
  await expectExit(0, id, "finished: succeeded\nreport written")
})

test("a session saved in the current format ends the wait the same way", async () => {
  const id = migrate(repo, commandLane(repo, 45, gone, [queued, commandResultLine("success", { finalText: "report written" })]))
  await expectExit(0, id, "finished: succeeded\nreport written")
  await expectState(migrate(repo, commandLane(repo, 46, alive, [queued])), "running")
  await expectState(migrate(repo, codexLane(47, gone)), "succeeded")
})

test("an executor gone without a result is reported", async () => {
  const id = commandLane(repo, 2, gone, [queued])
  await expectExit(3, id, "exited without terminal result (pid " + gone + "); last event: shell_command: Download kernel")
})

test("a quiet log reports the last queued tool", async () => {
  const id = commandLane(repo, 3, alive, [queued])
  await expectExit(2, id, "stalled: no executor output for 0 min; last event: shell_command: Download kernel", 0)
})

test("a missing backend is refused", async () => {
  const id = writeSession(repo, 4, { backend: undefined })
  await expectExit(4, id, "Invalid persisted worker lifecycle")
})

test("--state names a finished run without blocking", async () => {
  await expectState(commandLane(repo, 5, gone, [commandResultLine("success", { finalText: "done" })]), "succeeded")
})

test("--state names a gone executor", async () => {
  await expectState(commandLane(repo, 6, gone, [queued]), "interrupted")
})

test("--state names a live executor", async () => {
  await expectState(commandLane(repo, 7, alive, [queued]), "running")
})

test("--state names a backend it cannot follow", async () => {
  await expectState(writeSession(repo, 8, { backend: undefined }), "unknown")
})

test("--state of a session that does not exist is unknown", async () => {
  await expectState(sessionId(99), "unknown")
})

test("a live executor keeps the watch polling until its receipt appears", async () => {
  const id = commandLane(repo, 9, alive, [queued])
  const pending = watch(id)
  await new Promise((resolve) => setTimeout(resolve, 50))
  const early = await Promise.race([pending, Promise.resolve("blocked")])
  assert.equal(early, "blocked")
  const second = await scratch.gone()
  const run = runFor(repo, "lane-9", second)
  writeLog(run.output, [commandResultLine("max_turns", { finalText: "ran out" })])
  writeSession(repo, 9, { command_run: run })
  const done = await pending
  assert.equal(done.status, 0)
  assert.ok(done.text.startsWith("finished: turn_limit\nran out"), done.text)
})

test("watch backs off unchanged output and resets on activity", async () => {
  const id = commandLane(repo, 90, alive, [queued]), delays: number[] = []
  const run = runFor(repo, "lane-90", alive)
  const clock = { now: () => Date.now(), sleep: async (ms: number) => {
    delays.push(ms)
    if (delays.length === 3) writeLog(run.output, [toolQueued("new activity")])
    if (delays.length === 5) writeSession(repo, 90, { command_run: runFor(repo, "lane-90", gone) })
  } }
  const out = collect()
  await watchSession(repo.root, id, { idleMinutes: 45, stateOnly: false, clock }, realDeps(), out.write)
  assert.deepEqual(delays, [15000, 30000, 60000, 15000, 30000])
})

test("Pi SDK terminal result is observed", async () => {
  writePiChild(repo, gone, piSuccess("SDK proof\nACCEPTANCE: met"))
  const id = piSession(repo, 10)
  const { status, text } = await watch(id, 10, false, realDeps(optionalPiAdapter()))
  assert.equal(status, 0, text)
  assert.ok(text.startsWith("finished: succeeded\nSDK proof"), text)
})

test("Pi SDK receipt does not precede host termination", async () => {
  writePiChild(repo, alive, piSuccess())
  const id = piSession(repo, 11)
  const { text } = await watch(id, 10, true, realDeps(optionalPiAdapter()))
  assert.equal(text, "running\n")
})

const codexLines = [
  { type: "thread.started", thread_id: "thread" },
  { type: "item.completed", item: { type: "agent_message", text: "Codex proof" } },
  { type: "turn.completed" },
]
function codexLane(n: number, pid: number) {
  const run = runFor(repo, "codex-" + n, pid)
  writeLog(run.output, codexLines)
  return writeSession(repo, n, { backend: "codex", command_run: run })
}

test("Codex receipt does not precede process termination", async () => {
  await expectState(codexLane(20, alive), "running")
})

test("Codex completed turn is observed after termination", async () => {
  await expectState(codexLane(21, gone), "succeeded")
})

test("Codex proof is displayed", async () => {
  await expectExit(0, codexLane(22, gone), "Codex proof")
})
