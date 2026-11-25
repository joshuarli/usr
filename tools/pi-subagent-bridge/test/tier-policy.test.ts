import test from "node:test"
import assert from "node:assert/strict"
import { mkdtempSync, mkdirSync, rmSync, writeFileSync, existsSync } from "node:fs"
import { tmpdir } from "node:os"
import { join } from "node:path"
import {
  assertDelegation, canDelegate, DELEGATION, GO_TIER_MODELS,
  DEVIN_TIER_MODELS, DEVIN_AGENT_NAMES, DEVIN_DELEGATION,
  MAX_SUBAGENT_DEPTH, PI_MODEL_ALLOWLIST, PI_RUN_DEADLINE_MS,
  TIER_TOOLS, TIERS, tierForModel, type ChildOf, type Tier,
} from "../src/tier-policy.ts"
import { nestedCallRefusal, registerTierGuard } from "../src/nested-guard.ts"
import { resolveCurrentSubagentCapabilityCeiling } from "pi-subagents/capability-ceiling"
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent"
import { assertTierProfile, assertTierProfiles, tierGuardPath } from "../src/tier-profile.ts"

// The types must reject an expert/grandchild escalation even when the caller is
// generically parameterized. @ts-expect-error checks are compile-time gates.
function typechecked<P extends Tier>(_parent: P, _child: NoInfer<ChildOf<P>>): void {}
if (false) {
  typechecked("worker", "scout")
  typechecked("worker", "worker")
  // @ts-expect-error experts exceed the worker tier
  typechecked("worker", "expert")
  // @ts-expect-error only scout may descend from scout
  typechecked("scout", "mechanic")
  // @ts-expect-error god is not a Tier at all
  typechecked("expert", "god")
}

function profile(tier: Tier, family: "go" | "devin" = "go"): string {
  const devin = family === "devin"
  const devinTier = tier as keyof typeof DEVIN_TIER_MODELS
  const pin = devin ? DEVIN_TIER_MODELS[devinTier] : GO_TIER_MODELS[tier]
  const name = devin ? DEVIN_AGENT_NAMES[devinTier] : tier
  const children = devin ? DEVIN_DELEGATION[devinTier] : DELEGATION[tier]
  return [
    "---", "name: " + name, "description: Fixed profile",
    "model: " + pin.providerID + "/" + pin.id,
    "thinking: " + pin.variant,
    "tools:", ...TIER_TOOLS[tier].map(tool => "  - " + tool),
    "allowNestedSubagents: true",
    "maxSubagentDepth: " + MAX_SUBAGENT_DEPTH,
    "timeoutMs: " + PI_RUN_DEADLINE_MS,
    "allowedAgents:", ...(children as readonly string[]).map((child) => "  - " + child),
    "---", "Profile body.",
  ].join("\n") + "\n"
}
function profileSettings(): object {
  return { subagents: {
    agentOverrides: Object.fromEntries([
      ...TIERS.map((tier) => [tier, { model: GO_TIER_MODELS[tier].providerID + "/" + GO_TIER_MODELS[tier].id,
        thinking: GO_TIER_MODELS[tier].variant }]),
      ...Object.entries(DEVIN_TIER_MODELS).map(([tier, pin]) => [
        DEVIN_AGENT_NAMES[tier as keyof typeof DEVIN_AGENT_NAMES],
        { model: pin.providerID + "/" + pin.id, thinking: pin.variant }]),
    ]),
    modelScope: { enforce: true, strict: true,
      allow: [...PI_MODEL_ALLOWLIST],
      agents: Object.fromEntries([
        ...TIERS.map((tier) => [tier, { allow: [GO_TIER_MODELS[tier].providerID + "/" + GO_TIER_MODELS[tier].id] }]),
        ...Object.entries(DEVIN_TIER_MODELS).map(([tier, pin]) => [
          DEVIN_AGENT_NAMES[tier as keyof typeof DEVIN_AGENT_NAMES],
          { allow: [pin.providerID + "/" + pin.id] }]),
      ]),
    },
  } }
}

test("typed lattice is reflexive/monotone and excludes escalation or god", () => {
  assert.equal(MAX_SUBAGENT_DEPTH, 2)
  const expected = [1, 2, 3, 4]
  for (const [i, parent] of TIERS.entries()) {
    assert.equal(DELEGATION[parent].length, expected[i])
    for (const child of TIERS) assert.equal(canDelegate(parent, child), TIERS.indexOf(child) <= i)
    assert.throws(() => assertDelegation(parent, "god"), /cannot delegate/)
  }
  assert.equal(canDelegate("worker", "mechanic"), true)
  assert.equal(canDelegate("worker", "expert"), false)
})

test("pinned model / effective effort is a typed role identity, not a string lookup", () => {
  for (const tier of TIERS) {
    const model = GO_TIER_MODELS[tier]
    assert.equal(tierForModel(model, tier === "scout"), tier)
    assert.throws(() => tierForModel({ ...model, variant: "xhigh" }, tier === "scout"), /Unapproved/)
  }
  assert.throws(() => tierForModel({ providerID: "muse-sdk", id: "muse-spark-1.3", variant: "max" }, false), /Unapproved/)
})

test("code-owned tool boundary rejects model overrides, scripts, tier escalation, worktree escape", () => {
  assert.equal(nestedCallRefusal("worker", "subagent", { agent: "scout", task: "Read relevant files", options: { agentScope: "user" } }), undefined)
  assert.equal(nestedCallRefusal("mechanic", "subagent", { agent: "mechanic", task: "Make scoped change", options: { agentScope: "user" } }), undefined)
  assert.equal(nestedCallRefusal("expert", "subagent", { agent: "expert", task: "Investigate", options: { agentScope: "user" } }), undefined)
  for (const input of [
    { agent: "expert", task: "escalate", options: { agentScope: "user" } },
    { agent: "worker", task: "missing scope" },
    { agent: "worker", task: "project shadow", options: { agentScope: "project" } },
    { agent: "worker", task: "mixed options", options: { agentScope: "user", model: "opencode-go/deepseek-v4.1-flash:max" } },
    { agent: "god", task: "escalate" },
    { agent: "worker", task: "bypass", options: { agentScope: "user" }, model: "opencode-go/deepseek-v4.1-flash:max" },
    { agent: "worker", task: "bypass", cwd: "/tmp/outside" },
    { agent: "worker", task: "bypass", worktree: true },
    { agent: "worker", task: "bypass", options: { model: "expert" } },
    { agent: "worker", task: "bypass", tools: ["bash"] },
    { agent: "worker", task: "bypass", workflow: "./script.js" },
    { agent: "worker", task: "bypass", count: 4 },
    { agent: "worker", task: "" },
  ]) assert.ok(nestedCallRefusal("worker", "subagent", input), JSON.stringify(input))
  assert.ok(nestedCallRefusal("worker", "subagent_launch", { agent: "worker" }))
  assert.ok(nestedCallRefusal("scout", "subagent", { agent: "mechanic", task: "edit", options: { agentScope: "user" } }))
  assert.equal(nestedCallRefusal("worker", "subagent", { action: "status", id: "a" }), undefined)
  assert.ok(nestedCallRefusal("worker", "subagent", { action: "create" }))
  assert.equal(nestedCallRefusal("worker", "read", { path: "README" }), undefined)
})

test("real YAML profiles are validated as runtime policy; drift fails before spawning", () => {
  for (const tier of TIERS) {
    const family = "go" as const
    assertTierProfile(tier, profile(tier, family), family)
    assert.ok(tierGuardPath(tier).pathname.endsWith("/" + tier + ".ts"))
    assert.throws(() => assertTierProfile(tier,
      profile(tier, family).replace("maxSubagentDepth: 2", "maxSubagentDepth: 3"), family), /Unapproved/)
    assert.throws(() => assertTierProfile(tier,
      profile(tier, family).replace("allowedAgents:", "allowedAgents:\n  - god"), family), /allowlist/)
    assert.throws(() => assertTierProfile(tier,
      profile(tier, family).replace("tools:", "tools:\n  - unrestricted_shell"), family), /allowlist/)
    assert.throws(() => assertTierProfile(tier,
      profile(tier, family).replace("model: " + GO_TIER_MODELS[tier].providerID, "model: openrouter"), family), /Unapproved/)
    assert.throws(() => assertTierProfile(tier,
      profile(tier, family).replace("timeoutMs: " + PI_RUN_DEADLINE_MS, "timeoutMs: 1800000"), family), /Unapproved/)
    assert.throws(() => assertTierProfile(tier,
      profile(tier, family).replace("timeoutMs: " + PI_RUN_DEADLINE_MS + "\n", ""), family), /Unapproved/)
  }
  for (const tier of Object.keys(DEVIN_TIER_MODELS) as (keyof typeof DEVIN_TIER_MODELS)[]) {
    assertTierProfile(tier, profile(tier, "devin"), "devin")
    assert.ok(existsSync(tierGuardPath(tier, { providerID: "devin" })))
    assert.throws(() => assertTierProfile(tier,
      profile(tier, "devin").replace("thinking: " + DEVIN_TIER_MODELS[tier].variant, "thinking: xhigh"), "devin"), /Unapproved/)
  }
  assert.throws(() => assertTierProfile("expert", profile("expert"), "devin"), /Unapproved/)
  assert.throws(() => tierGuardPath("expert", { providerID: "devin" }), /Devin cannot/)
})

test("profile checks enforce one exact pinned scope and one max depth", () => {
  const home = mkdtempSync(join(tmpdir(), "usr-tier-policy-"))
  const agentDir = join(home, "agents")
  mkdirSync(agentDir)
  try {
    for (const tier of TIERS) writeFileSync(join(agentDir, tier + ".md"), profile(tier))
    for (const tier of Object.keys(DEVIN_TIER_MODELS) as (keyof typeof DEVIN_TIER_MODELS)[])
      writeFileSync(join(agentDir, DEVIN_AGENT_NAMES[tier] + ".md"), profile(tier, "devin"))
    const settings = profileSettings()
    writeFileSync(join(home, "settings.json"), JSON.stringify(settings))
    mkdirSync(join(home, "extensions", "subagent"), { recursive: true })
    writeFileSync(join(home, "extensions", "subagent", "config.json"), JSON.stringify({ maxSubagentDepth: 2 }))
    assert.doesNotThrow(() => assertTierProfiles(home))
    const extra = structuredClone(settings) as { subagents: { modelScope: { allow: string[] } } }
    extra.subagents.modelScope.allow.push("openrouter/foo")
    writeFileSync(join(home, "settings.json"), JSON.stringify(extra))
    assert.throws(() => assertTierProfiles(home), /allowlist/)
    writeFileSync(join(home, "settings.json"), JSON.stringify(settings))
    writeFileSync(join(home, "extensions", "subagent", "config.json"), JSON.stringify({ maxSubagentDepth: 3 }))
    assert.throws(() => assertTierProfiles(home), /depth\/model/)
  } finally {
    rmSync(home, { recursive: true, force: true })
  }
})

test("installed child guard registers a real monotonic capability ceiling", () => {
  const callbacks = new Map<string, (...args: unknown[]) => unknown>()
  const fakePi = { on(event: string, handler: (...args: unknown[]) => unknown) {
    callbacks.set(event, handler)
  } } as unknown as ExtensionAPI
  registerTierGuard("worker")(fakePi)
  const sessionId = "usr-capability-test"
  const started = callbacks.get("session_start")
  const launch = callbacks.get("tool_call")
  const shutdown = callbacks.get("session_shutdown")
  assert.ok(started && launch && shutdown)
  started({}, { sessionManager: { getSessionId: () => sessionId } })
  try {
    assert.deepEqual(resolveCurrentSubagentCapabilityCeiling(sessionId)?.allowedAgents,
      ["mechanic", "scout", "worker"])
    const refused = launch({ toolName: "subagent",
      input: { agent: "expert", task: "Escalate", options: { agentScope: "user" } } })
    assert.deepEqual(refused, { block: true, reason: "Tier worker cannot delegate to expert" })
    assert.equal(launch({ toolName: "subagent",
      input: { agent: "mechanic", task: "Scoped change", options: { agentScope: "user" } } }), undefined)
  } finally {
    shutdown({})
  }
  assert.equal(resolveCurrentSubagentCapabilityCeiling(sessionId), undefined)
})

test("Devin pins SWE-2.1 thinking by tier; escapes fail closed", () => {
  for (const tier of Object.keys(DEVIN_TIER_MODELS) as (keyof typeof DEVIN_TIER_MODELS)[]) {
    const pin = DEVIN_TIER_MODELS[tier]
    assert.equal(tierForModel(pin, tier === "scout"), tier)
    assert.throws(() => tierForModel(pin, tier !== "scout"), /Unapproved/)
    for (const variant of ["off", "minimal", "xhigh", "max"])
      assert.throws(() => tierForModel({ ...pin, variant }, tier === "scout"), /Unapproved/)
    assert.equal(nestedCallRefusal(tier, "subagent", {
      agent: DEVIN_AGENT_NAMES[tier], task: "Implement", options: { agentScope: "user" },
    }, "devin"), undefined)
  }
  assert.ok(nestedCallRefusal("worker", "subagent", {
    agent: "worker", task: "Escalate", options: { agentScope: "user" },
  }, "devin"))
  assert.ok(nestedCallRefusal("worker", "subagent", {
    agent: "expert", task: "Escalate", options: { agentScope: "user" },
  }, "devin"))
  assert.ok(nestedCallRefusal("scout", "subagent", {
    agent: "mechanic", task: "Escalate", options: { agentScope: "user" },
  }, "devin"))
  assert.ok(nestedCallRefusal("expert", "subagent", {
    agent: "devin-worker", task: "Escalate", options: { agentScope: "user" },
  }, "devin"))
})
