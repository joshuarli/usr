import test from "node:test"
import assert from "node:assert/strict"
import { execFileSync } from "node:child_process"
import { appendFileSync, mkdtempSync, mkdirSync, rmSync, writeFileSync, realpathSync } from "node:fs"
import { tmpdir } from "node:os"
import { join } from "node:path"
import { makeHybridBridge, type Scope } from "../src/hybrid.ts"
import { type OpenCodePort } from "../src/bridge.ts"
import { type CommandRun } from "../src/command.ts"

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
  const scope: Scope = { base_revision: git(cwd, "rev-parse", "HEAD"), writable_paths: ["README"],
    acceptance_proof: "Run a focused verifier; report exact command, exit code and output",
    attempt_limit: 2, stop_on: "Unexpected dependencies or contract changes" }
  return { root, cwd, scope, close: () => rmSync(root, { recursive: true, force: true }) }
}
function fake(cwd: string) {
  const calls: unknown[] = []
  let status = "succeeded", assistant = "PROOF: test exit 0", error: unknown = null
  let variants = ["medium", "high", "max"]
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
    models: async () => ({ data: ["deepseek-v4.1-flash", "muse-spark-1.3-contributor"].map((id) => ({
      id, providerID: "opencode-go",
      variants: variants.map((variant) => ({ id: variant })), enabled: true, status: "active",
    })) }),
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

test("every Pi tier pins exactly the requested provider, model, and effort", async () => {
  const f = fixture()
  try {
    const m = fake(f.cwd), bridge = makeHybridBridge(m.api, m.command)
    const expected = [
      ["scout", "muse-spark-1.3-contributor", "medium", "low"],
      ["mechanic", "muse-spark-1.3-contributor", "high", "high"],
      ["worker", "deepseek-v4.1-flash", "high", "high"],
      ["expert", "deepseek-v4.1-flash", "max", "max"],
    ] as const
    for (const [tier, id, variant, fallbackEffort] of expected) {
      const found = await bridge.modelCheck(f.cwd, tier)
      assert.deepEqual(found.primary.model, { providerID: "opencode-go", id, variant })
      assert.equal(found.primary.available, true)
      assert.equal(found.fallback.effort, fallbackEffort)
      assert.equal(found.fallback.model, "deepseek/deepseek-v4.1-flash")
    }
    await assert.rejects(bridge.modelCheck(f.cwd, "god"), /Unknown Pi tier/)
  } finally { f.close() }
})

test("OpenCode Go high runs a scoped worker; out-of-scope edits block acceptance", async () => {
  const f = fixture()
  try {
    const m = fake(f.cwd), bridge = makeHybridBridge(m.api, m.command)
    const task = await bridge.start(f.cwd, "fix", "worker", f.scope, "Edit README")
    assert.equal(task.backend, "pi")
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
    assert.match(task.fallback_notice ?? "", /needs no parent action/)
    assert.ok(m.calls.some((c) => JSON.stringify(c).includes('"readOnly":true')))
    assert.ok(m.calls.some((c) => JSON.stringify(c).includes('"effort":"low"')))
    m.done()
    assert.equal((await bridge.status(f.cwd, task.session_id)).state, "succeeded")
    await bridge.resume(f.cwd, task.session_id, "Give file:line evidence")
    assert.ok(m.calls.some((c) => JSON.stringify(c).includes('"resume":"cmd-session"')))
    await assert.rejects(bridge.resume(f.cwd, task.session_id, "third attempt"), /attempt limit/)
  } finally { f.close() }
})
test("an OpenCode server that cannot start admits the task on Command Code", async () => {
  const f = fixture()
  try {
    const m = fake(f.cwd)
    const api: OpenCodePort = { ...m.api, models: async () => { throw new Error("Failed to start server") } }
    const task = await makeHybridBridge(api, m.command).start(f.cwd, "fix", "worker", f.scope, "Edit README")
    assert.equal(task.backend, "command-code")
    assert.ok(m.calls.some((c) => JSON.stringify(c).includes('"effort":"high"')))
    assert.ok(!m.calls.some((c) => JSON.stringify(c).includes("ses_fixture")))
  } finally { f.close() }
})
test("a prompt rejected for quota right after admission starts on Command Code without a status poll", async () => {
  const f = fixture()
  try {
    const m = fake(f.cwd)
    const api: OpenCodePort = { ...m.api, prompt: async (input) => { m.calls.push(input); m.fail("weekly usage limit reached"); return {} } }
    const task = await makeHybridBridge(api, m.command).start(f.cwd, "fix", "worker", f.scope, "Edit README")
    assert.equal(task.backend, "command-code")
    assert.match(task.fallback_reason ?? "", /continued on Command Code/)
    assert.match(task.fallback_notice ?? "", /needs no parent action/)
    assert.equal(m.calls.filter((c) => JSON.stringify(c).includes('"command":true')).length, 1)
  } finally { f.close() }
})
test("a Command Code turn cap continues the task without spending its single attempt", async () => {
  const f = fixture()
  try {
    const m = fake(f.cwd)
    m.omitModels()
    const command = { ...m.command, status: () =>
      ({ state: "turn_limit", result: { subtype: "max_turns" as const, sessionId: "cmd-session", finalText: "partial" }, stderr: null }) }
    const bridge = makeHybridBridge(m.api, command)
    const task = await bridge.start(f.cwd, "fix", "worker", { ...f.scope, attempt_limit: 1 }, "Edit README")
    await bridge.resume(f.cwd, task.session_id, "continue")
    await bridge.resume(f.cwd, task.session_id, "continue")
    const continued = m.calls.filter((c) => JSON.stringify(c).includes("CONTINUE THE SAME TASK"))
    assert.equal(continued.length, 2)
    assert.ok(continued.every((c) => JSON.stringify(c).includes('"resume":"cmd-session"')))
    await assert.rejects(bridge.resume(f.cwd, task.session_id, "continue"), /continuation limit/)
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
    assert.equal(status.fallback_reason, "Primary Pi runner unavailable during execution (provider usage limit); no edits existed, so the task continued on Command Code.")
    assert.equal(status.error, null)
    assert.match(status.fallback_notice ?? "", /needs no parent action/)
    assert.match(status.fallback_notice ?? "", /Do not retry/)
    assert.match(status.fallback_detail ?? "", /quota exceeded/)
  } finally { f.close() }
})
test("an ordinary failed task mentioning quota in its prose never triggers a fallback", async () => {
  const f = fixture()
  try {
    const m = fake(f.cwd), bridge = makeHybridBridge(m.api, m.command)
    const task = await bridge.start(f.cwd, "fix", "worker", f.scope, "Edit README")
    m.fail("The project's quota test failed for a local assertion; no provider error", false)
    const status = await bridge.status(f.cwd, task.session_id)
    assert.equal(status.backend, "pi")
    assert.equal(status.state, "failed")
    assert.equal(status.fallback_reason, null)
    assert.equal(status.fallback_notice, null)
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
    assert.equal(status.backend, "pi")
    assert.equal(status.state, "blocked_partial_work")
    assert.equal(status.fallback_reason, null)
    assert.match(status.fallback_notice ?? "", /decide manually/)
  } finally { f.close() }
})
test("reject invalid scope, unapproved tier, and dirty worktree", async () => {
  const f = fixture()
  try {
    const m = fake(f.cwd), bridge = makeHybridBridge(m.api, m.command)
    await assert.rejects(bridge.start(f.cwd, "x", "worker", { ...f.scope, writable_paths: ["../secret"] }, "x"), /Invalid writable path/)
    await assert.rejects(bridge.start(f.cwd, "x", "scout", f.scope, "x"), /scouts are read-only/)
    await assert.rejects(bridge.start(f.cwd, "x", "opus", f.scope, "x"), /Unknown Pi tier/)
    await assert.rejects(bridge.start(f.cwd, "x", "god", f.scope, "x"), /Unknown Pi tier/)
    writeFileSync(join(f.cwd, "stray"), "x")
    await assert.rejects(bridge.start(f.cwd, "x", "worker", f.scope, "x"), /clean/)
  } finally { f.close() }
})

test("two concurrent status calls cannot spawn duplicate Command Code fallbacks", async () => {
  const f = fixture()
  try {
    const m = fake(f.cwd), bridge = makeHybridBridge(m.api, m.command)
    const task = await bridge.start(f.cwd, "fix", "worker", f.scope, "Edit README")
    m.fail("OpenCode usage allowance exhausted")
    const results = await Promise.allSettled([
      bridge.status(f.cwd, task.session_id),
      bridge.status(f.cwd, task.session_id),
    ])
    assert.equal(results.filter((r) => r.status === "fulfilled").length, 1)
    const refused = results.find((r) => r.status === "rejected")
    assert.ok(refused && refused.status === "rejected")
    assert.match(String(refused.reason), /transition in progress/)
    assert.equal(m.calls.filter((c) => JSON.stringify(c).includes('"command":true')).length, 1)
    assert.equal((await bridge.status(f.cwd, task.session_id)).backend, "command-code")
  } finally { f.close() }
})

test("overlapping corrections can admit at most one new Command Code run", async () => {
  const f = fixture()
  try {
    const m = fake(f.cwd), bridge = makeHybridBridge(m.api, m.command)
    m.omitModels()
    const task = await bridge.start(f.cwd, "fix", "worker", f.scope, "Edit README")
    m.done()
    const results = await Promise.allSettled([
      bridge.resume(f.cwd, task.session_id, "first correction"),
      bridge.resume(f.cwd, task.session_id, "second correction"),
    ])
    assert.equal(results.filter((r) => r.status === "fulfilled").length, 1)
    assert.equal(results.filter((r) => r.status === "rejected").length, 1)
    assert.equal(m.calls.filter((c) => JSON.stringify(c).includes('"command":true')).length, 2)
  } finally { f.close() }
})

test("interrupted Command Code launch remains a persisted blocked transition", async () => {
  const f = fixture()
  try {
    const m = fake(f.cwd)
    m.omitModels()
    let launched = 0
    const bridge = makeHybridBridge(m.api, {
      ...m.command,
      start: () => { launched++; throw new Error("could not spawn cmd") },
    })
    await assert.rejects(bridge.start(f.cwd, "fix", "worker", f.scope, "Edit README"), /could not spawn/)
    const stateDir = join(f.root, ".work", "worker-bridge")
    const { readdirSync } = await import("node:fs")
    const ids = readdirSync(stateDir).filter((name) => /^usrw_.*\.json$/.test(name))
    assert.equal(ids.length, 1)
    const sessionId = ids[0].replace(/\.json$/, "")
    const status = await bridge.status(f.cwd, sessionId)
    assert.equal(status.state, "blocked_transition")
    assert.equal(status.backend, "command-transition")
    assert.equal(launched, 1)
    await assert.rejects(bridge.resume(f.cwd, sessionId, "retry"), /transition interrupted/)
  } finally { f.close() }
})

test("ambiguous OpenCode prompt admission never launches a second paid worker", async () => {
  const f = fixture()
  try {
    const m = fake(f.cwd)
    const api = { ...m.api, prompt: async () => { throw new Error("quota exhausted") } }
    const bridge = makeHybridBridge(api, m.command)
    await assert.rejects(bridge.start(f.cwd, "fix", "worker", f.scope, "Edit README"), /prompt admission failed/)
    assert.equal(m.calls.filter((c) => JSON.stringify(c).includes('"command":true')).length, 0)
  } finally { f.close() }
})

test("overlapping worker starts admit at most one writer in the same worktree", async () => {
  const f = fixture()
  try {
    const m = fake(f.cwd)
    let releaseModels: () => void = () => {}
    const gate = new Promise<void>((resolve) => { releaseModels = resolve })
    const api: OpenCodePort = { ...m.api, models: async (input) => {
      await gate
      return m.api.models(input)
    } }
    const bridge = makeHybridBridge(api, m.command)
    const first = bridge.start(f.cwd, "first", "worker", f.scope, "Edit README")
    await assert.rejects(bridge.start(f.cwd, "second", "worker", f.scope, "Edit README"), /active worker/)
    releaseModels()
    const admitted = await first
    assert.equal(admitted.backend, "pi")
    assert.equal(m.calls.filter((c) => JSON.stringify(c).includes('"title"')).length, 1)
  } finally { f.close() }
})

test("a verified terminal result releases the worktree; old resume cannot race a new owner", async () => {
  const f = fixture()
  try {
    const m = fake(f.cwd), bridge = makeHybridBridge(m.api, m.command)
    const first = await bridge.start(f.cwd, "first", "worker", f.scope, "Edit README")
    await assert.rejects(bridge.start(f.cwd, "second", "worker", f.scope, "Edit README"), /active worker/)
    assert.equal((await bridge.status(f.cwd, first.session_id)).state, "succeeded")
    const second = await bridge.start(f.cwd, "second", "worker", f.scope, "Edit README")
    assert.notEqual(second.session_id, first.session_id)
    await assert.rejects(bridge.resume(f.cwd, first.session_id, "more feedback"), /active for worker/)
  } finally { f.close() }
})

test("a restarted bridge preserves an active admission lease until terminal status", async () => {
  const f = fixture()
  try {
    const m = fake(f.cwd)
    const first = await makeHybridBridge(m.api, m.command).start(f.cwd, "first", "worker", f.scope, "Edit README")
    const restarted = makeHybridBridge(m.api, m.command)
    await assert.rejects(restarted.start(f.cwd, "another", "worker", f.scope, "Edit README"), /active worker/)
    assert.equal((await restarted.status(f.cwd, first.session_id)).state, "succeeded")
    const next = await restarted.start(f.cwd, "next", "worker", f.scope, "Edit README")
    assert.notEqual(next.session_id, first.session_id)
  } finally { f.close() }
})

test("independent worktrees remain independently admissible", async () => {
  const f = fixture()
  try {
    const cwd2 = join(f.root, ".work", "wt", "b")
    git(f.root, "worktree", "add", "-qb", "lane-b", cwd2)
    const m = fake(f.cwd), bridge = makeHybridBridge(m.api, m.command)
    const scope2 = { ...f.scope, base_revision: git(cwd2, "rev-parse", "HEAD") }
    const [first, second] = await Promise.all([
      bridge.start(f.cwd, "one", "worker", f.scope, "Edit README"),
      bridge.start(cwd2, "two", "worker", scope2, "Edit README"),
    ])
    assert.notEqual(first.session_id, second.session_id)
  } finally { f.close() }
})

test("ambiguous admission retains its worktree lease and is inspectable after restart", async () => {
  const f = fixture()
  try {
    const m = fake(f.cwd)
    const api: OpenCodePort = { ...m.api, prompt: async () => { throw new Error("quota exhausted") } }
    const bridge = makeHybridBridge(api, m.command)
    await assert.rejects(bridge.start(f.cwd, "uncertain", "worker", f.scope, "Edit README"), /lease retained for session/)
    const { readdirSync } = await import("node:fs")
    const state = join(f.root, ".work", "worker-bridge")
    const ids = readdirSync(state).filter((name) => /^usrw_.*\.json$/.test(name))
    assert.equal(ids.length, 1)
    const sessionID = ids[0].replace(/\.json$/, "")
    const restarted = makeHybridBridge(m.api, m.command)
    const status = await restarted.status(f.cwd, sessionID)
    assert.equal(status.state, "blocked_admission")
    await assert.rejects(restarted.start(f.cwd, "second", "worker", f.scope, "Edit README"), /active worker/)
    await assert.rejects(restarted.resume(f.cwd, sessionID, "retry"), /transition interrupted/)
  } finally { f.close() }
})

test("cancel acknowledgement does not release a worktree until the backend is terminal", async () => {
  const f = fixture()
  try {
    const m = fake(f.cwd), bridge = makeHybridBridge(m.api, m.command)
    const first = await bridge.start(f.cwd, "one", "worker", f.scope, "Edit README")
    assert.equal((await bridge.cancel(f.cwd, first.session_id)).interrupted, true)
    await assert.rejects(bridge.start(f.cwd, "two", "worker", f.scope, "Edit README"), /active worker/)
    m.fail("ordinary failure", false)
    assert.equal((await bridge.status(f.cwd, first.session_id)).state, "failed")
    const second = await bridge.start(f.cwd, "two", "worker", f.scope, "Edit README")
    assert.notEqual(second.session_id, first.session_id)
  } finally { f.close() }
})

test("interrupted Pi resume cannot expose an old terminal result or release its lease", async () => {
  const f = fixture()
  try {
    const m = fake(f.cwd)
    let prompts = 0
    const api: OpenCodePort = {
      ...m.api,
      prompt: async (input) => {
        prompts++
        if (prompts === 2) throw new Error("resume admission interrupted")
        return m.api.prompt(input)
      },
    }
    const bridge = makeHybridBridge(api, m.command)
    const original = await bridge.start(f.cwd, "first", "worker", f.scope, "Edit README")
    assert.equal((await bridge.status(f.cwd, original.session_id)).state, "succeeded")
    await assert.rejects(bridge.resume(f.cwd, original.session_id, "correct this"), /resume admission interrupted/)
    const restarted = makeHybridBridge(m.api, m.command)
    const status = await restarted.status(f.cwd, original.session_id)
    assert.equal(status.state, "blocked_admission")
    assert.equal(status.backend, "pi-transition")
    await assert.rejects(restarted.start(f.cwd, "second", "worker", f.scope, "Edit README"), /active worker/)
    await assert.rejects(restarted.resume(f.cwd, original.session_id, "retry"), /transition interrupted/)
    assert.equal(m.calls.filter((c) => JSON.stringify(c).includes('"command":true')).length, 0)
  } finally { f.close() }
})
