import test from "node:test"
import assert from "node:assert/strict"
import { cpSync, existsSync, mkdirSync, mkdtempSync, readFileSync, readdirSync, rmSync, writeFileSync } from "node:fs"
import { spawnSync } from "node:child_process"
import { join } from "node:path"
import { tmpdir } from "node:os"
import { startCommand } from "../src/command.ts"
import { codexAvailable, startCodex } from "../src/codex.ts"
import { makeFxAdapter } from "../src/fx.ts"
import { optionalPiPort, diagnoseGoModel, piInstalled } from "../src/optional-pi.ts"
import { piPort } from "../src/pi-port.ts"
import { makeWorkerBridge, type OpenCodePort } from "../src/bridge.ts"
import { devinPreflight } from "../src/devin-provider.ts"
import type { LaunchRequest } from "../src/launch.ts"
import { NO_HARNESSES } from "./harness-fixtures.ts"

const model = { providerID: "opencode-go", id: "deepseek-v4.1-flash", variant: "high" }
const request: LaunchRequest = { directory: "/absent", logDirectory: "/absent", prompt: "fixture",
  selection: { model: "fixture", effort: "high" }, access: { kind: "write" } }

test("disabled direct process launchers fail before opening output or probing executables", () => {
  assert.throws(() => startCommand(request), /Command Code is disabled in harnesses.json/)
  assert.equal(codexAvailable(NO_HARNESSES), false)
  assert.throws(() => startCodex(request, NO_HARNESSES), /Codex is disabled in harnesses.json/)
  const root = mkdtempSync(join(tmpdir(), "disabled-fx-"))
  try {
    const fx = makeFxAdapter({ home: root, binary: "/absent/fx", binarySha256: "0".repeat(64),
      provider: "fixture", shell: "/bin/sh", transport: "cli", allowedCommands: [] }, NO_HARNESSES)
    const selection = { model: "fixture", effort: "high", provider: "fixture", runtimeVersion: "0.0.17" } as const
    assert.equal(fx.available(selection), false)
    assert.throws(() => fx.start({ ...request, selection }), /FX is disabled in harnesses.json/)
    assert.throws(() => fx.preflightResume({ ...request, selection, resume: "invalid" }), /FX is disabled in harnesses.json/)
    assert.deepEqual(readdirSync(root), [])
  } finally { rmSync(root, { recursive: true, force: true }) }
})

test("disabled Pi and providers do not load the SDK, resolve extensions, or inspect credentials", async () => {
  assert.equal(piInstalled(NO_HARNESSES), false)
  assert.match(await diagnoseGoModel(model, NO_HARNESSES) ?? "", /disabled in harnesses.json/)
  const extension = () => { throw new Error("Disabled extension resolver was called") }
  assert.deepEqual(devinPreflight({}, "/absent", extension, NO_HARNESSES), {
    available: false, issue: "Pi Devin provider is disabled in harnesses.json",
  })
  for (const port of [optionalPiPort(NO_HARNESSES), piPort({ switches: NO_HARNESSES })]) {
    assert.deepEqual(await port.models({ location: { directory: "/absent" } }), { data: [] })
    await assert.rejects(port.create({ title: "fixture", model, agent: "build", location: { directory: "/absent" },
      metadata: { usr_worker_v1: { directory: "/absent", model } } }), /disabled in harnesses.json/)
  }
})

test("direct scoped Pi admission and correction reject disabled providers before touching the port", async () => {
  const denied = async () => { throw new Error("Disabled Pi port was called") }
  const port: OpenCodePort = { models: denied, create: denied, prompt: denied, steer: denied,
    get: denied, active: denied, inbox: denied, messages: denied, interrupt: denied }
  const bridge = makeWorkerBridge(port, model, NO_HARNESSES)
  assert.deepEqual(await bridge.modelCheck("/absent"), { model, available: false })
  await assert.rejects(bridge.start("/absent", "fixture", "fixture"), /disabled in harnesses.json/)
  await assert.rejects(bridge.preflightResume("/absent", "ses_fixture", "fixture"), /disabled in harnesses.json/)
  await assert.rejects(bridge.steer("/absent", "ses_fixture", "fixture"), /disabled in harnesses.json/)
})


function disabledFxCheckout() {
  const root = mkdtempSync(join(tmpdir(), "disabled-fx-runtime-"))
  const close = () => rmSync(root, { recursive: true, force: true })
  try {
    const source = join(root, "tools/pi-subagent-bridge/src")
    cpSync(new URL("../src", import.meta.url), source, { recursive: true })
    writeFileSync(join(root, "harnesses.json"), JSON.stringify(NO_HARNESSES))
    return { root, source, close }
  } catch (error) {
    close()
    throw error
  }
}

for (const file of ["process-supervisor.ts", "fx-acp-supervisor.ts"]) {
  test(`disabled FX ${file} records terminal rejection without reading secrets or spawning`, () => {
    const f = disabledFxCheckout()
    try {
      const marker = join(f.root, "spawned"), output = join(f.root, "result.json"), errors = join(f.root, "stderr")
      const job = join(f.root, "job.json")
      writeFileSync(job, JSON.stringify({ nonce: "disabled-fixture", executable: process.execPath,
        args: ["-e", `require('node:fs').writeFileSync(${JSON.stringify(marker)}, 'spawned')`],
        cwd: f.root, env: {}, env_files: { FIXTURE_SECRET: "/absent/secret" }, wallMs: 1000,
        output, errors, prompt: "fixture", acp_log: join(f.root, "acp.log"), events: join(f.root, "events"),
        selection: { provider: "fixture", model: "fixture", effort: "high" }, ungated_tools: [],
      }))
      const result = spawnSync(process.execPath, [join(f.source, file), job], { encoding: "utf8", timeout: 5000 })
      assert.equal(result.status, 1, result.stderr)
      const receipt = JSON.parse(readFileSync(output, "utf8"))
      assert.equal(receipt.reason, "spawn")
      assert.equal(receipt.child_pid, null)
      assert.match(receipt.stderr, /FX is disabled in harnesses.json/)
      if (file === "fx-acp-supervisor.ts") assert.equal(receipt.termination, "verified")
      assert.equal(existsSync(marker), false)
      assert.equal(existsSync(errors), false)
    } finally { f.close() }
  })
}

test("disabled FX orphan launch exits before starting a detached process", () => {
  const f = disabledFxCheckout()
  try {
    const marker = join(f.root, "spawned")
    const result = spawnSync(process.execPath, [join(f.source, "fx-orphan-launcher.ts"), process.execPath,
      "-e", `require('node:fs').writeFileSync(${JSON.stringify(marker)}, 'spawned')`], { encoding: "utf8", timeout: 5000 })
    assert.equal(result.status, 1)
    assert.match(result.stderr, /FX is disabled in harnesses.json/)
    assert.equal(existsSync(marker), false)
  } finally { f.close() }
})

test("disabled FX child control rejects spawn, resume and steer before reading or changing its ledger", () => {
  const f = disabledFxCheckout()
  try {
    const home = join(f.root, "home"), config = join(home, "children.json"), job = join(f.root, "job.json")
    mkdirSync(home)
    writeFileSync(config, JSON.stringify({ schema: 1, adapter: { home, binary: "/absent/fx", binarySha256: "0".repeat(64),
      provider: "fixture", shell: "/bin/sh", transport: "cli", allowedCommands: [] }, selections: {},
      limits: { maxChildren: 1, maxConcurrent: 1 }, cwd: f.root, logDirectory: home }))
    writeFileSync(job, JSON.stringify({ deadlineAt: Date.now() + 1000 }))
    const ledger = join(home, "children-ledger.json")
    writeFileSync(ledger, "deliberately unreadable ledger")
    const calls = [
      { name: "spawn", arguments: { tier: "worker", task: "fixture", intent_id: "fixture" } },
      { name: "resume", arguments: { child_id: "old", feedback: "fixture" } },
      { name: "steer", arguments: { child_id: "old", note: "fixture" } },
      { name: "status", arguments: { child_id: "old" } },
      { name: "cancel", arguments: { child_id: "old" } },
    ]
    const input = calls.map((params, id) => JSON.stringify({ jsonrpc: "2.0", id, method: "tools/call", params })).join("\n") + "\n"
    const result = spawnSync(process.execPath, [join(f.source, "fx-children-mcp.ts"), config, job], { input, encoding: "utf8", timeout: 5000 })
    assert.equal(result.status, 0, result.stderr)
    const replies = result.stdout.trim().split("\n").map(line => JSON.parse(line))
    assert.equal(replies.length, calls.length)
    for (const reply of replies) {
      assert.equal(reply.result.isError, true)
      if (reply.id < 3) assert.match(reply.result.content[0].text, /FX is disabled in harnesses.json/)
      else assert.doesNotMatch(reply.result.content[0].text, /disabled/)
    }
    assert.equal(readFileSync(ledger, "utf8"), "deliberately unreadable ledger")
  } finally { f.close() }
})
