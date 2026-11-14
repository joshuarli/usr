import test from "node:test"
import assert from "node:assert/strict"
import {
  ANTIGRAVITY_PIN, BANNED_MODELS, CODEX_TIER_MODELS, COMMAND_TIER_MODELS,
  NATIVE_FALLBACK, OPENCODE_NATIVE, POLICY, ROOT_ROUTES, isBannedModel, rootPlan,
} from "../src/policy.ts"
import { GO_TIER_MODELS, PI_MODEL_ALLOWLIST, TIER_TOOLS, TIERS, isTier } from "../src/tier-policy.ts"

test("root admission keeps ordered lower-tier fallback and a terminal expert executor", () => {
  assert.deepEqual(ROOT_ROUTES.scout.map(route => route.executor), ["codex", "command-code", "pi"])
  assert.deepEqual(ROOT_ROUTES.mechanic.map(route => route.executor), ["codex", "command-code", "pi"])
  assert.deepEqual(ROOT_ROUTES.worker.map(route => route.executor), ["codex", "command-code", "pi", "pi"])
  assert.deepEqual(ROOT_ROUTES.expert, [{ executor: "antigravity", model: "gemini-4-hydrogen-xhigh", effort: "xhigh" }])
  assert.equal(ROOT_ROUTES.worker[2]?.providerID, "muse-sdk")
  assert.equal(ROOT_ROUTES.worker[3]?.providerID, "opencode-go")
  assert.equal(isTier("god"), false)
  for (const tier of ["scout", "mechanic", "worker"] as const) {
    assert.equal(ROOT_ROUTES[tier][0].model, CODEX_TIER_MODELS[tier].model)
    assert.equal(ROOT_ROUTES[tier][1].effort, COMMAND_TIER_MODELS[tier].effort)
  }
})

test("native contexts cannot become root expert fallbacks", () => {
  assert.equal(GO_TIER_MODELS.expert.providerID, "opencode-go")
  assert.notEqual(GO_TIER_MODELS.expert.id, ANTIGRAVITY_PIN.model)
  assert.deepEqual(NATIVE_FALLBACK.tiers, ["scout", "mechanic", "worker"])
  assert.equal(OPENCODE_NATIVE.usesBridge, false)
  assert.equal(OPENCODE_NATIVE.freeOnlyWhenParentFree, true)
  assert.ok(OPENCODE_NATIVE.model.endsWith("-free"))
  assert.deepEqual(OPENCODE_NATIVE.efforts, { scout: "low", mechanic: "medium", worker: "high", expert: "max" })
})

test("runtime plans resolve the same ordered routes and keep expert exclusive", () => {
  const expert = rootPlan("expert")
  assert.deepEqual(expert, { kind: "exclusive", pin: { model: "gemini-4-hydrogen-xhigh", effort: "xhigh" } })
  const worker = rootPlan("worker")
  assert.equal(worker.kind, "fallback")
  if (worker.kind !== "fallback") throw new Error("worker must retain its approved fallbacks")
  assert.deepEqual(worker.pi.map(pin => pin.providerID), ["muse-sdk", "opencode-go"])
  assert.deepEqual(worker.codex, { model: "gpt-6.1-terra", effort: "medium" })
  assert.deepEqual(worker.command, { model: "deepseek/deepseek-v4.1-flash", effort: "high" })
})

test("prohibited model families include every effort variant but not unrelated names", () => {
  for (const model of ["gemini-4-argon", "gemini-4-argon-low", "gemini-4-carbon-xhigh", "google/gemini-4-carbon-high"]) {
    assert.equal(isBannedModel(model), true, model)
  }
  assert.equal(isBannedModel("gemini-4-carbonite"), false)
  for (const routes of Object.values(ROOT_ROUTES)) {
    for (const route of routes) assert.equal(isBannedModel(route.model), false, route.model)
  }
  assert.deepEqual(BANNED_MODELS, ["gemini-4-argon", "gemini-4-carbon"])
})

test("projection contains each native model once without widening read-only tools", () => {
  assert.deepEqual(PI_MODEL_ALLOWLIST, [
    "opencode-go/deepseek-v4.1-flash", "opencode-go/muse-spark-1.3-contributor", "muse-sdk/muse-spark-1.3",
  ])
  assert.equal(new Set(PI_MODEL_ALLOWLIST).size, PI_MODEL_ALLOWLIST.length)
  for (const tool of ["bash", "edit", "write"]) assert.equal((TIER_TOOLS.scout as readonly string[]).includes(tool), false)
  assert.deepEqual(JSON.parse(JSON.stringify(POLICY)), POLICY)
  assert.deepEqual(Object.keys(POLICY.rootRoutes), POLICY.tiers)
})
