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

test("Devin preflight requires a synced Pi profile for every Devin agent override named in settings", () => {
  const home = mkdtempSync(join(tmpdir(), "usr-devin-profiles-"))
  const env: NodeJS.ProcessEnv = { XDG_CACHE_HOME: join(home, ".cache") }
  const resolveExtension = () => "/fixture/pi-devin-local/extensions/index.js"
  try {
    mkdirSync(join(home, ".local/share/devin"), { recursive: true })
    writeFileSync(join(home, ".local/share/devin/credentials.toml"), 'windsurf_api_key = "fixture-only"\n')
    mkdirSync(join(home, ".cache/pi-devin"), { recursive: true })
    writeFileSync(devinCatalogPath(env, home), JSON.stringify({ version: 1, fetchedAt: 0, catalog: {
      families: [{ slug: "swe-2.1", variants: ["swe-2-1-low", "swe-2-1-medium", "swe-2-1-high", "swe-2-1-max"].map(uid => ({ model_uid: uid })) }],
    } }))
    // Without settings there are no overrides, so the check is inert.
    assert.deepEqual(devinPreflight(env, home, resolveExtension), { available: true, issue: null })
    const agentDir = join(home, ".pi/agent")
    mkdirSync(join(agentDir, "agents"), { recursive: true })
    const settings = (overrides: Record<string, unknown>) =>
      writeFileSync(join(agentDir, "settings.json"), JSON.stringify({ subagents: { agentOverrides: overrides } }))
    // The incident shape: settings name devin-expert but agents/devin-expert.md is not linked yet.
    settings({ "devin-expert": { model: "devin/swe-2.1", thinking: "max" }, worker: { model: "opencode-go/deepseek-v4.1-flash", thinking: "high" } })
    const missing = devinPreflight(env, home, resolveExtension)
    assert.equal(missing.available, false)
    assert.match(missing.issue ?? "", /Pi profile devin-expert\.md is not installed; run sh sync/)
    // Overrides that are not Devin agents are outside this Devin-specific check.
    assert.doesNotMatch(missing.issue ?? "", /[^-]worker\.md/)
    // With the profile present the preflight is unchanged.
    writeFileSync(join(agentDir, "agents", "devin-expert.md"), "---\nname: devin-expert\n---\n")
    assert.deepEqual(devinPreflight(env, home, resolveExtension), { available: true, issue: null })
    // Every other missing Devin profile is named; installed ones are not.
    settings({ "devin-expert": { model: "devin/swe-2.1", thinking: "max" }, "devin-scout": { model: "devin/swe-2.1", thinking: "low" } })
    const partial = devinPreflight(env, home, resolveExtension)
    assert.equal(partial.available, false)
    assert.match(partial.issue ?? "", /devin-scout\.md is not installed; run sh sync/)
    assert.doesNotMatch(partial.issue ?? "", /devin-expert\.md is not installed/)
    // PI_CODING_AGENT_DIR relocates both settings and agents, the way the Pi runtime resolves them.
    const relocated = join(home, "elsewhere")
    mkdirSync(join(relocated, "agents"), { recursive: true })
    writeFileSync(join(relocated, "settings.json"), JSON.stringify({ subagents: { agentOverrides: { "devin-mechanic": {} } } }))
    const relocatedEnv = { ...env, PI_CODING_AGENT_DIR: relocated }
    assert.match(devinPreflight(relocatedEnv, home, resolveExtension).issue ?? "", /Pi profile devin-mechanic\.md is not installed; run sh sync/)
    writeFileSync(join(relocated, "agents", "devin-mechanic.md"), "---\nname: devin-mechanic\n---\n")
    assert.deepEqual(devinPreflight(relocatedEnv, home, resolveExtension), { available: true, issue: null })
    // A tilde-prefixed PI_CODING_AGENT_DIR expands against the same home.
    const tildeEnv = { ...env, PI_CODING_AGENT_DIR: "~/elsewhere" }
    assert.deepEqual(devinPreflight(tildeEnv, home, resolveExtension), { available: true, issue: null })
    // Malformed or missing settings never fail the preflight by themselves.
    writeFileSync(join(relocated, "settings.json"), "not json")
    assert.deepEqual(devinPreflight(relocatedEnv, home, resolveExtension), { available: true, issue: null })
  } finally {
    rmSync(home, { recursive: true, force: true })
  }
})
