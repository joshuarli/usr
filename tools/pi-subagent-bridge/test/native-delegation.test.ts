import test from "node:test"
import assert from "node:assert/strict"
import { role, runId, steerNative, terminal, unwrap, type Job, type Rpc } from "../src/native-delegation.ts"

function job(id: string, variant: string, readOnly = false, providerID = "opencode-go"): Job {
  return { cwd: "/work", prompt: "proof", model: { providerID, id, variant },
    readOnly, sessionDir: "/work/state", resultPath: "/work/result.json" }
}

test("native Pi roles fail closed on provider, model, thinking and write scope", () => {
  assert.equal(role(job("muse-spark-1.3-contributor", "medium", true, "opencode-go")), "scout")
  assert.equal(role(job("muse-spark-1.3-contributor", "high", false, "opencode-go")), "mechanic")
  assert.equal(role(job("deepseek-v4.1-flash", "high")), "worker")
  assert.throws(() => role(job("muse-spark-1.3-contributor", "high", true, "opencode-go")), /Unapproved/)
  assert.throws(() => role({ ...job("muse-ember-1.0", "medium", true, "opencode-go"),
    priorRunId: "old", priorSessionFile: "/work/old.jsonl" }), /Unapproved/)
  assert.equal(role(job("deepseek-v4.1-flash", "max")), "expert")
  assert.equal(role(job("muse-spark-1.3", "xhigh", false, "muse-sdk")), "worker")
  assert.throws(() => role(job("deepseek-v4.1-flash", "xhigh")), /Unapproved/)
  assert.throws(() => role(job("muse-spark-1.3-contributor", "medium", false, "opencode-go")), /Unapproved/)
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

test("USR-39: timeout recovery cannot inherit an old worker's proof", async () => {
  const { mkdtempSync, mkdirSync, writeFileSync, readFileSync, rmSync } = await import("node:fs")
  const { tmpdir } = await import("node:os")
  const { join } = await import("node:path")
  const { executeJob, artifactResult } = await import("../src/native-delegation.ts")
  const dir = mkdtempSync(join(tmpdir(), "identity-"))
  try {
    const artifacts = join(dir, "subagent-artifacts")
    mkdirSync(artifacts)
    writeFileSync(join(artifacts, "old_worker_meta.json"), JSON.stringify({ runId: "old", exitCode: 0 }))
    writeFileSync(join(artifacts, "old_worker_output.md"), "old proof")
    const current = { ...job("deepseek-v4.1-flash", "high"), sessionDir: dir, resultPath: join(dir, "result.json") }
    await executeJob(current, async (_, started, dispatching) => {
      dispatching()
      started({ runId: "new", asyncDir: null, sessionFile: "/new.jsonl" })
      throw new Error("timeout")
    })
    const result = JSON.parse(readFileSync(current.resultPath, "utf8"))
    assert.equal(result.state, "unknown_or_interrupted")
    assert.equal(result.runId, "new")
    assert.equal(result.text, null)
    assert.equal(artifactResult(dir, null, "", "/new.jsonl"), null)
    writeFileSync(join(artifacts, "new_worker_meta.json"), JSON.stringify({ runId: "old", exitCode: 0 }))
    writeFileSync(join(artifacts, "new_worker_output.md"), "wrong identity")
    assert.equal(artifactResult(dir, null, "new", "/new.jsonl"), null)
    writeFileSync(join(artifacts, "new_worker_meta.json"), JSON.stringify({ runId: "new", exitCode: 0 }))
    await executeJob(current, async (_, started) => {
      started({ runId: "new", asyncDir: null, sessionFile: "/new.jsonl" })
      throw new Error("timeout")
    })
    assert.equal(JSON.parse(readFileSync(current.resultPath, "utf8")).state, "succeeded")
    assert.equal(JSON.parse(readFileSync(current.resultPath, "utf8")).runId, "new")
  } finally { rmSync(dir, { recursive: true, force: true }) }
})
