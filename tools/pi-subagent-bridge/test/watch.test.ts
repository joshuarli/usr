import test, { after, before } from "node:test"
import assert from "node:assert/strict"
import { piPort } from "../src/pi-port.ts"
import { watchSession } from "../src/watch.ts"
import {
  Scratch, collect, commandLane, commandResultLine, piSession, piSuccess, realDeps, runFor, sessionId,
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

test("Pi SDK terminal result is observed", async () => {
  writePiChild(repo, gone, piSuccess("SDK proof\nACCEPTANCE: met"))
  const id = piSession(repo, 10)
  const { status, text } = await watch(id, 10, false, realDeps(piPort()))
  assert.equal(status, 0, text)
  assert.ok(text.startsWith("finished: succeeded\nSDK proof"), text)
})

test("Pi SDK receipt does not precede host termination", async () => {
  writePiChild(repo, alive, piSuccess())
  const id = piSession(repo, 11)
  const { text } = await watch(id, 10, true, realDeps(piPort()))
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
  return writeSession(repo, n, { backend: "codex", command_run: run, codex_model: "gpt-6.1-terra", codex_effort: "medium",
    command_model: undefined, command_effort: undefined })
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

const EXPERT = { tier: "expert", backend: "antigravity", command_model: undefined, command_effort: undefined }
const PIN = { model: "fixture-model", effort: "xhigh" }
const HYDROGEN = "gemini-4-hydrogen-xhigh"
function agyLane(n: number, pid: number, lines: Array<Record<string, unknown>>, fields: Record<string, unknown> = {}) {
  const run = runFor(repo, "agy-" + n, pid)
  writeLog(run.output, lines)
  return writeSession(repo, n, { ...EXPERT, antigravity_pin: PIN, command_run: run, ...fields })
}
const init = (model: string) => ({ event: "init", conversation_id: "conversation", init: { model } })
const agyResult = (status: string, extra: Record<string, unknown> = {}) => ({ event: "result", result: { status, ...extra } })

test("Antigravity receipt does not precede process termination", async () => {
  await expectState(agyLane(30, alive, [init("fixture-model"), agyResult("SUCCESS", { response: "Antigravity proof" })]), "running")
})

test("Antigravity success uses the admitted model pin", async () => {
  await expectState(agyLane(31, gone, [init("fixture-model"), agyResult("SUCCESS", { response: "Antigravity proof" })]), "succeeded")
})

test("Antigravity proof is displayed", async () => {
  await expectExit(0, agyLane(32, gone, [init("fixture-model"), agyResult("SUCCESS", { response: "Antigravity proof" })]), "Antigravity proof")
})

test("Antigravity cannot succeed with a mismatched model", async () => {
  await expectState(agyLane(33, gone, [init("wrong-model"), agyResult("SUCCESS")]), "failed")
})

test("Antigravity cannot succeed without an init model", async () => {
  await expectState(agyLane(34, gone, [agyResult("SUCCESS")]), "failed")
})

test("Antigravity provider failure remains failed", async () => {
  await expectState(agyLane(35, gone, [init("fixture-model"), agyResult("ERROR", { error: "quota exhausted" })]), "failed")
})

test("Antigravity error is displayed", async () => {
  await expectExit(0, agyLane(36, gone, [init("fixture-model"), agyResult("ERROR", { error: "quota exhausted" })]), "quota exhausted")
})

test("Antigravity without a terminal receipt is interrupted", async () => {
  await expectState(agyLane(37, gone, [init("fixture-model")]), "interrupted")
})

test("Antigravity without an admitted pin is unknown", async () => {
  const run = runFor(repo, "agy-38", gone)
  writeLog(run.output, [init("fixture-model"), agyResult("SUCCESS")])
  await expectState(writeSession(repo, 38, { ...EXPERT, command_run: run }), "unknown")
})

test("Antigravity interrupted admission stays unknown", async () => {
  const run = runFor(repo, "agy-39", gone)
  const unpinned = writeSession(repo, 39, { ...EXPERT, backend: "antigravity-transition", command_run: run })
  await expectState(unpinned, "unknown")
  const pinned = writeSession(repo, 40, { ...EXPERT, backend: "antigravity-transition", antigravity_pin: PIN, command_run: run })
  await expectState(pinned, "blocked_transition")
  await expectExit(4, pinned, "antigravity transition interrupted")
})

const legacy = { ...EXPERT, backend: "hydrogen", schema_version: undefined }
function legacyLane(n: number, lines: Array<Record<string, unknown>>, fields: Record<string, unknown> = {}) {
  const run = runFor(repo, "legacy-" + n, gone)
  writeLog(run.output, lines)
  return writeSession(repo, n, { ...legacy, command_run: run, ...fields })
}

test("legacy Hydrogen records retain their historical pin", async () => {
  await expectState(legacyLane(41, [init(HYDROGEN), agyResult("SUCCESS", { response: "Legacy proof" })]), "succeeded")
})

test("legacy Hydrogen cannot adopt a newly attached pin", async () => {
  const id = legacyLane(42, [init(HYDROGEN), agyResult("SUCCESS")], { antigravity_pin: { model: "different-model", effort: "xhigh" } })
  await expectState(id, "unknown")
})

test("a future session schema is not interpreted as successful", async () => {
  const run = runFor(repo, "future", gone)
  writeLog(run.output, [init(HYDROGEN), agyResult("SUCCESS")])
  const id = writeSession(repo, 43, { ...EXPERT, schema_version: 2, antigravity_pin: { model: HYDROGEN, effort: "xhigh" }, command_run: run })
  await expectState(id, "unknown")
})

test("legacy Hydrogen does not adopt a different model", async () => {
  await expectState(legacyLane(44, [init("wrong-model"), agyResult("SUCCESS")]), "failed")
})
