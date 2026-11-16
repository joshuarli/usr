import test from "node:test"
import assert from "node:assert/strict"
import { spawnSync } from "node:child_process"
import { copyFileSync, mkdirSync, mkdtempSync, readdirSync, rmSync, writeFileSync } from "node:fs"
import { tmpdir } from "node:os"
import { join } from "node:path"
import { fileURLToPath } from "node:url"
import { POLICY } from "../src/policy.ts"

test("missing command prints usage and exits 2", () => {
  const cli = fileURLToPath(new URL("../src/cli.ts", import.meta.url))
  const result = spawnSync(process.execPath, ["--experimental-strip-types", cli], { encoding: "utf8", timeout: 2000 })
  assert.equal(result.status, 2)
  assert.match(result.stderr, /usage: pi-subagent-bridge/)
  assert.equal(result.stdout, "")
})

test("relative non-worktree errors name the resolved path", () => {
  const cli = fileURLToPath(new URL("../src/cli.ts", import.meta.url))
  const result = spawnSync(process.execPath, ["--experimental-strip-types", cli, "model-check", "missing-worktree", "worker"], { encoding: "utf8" })
  assert.match(result.stderr, new RegExp(join(process.cwd(), "missing-worktree")))
})

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
  const commands = ["policy", "mcp", "model-check", "start", "status", "resume", "steer", "cancel", "scope-check", "inspect", "watch", "campaign wait", "campaign ack", "campaign list", "owner hello", "owner jobs", "owner status", "owner steer", "owner interrupt", "owner resume", "owner command"]
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

test("watch help reports the 45 minute default", () => {
  const cli = fileURLToPath(new URL("../src/cli.ts", import.meta.url))
  const result = spawnSync(process.execPath, ["--experimental-strip-types", cli, "watch", "--help"], { encoding: "utf8" })
  assert.equal(result.status, 0, result.stderr)
  assert.match(result.stdout, /default: 45/)
})

test("scope-check reports a native lane's changed paths, out-of-scope paths and lane drift", () => {
  const root = mkdtempSync(join(tmpdir(), "usr-scope-check-"))
  try {
    const git = (...args: string[]) => {
      const result = spawnSync("git", ["-C", root, ...args], { encoding: "utf8" })
      assert.equal(result.status, 0, result.stderr)
      return result.stdout.trim()
    }
    git("init", "-q", "-b", "lane/native")
    git("config", "user.email", "test@example.invalid")
    git("config", "user.name", "test")
    mkdirSync(join(root, "src"))
    writeFileSync(join(root, "src/a.ts"), "a\n")
    git("add", ".")
    git("commit", "-q", "-m", "base")
    const base = git("rev-parse", "HEAD")
    const scope = join(root, "..", "usr-scope-check-" + base.slice(0, 8) + ".json")
    writeFileSync(scope, JSON.stringify({ base_revision: base, writable_paths: ["src"] }))
    const cli = fileURLToPath(new URL("../src/cli.ts", import.meta.url))
    const run = (...extra: string[]) => {
      const result = spawnSync(process.execPath, ["--experimental-strip-types", cli, "scope-check", root, scope, ...extra], { encoding: "utf8" })
      return { status: result.status, stderr: result.stderr, report: result.stdout ? JSON.parse(result.stdout) : null }
    }
    try {
      writeFileSync(join(root, "src/a.ts"), "b\n")
      git("commit", "-qam", "in scope")
      writeFileSync(join(root, "src/new.ts"), "n\n")
      let result = run("lane/native")
      assert.equal(result.status, 0, result.stderr)
      assert.deepEqual(result.report.changed_paths, ["src/a.ts", "src/new.ts"])
      assert.deepEqual(result.report.out_of_scope_paths, [])
      assert.equal(result.report.commits_since_base, 1)
      assert.equal(result.report.in_scope, true)

      writeFileSync(join(root, "README.md"), "outside\n")
      result = run("lane/native")
      assert.equal(result.status, 1)
      assert.deepEqual(result.report.out_of_scope_paths, ["README.md"])
      assert.equal(result.report.in_scope, false)
      rmSync(join(root, "README.md"))

      git("switch", "-q", "-c", "elsewhere")
      result = run("lane/native")
      assert.equal(result.status, 1)
      assert.equal(result.report.head_on_lane, false)
      assert.match(result.report.drift, /current branch differs/)

      const bad = spawnSync(process.execPath, ["--experimental-strip-types", cli, "scope-check", root], { encoding: "utf8" })
      assert.equal(bad.status, 1)
      assert.match(bad.stderr, /usage: pi-subagent-bridge scope-check CWD SCOPE_JSON_FILE \[BRANCH\]/)
    } finally {
      rmSync(scope, { force: true })
    }
  } finally {
    rmSync(root, { recursive: true, force: true })
  }
})
