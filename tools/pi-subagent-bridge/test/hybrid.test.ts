import test from "node:test"
import assert from "node:assert/strict"
import { execFileSync, spawn } from "node:child_process"
import { appendFileSync, mkdtempSync, mkdirSync, readdirSync, readFileSync, rmSync, writeFileSync, realpathSync } from "node:fs"
import { tmpdir } from "node:os"
import { join } from "node:path"
import { makeHybridBridge, STEER_LIMIT, TURN_LIMIT_CONTINUATIONS, type Scope } from "../src/hybrid.ts"
import type { OpenCodePort } from "../src/bridge.ts"
import { commandResult, processStartTime, type CommandRun, type Effort } from "../src/command.ts"

const git = (cwd: string, ...args: string[]) =>
  execFileSync("git", ["-C", cwd, ...args], { encoding: "utf8" }).trim()

function fixture() {
  const root = realpathSync(mkdtempSync(join(tmpdir(), "usr-hybrid-")))
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
  const scope: Scope = {
    base_revision: git(cwd, "rev-parse", "HEAD"), writable_paths: ["README"],
    acceptance_proof: "Run a focused verifier; report command, exit and output",
    attempt_limit: 2, stop_on: "Unexpected dependencies or contract changes",
  }
  return { root, cwd, scope, close: () => rmSync(root, { recursive: true, force: true }) }
}

function fake(cwd: string) {
  const calls: unknown[] = []
  let piState = "succeeded", piError: unknown = null
  let variants = ["low", "medium", "high", "xhigh", "max"]
  let commandAvailable = true, commandDone = false, commandFailure: string | null = null
  let commandFinalText: string | null = null
  let model = { providerID: "opencode-go", id: "deepseek-v4.1-flash", variant: "high" }
  const api: OpenCodePort = {
    create: async (input) => {
      model = input.model as typeof model
      calls.push(input)
      return { data: { id: "ses_fixture" } }
    },
    prompt: async (input) => { calls.push(input); return {} },
    steer: async (input) => {
      calls.push({ op: "steer", input })
      return { data: { delivered: true, deliveryStatus: "delivered" } }
    },
    get: async () => ({ data: {
      id: "ses_fixture", title: "usr-worker: demo",
      model, location: { directory: cwd },
      metadata: { usr_worker_v1: { directory: cwd, model } },
      outcome: piState, error: piError,
    } }),
    active: async () => ({ data: {} }),
    inbox: async () => ({ data: [] }),
    messages: async () => ({ data: [{ type: "assistant", content: [{ type: "text", text: "PROOF: test exit 0" }] }] }),
    interrupt: async () => ({ data: { interrupted: true } }),
    models: async () => ({ data: [
      { id: "muse-spark-1.3-contributor", providerID: "opencode-go" },
      { id: "deepseek-v4.1-flash", providerID: "opencode-go" },
      { id: "muse-spark-1.3", providerID: "muse-sdk" },
    ].map(({ id, providerID }) => ({
      id, providerID, variants: variants.map((variant) => ({ id: variant })),
      enabled: true, status: "active",
    })) }),
  }
  const command = {
    available: () => commandAvailable,
    start: (dir: string, _log: string, prompt: string,
      effort: "low" | "medium" | "high" | "xhigh" | "max",
      readOnly: boolean, resume?: string, selectedModel?: string): CommandRun => {
      calls.push({ command: true, dir, prompt, effort, readOnly, resume, model: selectedModel })
      return { pid: 123, output: "fake", errors: "fake", started_at: "2026-11-09" }
    },
    status: () => commandFailure ?
      { state: "failed", result: { subtype: "error" as const,
        sessionId: "cmd-session", error: commandFailure, finalText: commandFinalText ?? "failed" }, stderr: null } :
      commandDone ?
      { state: "succeeded", result: { subtype: "success" as const,
        sessionId: "cmd-session", finalText: "proof" }, stderr: null } :
      { state: "running", result: null, stderr: null },
    cancel: () => true,
  }
  return {
    api, command, calls,
    failPi: (error: string) => { piState = "failed"; piError = { code: 429, message: error } },
    setPiState: (state: string) => { piState = state },
    omitGo: () => { variants = [] },
    noCommand: () => { commandAvailable = false },
    failCommand: (error: string, finalText?: string) => {
      commandFailure = error; commandFinalText = finalText ?? null
    },
    done: () => { commandDone = true },
  }
}
const commandCalls = (calls: unknown[]) =>
  calls.filter((value) => !!value && typeof value === "object" && "command" in value)
const piCreates = (calls: unknown[]) =>
  calls.filter((value) => !!value && typeof value === "object" && "title" in value)

function steerable(f: ReturnType<typeof fixture>, m: ReturnType<typeof fake>) {
  const control = { cancelled: false, starts: 0, alwaysRunning: false }
  const command = {
    ...m.command,
    start: (dir: string, _log: string, prompt: string, effort: Effort, readOnly: boolean,
      resume?: string, selectedModel?: string): CommandRun => {
      control.starts++
      const errors = join(f.root, "cmd-" + control.starts + ".stderr")
      writeFileSync(errors, "session: cmd-session\n")
      m.calls.push({ command: true, dir, prompt, effort, readOnly, resume, model: selectedModel })
      control.cancelled = false
      return { pid: 9000 + control.starts, output: "fake", errors, started_at: "2026-11-09", proc_start: "1" }
    },
    status: () => control.cancelled && !control.alwaysRunning
      ? { state: "interrupted" as const, result: null, stderr: null }
      : { state: "running" as const, result: null, stderr: null },
    cancel: () => { control.cancelled = true; return true },
  }
  return { command, control }
}

test("Command Code is primary, and fallback model pins are exclusively OpenCode Go", async () => {
  const f = fixture()
  try {
    const m = fake(f.cwd), bridge = makeHybridBridge(m.api, m.command)
    const expected = [
      ["scout", "meta/muse-ember", "medium"],
      ["mechanic", "meta/muse-ember", "xhigh"],
      ["worker", "deepseek/deepseek-v4.1-flash", "high"],
      ["expert", "deepseek/deepseek-v4.1-flash", "max"],
    ] as const
    for (const [tier, model, effort] of expected) {
      const status = await bridge.modelCheck(f.cwd, tier)
      assert.equal(status.primary.backend, "command-code")
      assert.equal(status.primary.model, model)
      assert.equal(status.primary.effort, effort)
      assert.equal(status.primary.available, true)
    }
    await assert.rejects(bridge.modelCheck(f.cwd, "god"), /Unknown Pi tier/)
  } finally { f.close() }
})

test("Command Code scout and mechanic use Ember medium and xhigh, even when Go has no models", async () => {
  for (const [tier, effort] of [["scout", "medium"], ["mechanic", "xhigh"]] as const) {
    const f = fixture()
    try {
      const m = fake(f.cwd), bridge = makeHybridBridge(m.api, m.command)
      m.omitGo()
      const scope = tier === "scout" ? { ...f.scope, writable_paths: [] } : f.scope
      const started = await bridge.start(f.cwd, tier, tier, scope, "Provide evidence")
      assert.equal(started.backend, "command-code")
      assert.equal(started.fallback_reason, null)
      assert.equal(commandCalls(m.calls).length, 1)
      assert.equal(piCreates(m.calls).length, 0)
      assert.match(JSON.stringify(commandCalls(m.calls)[0]), /"model":"meta\/muse-ember"/)
      assert.match(JSON.stringify(commandCalls(m.calls)[0]), new RegExp('"effort":"' + effort + '"'))
      m.done()
      const result = await bridge.status(f.cwd, started.session_id)
      assert.equal(result.model, "meta/muse-ember")
      assert.equal(result.effort, effort)
    } finally { f.close() }
  }
})

test("missing Command Code starts exactly the pinned Contributor fallback", async () => {
  for (const [tier, variant] of [["scout", "medium"], ["mechanic", "high"]] as const) {
    const f = fixture()
    try {
      const m = fake(f.cwd), bridge = makeHybridBridge(m.api, m.command)
      m.noCommand()
      const scope = tier === "scout" ? { ...f.scope, writable_paths: [] } : f.scope
      const started = await bridge.start(f.cwd, tier, tier, scope, "Find proof")
      assert.equal(started.backend === "pi", true)
      assert.match(started.fallback_notice ?? "", /needs no parent action/)
      const result = await bridge.status(f.cwd, started.session_id)
      assert.equal(commandCalls(m.calls).length, 0)
      assert.equal(piCreates(m.calls).length, 1)
      assert.deepEqual(result.model, { providerID: "opencode-go", id: "muse-spark-1.3-contributor", variant })
    } finally { f.close() }
  }
})

test("Command quota failure on a clean worktree switches once to OpenCode Go", async () => {
  const f = fixture()
  try {
    const m = fake(f.cwd), bridge = makeHybridBridge(m.api, m.command)
    const started = await bridge.start(f.cwd, "fix", "worker", f.scope, "Edit README")
    m.failCommand("quota exceeded, allowance exhausted")
    const result = await bridge.status(f.cwd, started.session_id)
    assert.equal(result.backend, "pi")
    assert.equal(result.state, "running")
    assert.equal(result.error, null)
    assert.equal(commandCalls(m.calls).length, 1)
    assert.equal(piCreates(m.calls).length, 1)
  } finally { f.close() }
})

test("explicit model-not-found error allows a single Go fallback", async () => {
  const f = fixture()
  try {
    const m = fake(f.cwd), bridge = makeHybridBridge(m.api, m.command)
    const task = await bridge.start(f.cwd, "read", "scout", { ...f.scope, writable_paths: [] }, "Locate evidence")
    m.failCommand("model not found")
    const status = await bridge.status(f.cwd, task.session_id)
    assert.equal(status.backend, "pi")
  } finally { f.close() }
})

test("quota in task prose is not a provider error and never causes fallback", async () => {
  const f = fixture()
  try {
    const m = fake(f.cwd), bridge = makeHybridBridge(m.api, m.command)
    const task = await bridge.start(f.cwd, "fix", "worker", f.scope, "Edit README")
    m.failCommand("ordinary task failure", "The project's quota assertion failed")
    const status = await bridge.status(f.cwd, task.session_id)
    assert.equal(status.backend, "command-code")
    assert.equal(status.state, "failed")
    assert.equal(status.fallback_reason, null)
    assert.equal(piCreates(m.calls).length, 0)
  } finally { f.close() }
})

test("Command quota after edits cannot replay partial work on Go", async () => {
  const f = fixture()
  try {
    const m = fake(f.cwd), bridge = makeHybridBridge(m.api, m.command)
    const task = await bridge.start(f.cwd, "fix", "worker", f.scope, "Edit README")
    writeFileSync(join(f.cwd, "README"), "partial\n")
    m.failCommand("rate limit exceeded")
    const result = await bridge.status(f.cwd, task.session_id)
    assert.equal(result.backend, "command-code")
    assert.equal(result.state, "blocked_partial_work")
    assert.match(result.fallback_notice ?? "", /decide manually/)
    assert.equal(piCreates(m.calls).length, 0)
  } finally { f.close() }
})

test("unavailable Go fallback blocks and stays blocked without polling retries", async () => {
  const f = fixture()
  try {
    const m = fake(f.cwd), bridge = makeHybridBridge(m.api, m.command)
    m.omitGo()
    const task = await bridge.start(f.cwd, "fix", "worker", f.scope, "Edit README")
    m.failCommand("quota exhausted")
    const first = await bridge.status(f.cwd, task.session_id)
    assert.equal(first.state, "blocked_fallback")
    assert.match(first.fallback_notice ?? "", /Pi fallback blocked/)
    const second = await bridge.status(f.cwd, task.session_id)
    assert.equal(second.state, "blocked_fallback")
    assert.equal(commandCalls(m.calls).length, 1)
    assert.equal(piCreates(m.calls).length, 0)
    await assert.rejects(bridge.start(f.cwd, "other", "worker", f.scope, "Edit README"), /active worker/)
  } finally { f.close() }
})

test("a failing Go fallback never restarts Command Code", async () => {
  const f = fixture()
  try {
    const m = fake(f.cwd), bridge = makeHybridBridge(m.api, m.command)
    m.noCommand()
    const task = await bridge.start(f.cwd, "fix", "worker", f.scope, "Edit README")
    m.failPi("quota exceeded")
    const result = await bridge.status(f.cwd, task.session_id)
    assert.equal(result.backend, "pi")
    assert.equal(result.state, "failed")
    assert.equal(commandCalls(m.calls).length, 0)
  } finally { f.close() }
})

test("Go fallback failure on a provider usage limit reports a terminal, action-required notice", async () => {
  const f = fixture()
  try {
    const m = fake(f.cwd), bridge = makeHybridBridge(m.api, m.command)
    m.noCommand()
    const task = await bridge.start(f.cwd, "read", "scout", { ...f.scope, writable_paths: [] }, "Provide evidence")
    assert.equal(task.backend, "pi")
    m.failPi("opencode API error (429): FreeUsageLimitError - Free usage limit reached")
    const result = await bridge.status(f.cwd, task.session_id)
    assert.equal(result.backend, "pi")
    assert.equal(result.state, "failed")
    assert.match(result.fallback_notice ?? "", /every pinned lane is exhausted/)
    assert.equal(/task continues on/i.test(result.fallback_notice ?? ""), false)
    assert.equal(commandCalls(m.calls).length, 0)
  } finally { f.close() }
})

test("uncertain Command termination must not start another provider", async () => {
  const f = fixture()
  try {
    const m = fake(f.cwd)
    const command = { ...m.command,
      status: () => ({ state: "unknown_or_interrupted", result: null, stderr: "quota exhausted" }) }
    const bridge = makeHybridBridge(m.api, command)
    const task = await bridge.start(f.cwd, "fix", "worker", f.scope, "Edit README")
    const result = await bridge.status(f.cwd, task.session_id)
    assert.equal(result.backend, "command-code")
    assert.equal(result.state, "unknown_or_interrupted")
    assert.equal(piCreates(m.calls).length, 0)
    await assert.rejects(bridge.start(f.cwd, "other", "worker", f.scope, "Edit README"), /active worker/)
  } finally { f.close() }
})

test("two overlapping status requests cannot duplicate a Go fallback", async () => {
  const f = fixture()
  try {
    const m = fake(f.cwd), bridge = makeHybridBridge(m.api, m.command)
    const task = await bridge.start(f.cwd, "fix", "worker", f.scope, "Edit README")
    m.failCommand("quota exhausted")
    const results = await Promise.allSettled([
      bridge.status(f.cwd, task.session_id),
      bridge.status(f.cwd, task.session_id),
    ])
    assert.equal(results.filter((x) => x.status === "fulfilled").length, 1)
    const rejected = results.find((x) => x.status === "rejected")
    assert.ok(rejected && rejected.status === "rejected")
    assert.match(String(rejected.reason), /transition in progress/)
    assert.equal(piCreates(m.calls).length, 1)
    assert.equal(commandCalls(m.calls).length, 1)
  } finally { f.close() }
})

test("fallback Pi writer still blocks out-of-scope edits", async () => {
  const f = fixture()
  try {
    const m = fake(f.cwd), bridge = makeHybridBridge(m.api, m.command)
    m.noCommand()
    const task = await bridge.start(f.cwd, "fix", "worker", f.scope, "Edit README")
    writeFileSync(join(f.cwd, "README"), "changed\n")
    writeFileSync(join(f.cwd, "unrelated"), "bad\n")
    const status = await bridge.status(f.cwd, task.session_id)
    assert.equal(status.acceptance_blocked, true)
    assert.deepEqual(status.out_of_scope_paths, ["unrelated"])
    await assert.rejects(bridge.resume(f.cwd, task.session_id, "fix tests"), /out-of-scope/)
  } finally { f.close() }
})

test("invalid scopes, unapproved tiers and dirty worktrees fail before any execution", async () => {
  const f = fixture()
  try {
    const m = fake(f.cwd), bridge = makeHybridBridge(m.api, m.command)
    await assert.rejects(bridge.start(f.cwd, "x", "worker",
      { ...f.scope, writable_paths: ["../secret"] }, "x"), /Invalid writable path/)
    await assert.rejects(bridge.start(f.cwd, "x", "scout", f.scope, "x"), /scouts are read-only/)
    await assert.rejects(bridge.start(f.cwd, "x", "god", f.scope, "x"), /Unknown Pi tier/)
    writeFileSync(join(f.cwd, "untracked"), "bad")
    await assert.rejects(bridge.start(f.cwd, "x", "worker", f.scope, "x"), /clean/)
    assert.equal(commandCalls(m.calls).length, 0)
  } finally { f.close() }
})

test("Command correction resumes the same pinned Ember session, with a bounded attempt count", async () => {
  const f = fixture()
  try {
    const m = fake(f.cwd), bridge = makeHybridBridge(m.api, m.command)
    const task = await bridge.start(f.cwd, "mechanical", "mechanic", f.scope, "Edit README")
    m.done()
    await bridge.resume(f.cwd, task.session_id, "Recheck the change")
    const calls = commandCalls(m.calls)
    assert.equal(calls.length, 2)
    assert.ok(calls.every((x) => JSON.stringify(x).includes('"model":"meta/muse-ember"')))
    assert.ok(calls.every((x) => JSON.stringify(x).includes('"effort":"xhigh"')))
    assert.match(JSON.stringify(calls[1]), /"resume":"cmd-session"/)
    await assert.rejects(bridge.resume(f.cwd, task.session_id, "third attempt"), /attempt limit/)
  } finally { f.close() }
})

test("Command turn cap continuation does not consume the normal retry budget", async () => {
  const f = fixture()
  try {
    const m = fake(f.cwd)
    const command = { ...m.command, status: () =>
      ({ state: "turn_limit", result: { subtype: "max_turns" as const,
        sessionId: "cmd-session", finalText: "partial" }, stderr: null }) }
    const bridge = makeHybridBridge(m.api, command)
    const task = await bridge.start(f.cwd, "fix", "worker", { ...f.scope, attempt_limit: 1 }, "Edit README")
    const initial = await bridge.status(f.cwd, task.session_id)
    assert.equal(initial.continuations, 0)
    assert.equal(initial.continuation_limit, TURN_LIMIT_CONTINUATIONS)
    await bridge.resume(f.cwd, task.session_id, "continue")
    await bridge.resume(f.cwd, task.session_id, "continue")
    const continued = commandCalls(m.calls).filter((c) => JSON.stringify(c).includes("CONTINUE THE SAME TASK"))
    assert.equal(continued.length, 2)
    await assert.rejects(bridge.resume(f.cwd, task.session_id, "continue"), /continuation limit/)
    const final = await bridge.status(f.cwd, task.session_id)
    assert.equal(final.continuations, 2)
    assert.equal(final.continuation_limit, TURN_LIMIT_CONTINUATIONS)
  } finally { f.close() }
})

test("worker_steer interrupts a running Command Code run, proves termination, and resumes its session without an attempt", async () => {
  const f = fixture()
  try {
    const m = fake(f.cwd)
    const { command } = steerable(f, m)
    const bridge = makeHybridBridge(m.api, command)
    const task = await bridge.start(f.cwd, "one", "worker", { ...f.scope, attempt_limit: 1 }, "Edit README")
    const steered = await bridge.steer(f.cwd, task.session_id, "Also check the edge case")
    assert.equal(steered.status, "steered")
    assert.equal(steered.interrupted, true)
    assert.equal(steered.steers, 1)
    assert.equal(steered.steer_limit, STEER_LIMIT)
    const calls = commandCalls(m.calls)
    assert.equal(calls.length, 2)
    assert.match(JSON.stringify(calls[1]), /"resume":"cmd-session"/)
    assert.match(JSON.stringify(calls[1]),
      /PARENT STEERING \(same scope and write boundaries\): Also check the edge case/)
    assert.match(JSON.stringify(calls[1]), /You execute a single scoped task/)
    const saved = JSON.parse(readFileSync(
      join(f.root, ".work", "worker-bridge", task.session_id + ".json"), "utf8")) as { attempts: number; steers?: number }
    assert.equal(saved.attempts, 1)
    assert.equal(saved.steers, 1)
    await bridge.steer(f.cwd, task.session_id, "Second bounded steer")
    const status = await bridge.status(f.cwd, task.session_id)
    assert.equal(status.steers, 2)
    assert.equal(status.steer_limit, STEER_LIMIT)
    await assert.rejects(bridge.steer(f.cwd, task.session_id, "Third steer"), /Steer limit/)
    assert.equal(commandCalls(m.calls).length, 3)
  } finally { f.close() }
})

test("worker_steer refuses a finished Command Code session and points to worker_resume", async () => {
  const f = fixture()
  try {
    const m = fake(f.cwd), bridge = makeHybridBridge(m.api, m.command)
    const task = await bridge.start(f.cwd, "one", "worker", f.scope, "Edit README")
    m.done()
    await assert.rejects(bridge.steer(f.cwd, task.session_id, "late steering"), /use worker_resume/)
    assert.equal(commandCalls(m.calls).length, 1)
  } finally { f.close() }
})

test("worker_steer refuses changed HEAD and out-of-scope work exactly like resume", async () => {
  const f = fixture()
  try {
    const m = fake(f.cwd)
    const { command } = steerable(f, m)
    const bridge = makeHybridBridge(m.api, command)
    const task = await bridge.start(f.cwd, "one", "worker", f.scope, "Edit README")
    writeFileSync(join(f.cwd, "unrelated"), "bad\n")
    await assert.rejects(bridge.steer(f.cwd, task.session_id, "note"), /out-of-scope/)
    rmSync(join(f.cwd, "unrelated"))
    git(f.cwd, "commit", "--allow-empty", "-qm", "moved")
    await assert.rejects(bridge.steer(f.cwd, task.session_id, "note"), /changed HEAD/)
    assert.equal(commandCalls(m.calls).length, 1)
  } finally { f.close() }
})

test("worker_steer never restarts an interrupted Command Code run that has not terminated", async () => {
  const f = fixture()
  try {
    const m = fake(f.cwd)
    const { command, control } = steerable(f, m)
    control.alwaysRunning = true
    const bridge = makeHybridBridge(m.api, command)
    const task = await bridge.start(f.cwd, "one", "worker", f.scope, "Edit README")
    await assert.rejects(bridge.steer(f.cwd, task.session_id, "note"), /did not terminate/)
    assert.equal(commandCalls(m.calls).length, 1)
  } finally { f.close() }
})

test("worker_steer on the Pi backend forwards the note through the native steer path", async () => {
  const f = fixture()
  try {
    const m = fake(f.cwd)
    m.noCommand()
    m.setPiState("running")
    const bridge = makeHybridBridge(m.api, m.command)
    const task = await bridge.start(f.cwd, "one", "worker", f.scope, "Edit README")
    assert.equal(task.backend, "pi")
    const steered = await bridge.steer(f.cwd, task.session_id, "Use the new helper")
    assert.equal(steered.status, "steered")
    assert.equal(steered.interrupted, false)
    const call = m.calls.find((value) =>
      !!value && typeof value === "object" && "op" in value && (value as { op?: string }).op === "steer")
    assert.ok(call)
    assert.match(JSON.stringify(call),
      /PARENT STEERING \(same scope and write boundaries\):\\nUse the new helper/)
    const status = await bridge.status(f.cwd, task.session_id)
    assert.equal(status.steers, 1)
    assert.equal(status.steer_limit, STEER_LIMIT)
  } finally { f.close() }
})

test("a gone Command Code PID is terminal interrupted, releases its lease, and admits a new worker", async () => {
  const f = fixture()
  try {
    const logs = join(f.root, "logs")
    mkdirSync(logs)
    let starts = 0
    const command = {
      available: () => true,
      start: (): CommandRun => {
        starts++
        const output = join(logs, "out" + starts + ".ndjson"), errors = join(logs, "err" + starts + ".stderr")
        writeFileSync(output, ""); writeFileSync(errors, "")
        return { pid: 2 ** 22 + 11, output, errors, started_at: "2026-11-09", proc_start: "1" }
      },
      status: (run: CommandRun) => commandResult(run),
      cancel: () => false,
    }
    const bridge = makeHybridBridge(fake(f.cwd).api, command)
    const first = await bridge.start(f.cwd, "one", "worker", f.scope, "Edit README")
    const status = await bridge.status(f.cwd, first.session_id)
    assert.equal(status.state, "interrupted")
    assert.match(String(status.error), /process is gone|PID identity changed/)
    const second = await bridge.start(f.cwd, "two", "worker", f.scope, "Edit README")
    assert.notEqual(second.session_id, first.session_id)
    assert.equal(starts, 2)
  } finally { f.close() }
})

test("a live Command Code PID with a different start time is interrupted and releases its lease", async () => {
  const f = fixture()
  const child = spawn("sleep", ["30"], { stdio: "ignore" })
  try {
    const logs = join(f.root, "logs")
    mkdirSync(logs)
    let starts = 0
    const command = {
      available: () => true,
      start: (): CommandRun => {
        starts++
        const output = join(logs, "out" + starts + ".ndjson"), errors = join(logs, "err" + starts + ".stderr")
        writeFileSync(output, ""); writeFileSync(errors, "")
        return { pid: child.pid!, output, errors, started_at: "2026-11-09", proc_start: "0" }
      },
      status: (run: CommandRun) => commandResult(run),
      cancel: () => false,
    }
    const bridge = makeHybridBridge(fake(f.cwd).api, command)
    const first = await bridge.start(f.cwd, "one", "worker", f.scope, "Edit README")
    assert.equal((await bridge.status(f.cwd, first.session_id)).state, "interrupted")
    const second = await bridge.start(f.cwd, "two", "worker", f.scope, "Edit README")
    assert.notEqual(first.session_id, second.session_id)
  } finally {
    child.kill("SIGKILL")
    if (child.exitCode === null) await new Promise((resolve) => child.on("exit", resolve))
    f.close()
  }
})

test("a live Command Code PID with the recorded start time stays running and keeps the lease", async () => {
  const f = fixture()
  const child = spawn("sleep", ["30"], { stdio: "ignore" })
  try {
    const recorded = processStartTime(child.pid!)
    assert.ok(recorded)
    const logs = join(f.root, "logs")
    mkdirSync(logs)
    let starts = 0
    const command = {
      available: () => true,
      start: (): CommandRun => {
        starts++
        const output = join(logs, "out" + starts + ".ndjson"), errors = join(logs, "err" + starts + ".stderr")
        writeFileSync(output, ""); writeFileSync(errors, "")
        return { pid: child.pid!, output, errors, started_at: "2026-11-09", proc_start: recorded }
      },
      status: (run: CommandRun) => commandResult(run),
      cancel: () => false,
    }
    const bridge = makeHybridBridge(fake(f.cwd).api, command)
    const first = await bridge.start(f.cwd, "one", "worker", f.scope, "Edit README")
    assert.equal((await bridge.status(f.cwd, first.session_id)).state, "running")
    await assert.rejects(bridge.start(f.cwd, "two", "worker", f.scope, "Edit README"), /active worker/)
  } finally {
    child.kill("SIGKILL")
    if (child.exitCode === null) await new Promise((resolve) => child.on("exit", resolve))
    f.close()
  }
})

test("interrupted Command launch preserves a blocked transition and lease", async () => {
  const f = fixture()
  try {
    const m = fake(f.cwd)
    const command = { ...m.command, start: () => { throw new Error("cannot spawn cmd") } }
    const bridge = makeHybridBridge(m.api, command)
    await assert.rejects(bridge.start(f.cwd, "fix", "worker", f.scope, "Edit README"), /cannot spawn/)
    const files = readdirSync(join(f.root, ".work", "worker-bridge"))
      .filter((name) => /^usrw_.*\.json$/.test(name))
    assert.equal(files.length, 1)
    const id = files[0].replace(/\.json$/, "")
    const status = await bridge.status(f.cwd, id)
    assert.equal(status.backend, "command-transition")
    assert.equal(status.state, "blocked_transition")
    assert.equal(piCreates(m.calls).length, 0)
    await assert.rejects(bridge.resume(f.cwd, id, "retry"), /transition interrupted/)
  } finally { f.close() }
})

test("uncertain Pi fallback admission retains lease, never restarts Command", async () => {
  const f = fixture()
  try {
    const m = fake(f.cwd)
    m.noCommand()
    const api: OpenCodePort = { ...m.api, prompt: async () => { throw new Error("quota exhausted") } }
    const bridge = makeHybridBridge(api, m.command)
    await assert.rejects(bridge.start(f.cwd, "uncertain", "worker", f.scope, "Edit README"),
      /lease retained for session/)
    const ids = readdirSync(join(f.root, ".work", "worker-bridge"))
      .filter((name) => /^usrw_.*\.json$/.test(name))
    assert.equal(ids.length, 1)
    const id = ids[0].replace(/\.json$/, "")
    const restarted = makeHybridBridge(m.api, m.command)
    const status = await restarted.status(f.cwd, id)
    assert.equal(status.backend, "pi-transition")
    assert.equal(status.state, "blocked_admission")
    assert.equal(commandCalls(m.calls).length, 0)
    await assert.rejects(restarted.start(f.cwd, "another", "worker", f.scope, "Edit README"), /active worker/)
  } finally { f.close() }
})

test("overlapping starts lease the worktree before admitting the first Command run", async () => {
  const f = fixture()
  try {
    const m = fake(f.cwd), bridge = makeHybridBridge(m.api, m.command)
    const first = bridge.start(f.cwd, "one", "worker", f.scope, "Edit README")
    await assert.rejects(bridge.start(f.cwd, "two", "worker", f.scope, "Edit README"), /active worker/)
    const started = await first
    assert.equal(started.backend, "command-code")
    assert.equal(commandCalls(m.calls).length, 1)
  } finally { f.close() }
})

test("independent linked worktrees can admit separate Command runs", async () => {
  const f = fixture()
  try {
    const secondCwd = join(f.root, ".work", "wt", "b")
    git(f.root, "worktree", "add", "-qb", "lane-b", secondCwd)
    const m = fake(f.cwd), bridge = makeHybridBridge(m.api, m.command)
    const secondScope = { ...f.scope, base_revision: git(secondCwd, "rev-parse", "HEAD") }
    const [a, b] = await Promise.all([
      bridge.start(f.cwd, "one", "worker", f.scope, "Edit README"),
      bridge.start(secondCwd, "two", "worker", secondScope, "Edit README"),
    ])
    assert.notEqual(a.session_id, b.session_id)
    assert.equal(commandCalls(m.calls).length, 2)
  } finally { f.close() }
})

test("terminal Command runs release worktrees, but old sessions cannot race new owners", async () => {
  const f = fixture()
  try {
    const m = fake(f.cwd), bridge = makeHybridBridge(m.api, m.command)
    const first = await bridge.start(f.cwd, "one", "worker", f.scope, "Edit README")
    await assert.rejects(bridge.start(f.cwd, "two", "worker", f.scope, "Edit README"), /active worker/)
    m.done()
    assert.equal((await bridge.status(f.cwd, first.session_id)).state, "succeeded")
    const second = await bridge.start(f.cwd, "two", "worker", f.scope, "Edit README")
    assert.notEqual(first.session_id, second.session_id)
    await assert.rejects(bridge.resume(f.cwd, first.session_id, "retry"), /active for worker/)
  } finally { f.close() }
})

test("restart preserves an active Command admission until terminal status", async () => {
  const f = fixture()
  try {
    const m = fake(f.cwd)
    const first = await makeHybridBridge(m.api, m.command)
      .start(f.cwd, "one", "worker", f.scope, "Edit README")
    const restarted = makeHybridBridge(m.api, m.command)
    await assert.rejects(restarted.start(f.cwd, "two", "worker", f.scope, "Edit README"), /active worker/)
    m.done()
    assert.equal((await restarted.status(f.cwd, first.session_id)).state, "succeeded")
    const next = await restarted.start(f.cwd, "two", "worker", f.scope, "Edit README")
    assert.notEqual(next.session_id, first.session_id)
  } finally { f.close() }
})

test("cancel acknowledgement cannot release a lease until a terminal backend result", async () => {
  const f = fixture()
  try {
    const m = fake(f.cwd), bridge = makeHybridBridge(m.api, m.command)
    const first = await bridge.start(f.cwd, "one", "worker", f.scope, "Edit README")
    assert.equal((await bridge.cancel(f.cwd, first.session_id)).interrupted, true)
    await assert.rejects(bridge.start(f.cwd, "two", "worker", f.scope, "Edit README"), /active worker/)
    m.failCommand("ordinary failure")
    assert.equal((await bridge.status(f.cwd, first.session_id)).state, "failed")
    const second = await bridge.start(f.cwd, "two", "worker", f.scope, "Edit README")
    assert.notEqual(second.session_id, first.session_id)
  } finally { f.close() }
})

test("interrupted Pi resume remains blocked without exposing an old success", async () => {
  const f = fixture()
  try {
    const m = fake(f.cwd)
    m.noCommand()
    let prompts = 0
    const api: OpenCodePort = { ...m.api, prompt: async (input) => {
      prompts++
      if (prompts === 2) throw new Error("resume admission interrupted")
      return m.api.prompt(input)
    } }
    const bridge = makeHybridBridge(api, m.command)
    const first = await bridge.start(f.cwd, "one", "worker", f.scope, "Edit README")
    assert.equal((await bridge.status(f.cwd, first.session_id)).state, "succeeded")
    await assert.rejects(bridge.resume(f.cwd, first.session_id, "correct"), /resume admission interrupted/)
    const restarted = makeHybridBridge(m.api, m.command)
    const result = await restarted.status(f.cwd, first.session_id)
    assert.equal(result.backend, "pi-transition")
    assert.equal(result.state, "blocked_admission")
    await assert.rejects(restarted.start(f.cwd, "two", "worker", f.scope, "Edit README"), /active worker/)
    assert.equal(commandCalls(m.calls).length, 0)
  } finally { f.close() }
})

test("scout stays Command-first; the pinned Contributor lane is the Pi fallback", async () => {
  const f = fixture()
  try {
    const m = fake(f.cwd), bridge = makeHybridBridge(m.api, m.command)
    const check = await bridge.modelCheck(f.cwd, "scout")
    assert.equal(check.primary.backend, "command-code")
    assert.deepEqual(check.fallback.model, { providerID: "opencode-go", id: "muse-spark-1.3-contributor", variant: "medium" })
    const start = await bridge.start(f.cwd, "Contributor scout", "scout", { ...f.scope, writable_paths: [] }, "Inspect README")
    assert.equal(start.backend, "command-code")
    assert.equal(commandCalls(m.calls).length, 1)
    assert.equal(piCreates(m.calls).length, 0)
    const worker = await bridge.modelCheck(f.cwd, "worker")
    assert.equal(worker.primary.backend, "command-code")
  } finally {
    f.close()
  }
})

test("mechanic stays Command-first with Contributor pinned for Pi fallback", async () => {
  const f = fixture()
  try {
    const m = fake(f.cwd), bridge = makeHybridBridge(m.api, m.command)
    const start = await bridge.start(f.cwd, "Contributor mechanic", "mechanic", f.scope, "Update README")
    // With cmd primary, Go is fallback
    assert.equal(start.backend, "command-code")
  } finally {
    f.close()
  }
})

for (const edge of ["create", "prompt"] as const) {
  for (const route of ["initial", "status"] as const) {
    test(`USR-41: uncertain Muse ${edge} on ${route} retains lease and never admits twice`, async () => {
      const f = fixture()
      try {
        const m = fake(f.cwd)
        let creates = 0, prompts = 0
        const create = m.api.create
        m.api.create = async (input) => {
          creates++
          if (edge === "create") throw new Error("create response lost")
          return create(input)
        }
        m.api.prompt = async () => { prompts++; throw new Error("prompt response lost") }
        const bridge = makeHybridBridge(m.api, m.command)
        let id: string
        if (route === "initial") {
          m.noCommand()
          await assert.rejects(bridge.start(f.cwd, "uncertain", "worker", f.scope, "Edit README"), /lost|admission/)
          const state = join(f.root, ".work", "worker-bridge")
          id = readdirSync(state).find((x) => /^usrw_.*\.json$/.test(x))!.slice(0, -5)
        } else {
          id = (await bridge.start(f.cwd, "uncertain", "worker", f.scope, "Edit README")).session_id
          const path = join(f.root, ".work", "worker-bridge", id + ".json")
          const session = JSON.parse(readFileSync(path, "utf8"))
          delete session.primary_model
          writeFileSync(path, JSON.stringify(session))
          m.failCommand("provider unavailable")
        }
        assert.equal((await bridge.status(f.cwd, id)).state, "blocked_admission")
        assert.equal((await bridge.status(f.cwd, id)).state, "blocked_admission")
        assert.equal(creates, 1)
        assert.equal(prompts, edge === "prompt" ? 1 : 0)
        await assert.rejects(bridge.start(f.cwd, "duplicate", "worker", f.scope, "Edit README"), /active worker/)
      } finally { f.close() }
    })
  }
}

for (const tier of ["scout", "mechanic", "worker", "expert"] as const) {
  for (const route of ["initial", "status"] as const) {
    test(`USR-45: ${tier} ${route} skips unavailable Muse and persists exact Go pin`, async () => {
      const { GO_TIER_MODELS } = await import("../src/tier-policy.ts")
      const f = fixture()
      try {
        const m = fake(f.cwd)
        const models = m.api.models
        m.api.models = async (input) => {
          const catalog = await models(input) as { data: Array<{ providerID: string }> }
          return { data: catalog.data.filter((model) => model.providerID === "opencode-go") }
        }
        const bridge = makeHybridBridge(m.api, m.command)
        const scope = tier === "scout" ? { ...f.scope, writable_paths: [] } : f.scope
        if (route === "initial") m.noCommand()
        const started = await bridge.start(f.cwd, "go", tier, scope, "Provide proof")
        if (route === "status") m.failCommand("provider unavailable")
        const status = await bridge.status(f.cwd, started.session_id)
        assert.equal(status.backend, "pi")
        assert.deepEqual(status.model, GO_TIER_MODELS[tier])
        assert.equal(piCreates(m.calls).length, 1)
        const stored = JSON.parse(readFileSync(join(f.root, ".work", "worker-bridge", started.session_id + ".json"), "utf8"))
        assert.deepEqual(stored.primary_model, GO_TIER_MODELS[tier])
        assert.deepEqual(stored.remaining_pi, [])
        assert.deepEqual((await makeHybridBridge(m.api, m.command).status(f.cwd, started.session_id)).model, GO_TIER_MODELS[tier])
      } finally { f.close() }
    })
  }
}

for (const route of ["initial", "status"] as const) {
  test(`USR-41/45: ${route} Muse loss before create can advance to Go`, async () => {
    const f = fixture()
    try {
      const m = fake(f.cwd)
      const models = m.api.models
      let queries = 0
      m.api.models = async (input) => {
        queries++
        const catalog = await models(input) as { data: Array<{ providerID: string }> }
        return queries === 1 ? catalog : { data: catalog.data.filter((model) => model.providerID === "opencode-go") }
      }
      const bridge = makeHybridBridge(m.api, m.command)
      if (route === "initial") m.noCommand()
      const started = await bridge.start(f.cwd, "race", "worker", f.scope, "Provide proof")
      if (route === "status") m.failCommand("provider unavailable")
      const status = await bridge.status(f.cwd, started.session_id)
      assert.equal(status.backend, "pi")
      assert.deepEqual(status.model, { providerID: "opencode-go", id: "deepseek-v4.1-flash", variant: "high" })
      assert.equal(piCreates(m.calls).length, 1)
    } finally { f.close() }
  })
}
