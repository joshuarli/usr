import test from "node:test"
import assert from "node:assert/strict"
import { execFileSync } from "node:child_process"
import { appendFileSync, mkdtempSync, mkdirSync, rmSync, writeFileSync } from "node:fs"
import { tmpdir } from "node:os"
import { join } from "node:path"
import { makeHybridBridge, type Scope } from "../src/hybrid.ts"
import { type OpenCodePort } from "../src/bridge.ts"
import { type CommandRun } from "../src/command.ts"

const git = (cwd: string, ...args: string[]) =>
  execFileSync("git", ["-C", cwd, ...args], { encoding: "utf8" }).trim()
function fixture() {
  const root = mkdtempSync(join(tmpdir(), "usr-hybrid-"))
  git(root, "init", "-q")
  git(root, "config", "user.email", "test@example.com")
  git(root, "config", "user.name", "Test")
  writeFileSync(join(root, "README"), "original\n")
  git(root, "add", "README")
  git(root, "commit", "-qm", "init")
  appendFileSync(join(root, ".git", "info", "exclude"), "\n/.work/\n")
  mkdirSync(join(root, ".work", "wt"), { recursive: true })
  const cwd = join(root, ".work", "wt", "a")
  git(root, "worktree", "add", "-qb", "lane-a", cwd)
  const scope: Scope = { base_revision: git(cwd, "rev-parse", "HEAD"), writable_paths: ["README"],
    acceptance_proof: "Run a focused verifier; report exact command, exit code and output",
    attempt_limit: 2, stop_on: "Unexpected dependencies or contract changes" }
  return { root, cwd, scope, close: () => rmSync(root, { recursive: true, force: true }) }
}
function fake(cwd: string) {
  const calls: unknown[] = []
  let status = "succeeded", assistant = "PROOF: test exit 0", error: unknown = null
  let variants = ["low", "high", "max"]
  let commandDone = false
  let model = { providerID: "opencode-go", id: "deepseek-v4.1-flash", variant: "high" }
  const api: OpenCodePort = {
    create: async (input) => {
      model = input.model as typeof model
      calls.push(input)
      return { data: { id: "ses_fixture" } }
    },
    prompt: async (input) => { calls.push(input); return {} },
    get: async () => ({ data: {
      id: "ses_fixture", title: "usr-worker: demo",
      model, location: { directory: cwd },
      metadata: { usr_worker_v1: { directory: cwd, model } },
      outcome: status, error,
    } }),
    active: async () => ({ data: {} }),
    inbox: async () => ({ data: [] }),
    messages: async () => ({ data: [
      { type: "assistant", content: [{ type: "text", text: assistant }] },
    ] }),
    interrupt: async () => ({ data: { interrupted: true } }),
    models: async () => ({ data: [{ id: "deepseek-v4.1-flash", providerID: "opencode-go",
      variants: variants.map((id) => ({ id })), enabled: true, status: "active" }] }),
  }
  const command = {
    available: () => true,
    start: (dir: string, _log: string, prompt: string, effort: "low" | "high" | "max", readOnly: boolean, resume?: string): CommandRun => {
      calls.push({ command: true, dir, prompt, effort, readOnly, resume })
      return { pid: 123, output: "fake", errors: "fake", started_at: "2026-11-06" }
    },
    status: () => commandDone ?
      { state: "succeeded", result: { subtype: "success" as const, sessionId: "cmd-session", finalText: "proof" }, stderr: null } :
      { state: "running", result: null, stderr: null },
    cancel: () => true,
  }
  return { api, command, calls,
    fail: (text: string, providerError = true) => { status = "failed"; assistant = text; error = providerError ? { code: 429, message: text } : null },
    omitModels: () => { variants = [] }, done: () => { commandDone = true } }
}

test("OpenCode Go high runs a scoped worker; out-of-scope edits block acceptance", async () => {
  const f = fixture()
  try {
    const m = fake(f.cwd), bridge = makeHybridBridge(m.api, m.command)
    const task = await bridge.start(f.cwd, "fix", "worker", f.scope, "Edit README")
    assert.equal(task.backend, "opencode")
    assert.ok(m.calls.some((c) => JSON.stringify(c).includes('"variant":"high"')))
    writeFileSync(join(f.cwd, "README"), "changed\n")
    writeFileSync(join(f.cwd, "unrelated"), "bad\n")
    const status = await bridge.status(f.cwd, task.session_id)
    assert.equal(status.acceptance_blocked, true)
    assert.deepEqual(status.out_of_scope_paths, ["unrelated"])
    await assert.rejects(bridge.resume(f.cwd, task.session_id, "fix tests"), /out-of-scope/)
  } finally { f.close() }
})
test("missing OpenCode variant starts read-only Command Code scout; resume is pinned", async () => {
  const f = fixture()
  try {
    const m = fake(f.cwd), bridge = makeHybridBridge(m.api, m.command)
    m.omitModels()
    const scope = { ...f.scope, writable_paths: [] }
    const task = await bridge.start(f.cwd, "research", "scout", scope, "Locate relevant code")
    assert.equal(task.backend, "command-code")
    assert.ok(m.calls.some((c) => JSON.stringify(c).includes('"readOnly":true')))
    assert.ok(m.calls.some((c) => JSON.stringify(c).includes('"effort":"low"')))
    m.done()
    assert.equal((await bridge.status(f.cwd, task.session_id)).state, "succeeded")
    await bridge.resume(f.cwd, task.session_id, "Give file:line evidence")
    assert.ok(m.calls.some((c) => JSON.stringify(c).includes('"resume":"cmd-session"')))
    await assert.rejects(bridge.resume(f.cwd, task.session_id, "third attempt"), /attempt limit/)
  } finally { f.close() }
})
test("terminal OpenCode quota failure falls back only when no changes exist", async () => {
  const f = fixture()
  try {
    const m = fake(f.cwd), bridge = makeHybridBridge(m.api, m.command)
    const task = await bridge.start(f.cwd, "fix", "worker", f.scope, "Edit README")
    m.fail("quota exceeded, monthly allowance exhausted")
    const status = await bridge.status(f.cwd, task.session_id)
    assert.equal(status.backend, "command-code")
    assert.equal(status.fallback_reason, "OpenCode quota/usage failure")
  } finally { f.close() }
})
test("an ordinary failed task mentioning quota in its prose never triggers a fallback", async () => {
  const f = fixture()
  try {
    const m = fake(f.cwd), bridge = makeHybridBridge(m.api, m.command)
    const task = await bridge.start(f.cwd, "fix", "worker", f.scope, "Edit README")
    m.fail("The project's quota test failed for a local assertion; no provider error", false)
    const status = await bridge.status(f.cwd, task.session_id)
    assert.equal(status.backend, "opencode")
    assert.equal(status.state, "failed")
    assert.equal(status.fallback_reason, null)
    assert.equal(m.calls.filter((c) => JSON.stringify(c).includes('"command":true')).length, 0)
  } finally { f.close() }
})

test("quota does not silently restart a partially edited worktree", async () => {
  const f = fixture()
  try {
    const m = fake(f.cwd), bridge = makeHybridBridge(m.api, m.command)
    const task = await bridge.start(f.cwd, "fix", "worker", f.scope, "Edit README")
    writeFileSync(join(f.cwd, "README"), "partial\n")
    m.fail("rate limit exceeded")
    const status = await bridge.status(f.cwd, task.session_id)
    assert.equal(status.backend, "opencode")
    assert.equal(status.state, "blocked_partial_work")
  } finally { f.close() }
})
test("reject invalid scope, unapproved tier, and dirty worktree", async () => {
  const f = fixture()
  try {
    const m = fake(f.cwd), bridge = makeHybridBridge(m.api, m.command)
    await assert.rejects(bridge.start(f.cwd, "x", "worker", { ...f.scope, writable_paths: ["../secret"] }, "x"), /Invalid writable path/)
    await assert.rejects(bridge.start(f.cwd, "x", "scout", f.scope, "x"), /scouts are read-only/)
    await assert.rejects(bridge.start(f.cwd, "x", "opus", f.scope, "x"), /Unknown DeepSeek tier/)
    writeFileSync(join(f.cwd, "stray"), "x")
    await assert.rejects(bridge.start(f.cwd, "x", "worker", f.scope, "x"), /clean/)
  } finally { f.close() }
})
