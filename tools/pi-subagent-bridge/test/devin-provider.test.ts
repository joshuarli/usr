import test from "node:test"
import assert from "node:assert/strict"
import { mkdirSync, mkdtempSync, rmSync, writeFileSync } from "node:fs"
import { tmpdir } from "node:os"
import { join } from "node:path"
import { devinPreflight, devinCatalogPath } from "../src/devin-provider.ts"

test("Devin preflight is read-only and requires official CLI credentials plus cached SWE-2.1 pins", () => {
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
    const catalog = (uids: string[]) => ({ version: 1, fetchedAt: Date.now(), catalog: {
      families: [{ slug: "swe-2.1", family_label: "SWE-2.1", family_uid: "swe-2-1",
        variants: uids.map(uid => ({ model_uid: uid, label: "SWE-2.1" })) }],
    } })
    writeFileSync(cache, JSON.stringify(catalog(["swe-2-1-high"])))
    assert.equal(devinPreflight(env, home, resolveExtension).available, false)
    writeFileSync(cache, JSON.stringify(catalog(["swe-2-1-low", "swe-2-1-medium", "swe-2-1-high"])))
    assert.equal(devinPreflight(env, home, resolveExtension).available, false)
    writeFileSync(cache, JSON.stringify(catalog(["swe-2-1-low", "swe-2-1-medium", "swe-2-1-high", "swe-2-1-max"])))
    assert.deepEqual(devinPreflight(env, home, resolveExtension), { available: true, issue: null })
    assert.match(devinPreflight(env, home, () => { throw Error("not installed") }).issue ?? "", /pi-devin-local missing/)
  } finally {
    rmSync(home, { recursive: true, force: true })
  }
})

test("the Pi port advertises every pinned Devin variant, so each Devin tier passes model check", async () => {
  const { devinModelEntry } = await import("../src/pi-port.ts")
  const { DEVIN_TIER_MODELS } = await import("../src/tier-policy.ts")
  const entry = devinModelEntry()
  assert.equal(entry.providerID, "devin")
  assert.deepEqual(entry.variants.map(v => v.id).sort(),
    [...new Set(Object.values(DEVIN_TIER_MODELS).map(pin => pin.variant))].sort())
  for (const pin of Object.values(DEVIN_TIER_MODELS))
    assert.ok(entry.id === pin.id && entry.variants.some(v => v.id === pin.variant), pin.variant)
})
