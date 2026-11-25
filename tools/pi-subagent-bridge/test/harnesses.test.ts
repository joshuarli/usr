import test from "node:test"
import assert from "node:assert/strict"
import { mkdirSync, mkdtempSync, rmSync, writeFileSync } from "node:fs"
import { tmpdir } from "node:os"
import { join } from "node:path"
import { HARNESS_SWITCHES, assertHarnessEnabled, parseHarnessSwitches, piProviderEnabled } from "../src/harnesses.ts"
import { snapshotSource, sourceChanged } from "../src/source-manifest.ts"

test("invalid switches fail closed instead of treating typos or strings as enabled", () => {
  for (const value of [null, [], true, { ...HARNESS_SWITCHES, cmd: true },
    { ...HARNESS_SWITCHES, "command-code": "false" }, { pi: true }])
    assert.throws(() => parseHarnessSwitches(value), /harnesses.json/)
  assert.throws(() => assertHarnessEnabled("command-code"), /Command Code is disabled in harnesses.json/)
  assert.doesNotThrow(() => assertHarnessEnabled("command-code", { ...HARNESS_SWITCHES, "command-code": true }))
})

test("Pi providers require the harness and their own switch, independently of native OpenCode", () => {
  assert.equal(piProviderEnabled("opencode-go", { ...HARNESS_SWITCHES, opencode: false }), true)
  assert.equal(piProviderEnabled("opencode-go", { ...HARNESS_SWITCHES, pi: false }), false)
  assert.equal(piProviderEnabled("opencode-go", { ...HARNESS_SWITCHES, "opencode-go": false }), false)
  assert.equal(piProviderEnabled("devin", { ...HARNESS_SWITCHES, devin: false }), false)
  assert.equal(piProviderEnabled("unknown", HARNESS_SWITCHES), false)
})

test("long-running server source snapshots detect a root switch change", () => {
  const root = mkdtempSync(join(tmpdir(), "usr-harness-source-"))
  const src = join(root, "tools/pi-subagent-bridge/src")
  try {
    mkdirSync(src, { recursive: true })
    const config = join(root, "harnesses.json")
    writeFileSync(config, JSON.stringify(HARNESS_SWITCHES))
    const before = snapshotSource(src)
    assert.equal(sourceChanged(before, src), null)
    writeFileSync(config, JSON.stringify({ ...HARNESS_SWITCHES, "command-code": true }))
    assert.equal(sourceChanged(before, src), "../../../harnesses.json")
  } finally { rmSync(root, { recursive: true, force: true }) }
})
