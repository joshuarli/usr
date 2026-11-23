import { piAdapter } from "../src/pi-adapter.ts"
import test, { after } from "node:test"
import assert from "node:assert/strict"
import { mkdirSync, mkdtempSync, readFileSync, realpathSync, rmSync, symlinkSync } from "node:fs"
import { tmpdir } from "node:os"
import { join } from "node:path"
import type { OpenCodePort } from "../src/bridge.ts"
import { codexSession } from "../src/codex.ts"
import type { LaunchRequest } from "../src/launch.ts"
import { makeHybridBridge } from "../src/hybrid.ts"
import { inspectStored } from "../src/inspect.ts"
import { Scratch, realDeps, runFor, writeLog, writeSession, type Repo } from "./worker-fixtures.ts"
import {
  ADMITTING_PARENT_ENV, activatePi, activateProcess, admittingParentFrom, backendOf, decodeSession, encodeSession, processRun, targetOf,
  transition, type Session,
} from "../src/session.ts"

const cwd = "/tmp/usr-session-fixture"
const id = "usrw_01234567-89ab-cdef-0123-456789abcdef"
const run = { pid: 12345, output: "/tmp/worker.ndjson", errors: "/tmp/worker.stderr", started_at: "2026-11-14T03:13:57Z", proc_start: "fixture-start" }
const scope = { base_revision: "a".repeat(40), writable_paths: ["README"], acceptance_proof: "Check the output", attempt_limit: 2, stop_on: "Scope expansion" }
const CODEX = { model: "gpt-6.1-terra", effort: "medium" } as const
const COMMAND = { model: "deepseek/deepseek-v4.1-flash", effort: "high" } as const
const DEVIN_WORKER = { providerID: "devin", id: "swe-2-flash", variant: "medium" } as const
const GO = { providerID: "opencode-go", id: "deepseek-v4.1-flash", variant: "high" } as const

function record(overrides: Record<string, unknown> = {}): Record<string, unknown> {
  return {
    schema_version: 1, id, cwd, title: "Review a bounded slice", task: "Read the source and return evidence",
    tier: "worker", scope, attempts: 0, backend: "codex", command_run: run,
    codex_model: CODEX.model, codex_effort: CODEX.effort,
    command_model: COMMAND.model, command_effort: COMMAND.effort, execution_order: "codex-first",
    ...overrides,
  }
}
function lower(overrides: Record<string, unknown> = {}): Record<string, unknown> {
  return record({
    tier: "worker", backend: "command-code", execution_order: "codex-first",
    codex_model: CODEX.model, codex_effort: CODEX.effort, command_model: COMMAND.model, command_effort: COMMAND.effort,
    pi_candidates: [DEVIN_WORKER, GO], ...overrides,
  })
}

function decode(value: Record<string, unknown>) { return decodeSession(value, cwd, id) }
function roundTrip(value: Record<string, unknown>) { return decodeSession(JSON.parse(JSON.stringify(encodeSession(decode(value)))), cwd, id) }

test("v1 lower-tier records convert to a typed fallback plan on every executor", () => {
  const cases = [
    { backend: "codex", executor: "codex", selection: CODEX },
    { backend: "command-code", executor: "command-code", selection: COMMAND },
  ]
  for (const { backend, executor, selection } of cases) for (const schema_version of [1, undefined]) {
    const parsed = roundTrip(lower({ backend, schema_version }))
    assert.deepEqual(parsed.plan, { kind: "fallback", codex: CODEX, command: COMMAND, pi: [DEVIN_WORKER, GO] })
    assert.deepEqual(parsed.execution, { kind: "process", executor, selection, run })
    assert.equal(backendOf(parsed), backend)
    assert.equal(encodeSession(parsed).schema_version, 2)
  }
  const transitional = roundTrip(lower({ backend: "command-transition", command_run: undefined }))
  assert.deepEqual(transitional.execution, { kind: "transition", to: { executor: "command-code", selection: COMMAND } })
  assert.equal(backendOf(transitional), "command-transition")
})

test("records admitted with the retired network scope flag still decode, and re-encode without it", () => {
  for (const schema_version of [1, 2, undefined]) {
    const legacy = schema_version === 2 ? JSON.parse(JSON.stringify({ ...encodeSession(decode(lower())), schema_version: 2 })) : lower({ schema_version })
    const parsed = decode({ ...legacy, scope: { ...scope, network: true } })
    assert.deepEqual(parsed.scope, scope)
    assert.equal("network" in (encodeSession(parsed).scope as object), false)
  }
})

test("a v1 Pi record keeps its selected destination first in the plan and its pending candidates after it", () => {
  const parsed = roundTrip(lower({ backend: "pi", command_run: undefined, pi_id: "ses_fixture", primary_model: DEVIN_WORKER, pi_candidates: [GO] }))
  assert.deepEqual(parsed.plan, { kind: "fallback", codex: CODEX, command: COMMAND, pi: [DEVIN_WORKER, GO] })
  assert.deepEqual(parsed.execution, { kind: "pi", selection: DEVIN_WORKER, session_id: "ses_fixture" })
  const drained = roundTrip(lower({ backend: "pi", command_run: undefined, pi_id: "ses_fixture", primary_model: GO, pi_candidates: [] }))
  assert.deepEqual(drained.plan.kind === "fallback" ? drained.plan.pi : null, [GO])
  for (const backend of ["pi-transition", "pi-admitting"]) {
    const interrupted = roundTrip(lower({ backend, command_run: undefined, primary_model: GO, pi_candidates: [] }))
    assert.deepEqual(interrupted.execution, { kind: "transition", to: { executor: "pi", selection: GO, ...(backend === "pi-admitting" ? { admitting: true } : {}) } })
    assert.equal(backendOf(interrupted), backend)
  }
})

test("v2 records round trip every execution shape unchanged", () => {
  const sessions: Session[] = [
    decode(record()),
    decode(lower({ backend: "codex" })),
    decode(lower({ backend: "pi", command_run: undefined, pi_id: "ses_fixture", primary_model: GO, pi_candidates: [] })),
    decode(lower({ backend: "pi-transition", command_run: run, primary_model: GO, pi_candidates: [] })),
    decode(lower({ backend: "command-transition", command_run: undefined })),
  ]
  for (const session of sessions) {
    const wire = JSON.parse(JSON.stringify(encodeSession(session)))
    assert.equal(wire.schema_version, 2)
    assert.deepEqual(decodeSession(wire, cwd, id), session)
  }
})

test("legacy records whose Pi fallback cannot be resolved still decode, keeping every lane they do have", () => {
  const cases: Array<[string, Record<string, unknown>, { kind: string }]> = [
    ["symbolic destinations", lower({ schema_version: undefined, pi_candidates: undefined, remaining_pi: ["muse", "go"] }), { kind: "fallback-unresolved-pi" }],
    ["no Pi information", lower({ pi_candidates: undefined }), { kind: "fallback-unresolved-pi" }],
    ["exhausted snapshot", lower({ pi_candidates: [] }), { kind: "fallback-unresolved-pi" }],
    ["a single recorded Pi pin", lower({ codex_model: undefined, codex_effort: undefined, pi_candidates: undefined, primary_model: GO, remaining_pi: [] }), { kind: "command-first" }],
    ["no Codex lane and symbolic destinations", lower({ codex_model: undefined, codex_effort: undefined, pi_candidates: undefined, remaining_pi: ["go"] }), { kind: "command-first-unresolved-pi" }],
    ["no execution order", lower({ execution_order: undefined, codex_model: undefined, codex_effort: undefined, pi_candidates: undefined }), { kind: "pi-first" }],
  ]
  for (const [name, input, plan] of cases) {
    const parsed = roundTrip(input)
    assert.equal(parsed.plan.kind, plan.kind, name)
    assert.deepEqual(parsed.execution, { kind: "process", executor: "command-code", selection: COMMAND, run }, name)
    assert.equal(backendOf(parsed), "command-code", name)
  }
  const onPi = roundTrip(lower({ schema_version: undefined, execution_order: "command-first", codex_model: undefined, codex_effort: undefined,
    backend: "pi", command_run: undefined, pi_id: "ses_fixture", primary_model: GO, pi_candidates: undefined, remaining_pi: [] }))
  assert.deepEqual(onPi.plan, { kind: "command-first", command: COMMAND, pi: [GO] })
  assert.throws(() => roundTrip(lower({ schema_version: undefined, tier: "expert", backend: "codex" })), /Unsupported persisted worker tier/)
})

test("incomplete or prohibited legacy records are refused for manual reconciliation", () => {
  const refused: Array<[Record<string, unknown>, RegExp]> = [
    [record({ command_run: undefined }), /Missing persisted worker process/],
    [lower({ command_model: undefined, command_effort: undefined }), /Missing admitted Command Code pin; manual reconciliation required/],
    [lower({ codex_effort: undefined }), /Incomplete persisted model pin; manual reconciliation required/],
    [lower({ backend: "pi", command_run: undefined, pi_id: "ses_fixture" }), /Missing admitted Pi pin; manual reconciliation required/],
    [lower({ backend: "pi", command_run: undefined, primary_model: GO }), /Missing persisted Pi session/],
    [lower({ backend: "pi", command_run: undefined, pi_id: "ses_fixture", primary_model: { providerID: "opencode-go", id: "deepseek-v4.1-flash" } }), /Missing admitted Pi effort; manual reconciliation required/],
    [lower({ pi_candidates: [{ providerID: "opencode-go", id: "deepseek-v4.1-flash" }] }), /Missing admitted Pi effort; manual reconciliation required/],
    [lower({ schema_version: undefined, execution_order: undefined, backend: "pi", pi_id: "ses_legacy", command_run: undefined, primary_model: undefined }), /Missing admitted Pi pin; manual reconciliation required/],
    [lower({ tier: "expert" }), /Unsupported persisted worker tier/],
    [record({ backend: "antigravity" }), /Invalid persisted worker lifecycle; manual reconciliation required/],
    [record({ backend: "hydrogen" }), /Invalid persisted worker lifecycle; manual reconciliation required/],
    [lower({ backend: "pi", command_run: undefined, pi_id: "ses_fixture", primary_model: GO, command_model: undefined, command_effort: undefined }), /Missing admitted Command Code pin; manual reconciliation required/],
    [lower({ pi_candidates: [{ ...GO, id: "gemini-4-argon-high" }] }), /Prohibited persisted model; manual reconciliation required/],
    [lower({ command_model: "google/gemini-4-carbon-high" }), /Prohibited persisted model; manual reconciliation required/],
    [lower({ codex_model: "openai/gpt-6.2-astra-xhigh" }), /Prohibited persisted model; manual reconciliation required/],
  ]
  for (const [malformed, message] of refused) assert.throws(() => decode(malformed), message)
})

test("unknown versions, removed tiers and malformed state fail at the boundary", () => {
  for (const malformed of [
    { schema_version: 5 }, { schema_version: "1" }, { schema_version: "2" }, { tier: "god" }, { backend: "carbon" },
    { id: "usrw_other" }, { cwd: "/tmp/another-worktree" }, { attempts: -1 }, { steers: 1.5 },
    { command_run: { ...run, pid: 0 } }, { command_run: { ...run, output: null } },
    { remaining_pi: ["other"] }, { execution_order: "other" }, { cancel_requested: "yes" },
  ]) assert.throws(() => decode(record(malformed)))
  assert.throws(() => decode(lower({ pi_candidates: [null] })))
  assert.throws(() => decode(lower({ remaining_pi: ["other"] })))
  assert.throws(() => decodeSession(null, cwd, id), /Invalid/)
})

test("a session recorded under a renamed checkout's old path decodes when that path resolves to the worktree", () => {
  const root = mkdtempSync(join(tmpdir(), "usr-session-rename-"))
  after(() => rmSync(root, { recursive: true, force: true }))
  const renamed = join(root, "tf")
  mkdirSync(renamed)
  symlinkSync("tf", join(root, "old"))
  const worktree = realpathSync(renamed)
  assert.equal(decodeSession(record({ cwd: join(root, "old") }), worktree, id).cwd, worktree)
  assert.throws(() => decodeSession(record({ cwd: join(root, "missing") }), worktree, id), /different worktree/)
  assert.throws(() => decodeSession(record({ tier: "god" }), cwd, id), /tier/)
})

test("an admitting parent identity round trips unchanged and stays absent on records that never declared one", () => {
  const parent = "claude:7f3c2a90-1b4d-4e8f-9a6b-0c1d2e3f4a5b"
  for (const value of [record(), lower(), JSON.parse(JSON.stringify(encodeSession(decode(lower()))))]) {
    const declared = roundTrip({ ...value, admitting_parent: parent })
    assert.equal(declared.admitting_parent, parent)
    assert.equal(encodeSession(declared).admitting_parent, parent)
    assert.equal(encodeSession(declared).schema_version, encodeSession(decode(value)).schema_version)
    const legacy = roundTrip(value)
    assert.equal(Object.hasOwn(legacy, "admitting_parent"), false)
    assert.equal(Object.hasOwn(JSON.parse(JSON.stringify(encodeSession(legacy))), "admitting_parent"), false)
  }
})

test("a malformed admitting parent identity is refused in the record and at admission", () => {
  for (const malformed of [null, "", " parent", "parent ", "two\nlines", "tab\there", "x".repeat(257), "unknown", 7, { id: "p" }]) {
    assert.throws(() => decode(record({ admitting_parent: malformed })), /Invalid persisted admitting parent/)
    if (typeof malformed === "string") assert.throws(() => admittingParentFrom({ [ADMITTING_PARENT_ENV]: malformed }), new RegExp(ADMITTING_PARENT_ENV))
  }
  assert.equal(admittingParentFrom({}), undefined)
  assert.equal(admittingParentFrom({ [ADMITTING_PARENT_ENV]: "codex:run-42" }), "codex:run-42")
  assert.equal(admittingParentFrom({ [ADMITTING_PARENT_ENV]: "x".repeat(256) }), "x".repeat(256))
})

function current(overrides: Record<string, unknown> = {}): Record<string, unknown> {
  return JSON.parse(JSON.stringify({ ...encodeSession(decode(lower())), ...overrides }))
}

test("v2 records are checked against their admitted plan", () => {
  const plan = { kind: "fallback", codex: CODEX, command: COMMAND, pi: [DEVIN_WORKER, GO] }
  assert.equal(decode(current()).plan.kind, "fallback")
  const sol = { model: "gpt-6.2-sol", effort: "xhigh" }
  const admitted = decode(current({ plan: { ...plan, codex: sol } })).plan
  assert.deepEqual(admitted, { ...plan, codex: sol })
  assert.throws(
    () => decode(current({ plan: { ...plan, codex: { ...CODEX, model: "openai/gpt-6.2-astra-xhigh" } } })),
    /Prohibited persisted model; manual reconciliation required/,
  )
  for (const malformed of [
    { plan: { kind: "fallback", codex: CODEX, command: COMMAND, pi: [] } },
    { plan: { ...plan, pi: [{ providerID: "opencode-go", id: "deepseek-v4.1-flash" }] } },
    { plan: { kind: "other" } }, { plan: undefined }, { execution: undefined }, { execution: { kind: "other" } },
    { plan: { ...plan, command: { model: "elsewhere", effort: "high" } } },
    { plan: { kind: "exclusive", target: CODEX } },
    { execution: { kind: "pi", selection: { ...GO, id: "elsewhere" }, session_id: "ses_fixture" } },
    { execution: { kind: "process", executor: "codex", selection: { model: "other-model", effort: "high" }, run } },
    { execution: { kind: "process", executor: "pi", selection: COMMAND, run } },
    { execution: { kind: "process", executor: "command-code", selection: COMMAND } },
    { execution: { kind: "transition", to: { executor: "pi", selection: COMMAND } } },
  ]) assert.throws(() => decode(current(malformed)), /plan|lifecycle|Invalid|Missing/)
})

test("lifecycle transitions cannot expose a previous receipt as an active run", () => {
  const parsed = decode(record())
  const target = { executor: "codex", selection: CODEX } as const
  transition(parsed, target)
  assert.deepEqual(parsed.execution, { kind: "transition", to: target })
  assert.equal(processRun(parsed), undefined)
  assert.equal(backendOf(parsed), "codex-transition")
  assert.equal(encodeSession(parsed).command_run, undefined)
  activateProcess(parsed, target, run)
  transition(parsed, target, true)
  assert.equal(backendOf(parsed), "codex-transition")
  assert.deepEqual(processRun(parsed), run)
  activatePi(parsed, GO, "ses_next")
  assert.deepEqual(parsed.execution, { kind: "pi", selection: GO, session_id: "ses_next" })
  assert.equal(processRun(parsed), undefined)
  const wire = encodeSession(parsed)
  assert.equal(wire.backend, "pi")
  assert.equal(wire.pi_id, "ses_next")
})

const scratch = new Scratch()
after(() => scratch.close())

function recordingApi(calls: string[]) {
  return new Proxy({}, { get: (_target, name) => () => { calls.push(String(name)); throw new Error("Pi must not be touched") } }) as OpenCodePort
}

// Fields copied from a real record written by a bridge process that predates schema_version.
function realShape(repo: Repo, n: number, backend: "codex" | "command-code", pid: number, lines: Array<Record<string, unknown>>) {
  const processRecord = runFor(repo, "real-" + n, pid)
  writeLog(processRecord.output, lines)
  return writeSession(repo, n, {
    schema_version: undefined, tier: "worker", backend, attempts: 1, execution_order: "codex-first",
    codex_model: "gpt-6.1-terra", codex_effort: "medium", remaining_pi: ["muse", "go"], pi_candidates: undefined,
    command_model: "deepseek/deepseek-v4.1-flash", command_effort: "high", command_run: processRecord,
  })
}

const failed = { state: "failed", result: { subtype: "error" as const, sessionId: "thread", error: "429 quota" }, stderr: null }
const succeeded = { state: "succeeded", result: { subtype: "success" as const, sessionId: "thread", finalText: "proof\nACCEPTANCE: met" }, stderr: null }
const REFUSAL = /Legacy Pi fallback has no exact model snapshot; manual reconciliation required/

test("a real in-flight codex-first record with only symbolic Pi destinations is observed, resumed and cancelled normally", async () => {
  const done = [{ type: "thread.started", thread_id: "thread" }, { type: "turn.completed" }]
  const repo = scratch.repo()
  const live = realShape(repo, 1, "codex", scratch.alive(), done)
  const decoded = decodeSession(JSON.parse(readFileSync(join(repo.directory, live + ".json"), "utf8")), repo.cwd, live)
  assert.equal(decoded.plan.kind, "fallback-unresolved-pi")
  assert.equal(backendOf(decoded), "codex")
  assert.deepEqual(targetOf(decoded), { executor: "codex", selection: CODEX })
  assert.equal((await inspectStored(repo.directory, live, realDeps())).execution_state, "running")
  const ended = realShape(repo, 2, "codex", await scratch.gone(), done)
  const snapshot = await inspectStored(repo.directory, ended, realDeps())
  assert.equal(snapshot.execution_state, "succeeded")
  assert.equal(snapshot.backend, "codex")
  assert.deepEqual(snapshot.model, "gpt-6.1-terra")
  assert.equal(snapshot.reason, null)

  const starts: string[] = []
  const codex = { available: () => true, status: () => succeeded, cancel: () => true, session: codexSession,
    start: (request: LaunchRequest) => { starts.push(request.resume ?? ""); return { pid: 1, output: "fake", errors: "fake", started_at: "now" } } }
  const command = { available: () => false, start: () => { throw new Error("unexpected") }, status: () => failed, cancel: () => false }
  const calls: string[] = []
  const bridge = makeHybridBridge(piAdapter(recordingApi(calls)), command, codex)
  assert.equal((await bridge.status(repo.cwd, ended)).state, "succeeded")
  assert.equal((await bridge.resume(repo.cwd, ended, "Same-scope correction")).backend, "codex")
  assert.deepEqual(starts, ["thread"])
  assert.equal((await bridge.cancel(repo.cwd, ended)).interrupted, true)
  assert.deepEqual(calls, [])
})

test("only a Pi fallback from that record is refused, with the reconciliation error and without touching Pi", async () => {
  const repo = scratch.repo()
  const calls: string[] = []
  const codex = { available: () => false, start: () => { throw new Error("unexpected") }, status: () => failed, cancel: () => false, session: codexSession }
  const unavailable = { available: () => false, start: () => { throw new Error("unexpected") }, status: () => failed, cancel: () => false }
  const fromCodex = realShape(repo, 3, "codex", await scratch.gone(), [])
  const first = await makeHybridBridge(piAdapter(recordingApi(calls)), unavailable, codex).status(repo.cwd, fromCodex)
  assert.equal(first.state, "blocked_admission")
  assert.match(String(first.fallback_notice ?? ""), /Fallback blocked/)
  assert.match(JSON.parse(readFileSync(join(repo.directory, fromCodex + ".json"), "utf8")).fallback_blocked, REFUSAL)

  const other = scratch.repo()
  const fromCommand = realShape(other, 4, "command-code", await scratch.gone(), [])
  const second = await makeHybridBridge(piAdapter(recordingApi(calls)), { ...unavailable, available: () => true }, codex).status(other.cwd, fromCommand)
  assert.equal(second.state, "blocked_fallback")
  assert.match(JSON.parse(readFileSync(join(other.directory, fromCommand + ".json"), "utf8")).fallback_blocked, REFUSAL)
  assert.deepEqual(calls, [])
})
