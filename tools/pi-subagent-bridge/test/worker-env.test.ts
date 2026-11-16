import assert from "node:assert/strict"
import { spawnSync } from "node:child_process"
import { existsSync, mkdtempSync, mkdirSync, readFileSync, rmSync, writeFileSync } from "node:fs"
import { tmpdir } from "node:os"
import { join } from "node:path"
import test from "node:test"
import { stripIntercomEnvironment, workerEnvironment } from "../src/worker-env.ts"
import { startCodex } from "../src/codex.ts"
import { startCommand } from "../src/command.ts"

test("a scoped worker process receives provider settings but no coordinator authority", () => {
  const parent = {
    ...process.env,
    AGENT_INTERCOM_REMOTE_ENDPOINT: "tcp://100.64.0.1:47831",
    AGENT_INTERCOM_REMOTE_LISTEN: "tcp://100.64.0.2:47831",
    AGENT_INTERCOM_ACCESS_CREDENTIAL_PATH: "/private/coordinator.json",
    AGENT_INTERCOM_REMOTE_ACCESS_CREDENTIAL_PATH: "/private/legacy.json",
    AGENT_INTERCOM_BOSS_RUN_ID: "coordinator",
    AGENT_INTERCOM_FUTURE_AUTHORITY: "must-also-be-removed",
    PI_INTERCOM_TCP: "1",
    PI_OFFLINE: "1",
    OPENCODE_API_KEY: "fixture-provider-key",
  }
  const child = spawnSync(process.execPath, ["-e", "process.stdout.write(JSON.stringify(process.env))"], {
    env: workerEnvironment(parent), encoding: "utf8",
  })
  assert.equal(child.status, 0, child.stderr)
  const received: Record<string, string> = JSON.parse(child.stdout)
  assert.equal(Object.keys(received).some((key) => key.startsWith("AGENT_INTERCOM_") || key.startsWith("PI_INTERCOM_")), false)
  assert.equal(received.OPENCODE_API_KEY, "fixture-provider-key")
  assert.equal(received.PI_OFFLINE, "1")
  assert.equal(received.USR_SCOPED_WORKER, "1")
  assert.equal(parent.AGENT_INTERCOM_ACCESS_CREDENTIAL_PATH, "/private/coordinator.json", "parent enrollment remains intact")
})

test("direct SDK entry scrubs its environment before native nested children inherit it", () => {
  const env = { AGENT_INTERCOM_REMOTE_ENDPOINT: "tcp://100.64.0.1:47831", PI_OFFLINE: "1" }
  stripIntercomEnvironment(env)
  assert.deepEqual(env, { PI_OFFLINE: "1" })
})

test("every CLI worker launcher actually strips coordinator authority before exec", async () => {
  const root = mkdtempSync(join(tmpdir(), "intercom-worker-")), bin = join(root, "bin")
  mkdirSync(bin)
  const values = {
    PATH: bin + ":" + (process.env.PATH ?? ""),
    AGENT_INTERCOM_REMOTE_ENDPOINT: "tcp://100.64.0.1:47831",
    AGENT_INTERCOM_ACCESS_CREDENTIAL_PATH: "/private/coordinator.json",
    PI_INTERCOM_TCP: "1",
    USR_ENV_REPORT: "",
  }
  const previous = Object.fromEntries(Object.keys(values).map((key) => [key, process.env[key]]))
  try {
    Object.assign(process.env, values)
    for (const name of ["codex", "cmd"]) {
      writeFileSync(join(bin, name), `#!${process.execPath}\n` +
        'require("node:fs").writeFileSync(process.env.USR_ENV_REPORT, JSON.stringify(Object.fromEntries(Object.entries(process.env).filter(([key]) => key.includes("INTERCOM") || key === "USR_SCOPED_WORKER"))))\n', { mode: 0o700 })
    }
    const cases = [
      { launch: startCodex, model: "gpt-6.1-terra" },
      { launch: startCommand, model: "deepseek/deepseek-v4.1-flash" },
    ]
    for (const [index, { launch, model }] of cases.entries()) {
      const report = join(root, `report-${index}.json`)
      process.env.USR_ENV_REPORT = report
      launch({ directory: root, logDirectory: root, prompt: "fixture", selection: { model, effort: "high" }, access: { kind: "write" } })
      for (let attempt = 0; attempt < 200 && !existsSync(report); attempt++)
        await new Promise((resolve) => setTimeout(resolve, 10))
      assert.deepEqual(JSON.parse(readFileSync(report, "utf8")), { USR_SCOPED_WORKER: "1" }, model)
    }
  } finally {
    for (const [key, value] of Object.entries(previous)) {
      if (value === undefined) delete process.env[key]
      else process.env[key] = value
    }
    rmSync(root, { recursive: true, force: true })
  }
})
