import test from "node:test"
import assert from "node:assert/strict"
import { mkdtempSync, mkdirSync, readFileSync, rmSync, writeFileSync } from "node:fs"
import { tmpdir } from "node:os"
import { join } from "node:path"
import { codexResult, codexSession, startCodex } from "../src/codex.ts"
import type { LaunchRequest } from "../src/launch.ts"

const delay = () => new Promise((resolve) => setTimeout(resolve, 10))
const WRITE = { kind: "write" } as const
const luna = { model: "gpt-6-luna", effort: "high" } as const
const terra = { model: "gpt-6.1-terra", effort: "medium" } as const
function request(root: string, overrides: Partial<LaunchRequest> = {}): LaunchRequest {
  return { directory: root, logDirectory: root, prompt: "do work", selection: terra, access: WRITE, ...overrides }
}

test("Codex captures the thread and completed turn and resumes with the same model", async () => {
  const root = mkdtempSync(join(tmpdir(), "codex-worker-")), bin = join(root, "bin")
  mkdirSync(bin)
  const oldPath = process.env.PATH, args = join(root, "args")
  try {
    writeFileSync(join(bin, "codex"), '#!/bin/sh\nprintf "%s\\n" "$@" >> ' + JSON.stringify(args) +
      '\nprintf \'{"type":"thread.started","thread_id":"thread-1"}\\n{"type":"item.completed","item":{"type":"agent_message","text":"proof"}}\\n{"type":"turn.completed","usage":{"input_tokens":3}}\\n\'\n', { mode: 0o755 })
    process.env.PATH = bin + ":" + oldPath
    const run = startCodex(request(root))
    let result = codexResult(run)
    for (let i = 0; i < 200 && result.state === "running"; i++) { await delay(); result = codexResult(run) }
    assert.equal(result.state, "succeeded")
    assert.equal(result.result?.finalText, "proof")
    assert.equal(codexSession(run), "thread-1")
    const next = startCodex(request(root, { prompt: "correction", resume: "thread-1" }))
    for (let i = 0; i < 200 && codexResult(next).state === "running"; i++) await delay()
    assert.match(readFileSync(args, "utf8"), /resume\nthread-1\ncorrection/)
    assert.match(readFileSync(args, "utf8"), /--ignore-user-config/)
    assert.match(readFileSync(args, "utf8"), /--sandbox\ndanger-full-access/)
    assert.doesNotMatch(readFileSync(args, "utf8"), /workspace-write|network_access/)
    const admittedPin = { model: "fixture-historical-codex", effort: "high" } as const
    const retained = startCodex(request(root, { prompt: "retain pin", resume: "thread-1", selection: admittedPin }))
    for (let i = 0; i < 200 && codexResult(retained).state === "running"; i++) await delay()
    assert.equal(codexResult(retained).state, "succeeded")
    assert.match(readFileSync(args, "utf8"), /model_reasoning_effort="high"[\s\S]*--model\nfixture-historical-codex\nresume\nthread-1\nretain pin/)
  } finally { process.env.PATH = oldPath; rmSync(root, { recursive: true, force: true }) }
})

test("Codex refuses a forbidden family and a read-only run is unsandboxed but has no execution tools", async () => {
  for (const model of ["gemini-4-argon-high", "google/gemini-4-carbon-high"]) {
    assert.throws(() => startCodex(request("/absent", { selection: { model, effort: "high" } })), /Prohibited Codex model/)
  }
  const root = mkdtempSync(join(tmpdir(), "codex-readonly-")), bin = join(root, "bin"), args = join(root, "args")
  mkdirSync(bin)
  const oldPath = process.env.PATH
  try {
    writeFileSync(join(bin, "codex"), '#!/bin/sh\nprintf "%s\\n" "$@" >> ' + JSON.stringify(args) + '\n', { mode: 0o755 })
    process.env.PATH = bin + ":" + oldPath
    const run = startCodex(request(root, { access: { kind: "read-only" } }))
    for (let i = 0; i < 200 && codexResult(run).state === "running"; i++) await delay()
    const recorded = readFileSync(args, "utf8")
    assert.match(recorded, /--sandbox\ndanger-full-access/)
    for (const feature of ["shell_tool", "unified_exec", "computer_use", "browser_use", "in_app_browser"])
      assert.match(recorded, new RegExp("--disable\n" + feature + "\n"), feature)
    assert.doesNotMatch(recorded, /--disable\ncode_mode_host\n/)
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
    const run = startCodex(request(root, { selection: luna }))
    const { existsSync } = await import("node:fs")
    for (let i = 0; i < 200 && !existsSync(ready); i++) await delay()
    assert.ok(existsSync(ready))
    assert.equal(cancelCodex(run), true)
    let state = codexResult(run).state
    for (let i = 0; i < 200 && state === "running"; i++) { await delay(); state = codexResult(run).state }
    assert.equal(state, "interrupted")
  } finally { process.env.PATH = oldPath; rmSync(root, { recursive: true, force: true }) }
})
