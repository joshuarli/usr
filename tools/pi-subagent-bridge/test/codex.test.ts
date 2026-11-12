import test from "node:test"
import assert from "node:assert/strict"
import { mkdtempSync, mkdirSync, readFileSync, rmSync, writeFileSync } from "node:fs"
import { tmpdir } from "node:os"
import { join } from "node:path"
import { codexResult, codexSession, startCodex } from "../src/codex.ts"

const delay = () => new Promise((resolve) => setTimeout(resolve, 10))

test("Codex captures the thread and completed turn and resumes with the same model", async () => {
  const root = mkdtempSync(join(tmpdir(), "codex-worker-")), bin = join(root, "bin")
  mkdirSync(bin)
  const oldPath = process.env.PATH, args = join(root, "args")
  try {
    writeFileSync(join(bin, "codex"), '#!/bin/sh\nprintf "%s\\n" "$@" >> ' + JSON.stringify(args) +
      '\nprintf \'{"type":"thread.started","thread_id":"thread-1"}\\n{"type":"item.completed","item":{"type":"agent_message","text":"proof"}}\\n{"type":"turn.completed","usage":{"input_tokens":3}}\\n\'\n', { mode: 0o755 })
    process.env.PATH = bin + ":" + oldPath
    const run = startCodex(root, root, "do work", "medium", false, undefined, "gpt-6.1-terra")
    let result = codexResult(run)
    for (let i = 0; i < 200 && result.state === "running"; i++) { await delay(); result = codexResult(run) }
    assert.equal(result.state, "succeeded")
    assert.equal(result.result?.finalText, "proof")
    assert.equal(codexSession(run), "thread-1")
    const next = startCodex(root, root, "correction", "medium", false, "thread-1", "gpt-6.1-terra")
    for (let i = 0; i < 200 && codexResult(next).state === "running"; i++) await delay()
    assert.match(readFileSync(args, "utf8"), /resume\nthread-1\ncorrection/)
    assert.match(readFileSync(args, "utf8"), /--ignore-user-config/)
  } finally { process.env.PATH = oldPath; rmSync(root, { recursive: true, force: true }) }
})

test("an unreceipted exit is interrupted, never a provider failure", () => {
  const root = mkdtempSync(join(tmpdir(), "codex-lost-"))
  try {
    const output = join(root, "out"), errors = join(root, "err")
    writeFileSync(output, '{"type":"thread.started","thread_id":"thread-1"}\n')
    writeFileSync(errors, "429 quota")
    assert.equal(codexResult({ pid: 2 ** 22 + 1, output, errors, started_at: "now" }).state, "interrupted")
  } finally { rmSync(root, { recursive: true, force: true }) }
})

test("scout exposes only read-only file tools and bounds file reads", async () => {
  const { spawn } = await import("node:child_process")
  const root = mkdtempSync(join(tmpdir(), "codex-scout-"))
  writeFileSync(join(root, "fixture"), "first\nneedle\n")
  const child = spawn(process.execPath, ["--experimental-strip-types", "src/codex-scout.ts"], { cwd: process.cwd(), stdio: ["pipe", "pipe", "pipe"] })
  try {
    const requests = [
      { jsonrpc: "2.0", id: 1, method: "tools/list" },
      { jsonrpc: "2.0", id: 2, method: "tools/call", params: { name: "read_file", arguments: { path: join(root, "fixture") } } },
      { jsonrpc: "2.0", id: 3, method: "tools/call", params: { name: "search_files", arguments: { pattern: "needle", path: join(root, "fixture") } } },
      { jsonrpc: "2.0", id: 4, method: "tools/call", params: { name: "read_file", arguments: { path: root } } },
      { jsonrpc: "2.0", id: 5, method: "tools/call", params: { name: "shell", arguments: {} } },
    ]
    let output = ""
    child.stdout.setEncoding("utf8")
    child.stdout.on("data", (chunk: string) => { output += chunk })
    child.stdin.end(requests.map((request) => JSON.stringify(request)).join("\n") + "\n")
    await new Promise<void>((resolve, reject) => { child.on("error", reject); child.on("close", () => resolve()) })
    const responses = output.trim().split("\n").map((line) => JSON.parse(line))
    assert.deepEqual(responses[0].result.tools.map((tool: { name: string }) => tool.name), ["read_file", "search_files", "list_files"])
    assert.ok(responses[0].result.tools.every((tool: { annotations: { readOnlyHint: boolean } }) => tool.annotations.readOnlyHint))
    assert.match(responses[1].result.content[0].text, /first\nneedle/)
    assert.match(responses[2].result.content[0].text, /2:needle/)
    assert.equal(responses[3].result.isError, true)
    assert.equal(responses[4].result.isError, true)
  } finally { child.kill(); rmSync(root, { recursive: true, force: true }) }
})

test("cancelling an owned Codex run terminates its process group", async () => {
  const { cancelCodex } = await import("../src/codex.ts")
  const root = mkdtempSync(join(tmpdir(), "codex-cancel-")), bin = join(root, "bin"), ready = join(root, "ready")
  mkdirSync(bin)
  const oldPath = process.env.PATH
  try {
    writeFileSync(join(bin, "codex"), '#!/bin/sh\nsleep 30 &\nprintf "%s" "$!" > ' + JSON.stringify(ready) + '\nwait\n', { mode: 0o755 })
    process.env.PATH = bin + ":" + oldPath
    const run = startCodex(root, root, "work", "high", false, undefined, "gpt-6-luna")
    const { existsSync } = await import("node:fs")
    for (let i = 0; i < 200 && !existsSync(ready); i++) await delay()
    assert.ok(existsSync(ready))
    assert.equal(cancelCodex(run), true)
    let state = codexResult(run).state
    for (let i = 0; i < 200 && state === "running"; i++) { await delay(); state = codexResult(run).state }
    assert.equal(state, "interrupted")
  } finally { process.env.PATH = oldPath; rmSync(root, { recursive: true, force: true }) }
})
