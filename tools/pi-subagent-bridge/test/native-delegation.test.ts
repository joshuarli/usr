import test from "node:test"
import assert from "node:assert/strict"
import { role, runId, terminal, unwrap, type Job } from "../src/native-delegation.ts"

function job(id: string, variant: string, readOnly = false, providerID = "opencode-go"): Job {
  return { cwd: "/work", prompt: "proof", model: { providerID, id, variant },
    readOnly, sessionDir: "/work/state", resultPath: "/work/result.json" }
}

test("native Pi roles fail closed on provider, model, thinking and write scope", () => {
  assert.equal(role(job("muse-spark-1.3-contributor", "medium", true)), "scout")
  assert.equal(role(job("muse-spark-1.3-contributor", "high")), "mechanic")
  assert.throws(() => role(job("muse-ember-1.0", "medium", true, "opencode")), /Unapproved/)
  assert.throws(() => role({ ...job("muse-ember-1.0", "xhigh", false, "opencode"),
    priorRunId: "old", priorSessionFile: "/work/old.jsonl" }), /Unapproved/)
  assert.equal(role(job("deepseek-v4.1-flash", "high")), "worker")
  assert.equal(role(job("deepseek-v4.1-flash", "max")), "expert")
  assert.throws(() => role(job("deepseek-v4.1-flash", "xhigh")), /Unapproved/)
  assert.throws(() => role(job("muse-spark-1.3-contributor", "medium", false)), /Unapproved/)
  assert.throws(() => role(job("deepseek-v4.1-flash", "high", true)), /Unapproved/)
  assert.throws(() => role(job("god", "max")), /Unapproved/)
})

test("native run IDs are provider-issued and path safe", () => {
  assert.equal(runId({ success: true, data: { details: { asyncId: "run-123" } } }), "run-123")
  assert.equal(runId({ success: true, data: { details: { runId: "resumed-456" } } }), "resumed-456")
  assert.throws(() => runId({ success: true, data: { details: {} } }), /identity/)
  assert.throws(() => runId({ success: true, data: { details: { asyncId: "../escape" } } }), /identity/)
  assert.throws(() => unwrap({ success: false, error: { message: "model unavailable" } }), /model unavailable/)
})

test("native terminal receipts require one successful child and actual proof output", () => {
  const ok = { success: true, results: [{ success: true, output: "test: exit 0" }] }
  assert.equal(terminal(ok, "r", "/session").state, "succeeded")
  assert.equal(terminal({ success: true, summary: "looks good", results: [{ success: true }] }, "r", "/session").state, "failed")
  assert.equal(terminal({ success: true, results: [{ success: true, output: "a" }, { success: true, output: "b" }] }, "r", "/session").state, "failed")
  assert.equal(terminal({ success: false, results: [{ success: false, error: "quota exhausted" }] }, "r", "/session").error, "quota exhausted")
  assert.equal(terminal({ state: "stopped", results: [{ stopped: true }] }, "r", "/session").state, "cancelled")
  assert.equal(terminal({ success: false, summary: "quota local assertion", results: [{ success: false }] }, "r", "/session").error, "Native subagent failed")
})
