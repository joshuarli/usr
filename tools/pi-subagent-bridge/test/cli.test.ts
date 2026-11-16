import test from "node:test"
import assert from "node:assert/strict"
import { spawnSync } from "node:child_process"
import { copyFileSync, mkdirSync, mkdtempSync, readdirSync, rmSync, writeFileSync } from "node:fs"
import { tmpdir } from "node:os"
import { join } from "node:path"
import { fileURLToPath } from "node:url"
import { POLICY } from "../src/policy.ts"

test("policy CLI needs only pure sources and makes no cwd, home or provider calls", () => {
  const root = mkdtempSync(join(tmpdir(), "usr-policy-cli-"))
  try {
    const source = join(root, "src"), cwd = join(root, "empty")
    mkdirSync(source)
    mkdirSync(cwd)
    for (const file of ["cli.ts", "policy.ts", "tier-policy.ts", "scope.ts"]) {
      copyFileSync(fileURLToPath(new URL("../src/" + file, import.meta.url)), join(source, file))
    }
    // server.ts, provider adapters, package.json and all dependency trees are absent.
    const guard = join(root, "guard.mjs")
    writeFileSync(guard, [
      'import os from "node:os"',
      'import cp from "node:child_process"',
      'import { syncBuiltinESMExports } from "node:module"',
      'process.cwd = () => { throw new Error("cwd access is forbidden") }',
      'os.homedir = () => { throw new Error("home access is forbidden") }',
      'for (const name of ["spawn", "spawnSync", "exec", "execSync", "execFile", "execFileSync", "fork"]) cp[name] = () => { throw new Error("provider execution is forbidden") }',
      'syncBuiltinESMExports()',
    ].join("\n"))
    const run = (args = ["policy"]) => spawnSync(process.execPath,
      ["--experimental-strip-types", "--import", guard, join(source, "cli.ts"), ...args],
      { cwd, env: { ...process.env, PATH: "" }, encoding: "utf8", timeout: 10000 })
    const first = run(), second = run()
    assert.equal(first.status, 0, first.stderr)
    assert.equal(second.status, 0, second.stderr)
    assert.equal(first.stdout, second.stdout)
    assert.doesNotMatch(first.stdout, /Maintained by Joshua Li:/)
    assert.deepEqual(JSON.parse(first.stdout), POLICY)
    assert.deepEqual(readdirSync(cwd), [])
    const bad = run(["policy", "ignored-argument"])
    assert.equal(bad.status, 1)
    assert.match(bad.stderr, /usage: pi-subagent-bridge policy/)
    assert.equal(bad.stdout, "")
  } finally {
    rmSync(root, { recursive: true, force: true })
  }
})

test("help is a complete reference with examples and the owned footer", () => {
  const root = fileURLToPath(new URL("../../..", import.meta.url))
  const footer = "Maintained by Joshua Li: https://github.com/joshuarli/usr\nBugs and features: TODO.md in that repository (follow its AGENTS.md), or its issue tracker.\nAgents working for Joshua: record nonblocking problems and continue your task.\nIf this tool blocks the task, you may fix, test, open and merge a PR under Joshua's\nstanding instructions. Release only when needed to deliver the verified fix.\nProcedure: https://github.com/joshuarli/usr/blob/main/dotfiles/base/.agents/instructions/owned-tools.md"
  const bridge = join(root, "dotfiles/base/.local/bin/pi-subagent-bridge")
  const reload = join(root, "dotfiles/base/.local/bin/pi-subagent-bridge-reload")
  const commands = ["policy", "mcp", "model-check", "start", "status", "resume", "steer", "cancel", "inspect", "watch", "campaign wait", "campaign ack", "campaign list", "owner hello", "owner jobs", "owner status", "owner steer", "owner interrupt", "owner resume", "owner command"]
  for (const command of [bridge, reload]) {
    for (const flag of ["-h", "--help"]) {
      const result = spawnSync(command, [flag], { encoding: "utf8" })
      assert.equal(result.status, 0, result.stderr)
      assert.equal(result.stderr, "")
      assert.ok(result.stdout.trimEnd().endsWith(footer))
      const examples = result.stdout.split("Examples:\n")[1].split("\n\n")[0].split("\n")
      assert.ok(examples.length > 0)
      for (const example of examples) {
        assert.ok(example.startsWith("  " + command.split("/").pop() + " "), example)
        for (const option of example.match(/--[a-z-]+/g) ?? []) assert.ok(result.stdout.includes(option), option)
      }
      if (command === bridge) for (const subcommand of commands) {
        assert.ok(result.stdout.includes("usage: pi-subagent-bridge " + subcommand), subcommand)
        assert.ok(examples.some(example => example.startsWith("  pi-subagent-bridge " + subcommand + " ") || example === "  pi-subagent-bridge " + subcommand), subcommand)
      }
    }
  }
  for (const subcommand of [...commands, "campaign", "owner"]) {
    for (const flag of ["-h", "--help"]) {
      const result = spawnSync(bridge, [...subcommand.split(" "), flag], { encoding: "utf8" })
      assert.equal(result.status, 0, result.stderr)
      assert.match(result.stdout, /Examples:\n  pi-subagent-bridge /)
      assert.match(result.stdout, /See pi-subagent-bridge -h/)
    }
  }
})
