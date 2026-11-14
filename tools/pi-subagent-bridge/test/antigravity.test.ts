import test from "node:test"
import assert from "node:assert/strict"
import { mkdtempSync, rmSync, writeFileSync } from "node:fs"
import { tmpdir } from "node:os"
import { join } from "node:path"
import { antigravityResult, antigravitySession, startAntigravity } from "../src/antigravity.ts"
import { ANTIGRAVITY_PIN } from "../src/policy.ts"
import type { CommandRun } from "../src/command.ts"

const ID = "81b3ef61-4006-4d78-990b-cbf3e448aa5c"

function fixture(initModel: string, status: string) {
  const dir = mkdtempSync(join(tmpdir(), "usr-antigravity-"))
  const output = join(dir, "events")
  const events = [
    { event: "init", conversation_id: ID, init: { cwd: dir, model: initModel, permission_mode: "always-proceed" } },
    { event: "step_update", step_update: { conversation_id: ID, state: "DONE", step_type: "agent_response", text_delta: "proof" } },
    { event: "result", result: { conversation_id: ID, status, response: "proof", ...(status === "ERROR" ? { error: "quota exhausted" } : {}), usage: { total_tokens: 100 } } },
  ]
  writeFileSync(output, events.map(event => JSON.stringify(event)).join("\n") + "\n")
  const run: CommandRun = { pid: 99999999, output, errors: join(dir, "stderr"), started_at: "now", proc_start: "unreachable" }
  return { run, close: () => rmSync(dir, { recursive: true, force: true }) }
}

test("Antigravity stream exposes the conversation and accepts a pinned successful result", () => {
  const f = fixture(ANTIGRAVITY_PIN.model, "SUCCESS")
  try {
    assert.equal(antigravitySession(f.run), ID)
    const result = antigravityResult(f.run, ANTIGRAVITY_PIN)
    assert.equal(result.state, "succeeded")
    assert.equal(result.result?.sessionId, ID)
    assert.equal(result.result?.usage && typeof result.result.usage, "object")
  } finally { f.close() }
})

test("even a successful response cannot accept Argon as a Antigravity run", () => {
  const f = fixture("gemini-4-argon-high", "SUCCESS")
  try {
    const result = antigravityResult(f.run, ANTIGRAVITY_PIN)
    assert.equal(result.state, "failed")
    assert.match(String(result.result?.error), /admitted model/)
  } finally { f.close() }
})

test("Antigravity terminal errors never masquerade as success", () => {
  const f = fixture(ANTIGRAVITY_PIN.model, "ERROR")
  try {
    const result = antigravityResult(f.run, ANTIGRAVITY_PIN)
    assert.equal(result.state, "failed")
    assert.match(String(result.result?.error), /quota exhausted/)
  } finally { f.close() }
})

test("Antigravity launcher refuses a forbidden family before launching a process", () => {
  const f = fixture(ANTIGRAVITY_PIN.model, "SUCCESS")
  try {
    for (const model of ["gemini-4-argon-high", "google/gemini-4-carbon-high"]) {
      assert.throws(() => startAntigravity({ directory: f.run.output, logDirectory: f.run.output, prompt: "Work",
        selection: { model, effort: "high" }, access: { kind: "write" } }), /Prohibited Antigravity model/)
    }
    assert.throws(() => startAntigravity({ directory: f.run.output, logDirectory: f.run.output, prompt: "Work",
      selection: ANTIGRAVITY_PIN, access: { kind: "write" }, resume: "not-a-conversation" }), /Invalid Antigravity conversation ID/)
  } finally { f.close() }
})
