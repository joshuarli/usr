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
