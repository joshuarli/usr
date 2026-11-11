import test from "node:test"
import assert from "node:assert/strict"
import { role, runId, steerNative, terminal, unwrap, type Job, type Rpc } from "../src/native-delegation.ts"

function job(id: string, variant: string, readOnly = false, providerID = "opencode-go"): Job {
  return { cwd: "/work", prompt: "proof", model: { providerID, id, variant },
    readOnly, sessionDir: "/work/state", resultPath: "/work/result.json" }
}

test("native Pi roles fail closed on provider, model, thinking and write scope", () => {
  assert.equal(role(job("muse-spark-1.3-contributor", "medium", true)), "scout")
  assert.equal(role(job("muse-spark-1.3-contributor", "high")), "mechanic")
  assert.equal(role(job("deepseek-v4.1-flash", "high")), "worker")
  assert.throws(() => role(job("muse-ember-1.0", "medium", true, "opencode")), /Unapproved/)
  assert.throws(() => role({ ...job("muse-ember-1.0", "xhigh", false, "opencode"),
    priorRunId: "old", priorSessionFile: "/work/old.jsonl" }), /Unapproved/)
  assert.equal(role(job("deepseek-v4.1-flash", "max")), "expert")
  assert.equal(role(job("muse-ember-1.0", "medium", true, "muse-sdk")), "scout")
  assert.equal(role(job("muse-ember-1.0", "xhigh", false, "muse-sdk")), "mechanic")
  assert.equal(role(job("muse-spark-1.3", "xhigh", false, "muse-sdk")), "worker")
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

test("native steer forwards the exact run and note to the pi-subagents steer RPC", async () => {
  const calls: Array<{ method: string; params: Record<string, unknown> }> = []
  const rpc: Rpc = async (method, params) => {
    calls.push({ method, params })
    return { success: true, data: { state: "delivered", deliveryStatus: "delivered" } }
  }
  const receipt = await steerNative(rpc, "run-42", "tighten the focused test")
  assert.equal(calls.length, 1)
  assert.equal(calls[0].method, "steer")
  assert.deepEqual(calls[0].params, { id: "run-42", message: "tighten the focused test" })
  assert.equal(receipt?.deliveryStatus, "delivered")
  await assert.rejects(
    steerNative(async () => ({ success: false, error: { message: "no live run" } }), "run-42", "x"),
    /no live run/)
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
