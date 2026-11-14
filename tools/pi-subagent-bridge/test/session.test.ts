import test from "node:test"
import assert from "node:assert/strict"
import { activatePi, activateProcess, backendOf, decodeSession, encodeSession, processRun, transition } from "../src/session.ts"

const cwd = "/tmp/usr-session-fixture"
const id = "usrw_01234567-89ab-cdef-0123-456789abcdef"
const run = { pid: 12345, output: "/tmp/worker.ndjson", errors: "/tmp/worker.stderr", started_at: "2026-11-14T03:13:57Z", proc_start: "fixture-start" }
const scope = { base_revision: "a".repeat(40), writable_paths: ["README"], acceptance_proof: "Check the output", attempt_limit: 2, stop_on: "Scope expansion" }

function record(overrides: Record<string, unknown> = {}): Record<string, unknown> {
  return {
    schema_version: 1, id, cwd, title: "Review a bounded slice", task: "Read the source and return evidence",
    tier: "expert", scope, attempts: 0, backend: "antigravity", command_run: run,
    antigravity_pin: { model: "gemini-4-hydrogen-xhigh", effort: "xhigh" },
    ...overrides,
  }
}

function decode(value: Record<string, unknown>) { return decodeSession(value, cwd, id) }
function roundTrip(value: Record<string, unknown>) { return decodeSession(JSON.parse(JSON.stringify(encodeSession(decode(value)))), cwd, id) }

test("a process session round trip preserves its admitted pin independently of current defaults", () => {
  const selected = { model: "fixture-admitted-model", effort: "high" }
  const parsed = roundTrip(record({ antigravity_pin: selected }))
  assert.deepEqual(parsed.antigravity_pin, selected)
  assert.deepEqual(parsed.execution, { kind: "process", executor: "antigravity", run })
  assert.equal(backendOf(parsed), "antigravity")
  assert.deepEqual(processRun(parsed), run)
  const wire = encodeSession(parsed)
  assert.equal(wire.schema_version, 1)
  assert.equal(wire.backend, "antigravity")
  assert.deepEqual(wire.command_run, run)
  assert.equal("execution" in wire, false)
})

test("unversioned Hydrogen records use the historical pin and round trip without renaming a model into authority", () => {
  for (const backend of ["hydrogen", "hydrogen-transition"]) {
    const parsed = roundTrip(record({ schema_version: undefined, backend, antigravity_pin: undefined }))
    assert.deepEqual(parsed.antigravity_pin, { model: "gemini-4-hydrogen-xhigh", effort: "xhigh" })
    assert.equal(backendOf(parsed), backend === "hydrogen" ? "antigravity" : "antigravity-transition")
  }
  assert.throws(() => decode(record({ schema_version: undefined, backend: "hydrogen", antigravity_pin: { model: "different-model", effort: "xhigh" } })), /legacy|Ambiguous/)
})

test("accepted legacy Command and Pi records remain loadable after a save without inventing new policy pins", () => {
  for (const legacy of [
    { backend: "command-code", command_run: run },
    { backend: "command-transition", command_run: undefined },
    { backend: "pi", command_run: undefined, pi_id: "ses_legacy" },
  ]) {
    const input = record({ schema_version: undefined, tier: "worker", antigravity_pin: undefined, ...legacy })
    const parsed = roundTrip(input)
    assert.equal(backendOf(parsed), legacy.backend)
    assert.equal(parsed.command_model, undefined)
    assert.equal(parsed.primary_model, undefined)
  }
})

test("legacy lower-tier snapshots keep every recorded pin and remaining provider", () => {
  const input = record({
    schema_version: undefined, tier: "worker", backend: "command-code", antigravity_pin: undefined,
    command_model: "historical/model", command_effort: "high", codex_model: "historical-codex", codex_effort: "medium",
    primary_model: { providerID: "historical-provider", id: "historical-pi", variant: "high" },
    remaining_pi: ["go"], fallback_detail: "", fallback_reason: "quota",
  })
  const parsed = roundTrip(input)
  assert.equal(parsed.command_model, "historical/model")
  assert.equal(parsed.command_effort, "high")
  assert.equal(parsed.codex_model, "historical-codex")
  assert.equal(parsed.codex_effort, "medium")
  assert.deepEqual(parsed.primary_model, input.primary_model)
  assert.deepEqual(parsed.remaining_pi, ["go"])
  assert.equal(parsed.fallback_detail, "")
})

test("new records require complete pins and active execution handles", () => {
  for (const malformed of [
    { antigravity_pin: undefined },
    { command_run: undefined },
    { tier: "worker", backend: "codex", codex_model: "gpt-6-luna" },
    { tier: "worker", backend: "codex", codex_effort: "medium" },
    { tier: "worker", backend: "command-code", antigravity_pin: undefined },
    { tier: "worker", backend: "pi", command_run: undefined, pi_id: "ses_fixture" },
    { tier: "worker", backend: "pi", command_run: undefined, primary_model: { providerID: "opencode-go", id: "deepseek-v4.1-flash", variant: "high" } },
    { backend: "codex", codex_model: "gpt-6.1-terra", codex_effort: "xhigh" },
    { tier: "worker", backend: "pi", command_run: undefined, pi_id: "ses_fixture", primary_model: { providerID: "opencode-go", id: "deepseek-v4.1-flash" } },
    { pi_candidates: [{ providerID: "opencode-go", id: "deepseek-v4.1-flash" }] },
  ]) assert.throws(() => decode(record(malformed)), /Missing|Incomplete|Invalid/)
})

test("unknown versions, removed tiers, banned models and malformed state fail at the boundary", () => {
  for (const malformed of [
    { schema_version: 2 }, { schema_version: "1" }, { tier: "god" }, { backend: "carbon" },
    { id: "usrw_other" }, { cwd: "/tmp/another-worktree" }, { attempts: -1 }, { steers: 1.5 },
    { command_run: { ...run, pid: 0 } }, { command_run: { ...run, output: null } },
    { antigravity_pin: { model: "gemini-4-carbon-high", effort: "high" } },
    { antigravity_pin: { model: "gemini-4-argon-xhigh", effort: "xhigh" } },
    { antigravity_pin: { model: "gemini-4-hydrogen-xhigh", effort: "unlimited" } },
    { remaining_pi: ["other"] }, { pi_candidates: [null] }, { cancel_requested: "yes" },
  ]) assert.throws(() => decode(record(malformed)))
  assert.throws(() => decodeSession(null, cwd, id), /Invalid/)
})

test("lifecycle transitions cannot expose a previous receipt as an active run", () => {
  const parsed = decode(record())
  transition(parsed, "antigravity")
  assert.deepEqual(parsed.execution, { kind: "transition", executor: "antigravity" })
  assert.equal(processRun(parsed), undefined)
  assert.equal(backendOf(parsed), "antigravity-transition")
  assert.equal(encodeSession(parsed).command_run, undefined)
  activateProcess(parsed, "antigravity", run)
  transition(parsed, "antigravity", true)
  assert.equal(backendOf(parsed), "antigravity-transition")
  assert.deepEqual(processRun(parsed), run)
  activatePi(parsed, "ses_next")
  assert.deepEqual(parsed.execution, { kind: "pi", session_id: "ses_next" })
  assert.equal(processRun(parsed), undefined)
  const wire = encodeSession(parsed)
  assert.equal(wire.backend, "pi")
  assert.equal(wire.pi_id, "ses_next")
})

