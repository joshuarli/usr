import test from "node:test"
import assert from "node:assert/strict"
import { mkdtempSync, rmSync, writeFileSync } from "node:fs"
import { tmpdir } from "node:os"
import { join } from "node:path"
import { readBoundedLog } from "../src/bounded-log.ts"
import { codexResult } from "../src/codex.ts"

const id = "81b3ef61-4006-4d78-990b-cbf3e448aa5c"

test("completion records crossing the prefix boundary survive for both readers", () => {
  const dir = mkdtempSync(join(tmpdir(), "bounded-log-")), output = join(dir, "out")
  const run = { pid: 99999999, output, errors: join(dir, "err"), started_at: "now", proc_start: "unreachable" }
  const text = "x".repeat(2000) + "\nACCEPTANCE: met"
  try {
    const init = JSON.stringify({ type: "thread.started", thread_id: id }) + "\n"
    const padding = " ".repeat(65000 - Buffer.byteLength(init) - 1) + "\n"
    const completion = JSON.stringify({ type: "item.completed", item: { type: "agent_message", text } }) + "\n" + JSON.stringify({ type: "turn.completed" })
    writeFileSync(output, init + padding + completion + "\n")
    const result = codexResult(run)
    assert.equal(result.state, "succeeded")
    assert.equal(result.result?.sessionId, id)
    assert.equal(result.result?.finalText, text)
    assert.match(result.result?.finalText ?? "", /ACCEPTANCE: met/)
    const unicode = "a".repeat(65535) + "😀" + "end"
    writeFileSync(output, unicode)
    assert.equal(readBoundedLog(output), unicode)
  } finally { rmSync(dir, { recursive: true, force: true }) }
})

test("a real gap discards partial records while preserving terminal events", () => {
  const dir = mkdtempSync(join(tmpdir(), "bounded-gap-")), output = join(dir, "out")
  const run = { pid: 99999999, output, errors: join(dir, "err"), started_at: "now", proc_start: "unreachable" }
  try {
    const init = JSON.stringify({ type: "thread.started", thread_id: id }) + "\n"
    const terminal = JSON.stringify({ type: "item.completed", item: { type: "agent_message", text: "ACCEPTANCE: met" } }) + "\n" + JSON.stringify({ type: "turn.completed" })
    writeFileSync(output, init + "partial" + "x".repeat(1200000) + "fragment\n" + terminal + "\n")
    assert.equal(readBoundedLog(output), init + terminal + "\n")
    const result = codexResult(run)
    assert.equal(result.state, "succeeded")
    assert.equal(result.result?.sessionId, id)
    assert.equal(result.result?.finalText, "ACCEPTANCE: met")
  } finally { rmSync(dir, { recursive: true, force: true }) }
})
