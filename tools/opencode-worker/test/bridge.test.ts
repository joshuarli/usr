import test from "node:test"
import assert from "node:assert/strict"
import { execFileSync } from "node:child_process"
import { mkdtempSync, mkdirSync, rmSync, writeFileSync, realpathSync } from "node:fs"
import { tmpdir } from "node:os"
import { join } from "node:path"
import { DEFAULT_MODEL, FREE_MODEL, GO_MODEL, checkedWorktree, makeWorkerBridge, selectedModel, type OpenCodePort } from "../src/bridge.ts"

function git(cwd: string, ...args: string[]): string {
  return execFileSync("git", ["-C", cwd, ...args], { encoding: "utf8" }).trim()
}
function fixture() {
  const root = realpathSync(mkdtempSync(join(tmpdir(), "usr-oc-")))
  git(root, "init", "-q")
  git(root, "config", "user.email", "test@example.com")
  git(root, "config", "user.name", "Test")
  writeFileSync(join(root, "README"), "hello\n")
  git(root, "add", "README")
  git(root, "commit", "-qm", "init")
  mkdirSync(join(root, ".work", "wt"), { recursive: true })
  const cwd = join(root, ".work", "wt", "worker-a")
  git(root, "worktree", "add", "-qb", "worker-a", cwd)
  return { root, cwd, close: () => rmSync(root, { recursive: true, force: true }) }
}

function fake(cwd: string) {
  const calls: Array<{ op: string; input: unknown }> = []
  const info = { id: "ses_fixture", title: "usr-worker: demo", model: DEFAULT_MODEL,
    location: { directory: cwd }, metadata: { usr_worker_v1: { directory: cwd, model: DEFAULT_MODEL } },
    outcome: "succeeded", cost: 0.012, tokens: { input: 200, output: 50 } }
  let active = false
  let queued = 0
  const api: OpenCodePort = {
    create: async (input) => { calls.push({ op: "create", input }); return { data: { ...info } } },
    prompt: async (input) => { calls.push({ op: "prompt", input }); return {} },
    get: async (input) => { calls.push({ op: "get", input }); return { data: info } },
    active: async () => ({ data: active ? { ses_fixture: {} } : {} }),
    inbox: async () => ({ data: Array.from({ length: queued }, (_, i) => ({ id: i })) }),
    messages: async () => ({ data: [
      { type: "assistant", content: [{ type: "reasoning", text: "secret chain" }, { type: "text", text: "Done; ran tests" }] },
    ] }),
    interrupt: async (input) => { calls.push({ op: "interrupt", input }); return { interrupted: active } },
    models: async () => ({ location: { directory: cwd }, data: [{ providerID: "opencode", id: "deepseek-v4.1-flash-free", modelID: "deepseek-v4.1-flash-free", variants: [], enabled: true, status: "active" }] }),
  }
  return { api, calls, setActive: (value: boolean) => { active = value }, setQueued: (value: number) => { queued = value }, info }
}

test("model selection is closed; never silently switch providers", () => {
  assert.deepEqual(selectedModel("go"), GO_MODEL)
  assert.deepEqual(selectedModel(), FREE_MODEL)
  assert.deepEqual(selectedModel("free"), FREE_MODEL)
  assert.throws(() => selectedModel("gpt-6"), /no silent model fallback/)
})

test("requires a clean linked worktree in .work/wt, not primary repo", () => {
  const f = fixture()
  try {
    assert.equal(checkedWorktree(f.cwd, true), f.cwd)
    assert.throws(() => checkedWorktree(f.root), /primary worktree/)
    assert.equal(checkedWorktree(join(f.cwd, ".")), f.cwd) // normalized
    mkdirSync(join(f.cwd, "subdir"))
    assert.throws(() => checkedWorktree(join(f.cwd, "subdir")), /worktree root/)
    const outside = join(f.root, "other-worktree")
    git(f.root, "worktree", "add", "-qb", "other-worker", outside)
    assert.throws(() => checkedWorktree(outside), /immediate children/)
  } finally { f.close() }
})

test("worker session is admitted, observable, resumable, interruptible; model and directory pinned", async () => {
  const f = fixture()
  try {
    const mock = fake(f.cwd)
    const bridge = makeWorkerBridge(mock.api)
    assert.deepEqual(await bridge.modelCheck(f.cwd), { model: DEFAULT_MODEL, available: true })
    const started = await bridge.start(f.cwd, "demo", "Own README. Add a test. Run node --test. Stop at 1 attempt.")
    assert.equal(started.session_id, "ses_fixture")
    assert.match(JSON.stringify(mock.calls), /Do not spawn subagents/)
    assert.deepEqual((mock.calls.find((c) => c.op === "create")?.input as { model: unknown }).model, DEFAULT_MODEL)
    const status = await bridge.status(f.cwd, "ses_fixture")
    assert.equal(status.state, "succeeded")
    assert.equal(status.last_assistant_text, "Done; ran tests")
    assert.equal(status.cost_reported_usd, 0.012)
    assert.deepEqual(status.git_status, [])
    mock.setActive(true)
    assert.equal((await bridge.status(f.cwd, "ses_fixture")).state, "running")
    await assert.rejects(bridge.resume(f.cwd, "ses_fixture", "fix test"), /running or has queued input/)
    mock.setActive(false)
    mock.setQueued(1)
    assert.equal((await bridge.status(f.cwd, "ses_fixture")).state, "queued")
    await assert.rejects(bridge.resume(f.cwd, "ses_fixture", "fix test"), /running or has queued input/)
    mock.setQueued(0)
    assert.equal((await bridge.resume(f.cwd, "ses_fixture", "fix test")).status, "admitted")
    assert.equal((await bridge.cancel(f.cwd, "ses_fixture")).interrupted, false)
    assert.equal(mock.calls.filter((c) => c.op === "prompt").length, 2)
  } finally { f.close() }
})

test("new sessions reject dirty trees, model absence, cross-directory session reuse and unrelated sessions", async () => {
  const a = fixture(), b = fixture()
  try {
    const mock = fake(a.cwd)
    const bridge = makeWorkerBridge(mock.api)
    writeFileSync(join(a.cwd, "new.txt"), "changes")
    await assert.rejects(bridge.start(a.cwd, "dirty", "work"), /clean/)
    rmSync(join(a.cwd, "new.txt"))
    const noModel = makeWorkerBridge({ ...mock.api, models: async () => [] })
    await assert.rejects(noModel.start(a.cwd, "missing", "work"), /unavailable/)
    await assert.rejects(bridge.resume(b.cwd, "ses_fixture", "wrong worktree"), /mismatch/)
    mock.info.title = "unrelated"
    await assert.rejects(bridge.cancel(a.cwd, "ses_fixture"), /Refusing a session/)
    mock.info.title = "usr-worker: demo"
    mock.info.metadata.usr_worker_v1.directory = b.cwd
    await assert.rejects(bridge.status(a.cwd, "ses_fixture"), /ownership, worktree, or model mismatch/)
    await assert.rejects(bridge.status(a.cwd, "wrong-session"), /Invalid OpenCode session ID/)
  } finally { a.close(); b.close() }
})

test("a prompt admission error includes the created session ID for recovery", async () => {
  const f = fixture()
  try {
    const mock = fake(f.cwd)
    const bridge = makeWorkerBridge({ ...mock.api, prompt: async () => { throw new Error("network dropped") } })
    await assert.rejects(bridge.start(f.cwd, "demo", "work"), /ses_fixture created but prompt admission failed/)
  } finally { f.close() }
})
