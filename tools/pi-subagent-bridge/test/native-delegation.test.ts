import test from "node:test"
import assert from "node:assert/strict"
import { role, runId, steerNative, terminal, unwrap, dispatchParams, type Job, type Rpc } from "../src/native-delegation.ts"
import { PI_RUN_DEADLINE_MS } from "../src/tier-policy.ts"

function job(id: string, variant: string, readOnly = false, providerID = "opencode-go"): Job {
  return { cwd: "/work", prompt: "proof", model: { providerID, id, variant },
    readOnly, sessionDir: "/work/state", resultPath: "/work/result.json" }
}

test("native Pi roles fail closed on provider, model, thinking and write scope", () => {
  assert.equal(role(job("muse-spark-1.3-contributor", "medium", true, "opencode-go")), "scout")
  assert.equal(role(job("muse-spark-1.3-contributor", "high", false, "opencode-go")), "mechanic")
  assert.equal(role(job("deepseek-v4.1-flash", "high")), "worker")
  assert.equal(role(job("swe-2.1", "low", true, "devin")), "scout")
  assert.equal(role(job("swe-2.1", "medium", false, "devin")), "mechanic")
  assert.equal(role(job("swe-2.1", "high", false, "devin")), "worker")
  assert.throws(() => role(job("swe-2.1", "xhigh", false, "devin")), /Unapproved/)
  assert.throws(() => role(job("muse-spark-1.3-contributor", "high", true, "opencode-go")), /Unapproved/)
  assert.throws(() => role({ ...job("muse-ember-1.0", "medium", true, "opencode-go"),
    priorRunId: "old", priorSessionFile: "/work/old.jsonl" }), /Unapproved/)
  assert.equal(role(job("deepseek-v4.1-flash", "max")), "expert")
  assert.throws(() => role(job("muse-spark-1.3", "xhigh", false, "muse-sdk")), /Unapproved/)
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

test("a deadline-expired run is its own state with the partial output preserved", () => {
  const partial = { timedOut: true, success: false, error: "Subagent timed out after 14400000ms.",
    results: [{ success: false, timedOut: true, error: "Subagent timed out after 14400000ms.", output: "Partial output before timeout:\nimplemented fix" }] }
  const result = terminal(partial, "r", "/session")
  assert.equal(result.state, "timed_out")
  assert.match(result.error ?? "", /timed out after 14400000ms/)
  assert.match(result.text ?? "", /implemented fix/)
  assert.equal(terminal({ success: false, results: [{ success: false, error: "Subagent timed out after 4ms." }] }, "r", "/s").state, "timed_out")
  assert.equal(terminal({ success: false, results: [{ success: false, error: "quota exhausted" }] }, "r", "/s").state, "failed")
})

test("a native worker dispatch carries the tier run deadline, including resume", () => {
  const go = dispatchParams(job("deepseek-v4.1-flash", "high"))
  assert.equal(go.agent, "worker")
  assert.equal(go.async, true)
  assert.equal(go.model, "opencode-go/deepseek-v4.1-flash:high")
  assert.equal(go.timeoutMs, PI_RUN_DEADLINE_MS)
  const devin = dispatchParams(job("swe-2.1", "high", false, "devin"))
  assert.equal(devin.agent, "devin-worker")
  assert.equal(devin.timeoutMs, PI_RUN_DEADLINE_MS)
  const devinScout = dispatchParams(job("swe-2.1", "low", true, "devin"))
  assert.equal(devinScout.agent, "devin-scout")
  const devinMechanic = dispatchParams(job("swe-2.1", "medium", false, "devin"))
  assert.equal(devinMechanic.agent, "devin-mechanic")
  const resumed = dispatchParams({ ...job("deepseek-v4.1-flash", "high"), priorRunId: "old-run", priorSessionFile: "/work/old.jsonl" })
  assert.equal(resumed.timeoutMs, PI_RUN_DEADLINE_MS)
  assert.equal(resumed.id, "old-run")
  assert.equal(resumed.message, "proof")
})

test("an expired run reports timed_out from runner status or the meta error, keeping partial output", async () => {
  const { mkdtempSync, mkdirSync, writeFileSync, readFileSync, rmSync } = await import("node:fs")
  const { tmpdir } = await import("node:os")
  const { join } = await import("node:path")
  const { executeJob, artifactResult } = await import("../src/native-delegation.ts")
  const dir = mkdtempSync(join(tmpdir(), "deadline-"))
  try {
    const asyncDir = join(dir, "async-run")
    const artifacts = join(dir, "subagent-artifacts")
    mkdirSync(asyncDir, { recursive: true })
    mkdirSync(artifacts, { recursive: true })
    writeFileSync(join(asyncDir, "status.json"), JSON.stringify({ runId: "run-x", state: "failed", timedOut: true }))
    writeFileSync(join(artifacts, "run-x_worker_meta.json"), JSON.stringify({ runId: "run-x", exitCode: 1, error: "boom" }))
    writeFileSync(join(artifacts, "run-x_worker_output.md"), "Partial output before timeout:\nhalf the fix")
    const found = artifactResult(dir, asyncDir, "run-x", "/session.jsonl")
    assert.equal(found?.state, "timed_out")
    assert.equal(found?.text?.includes("half the fix"), true)
    // Without the runner's timedOut marker, the meta error string still identifies the deadline.
    rmSync(join(asyncDir, "status.json"))
    writeFileSync(join(artifacts, "run-x_worker_meta.json"), JSON.stringify({ runId: "run-x", exitCode: 1, error: "Subagent timed out after 14400000ms." }))
    const inferred = artifactResult(dir, asyncDir, "run-x", "/session.jsonl")
    assert.equal(inferred?.state, "timed_out")
    // A provider failure stays failed.
    writeFileSync(join(artifacts, "run-x_worker_meta.json"), JSON.stringify({ runId: "run-x", exitCode: 1, error: "429 quota exhausted" }))
    assert.equal(artifactResult(dir, asyncDir, "run-x", "/session.jsonl")?.state, "failed")
    writeFileSync(join(artifacts, "run-x_worker_meta.json"), JSON.stringify({ runId: "run-x", exitCode: 1, error: "Subagent timed out after 14400000ms." }))
    const job2 = { ...job("deepseek-v4.1-flash", "high"), sessionDir: dir, resultPath: join(dir, "result2.json") }
    await executeJob(job2, async (_, started) => {
      started({ runId: "run-x", asyncDir, sessionFile: "/session.jsonl" })
      throw new Error("Timed out waiting for native subagent completion")
    })
    assert.equal(JSON.parse(readFileSync(job2.resultPath, "utf8")).state, "timed_out")
  } finally { rmSync(dir, { recursive: true, force: true }) }
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

test("a run that ends early keeps the tail of its transcript notes; a success does not", async () => {
  const { mkdtempSync, mkdirSync, writeFileSync, readFileSync, rmSync } = await import("node:fs")
  const { tmpdir } = await import("node:os")
  const { join } = await import("node:path")
  const { executeJob } = await import("../src/native-delegation.ts")
  const dir = mkdtempSync(join(tmpdir(), "partial-"))
  try {
    const artifacts = join(dir, "subagent-artifacts")
    mkdirSync(artifacts, { recursive: true })
    const message = (content: unknown[]) => JSON.stringify({ recordType: "message", role: "assistant", message: { role: "assistant", content } })
    writeFileSync(join(artifacts, "run-p_devin-expert_transcript.jsonl"), [
      message([{ type: "thinking", thinking: "Finding 1: recvfrom keeps a bad buffer" }, { type: "toolCall", name: "bash" }]),
      JSON.stringify({ recordType: "message", role: "toolResult", text: "tool output is not a finding" }),
      message([{ type: "text", text: "Finding 2: addrlen is written on error" }]),
      message([]),
      "not json",
    ].join("\n"))
    const limited = "Reached free model rate limit. Please switch to a different model. Your limit will reset in 2 seconds (at 22:23 UTC)."
    const failed = { ...job("swe-2.1", "max", false, "devin"), sessionDir: dir, resultPath: join(dir, "failed.json") }
    await executeJob(failed, async () => ({ state: "failed", error: limited, text: "Subagent run failed before producing output.", sessionFile: null, runId: "run-p", usage: null }))
    const kept = JSON.parse(readFileSync(failed.resultPath, "utf8")) as { state: string; text: string }
    assert.equal(kept.state, "failed")
    assert.match(kept.text, /^Subagent run failed before producing output\./)
    assert.match(kept.text, /Partial work before the run ended \(2 assistant turns;/)
    assert.ok(kept.text.indexOf("Finding 1") < kept.text.indexOf("Finding 2"))
    assert.doesNotMatch(kept.text, /tool output is not a finding/)

    const ok = { ...failed, resultPath: join(dir, "ok.json") }
    await executeJob(ok, async () => ({ state: "succeeded", error: null, text: "ACCEPTANCE: met", sessionFile: null, runId: "run-p", usage: null }))
    assert.equal((JSON.parse(readFileSync(ok.resultPath, "utf8")) as { text: string }).text, "ACCEPTANCE: met")
  } finally { rmSync(dir, { recursive: true, force: true }) }
})

test("partial notes keep the newest notes within the limit", async () => {
  const { partialFindings } = await import("../src/native-delegation.ts")
  const line = (text: string) => JSON.stringify({ recordType: "message", role: "assistant", message: { content: [{ type: "text", text }] } })
  const found = partialFindings([line("old ".repeat(10)), line("new ".repeat(10))].join("\n"), 50)
  assert.equal(found?.turns, 2)
  assert.match(found?.notes ?? "", /new/)
  assert.doesNotMatch(found?.notes ?? "", /old/)
  assert.equal(partialFindings(line("x".repeat(100)), 10)?.notes, "…" + "x".repeat(10))
})
