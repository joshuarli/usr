import { startCodex, codexResult, cancelCodex, codexSession } from "../src/codex.ts"
const noCodex = { available: () => false, start: startCodex, status: codexResult, cancel: cancelCodex, session: codexSession }
import test from "node:test"
import assert from "node:assert/strict"
import { execFileSync } from "node:child_process"
import { appendFileSync, mkdtempSync, mkdirSync, rmSync, writeFileSync, realpathSync } from "node:fs"
import { tmpdir } from "node:os"
import { join } from "node:path"
import { makeHybridBridge, type Scope } from "../src/hybrid.ts"
import type { OpenCodePort } from "../src/bridge.ts"
import { nestedCallRefusal, registerTierGuard } from "../src/nested-guard.ts"
import { resolveCurrentSubagentCapabilityCeiling } from "pi-subagents/capability-ceiling"
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent"

const git = (cwd: string, ...args: string[]) =>
  execFileSync("git", ["-C", cwd, ...args], { encoding: "utf8" }).trim()

function fixture() {
  const root = realpathSync(mkdtempSync(join(tmpdir(), "usr-bridge-integration-")))
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
  const head = git(cwd, "rev-parse", "HEAD")
  const scope: Scope = {
    base_revision: head, writable_paths: ["README"],
    acceptance_proof: "Run a focused verifier; report command, exit and output",
    attempt_limit: 1, stop_on: "Unexpected dependencies or contract changes",
  }
  return { root, cwd, head, scope, close: () => rmSync(root, { recursive: true, force: true }) }
}

function fake(cwd: string) {
  let model = { providerID: "opencode-go", id: "deepseek-v4.1-flash", variant: "high" }
  const api: OpenCodePort = {
    create: async (input) => { model = input.model as typeof model; return { data: { id: "ses_fixture" } } },
    prompt: async () => ({}),
    steer: async () => ({ data: { delivered: true, deliveryStatus: "delivered" } }),
    get: async () => ({ data: {
      id: "ses_fixture", title: "usr-worker: demo", model, location: { directory: cwd },
      metadata: { usr_worker_v1: { directory: cwd, model } }, outcome: "succeeded", error: null,
    } }),
    active: async () => ({ data: {} }),
    inbox: async () => ({ data: [] }),
    messages: async () => ({ data: [{ type: "assistant", content: [{ type: "text", text: "PROOF: ok" }] }] }),
    interrupt: async () => ({ data: { interrupted: true } }),
    models: async () => ({ data: [
      { id: "deepseek-v4.1-flash", providerID: "opencode-go", variants: [{ id: "high" }, { id: "max" }], enabled: true, status: "active" },
      { id: "muse-spark-1.3-contributor", providerID: "opencode-go", variants: [{ id: "medium" }, { id: "high" }], enabled: true, status: "active" },
    ] }),
  }
  const command: NonNullable<Parameters<typeof makeHybridBridge>[1]> = {
    available: () => true,
    start: () => ({ pid: 123, output: "fake", errors: "fake", started_at: "2026-11-09" }),
    status: () => ({ state: "succeeded" as const, result: { subtype: "success" as const, sessionId: "cmd", finalText: "proof" }, stderr: null }),
    cancel: () => true,
  }
  return { api, command }
}

test("integration: HEAD-pinned scoped admission and status report unchanged head", async () => {
  const f = fixture()
  try {
    const m = fake(f.cwd), bridge = makeHybridBridge(m.api, m.command, noCodex)
    const started = await bridge.start(f.cwd, "smoke", "worker", f.scope, "Do scoped work")
    assert.match(started.session_id, /^usrw_/)
    assert.equal(started.backend, "command-code")
    const status = await bridge.status(f.cwd, started.session_id)
    assert.equal(status.state, "succeeded")
    assert.equal(status.head_unchanged, true)
    assert.deepEqual(status.changed_paths, [])
    assert.deepEqual(status.out_of_scope_paths, [])

    await assert.rejects(
      bridge.start(f.cwd, "bad-head", "worker", { ...f.scope, base_revision: "0".repeat(40) }, "x"),
      /base_revision|HEAD/,
    )
  } finally { f.close() }
})

test("integration: active worktree lease blocks a second start, including higher-tier escalation attempt", async () => {
  const f = fixture()
  try {
    let done = false
    const m = fake(f.cwd)
    m.command.status = () => done
      ? { state: "succeeded" as const, result: { subtype: "success" as const, sessionId: "cmd", finalText: "proof" }, stderr: null }
      : { state: "running" as const, result: null, stderr: null }
    const bridge = makeHybridBridge(m.api, m.command, noCodex)
    const started = await bridge.start(f.cwd, "owner", "mechanic", f.scope, "Hold lease")
    assert.equal(started.backend, "command-code")
    await assert.rejects(
      bridge.start(f.cwd, "escalate", "expert", f.scope, "Try higher lane"),
      /active worker|inspect/i,
    )
    done = true
    const status = await bridge.status(f.cwd, started.session_id)
    assert.equal(status.state, "succeeded")
  } finally { f.close() }
})

test("integration: child-spawned-child is allowed only one level and never to a higher lane", () => {
  // Demonstrates policy for nested delegation: a root child may spawn one equal-or-weaker child,
  // but cannot escalate tiers and cannot start a third layer (depth > MAX_SUBAGENT_DEPTH guarded upstream).
  assert.equal(nestedCallRefusal("worker", "subagent", {
    agent: "scout", task: "Read proof", options: { agentScope: "user" },
  }), undefined, "worker may spawn lower/equal child (child-spawned-child, depth 1->2)")
  assert.equal(nestedCallRefusal("worker", "subagent", {
    agent: "mechanic", task: "Scoped fix", options: { agentScope: "user" },
  }), undefined)
  assert.match(nestedCallRefusal("worker", "subagent", {
    agent: "expert", task: "Escalate", options: { agentScope: "user" },
  }) ?? "", /cannot delegate|Tier worker/i, "higher lane escalation must be blocked")
  assert.match(nestedCallRefusal("mechanic", "subagent", {
    agent: "worker", task: "Escalate", options: { agentScope: "user" },
  }) ?? "", /cannot delegate|Tier mechanic/i)
  assert.match(nestedCallRefusal("scout", "subagent", {
    agent: "mechanic", task: "Edit", options: { agentScope: "user" },
  }) ?? "", /cannot delegate|Tier scout/i)

  // Installed child guard enforces a real monotonic ceiling in-process for the spawned child.
  const callbacks = new Map<string, (...args: unknown[]) => unknown>()
  const fakePi = { on(event: string, handler: (...args: unknown[]) => unknown) {
    callbacks.set(event, handler)
  } } as unknown as ExtensionAPI
  registerTierGuard("mechanic")(fakePi)
  const sessionId = "usr-integration-child"
  const started = callbacks.get("session_start")
  const launch = callbacks.get("tool_call")
  const shutdown = callbacks.get("session_shutdown")
  assert.ok(started && launch && shutdown)
  started({}, { sessionManager: { getSessionId: () => sessionId } })
  try {
    assert.deepEqual(resolveCurrentSubagentCapabilityCeiling(sessionId)?.allowedAgents, ["mechanic", "scout"])
    assert.equal(launch({ toolName: "subagent", input: { agent: "scout", task: "Inspect", options: { agentScope: "user" } } }), undefined)
    assert.deepEqual(launch({ toolName: "subagent", input: { agent: "worker", task: "Escalate", options: { agentScope: "user" } } }),
      { block: true, reason: "Tier mechanic cannot delegate to worker" })
  } finally {
    shutdown({})
  }
  assert.equal(resolveCurrentSubagentCapabilityCeiling(sessionId), undefined)
})
