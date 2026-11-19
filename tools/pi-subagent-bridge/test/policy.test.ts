import test from "node:test"
import assert from "node:assert/strict"
import {
  ANTIGRAVITY_DIRECT, BANNED_MODELS, CODEX_TIER_MODELS, COMMAND_TIER_MODELS,
  NATIVE_FALLBACK, OPENCODE_NATIVE, POLICY, ROOT_PLANS, isBannedModel, routesOf,
} from "../src/policy.ts"
import { GO_TIER_MODELS, PI_MODEL_ALLOWLIST, TIER_TOOLS, isTier, BRIDGE_TIERS } from "../src/tier-policy.ts"

test("root admission keeps ordered lower-tier fallback and no expert route", () => {
  assert.deepEqual(routesOf(ROOT_PLANS.scout).map(route => route.executor), ["codex", "command-code", "pi"])
  assert.deepEqual(routesOf(ROOT_PLANS.mechanic).map(route => route.executor), ["codex", "command-code", "pi"])
  assert.deepEqual(routesOf(ROOT_PLANS.worker).map(route => route.executor), ["codex", "command-code", "pi", "pi", "pi"])
  assert.deepEqual(ROOT_PLANS.worker.pi.map(pin => pin.providerID), ["muse-sdk", "opencode-go", "devin"])
  assert.equal("expert" in ROOT_PLANS, false)
  assert.equal("expert" in POLICY.rootRoutes, false)
  assert.equal(isTier("god"), false)
  assert.deepEqual([...BRIDGE_TIERS], ["scout", "mechanic", "worker"])
  for (const tier of ["scout", "mechanic", "worker"] as const) {
    assert.deepEqual(ROOT_PLANS[tier].codex, CODEX_TIER_MODELS[tier])
    assert.deepEqual(ROOT_PLANS[tier].command, COMMAND_TIER_MODELS[tier])
  }
})

test("native expert paths are first-class and Claude Code pins opus at xhigh effort", () => {
  assert.equal(GO_TIER_MODELS.expert.providerID, "opencode-go")
  assert.deepEqual(NATIVE_FALLBACK.tiers, ["scout", "mechanic", "worker"])
  assert.deepEqual(NATIVE_FALLBACK.claudeModels, { scout: "haiku", mechanic: "sonnet", worker: "sonnet", expert: "opus" })
  assert.deepEqual(NATIVE_FALLBACK.claudeEffort, { expert: "xhigh" })
  assert.ok(OPENCODE_NATIVE.model.endsWith("-free"))
  assert.deepEqual(OPENCODE_NATIVE.efforts, { scout: "high", mechanic: "high", worker: "high", expert: "high" })
})

test("the plans are the pins the bridge admits, and the exported routes derive from them", () => {
  assert.equal(ROOT_PLANS.worker.kind, "fallback")
  assert.deepEqual(ROOT_PLANS.worker.codex, { model: "gpt-6.1-terra", effort: "high" })
  assert.deepEqual(ROOT_PLANS.worker.command, { model: "deepseek/deepseek-v4.1-flash", effort: "high" })
  for (const tier of BRIDGE_TIERS) assert.deepEqual(POLICY.rootRoutes[tier], routesOf(ROOT_PLANS[tier]))
})

test("prohibited model families include every effort variant but not unrelated names", () => {
  for (const model of [
    "gemini-3.8-flash", "google/gemini-3.8-pro", "gemini-4-argon", "gemini-4-argon-low", "gemini-4-carbon-xhigh", "google/gemini-4-carbon-high",
    "gpt-6-astra", "gpt-6.1-astra-high", "openai/gpt-6.2-astra-xhigh",
  ]) {
    assert.equal(isBannedModel(model), true, model)
  }
  assert.equal(isBannedModel("gemini-4-carbonite"), false)
  assert.equal(isBannedModel("openai/gpt-6.2-sol-xhigh"), false)
  for (const tier of BRIDGE_TIERS) {
    for (const route of routesOf(ROOT_PLANS[tier])) assert.equal(isBannedModel(route.model), false, tier + " " + route.model)
  }
  assert.deepEqual(BANNED_MODELS, [
    "gemini-3.8", "gemini-4-argon", "gemini-4-carbon", "gpt-6-astra", "gpt-6.1-astra", "gpt-6.2-astra",
  ])
})

test("projection contains each native model once without widening read-only tools", () => {
  assert.deepEqual(PI_MODEL_ALLOWLIST, [
    "opencode-go/deepseek-v4.1-flash", "opencode-go/muse-spark-1.3-contributor", "muse-sdk/muse-spark-1.3", "devin/swe-2-flash",
  ])
  assert.equal(new Set(PI_MODEL_ALLOWLIST).size, PI_MODEL_ALLOWLIST.length)
  for (const tool of ["bash", "edit", "write"]) assert.equal((TIER_TOOLS.scout as readonly string[]).includes(tool), false)
  assert.deepEqual(JSON.parse(JSON.stringify(POLICY)), POLICY)
  assert.deepEqual(Object.keys(POLICY.rootRoutes), POLICY.tiers)
})

test("Antigravity uses native-only Neon and Hydrogen tiers", () => {
  assert.deepEqual(ANTIGRAVITY_DIRECT.main, { model: "gemini-4-neon-high", effort: "high" })
  assert.deepEqual(ANTIGRAVITY_DIRECT.god, { model: "gemini-4-neon-xhigh", effort: "xhigh" })
  assert.deepEqual(Object.keys(ANTIGRAVITY_DIRECT.tiers), ["scout", "mechanic", "worker", "expert"])
  for (const tier of ["scout", "mechanic", "worker"] as const) {
    assert.match(ANTIGRAVITY_DIRECT.tiers[tier].model, /^gemini-4-hydrogen-/)
    assert.equal(ANTIGRAVITY_DIRECT.tiers[tier].selector, "flash")
  }
  assert.equal(ANTIGRAVITY_DIRECT.tiers.expert.model, "gemini-4-neon-high")
  assert.equal(ANTIGRAVITY_DIRECT.tiers.expert.selector, "pro")
  assert.equal(isBannedModel(ANTIGRAVITY_DIRECT.manualCarbon), true)
  assert.ok(!(ANTIGRAVITY_DIRECT.models as readonly string[]).includes(ANTIGRAVITY_DIRECT.manualCarbon))
  assert.deepEqual(ANTIGRAVITY_DIRECT.retired, ["gemini-3.8-flash", "gemini-4-argon"])
})
