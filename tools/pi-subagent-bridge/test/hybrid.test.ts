import test from "node:test"
import assert from "node:assert/strict"
import { execFileSync, spawn } from "node:child_process"
import { appendFileSync, mkdtempSync, mkdirSync, readdirSync, readFileSync, rmSync, writeFileSync, realpathSync } from "node:fs"
import { tmpdir } from "node:os"
import { join } from "node:path"
import { makeHybridBridge, type Scope } from "../src/hybrid.ts"
import { stateDir } from "../src/git.ts"
import { STEER_LIMIT, TURN_LIMIT_CONTINUATIONS } from "../src/session.ts"
import { startCodex, codexResult, cancelCodex, codexSession } from "../src/codex.ts"
import type { LaunchRequest } from "../src/launch.ts"
import { ANTIGRAVITY_PIN, ROOT_PLANS, type CliPin, type FallbackPlan, type RootPlan } from "../src/policy.ts"
import type { OpenCodePort } from "../src/bridge.ts"
import { activeWorktreeOwner, claimWorktree } from "../src/worktree-lease.ts"
import { commandResult, processStartTime, type CommandRun } from "../src/command.ts"

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

function recorded(request: LaunchRequest) {
  return { command: true, dir: request.directory, prompt: request.prompt, effort: request.selection.effort,
    readOnly: request.access.kind === "read-only", resume: request.resume, model: request.selection.model }
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
    messages: async () => ({ data: [{ type: "assistant", content: [{ type: "text", text: "PROOF: test exit 0\nACCEPTANCE: met" }] }] }),
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
    start: (request: LaunchRequest): CommandRun => {
      calls.push(recorded(request))
      return { pid: 123, output: "fake", errors: "fake", started_at: "2026-11-09" }
    },
    status: () => commandFailure ?
      { state: "failed", result: { subtype: "error" as const,
        sessionId: "cmd-session", error: commandFailure, finalText: commandFinalText ?? "failed" }, stderr: null } :
      commandDone ?
      { state: "succeeded", result: { subtype: "success" as const,
        sessionId: "cmd-session", finalText: "proof\nACCEPTANCE: met" }, stderr: null } :
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
const noCodex = { available: () => false, start: startCodex, status: codexResult, cancel: cancelCodex, session: codexSession }
const commandCalls = (calls: unknown[]) =>
  calls.filter((value) => !!value && typeof value === "object" && "command" in value)
const piCreates = (calls: unknown[]) =>
  calls.filter((value) => !!value && typeof value === "object" && "title" in value)

function steerable(f: ReturnType<typeof fixture>, m: ReturnType<typeof fake>) {
  const control = { cancelled: false, starts: 0, alwaysRunning: false }
  const command = {
    ...m.command,
    start: (request: LaunchRequest): CommandRun => {
      control.starts++
      const errors = join(f.root, "cmd-" + control.starts + ".stderr")
      writeFileSync(errors, "session: cmd-session\n")
      m.calls.push(recorded(request))
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

test("model check reports Codex primary and Command Code pins", async () => {
  const f = fixture()
  try {
    const m = fake(f.cwd), bridge = makeHybridBridge(m.api, m.command, noCodex)
    const expected = [
      ["scout", "meta/muse-ember", "medium"],
      ["mechanic", "meta/muse-ember", "xhigh"],
      ["worker", "deepseek/deepseek-v4.1-flash", "high"],
    ] as const
    for (const [tier, model, effort] of expected) {
      const status = await bridge.modelCheck(f.cwd, tier)
      assert.equal(status.primary.backend, "codex")
      assert.equal(status.primary.available, false)
      assert.ok(status.command_code)
      assert.equal(status.command_code.model, model)
      assert.equal(status.command_code.effort, effort)
      assert.equal(status.command_code.available, true)
    }
    assert.equal((await bridge.modelCheck(f.cwd, "expert")).primary.model, ANTIGRAVITY_PIN.model)
  } finally { f.close() }
})


function antigravityFake(pin: CliPin = ANTIGRAVITY_PIN) {
  const starts: Array<{ model: string; effort: string; resume?: string; readOnly: boolean }> = []
  let available = true
  let failed = false
  const run: CommandRun = { pid: 9012, output: "fake", errors: "fake", started_at: "now" }
  return {
    starts,
    setAvailable: (value: boolean) => { available = value },
    fail: () => { failed = true },
    runner: {
      available: () => available,
      start: (request: LaunchRequest): CommandRun => {
        const { model, effort } = request.selection
        if (model !== pin.model || effort !== pin.effort || request.access.kind === "read-only") throw new Error("Unapproved Antigravity dispatch")
        starts.push({ model, effort, readOnly: false, resume: request.resume })
        return run
      },
      status: (_run?: CommandRun, admitted?: CliPin) => {
        if (admitted) assert.deepEqual(admitted, pin)
        return failed ?
        { state: "failed", result: { subtype: "error" as const, sessionId: "7ce10216-708a-4ba7-9128-53789b2ce8ad", error: "429 quota exhausted" }, stderr: null } :
        { state: "succeeded", result: { subtype: "success" as const, sessionId: "7ce10216-708a-4ba7-9128-53789b2ce8ad", finalText: "PROOF\nACCEPTANCE: met" }, stderr: null }
      },
      cancel: () => true,
      session: () => "7ce10216-708a-4ba7-9128-53789b2ce8ad",
    },
  }
}

test("expert uses only pinned Antigravity XHigh, persists it, and never falls back on quota", async () => {
  const f = fixture()
  try {
    const m = fake(f.cwd), antigravity = antigravityFake()
    const bridge = makeHybridBridge(m.api, m.command, noCodex, antigravity.runner)
    const check = await bridge.modelCheck(f.cwd, "expert")
    assert.deepEqual(check.primary, { backend: "antigravity", model: ANTIGRAVITY_PIN.model, effort: ANTIGRAVITY_PIN.effort, available: true })
    assert.equal(check.fallback, null)
    const task = await bridge.start(f.cwd, "expert", "expert", f.scope, "Inspect source and prove behavior")
    assert.equal(task.backend, "antigravity")
    assert.deepEqual(antigravity.starts, [{ model: ANTIGRAVITY_PIN.model, effort: "xhigh", readOnly: false, resume: undefined }])
    const persisted = JSON.parse(readFileSync(join(f.root, ".work", "worker-bridge", task.session_id + ".json"), "utf8"))
    assert.equal(persisted.backend, "antigravity")
    assert.equal(persisted.tier, "expert")
    assert.deepEqual(persisted.plan, { kind: "exclusive", target: ANTIGRAVITY_PIN })
    assert.equal(persisted.execution.kind, "process")
    antigravity.fail()
    const status = await bridge.status(f.cwd, task.session_id)
    assert.equal(status.state, "failed")
    assert.equal(status.model, ANTIGRAVITY_PIN.model)
    assert.equal(status.fallback_reason, null)
    assert.equal(antigravity.starts.length, 1)
    assert.equal(commandCalls(m.calls).length, 0)
    assert.equal(piCreates(m.calls).length, 0)
  } finally { f.close() }
})

test("unavailable Antigravity blocks expert before starting any other model or claiming a lease", async () => {
  const f = fixture()
  try {
    const m = fake(f.cwd), antigravity = antigravityFake()
    antigravity.setAvailable(false)
    const bridge = makeHybridBridge(m.api, m.command, noCodex, antigravity.runner)
    await assert.rejects(bridge.start(f.cwd, "expert", "expert", f.scope, "Work"), /Antigravity model .* unavailable.*No fallback/)
    assert.equal(antigravity.starts.length, 0)
    assert.equal(commandCalls(m.calls).length, 0)
    assert.equal(piCreates(m.calls).length, 0)
    const task = await bridge.start(f.cwd, "safe", "worker", f.scope, "Work")
    assert.equal(task.backend, "command-code")
  } finally { f.close() }
})

test("Antigravity corrections preserve the exact model and conversation", async () => {
  const f = fixture()
  try {
    const m = fake(f.cwd), antigravity = antigravityFake()
    const bridge = makeHybridBridge(m.api, m.command, noCodex, antigravity.runner)
    const task = await bridge.start(f.cwd, "review", "expert", f.scope, "Work")
    assert.equal((await bridge.status(f.cwd, task.session_id)).state, "succeeded")
    await bridge.resume(f.cwd, task.session_id, "Verify a second edge case")
    assert.deepEqual(antigravity.starts[1], { model: ANTIGRAVITY_PIN.model, effort: "xhigh", readOnly: false,
      resume: "7ce10216-708a-4ba7-9128-53789b2ce8ad" })
  } finally { f.close() }
})

test("a restarted expert keeps its admitted model when current policy changes", async () => {
  const f = fixture()
  try {
    const oldPin: CliPin = { model: "fixture-expert-v1", effort: "high" }
    const newPin: CliPin = { model: "fixture-expert-v2", effort: "xhigh" }
    const m = fake(f.cwd), executor = antigravityFake(oldPin)
    const before = makeHybridBridge(m.api, m.command, noCodex, executor.runner,
      () => ({ kind: "exclusive", target: oldPin }))
    const task = await before.start(f.cwd, "snapshot", "expert", f.scope, "Verify the pin")
    const stored = JSON.parse(readFileSync(join(f.root, ".work", "worker-bridge", task.session_id + ".json"), "utf8"))
    assert.deepEqual(stored.plan, { kind: "exclusive", target: oldPin })
    assert.deepEqual(stored.execution.selection, oldPin)
    assert.equal(stored.schema_version, 2)
    const after = makeHybridBridge(m.api, m.command, noCodex, executor.runner,
      () => ({ kind: "exclusive", target: newPin }))
    assert.equal((await after.modelCheck(f.cwd, "expert")).primary.model, "fixture-expert-v2")
    assert.equal((await after.status(f.cwd, task.session_id)).model, "fixture-expert-v1")
    await after.resume(f.cwd, task.session_id, "Recheck the same work")
    assert.deepEqual(executor.starts.map(({ model, effort }) => ({ model, effort })), [oldPin, oldPin])
    assert.equal(commandCalls(m.calls).length, 0)
  } finally { f.close() }
})

for (const executor of ["codex", "command-code"] as const) {
  test(`a restarted ${executor} retains its admitted pair after a policy change`, async () => {
    const f = fixture()
    try {
      const oldPin: CliPin = { model: "fixture-before", effort: "high" }
      const newPin: CliPin = { model: "fixture-after", effort: "medium" }
      const plan: FallbackPlan = ROOT_PLANS.worker
      const withPin = (pin: CliPin): RootPlan => ({ ...plan, [executor === "codex" ? "codex" : "command"]: pin })
      const m = fake(f.cwd)
      const codex = executor === "codex" ? { ...m.command, session: () => "cmd-session" } : noCodex
      const before = makeHybridBridge(m.api, m.command, codex, undefined, () => withPin(oldPin))
      const task = await before.start(f.cwd, "snapshot", "worker", f.scope, "Verify the pin")
      assert.equal(task.backend, executor)
      m.done()
      const after = makeHybridBridge(m.api, m.command, codex, undefined, () => withPin(newPin))
      assert.equal((await after.status(f.cwd, task.session_id)).model, "fixture-before")
      await after.resume(f.cwd, task.session_id, "Recheck the same work")
      const launches = commandCalls(m.calls)
      assert.equal(launches.length, 2)
      for (const launch of launches) {
        assert.match(JSON.stringify(launch), /"model":"fixture-before"/)
        assert.match(JSON.stringify(launch), /"effort":"high"/)
      }
    } finally { f.close() }
  })
}

test("pending Pi fallback uses its admitted plan after restart, not the new policy", async () => {
  const f = fixture()
  try {
    const m = fake(f.cwd)
    const before = makeHybridBridge(m.api, m.command, noCodex)
    const task = await before.start(f.cwd, "snapshot", "scout", { ...f.scope, writable_paths: [] }, "Inspect README")
    m.failCommand("quota exhausted")
    const changedPlan: FallbackPlan = ROOT_PLANS.scout
    const after = makeHybridBridge(m.api, m.command, noCodex, undefined,
      () => ({ ...changedPlan, pi: [{ providerID: "opencode-go", id: "unavailable-new-model", variant: "high" }] }))
    const status = await after.status(f.cwd, task.session_id)
    assert.equal(status.backend, "pi")
    assert.deepEqual(status.model, { providerID: "opencode-go", id: "muse-spark-1.3-contributor", variant: "medium" })
    assert.equal(piCreates(m.calls).length, 1)
  } finally { f.close() }
})

test("Command Code scout and mechanic use Ember medium and xhigh, even when Go has no models", async () => {
  for (const [tier, effort] of [["scout", "medium"], ["mechanic", "xhigh"]] as const) {
    const f = fixture()
    try {
      const m = fake(f.cwd), bridge = makeHybridBridge(m.api, m.command, noCodex)
      m.omitGo()
      const scope = tier === "scout" ? { ...f.scope, writable_paths: [] } : f.scope
      const started = await bridge.start(f.cwd, tier, tier, scope, "Provide evidence")
      assert.equal(started.backend, "command-code")
      assert.match(started.fallback_reason ?? "", /Codex subscription unavailable/)
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
      const m = fake(f.cwd), bridge = makeHybridBridge(m.api, m.command, noCodex)
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
    const m = fake(f.cwd), bridge = makeHybridBridge(m.api, m.command, noCodex)
    const started = await bridge.start(f.cwd, "fix", "worker", f.scope, "Edit README")
    m.failCommand("quota exceeded, allowance exhausted")
    const result = await bridge.status(f.cwd, started.session_id)
    assert.equal(result.backend, "pi")
    assert.equal(result.state, "succeeded")
    assert.equal(result.error, null)
    assert.equal(commandCalls(m.calls).length, 1)
    assert.equal(piCreates(m.calls).length, 1)
  } finally { f.close() }
})

test("explicit model-not-found error allows a single Go fallback", async () => {
  const f = fixture()
  try {
    const m = fake(f.cwd), bridge = makeHybridBridge(m.api, m.command, noCodex)
    const task = await bridge.start(f.cwd, "read", "scout", { ...f.scope, writable_paths: [] }, "Locate evidence")
    m.failCommand("model not found")
    const status = await bridge.status(f.cwd, task.session_id)
    assert.equal(status.backend, "pi")
  } finally { f.close() }
})

test("quota in task prose is not a provider error and never causes fallback", async () => {
  const f = fixture()
  try {
    const m = fake(f.cwd), bridge = makeHybridBridge(m.api, m.command, noCodex)
    const task = await bridge.start(f.cwd, "fix", "worker", f.scope, "Edit README")
    m.failCommand("ordinary task failure", "The project's quota assertion failed")
    const status = await bridge.status(f.cwd, task.session_id)
    assert.equal(status.backend, "command-code")
    assert.equal(status.state, "failed")
    assert.match(status.fallback_reason ?? "", /Codex subscription unavailable/)
    assert.equal(piCreates(m.calls).length, 0)
  } finally { f.close() }
})

test("Command quota after edits cannot replay partial work on Go", async () => {
  const f = fixture()
  try {
    const m = fake(f.cwd), bridge = makeHybridBridge(m.api, m.command, noCodex)
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

test("cancel releases a blocked_partial_work lease after the parent preserves the work", async () => {
  const f = fixture()
  try {
    const m = fake(f.cwd), bridge = makeHybridBridge(m.api, m.command, noCodex)
    const task = await bridge.start(f.cwd, "fix", "worker", f.scope, "Edit README")
    writeFileSync(join(f.cwd, "README"), "partial\n")
    m.failCommand("rate limit exceeded")
    const blocked = await bridge.status(f.cwd, task.session_id)
    assert.equal(blocked.state, "blocked_partial_work")
    const leaseDir = stateDir(f.cwd)
    assert.equal(activeWorktreeOwner(leaseDir, f.cwd), task.session_id)
    const cancel = await bridge.cancel(f.cwd, task.session_id)
    assert.equal(cancel.released, true)
    assert.equal(cancel.interrupted, false)
    assert.equal(activeWorktreeOwner(leaseDir, f.cwd), null)
    assert.equal((await bridge.status(f.cwd, task.session_id)).state, "cancelled")
    git(f.cwd, "checkout", "--", "README")
    const again = await bridge.start(f.cwd, "next", "worker", f.scope, "Edit README")
    assert.ok(again.session_id)
  } finally { f.close() }
})

test("unavailable Go fallback blocks and stays blocked without polling retries", async () => {
  const f = fixture()
  try {
    const m = fake(f.cwd), bridge = makeHybridBridge(m.api, m.command, noCodex)
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
    const m = fake(f.cwd), bridge = makeHybridBridge(m.api, m.command, noCodex)
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
    const m = fake(f.cwd), bridge = makeHybridBridge(m.api, m.command, noCodex)
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
    const bridge = makeHybridBridge(m.api, command, noCodex)
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
    const m = fake(f.cwd), bridge = makeHybridBridge(m.api, m.command, noCodex)
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
    const m = fake(f.cwd), bridge = makeHybridBridge(m.api, m.command, noCodex)
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
    const m = fake(f.cwd), bridge = makeHybridBridge(m.api, m.command, noCodex)
    await assert.rejects(bridge.start(f.cwd, "x", "worker",
      { ...f.scope, writable_paths: ["../secret"] }, "x"), /Invalid writable path/)
    await assert.rejects(bridge.start(f.cwd, "x", "scout", f.scope, "x"), /scouts are read-only/)
    await assert.rejects(bridge.start(f.cwd, "x", "titan", f.scope, "x"), /Unknown Pi tier/)
    writeFileSync(join(f.cwd, "untracked"), "bad")
    await assert.rejects(bridge.start(f.cwd, "x", "worker", f.scope, "x"), /clean/)
    assert.equal(commandCalls(m.calls).length, 0)
  } finally { f.close() }
})

test("Command correction resumes the same pinned Ember session, with a bounded attempt count", async () => {
  const f = fixture()
  try {
    const m = fake(f.cwd), bridge = makeHybridBridge(m.api, m.command, noCodex)
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
    const bridge = makeHybridBridge(m.api, command, noCodex)
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
    const bridge = makeHybridBridge(m.api, command, noCodex)
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
    const m = fake(f.cwd), bridge = makeHybridBridge(m.api, m.command, noCodex)
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
    const bridge = makeHybridBridge(m.api, command, noCodex)
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
    const bridge = makeHybridBridge(m.api, command, noCodex)
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
    const bridge = makeHybridBridge(m.api, m.command, noCodex)
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
    const bridge = makeHybridBridge(fake(f.cwd).api, command, noCodex)
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
    const bridge = makeHybridBridge(fake(f.cwd).api, command, noCodex)
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
    const bridge = makeHybridBridge(fake(f.cwd).api, command, noCodex)
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
    const bridge = makeHybridBridge(m.api, command, noCodex)
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
    const bridge = makeHybridBridge(api, m.command, noCodex)
    await assert.rejects(bridge.start(f.cwd, "uncertain", "worker", f.scope, "Edit README"),
      /lease retained for session/)
    const ids = readdirSync(join(f.root, ".work", "worker-bridge"))
      .filter((name) => /^usrw_.*\.json$/.test(name))
    assert.equal(ids.length, 1)
    const id = ids[0].replace(/\.json$/, "")
    const restarted = makeHybridBridge(m.api, m.command, noCodex)
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
    const m = fake(f.cwd), bridge = makeHybridBridge(m.api, m.command, noCodex)
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
    const m = fake(f.cwd), bridge = makeHybridBridge(m.api, m.command, noCodex)
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
    const m = fake(f.cwd), bridge = makeHybridBridge(m.api, m.command, noCodex)
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
    const first = await makeHybridBridge(m.api, m.command, noCodex)
      .start(f.cwd, "one", "worker", f.scope, "Edit README")
    const restarted = makeHybridBridge(m.api, m.command, noCodex)
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
    const m = fake(f.cwd), bridge = makeHybridBridge(m.api, m.command, noCodex)
    const first = await bridge.start(f.cwd, "one", "worker", f.scope, "Edit README")
    assert.equal((await bridge.cancel(f.cwd, first.session_id)).interrupted, true)
    await assert.rejects(bridge.start(f.cwd, "two", "worker", f.scope, "Edit README"), /active worker/)
    m.failCommand("ordinary failure")
    assert.equal((await bridge.status(f.cwd, first.session_id)).state, "cancelled")
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
    const bridge = makeHybridBridge(api, m.command, noCodex)
    const first = await bridge.start(f.cwd, "one", "worker", f.scope, "Edit README")
    assert.equal((await bridge.status(f.cwd, first.session_id)).state, "succeeded")
    await assert.rejects(bridge.resume(f.cwd, first.session_id, "correct"), /resume admission interrupted/)
    const restarted = makeHybridBridge(m.api, m.command, noCodex)
    const result = await restarted.status(f.cwd, first.session_id)
    assert.equal(result.backend, "pi-transition")
    assert.equal(result.state, "blocked_admission")
    await assert.rejects(restarted.start(f.cwd, "two", "worker", f.scope, "Edit README"), /active worker/)
    assert.equal(commandCalls(m.calls).length, 0)
  } finally { f.close() }
})

test("scout uses Command when Codex is unavailable and retains the Contributor fallback", async () => {
  const f = fixture()
  try {
    const m = fake(f.cwd), bridge = makeHybridBridge(m.api, m.command, noCodex)
    const check = await bridge.modelCheck(f.cwd, "scout")
    assert.equal(check.primary.backend, "codex")
    assert.ok(check.pi_fallback)
    assert.deepEqual(check.pi_fallback.model, { providerID: "opencode-go", id: "muse-spark-1.3-contributor", variant: "medium" })
    const start = await bridge.start(f.cwd, "Contributor scout", "scout", { ...f.scope, writable_paths: [] }, "Inspect README")
    assert.equal(start.backend, "command-code")
    assert.equal(commandCalls(m.calls).length, 1)
    assert.equal(piCreates(m.calls).length, 0)
    const worker = await bridge.modelCheck(f.cwd, "worker")
    assert.equal(worker.primary.backend, "codex")
  } finally {
    f.close()
  }
})

test("mechanic uses Command when Codex is unavailable and retains Contributor fallback", async () => {
  const f = fixture()
  try {
    const m = fake(f.cwd), bridge = makeHybridBridge(m.api, m.command, noCodex)
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
        const bridge = makeHybridBridge(m.api, m.command, noCodex)
        let id: string
        if (route === "initial") {
          m.noCommand()
          await assert.rejects(bridge.start(f.cwd, "uncertain", "worker", f.scope, "Edit README"), /lost|admission/)
          const state = join(f.root, ".work", "worker-bridge")
          id = readdirSync(state).find((x) => /^usrw_.*\.json$/.test(x))!.slice(0, -5)
        } else {
          id = (await bridge.start(f.cwd, "uncertain", "worker", f.scope, "Edit README")).session_id
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

for (const tier of ["scout", "mechanic", "worker"] as const) {
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
        const bridge = makeHybridBridge(m.api, m.command, noCodex)
        const scope = tier === "scout" ? { ...f.scope, writable_paths: [] } : f.scope
        if (route === "initial") m.noCommand()
        const started = await bridge.start(f.cwd, "go", tier, scope, "Provide proof")
        if (route === "status") m.failCommand("provider unavailable")
        const status = await bridge.status(f.cwd, started.session_id)
        assert.equal(status.backend, "pi")
        assert.deepEqual(status.model, GO_TIER_MODELS[tier])
        assert.equal(piCreates(m.calls).length, 1)
        const stored = JSON.parse(readFileSync(join(f.root, ".work", "worker-bridge", started.session_id + ".json"), "utf8"))
        assert.deepEqual(stored.execution.selection, GO_TIER_MODELS[tier])
        assert.deepEqual(stored.plan.pi.at(-1), GO_TIER_MODELS[tier])
        assert.deepEqual((await makeHybridBridge(m.api, m.command, noCodex).status(f.cwd, started.session_id)).model, GO_TIER_MODELS[tier])
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
      const bridge = makeHybridBridge(m.api, m.command, noCodex)
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


test("Codex is first for standard tiers and a pre-edit quota failure advances to Command Code", async () => {
  for (const tier of ["scout", "mechanic", "worker"] as const) {
    const f = fixture()
    try {
      const m = fake(f.cwd)
      let fail = false
      const codex = { ...noCodex, available: () => true,
        start: (request: LaunchRequest) => { m.calls.push({ codex: request }); return { pid: 123, output: "fake", errors: "fake", started_at: "now" } },
        status: () => fail ? { state: "failed", result: { subtype: "error" as const, error: "429 quota" }, stderr: null } : { state: "running", result: null, stderr: null } }
      const bridge = makeHybridBridge(m.api, m.command, codex)
      assert.equal((await bridge.modelCheck(f.cwd, tier)).primary.backend, "codex")
      const scope = tier === "scout" ? { ...f.scope, writable_paths: [] } : f.scope
      const started = await bridge.start(f.cwd, tier, tier, scope, "Do scoped work")
      assert.equal(started.backend, "codex")
      assert.equal(commandCalls(m.calls).length, 0)
      fail = true
      const state = await bridge.status(f.cwd, started.session_id)
      assert.equal(state.backend, "command-code")
      assert.equal(commandCalls(m.calls).length, 1)
    } finally { f.close() }
  }
})

test("Codex quota failure after an edit does not replay the task", async () => {
  const f = fixture()
  try {
    const m = fake(f.cwd)
    const codex = { ...noCodex, available: () => true,
      start: () => ({ pid: 123, output: "fake", errors: "fake", started_at: "now" }),
      status: () => ({ state: "failed", result: { subtype: "error" as const, error: "429 quota" }, stderr: null }) }
    const bridge = makeHybridBridge(m.api, m.command, codex)
    const started = await bridge.start(f.cwd, "edit", "worker", f.scope, "Do scoped work")
    writeFileSync(join(f.cwd, "README"), "partial")
    assert.equal((await bridge.status(f.cwd, started.session_id)).state, "blocked_partial_work")
    assert.equal(commandCalls(m.calls).length, 0)
  } finally { f.close() }
})

test("an interrupted Codex run never triggers fallback", async () => {
  const f = fixture()
  try {
    const m = fake(f.cwd)
    const codex = { ...noCodex, available: () => true,
      start: () => ({ pid: 123, output: "fake", errors: "fake", started_at: "now" }),
      status: () => ({ state: "interrupted", result: null, stderr: "429 quota" }) }
    const bridge = makeHybridBridge(m.api, m.command, codex)
    const started = await bridge.start(f.cwd, "edit", "worker", f.scope, "Do scoped work")
    assert.equal((await bridge.status(f.cwd, started.session_id)).state, "interrupted")
    assert.equal(commandCalls(m.calls).length, 0)
  } finally { f.close() }
})

test("Codex correction resumes the same thread and pinned model", async () => {
  const f = fixture()
  try {
    const m = fake(f.cwd), starts: LaunchRequest[] = []
    const codex = { ...noCodex, available: () => true,
      start: (request: LaunchRequest) => { starts.push(request); return { pid: 123, output: "fake", errors: "fake", started_at: "now" } },
      status: () => ({ state: "succeeded", result: { subtype: "success" as const, sessionId: "codex-thread", finalText: "proof" }, stderr: null }) }
    const bridge = makeHybridBridge(m.api, m.command, codex)
    const started = await bridge.start(f.cwd, "edit", "worker", f.scope, "Do scoped work")
    await bridge.status(f.cwd, started.session_id)
    await bridge.resume(f.cwd, started.session_id, "Correct the same file")
    assert.equal(starts.length, 2)
    assert.equal(starts[1].resume, "codex-thread")
    assert.deepEqual(starts[1].selection, { model: "gpt-6.1-terra", effort: "medium" })
  } finally { f.close() }
})

test("Codex quota failure skips missing Command Code and goes to Pi", async () => {
  const f = fixture()
  try {
    const m = fake(f.cwd)
    m.noCommand()
    const codex = { ...noCodex, available: () => true,
      start: () => ({ pid: 123, output: "fake", errors: "fake", started_at: "now" }),
      status: () => ({ state: "failed", result: { subtype: "error" as const, error: "429 quota" }, stderr: null }) }
    const bridge = makeHybridBridge(m.api, m.command, codex)
    const started = await bridge.start(f.cwd, "research", "scout", { ...f.scope, writable_paths: [] }, "Find proof")
    assert.equal((await bridge.status(f.cwd, started.session_id)).backend, "pi")
    assert.equal(piCreates(m.calls).length, 1)
  } finally { f.close() }
})

test("an acknowledged Codex cancellation does not fall back on a quota-shaped failure", async () => {
  const f = fixture()
  try {
    const m = fake(f.cwd)
    let cancelled = false
    const codex = { ...noCodex, available: () => true,
      start: () => ({ pid: 123, output: "fake", errors: "fake", started_at: "now" }),
      cancel: () => { cancelled = true; return true },
      status: () => cancelled ? { state: "failed", result: { subtype: "error" as const, error: "429 quota" }, stderr: null } : { state: "running", result: null, stderr: null } }
    const bridge = makeHybridBridge(m.api, m.command, codex)
    const started = await bridge.start(f.cwd, "edit", "worker", f.scope, "Do scoped work")
    assert.equal((await bridge.cancel(f.cwd, started.session_id)).interrupted, true)
    assert.equal((await bridge.status(f.cwd, started.session_id)).state, "cancelled")
    assert.equal(commandCalls(m.calls).length, 0)
  } finally { f.close() }
})

test("a run without a final ACCEPTANCE: met line is incomplete", async () => {
  for (const [finalText, state, claim] of [
    ["proof\nACCEPTANCE: met", "succeeded", "met"],
    ["proof\n**ACCEPTANCE: not met**", "incomplete", "not_met"],
    ["partial, no blocker", "incomplete", "missing"],
  ] as const) {
    const f = fixture()
    try {
      const m = fake(f.cwd), starts: LaunchRequest[] = []
      const codex = { ...noCodex, available: () => true,
        start: (request: LaunchRequest) => { starts.push(request); return { pid: 123, output: "fake", errors: "fake", started_at: "now" } },
        status: () => ({ state: "succeeded", result: { subtype: "success" as const, sessionId: "t", finalText }, stderr: null }) }
      const bridge = makeHybridBridge(m.api, m.command, codex)
      const started = await bridge.start(f.cwd, "edit", "worker", f.scope, "Do scoped work")
      assert.match(started.watch, /^pi-subagent-bridge watch ".+" usrw_/)
      assert.deepEqual(starts[0].access, { kind: "write" })
      const status = await bridge.status(f.cwd, started.session_id)
      assert.equal(status.state, state)
      assert.equal(status.acceptance_claim, claim)
      assert.equal(status.acceptance_blocked, claim !== "met")
    } finally { f.close() }
  }
})

test("the retired network scope flag is rejected for new work", async () => {
  const f = fixture()
  try {
    const m = fake(f.cwd)
    const bridge = makeHybridBridge(m.api, m.command, { ...noCodex, available: () => true })
    await assert.rejects(bridge.start(f.cwd, "edit", "worker", { ...f.scope, network: true }, "Edit"), /Unknown scope field: network/)
  } finally { f.close() }
})

test("an order-less legacy Pi record still falls back to Command Code on a provider usage limit before edits", async () => {
  const f = fixture()
  try {
    const m = fake(f.cwd)
    const state = join(f.root, ".work", "worker-bridge")
    mkdirSync(state, { recursive: true })
    const id = "usrw_01234567-89ab-cdef-0123-456789abcdef"
    writeFileSync(join(state, id + ".json"), JSON.stringify({
      id, cwd: f.cwd, tier: "worker", title: "Legacy Pi lane", task: "Edit README", scope: f.scope, backend: "pi", attempts: 1,
      pi_id: "ses_fixture", primary_model: { providerID: "opencode-go", id: "deepseek-v4.1-flash", variant: "high" },
      command_model: "deepseek/deepseek-v4.1-flash", command_effort: "high", remaining_pi: [],
    }))
    claimWorktree(state, f.cwd, id)
    m.failPi("429 quota exhausted")
    const status = await makeHybridBridge(m.api, m.command, noCodex).status(f.cwd, id)
    assert.equal(status.backend, "command-code")
    assert.equal(status.state, "running")
    assert.match(status.fallback_reason ?? "", /Primary Pi runner unavailable/)
    assert.equal(commandCalls(m.calls).length, 1)
  } finally { f.close() }
})
