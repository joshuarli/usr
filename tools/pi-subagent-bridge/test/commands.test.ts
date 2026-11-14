import test from "node:test"
import assert from "node:assert/strict"
import { COMMANDS, COMMAND_NAMES, cliArguments, decodeCommand, toolSchema, usage } from "../src/commands.ts"
import { SCOPE_SCHEMA } from "../src/scope.ts"
import { TIERS } from "../src/tier-policy.ts"

const scope = { base_revision: "a".repeat(40), writable_paths: ["src/"], acceptance_proof: "Run a check", attempt_limit: 1, stop_on: "Scope change" }
const session_id = "usrw_01234567-89ab-cdef-0123-456789abcdef"
const files: Record<string, string> = { "scope.json": JSON.stringify(scope), "brief.txt": "Do the work", "feedback.txt": "Fix it", "note.txt": "Look here" }
const read = (path: string) => {
  const text = files[path]
  if (text === undefined) throw new Error("no such file: " + path)
  return text
}

test("every command decodes once into its typed shape", () => {
  assert.deepEqual(decodeCommand("model_check", { cwd: "/w", tier: "scout" }), { name: "model_check", cwd: "/w", tier: "scout" })
  assert.deepEqual(decodeCommand("start", { cwd: "/w", title: "t", tier: "worker", scope, brief: "b" }),
    { name: "start", cwd: "/w", title: "t", tier: "worker", scope, brief: "b" })
  assert.deepEqual(decodeCommand("status", { cwd: "/w", session_id }), { name: "status", cwd: "/w", session_id })
  assert.deepEqual(decodeCommand("resume", { cwd: "/w", session_id, feedback: "f" }), { name: "resume", cwd: "/w", session_id, feedback: "f" })
  assert.deepEqual(decodeCommand("steer", { cwd: "/w", session_id, note: "n" }), { name: "steer", cwd: "/w", session_id, note: "n" })
  assert.deepEqual(decodeCommand("cancel", { cwd: "/w", session_id }), { name: "cancel", cwd: "/w", session_id })
})

test("malformed arguments are refused before any value reaches the bridge", () => {
  const valid = { cwd: "/w", title: "t", tier: "scout", scope: { ...scope, writable_paths: [] }, brief: "b" }
  const cases: Array<[Parameters<typeof decodeCommand>[0], unknown, RegExp]> = [
    ["start", null, /must be an object/], ["start", [], /must be an object/],
    ["start", { cwd: "/w", title: "t", tier: "scout", brief: "b" }, /Missing tool argument: scope/],
    ["start", { ...valid, extra: 1 }, /Unknown tool argument: extra/],
    ["start", { ...valid, cwd: " " }, /Invalid cwd/], ["start", { ...valid, tier: "god" }, /Unknown Pi tier/],
    ["start", { ...valid, title: "" }, /Invalid title/], ["start", { ...valid, brief: "x".repeat(32001) }, /Invalid brief/],
    ["start", { ...valid, scope: { ...valid.scope, extra: true } }, /Unknown scope field: extra/],
    ["start", { ...valid, tier: "worker" }, /scouts are read-only|writers need/],
    ["model_check", { cwd: "/w" }, /Missing tool argument: tier/],
    ["status", { cwd: "/w", session_id: "x".repeat(65) }, /Invalid session_id/],
    ["resume", { cwd: "/w", session_id, feedback: " " }, /Invalid feedback/],
    ["steer", { cwd: "/w", session_id, note: "" }, /Invalid note/],
    ["cancel", { cwd: "/w", session_id, note: "n" }, /Unknown tool argument: note/],
  ]
  for (const [name, args, message] of cases) assert.throws(() => decodeCommand(name, args), message, name)
})

test("MCP input schemas are derived from the shared field list", () => {
  assert.deepEqual(COMMAND_NAMES.map(name => COMMANDS[name].tool),
    ["worker_model_check", "worker_start", "worker_status", "worker_resume", "worker_steer", "worker_cancel"])
  const start = toolSchema("start")
  assert.deepEqual(Object.keys(start.properties), ["cwd", "title", "tier", "scope", "brief"])
  assert.deepEqual(start.required, ["cwd", "title", "tier", "scope", "brief"])
  assert.equal(start.additionalProperties, false)
  assert.deepEqual(start.properties.scope, SCOPE_SCHEMA)
  assert.deepEqual(start.properties.tier, { type: "string", minLength: 1, maxLength: 8, enum: TIERS })
  assert.match(COMMANDS.start.description, /scout: codex then command-code then pi; mechanic: .*; worker: codex then command-code then pi then pi; expert: antigravity, no fallback\)/)
  assert.deepEqual(toolSchema("steer").required, ["cwd", "session_id", "note"])
  for (const name of COMMAND_NAMES) {
    const sample = { cwd: "/w", title: "t", tier: "scout", scope: { ...scope, writable_paths: [] }, brief: "b", session_id, feedback: "f", note: "n" }
    const args = Object.fromEntries(toolSchema(name).required.map(field => [field, sample[field]]))
    assert.equal(decodeCommand(name, args).name, name)
  }
})

test("CLI arguments become the same named arguments, reading file-valued ones", () => {
  assert.deepEqual(decodeCommand("start", cliArguments("start", ["/w", "t", "worker", "scope.json", "brief.txt"], read)),
    decodeCommand("start", { cwd: "/w", title: "t", tier: "worker", scope, brief: "Do the work" }))
  assert.deepEqual(cliArguments("resume", ["/w", session_id, "feedback.txt"], read), { cwd: "/w", session_id, feedback: "Fix it" })
  assert.deepEqual(cliArguments("steer", ["/w", session_id, "note.txt"], read), { cwd: "/w", session_id, note: "Look here" })
  assert.deepEqual(cliArguments("status", ["/w", session_id], read), { cwd: "/w", session_id })
  assert.equal(usage("start"), "usage: pi-subagent-bridge start CWD TITLE TIER SCOPE_JSON_FILE BRIEF_FILE")
  assert.equal(usage("model_check"), "usage: pi-subagent-bridge model-check CWD TIER")
  for (const rest of [[], ["/w"], ["/w", "scout", "extra"], ["", "scout"]])
    assert.throws(() => cliArguments("model_check", rest, read), /^Error: usage: pi-subagent-bridge model-check CWD TIER$/)
  assert.throws(() => cliArguments("start", ["/w", "t", "worker", "missing.json", "brief.txt"], read), /no such file/)
})

test("string field bounds agree between schema and decoder", () => {
  const sample = { cwd: "/w", title: "t", tier: "worker", scope, brief: "b", session_id, feedback: "f", note: "n" }
  for (const [name, field, max] of [["start", "cwd", 32000], ["model_check", "tier", 8], ["start", "title", 100], ["start", "brief", 32000], ["status", "session_id", 64], ["resume", "feedback", 32000], ["steer", "note", 32000]] as const) {
    const args = Object.fromEntries(toolSchema(name).required.map(key => [key, sample[key]]))
    const schema = toolSchema(name).properties[field] as { minLength?: number; maxLength?: number }
    assert.throws(() => decodeCommand(name, { ...args, [field]: "" }), field)
    assert.throws(() => decodeCommand(name, { ...args, [field]: "x".repeat(max + 1) }), field)
    assert.equal(schema.minLength, 1, field)
    assert.equal(schema.maxLength, max, field)
  }
})
