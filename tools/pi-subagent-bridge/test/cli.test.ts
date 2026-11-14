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

test("launchers print their primary help footer", () => {
  const root = fileURLToPath(new URL("../../..", import.meta.url))
  const footer = "Maintained by Joshua Li: https://github.com/joshuarli/usr\nBugs and features: TODO.md in that repository (follow its AGENTS.md), or its issue tracker.\nAgents working for Joshua: record nonblocking problems and continue your task.\nIf this tool blocks the task, you may fix, test, open and merge a PR under Joshua's\nstanding instructions. Release only when needed to deliver the verified fix.\nProcedure: https://github.com/joshuarli/usr/blob/main/dotfiles/base/.agents/instructions/owned-tools.md"
  for (const [command, status] of [["pi-subagent-bridge", 0], ["pi-subagent-bridge-reload", 2]] as const) {
    const result = spawnSync(join(root, "dotfiles/base/.local/bin", command), ["--help"], { encoding: "utf8" })
    assert.equal(result.status, status, result.stderr)
    assert.ok((result.stdout + result.stderr).trimEnd().endsWith(footer))
  }
})
