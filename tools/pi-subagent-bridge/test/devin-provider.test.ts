import test from "node:test"
import assert from "node:assert/strict"
import { mkdirSync, mkdtempSync, rmSync, writeFileSync } from "node:fs"
import { tmpdir } from "node:os"
import { join } from "node:path"
import { devinPreflight, devinCatalogPath } from "../src/devin-provider.ts"

test("Devin preflight is read-only and requires official CLI credentials plus cached Flash medium model", () => {
  const home = mkdtempSync(join(tmpdir(), "usr-devin-"))
  const env: NodeJS.ProcessEnv = { XDG_CACHE_HOME: join(home, ".cache") }
  const resolveExtension = () => "/fixture/pi-devin-local/extensions/index.js"
  try {
    assert.match(devinPreflight(env, home, resolveExtension).issue ?? "", /credentials missing/)
    mkdirSync(join(home, ".local/share/devin"), { recursive: true })
    writeFileSync(join(home, ".local/share/devin/credentials.toml"), 'windsurf_api_key = "fixture-only"\n')
    assert.match(devinPreflight(env, home, resolveExtension).issue ?? "", /catalog absent/)
    const cache = devinCatalogPath(env, home)
    mkdirSync(join(home, ".cache/pi-devin"), { recursive: true })
    const catalog = (uid: string) => ({ version: 1, fetchedAt: Date.now(), catalog: {
      families: [{ slug: "swe-2-flash", family_label: "SWE-2 Flash", family_uid: "swe-2-flash",
        variants: [{ model_uid: uid, label: "SWE-2 Flash" }] }],
    } })
    writeFileSync(cache, JSON.stringify(catalog("swe-2-flash-high")))
    assert.equal(devinPreflight(env, home, resolveExtension).available, false)
    writeFileSync(cache, JSON.stringify(catalog("swe-2-flash-medium")))
    assert.deepEqual(devinPreflight(env, home, resolveExtension), { available: true, issue: null })
    assert.match(devinPreflight(env, home, () => { throw Error("not installed") }).issue ?? "", /pi-devin-local missing/)
  } finally {
    rmSync(home, { recursive: true, force: true })
  }
})
