import test from "node:test"
import assert from "node:assert/strict"
import { mkdtempSync, mkdirSync, rmSync, writeFileSync } from "node:fs"
import { tmpdir } from "node:os"
import { join } from "node:path"
import {
  assertDelegation, canDelegate, DELEGATION, GO_TIER_MODELS, MUSE_TIER_MODELS, MUSE_AGENT_NAMES,
  MUSE_DELEGATION, museSubscriptionSelected, MAX_SUBAGENT_DEPTH,
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

function profile(tier: Tier, family: "go" | "muse" = "go"): string {
  const muse = family === "muse" && ((tier === "scout" || tier === "mechanic" || tier === "worker") && (MUSE_TIER_MODELS as any)[tier])
  const pin = muse ? (MUSE_TIER_MODELS as any)[tier] : (GO_TIER_MODELS as any)[tier]
  const name = muse ? (MUSE_AGENT_NAMES as any)[tier] : tier
  const children = muse ? (MUSE_DELEGATION as any)[tier] : (DELEGATION as any)[tier]
  return [
    "---", "name: " + name, "description: Fixed profile",
    "model: " + pin.providerID + "/" + pin.id,
    "thinking: " + pin.variant,
    "tools:", ...(TIER_TOOLS as any)[tier].map((tool: string) => "  - " + tool),
    "allowNestedSubagents: true",
    "maxSubagentDepth: " + MAX_SUBAGENT_DEPTH,
    "allowedAgents:", ...(children as string[]).map((child: string) => "  - " + child),
    "---", "Profile body.",
  ].join("\n") + "\n"
}
function profileSettings(): object {
  return { subagents: {
    agentOverrides: Object.fromEntries([
      ...TIERS.map((tier) => [tier, { model: GO_TIER_MODELS[tier].providerID + "/" + GO_TIER_MODELS[tier].id,
        thinking: GO_TIER_MODELS[tier].variant }]),
      ...(["scout", "mechanic"] as const).map((tier) => [MUSE_AGENT_NAMES[tier], {
        model: (MUSE_TIER_MODELS as any)[tier].providerID + "/" + (MUSE_TIER_MODELS as any)[tier].id, thinking: (MUSE_TIER_MODELS as any)[tier].variant }]),
    ]),
    modelScope: { enforce: true, strict: true,
      allow: ["opencode-go/deepseek-v4.1-flash", "opencode-go/muse-spark-1.3-contributor",
        "muse-sdk/muse-spark-1.3", "muse-sdk/muse-ember-1.0"],
      agents: Object.fromEntries([
        ...TIERS.map((tier) => [tier, { allow: [GO_TIER_MODELS[tier].providerID + "/" + GO_TIER_MODELS[tier].id] }]),
        ...(["scout", "mechanic"] as const).map((tier) => [MUSE_AGENT_NAMES[tier], {
          allow: [(MUSE_TIER_MODELS as any)[tier].providerID + "/" + (MUSE_TIER_MODELS as any)[tier].id] }]),
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

test("Go model / effective effort is a typed role identity, not a string lookup", () => {
  for (const tier of TIERS) {
    const model = GO_TIER_MODELS[tier]
    assert.equal(tierForModel(model, tier === "scout"), tier)
    assert.throws(() => tierForModel({ ...model, providerID: "opencode" }, tier === "scout"), /Unapproved/)
    assert.throws(() => tierForModel({ ...model, variant: "xhigh" }, tier === "scout"), /Unapproved/)
  }
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
    assertTierProfile(tier, profile(tier))
    assert.ok(tierGuardPath(tier).pathname.endsWith("/" + tier + ".ts"))
    assert.throws(() => assertTierProfile(tier,
      profile(tier).replace("maxSubagentDepth: 2", "maxSubagentDepth: 3")), /Unapproved/)
    assert.throws(() => assertTierProfile(tier,
      profile(tier).replace("allowedAgents:", "allowedAgents:\n  - god")), /allowlist/)
    assert.throws(() => assertTierProfile(tier,
      profile(tier).replace("tools:", "tools:\n  - unrestricted_shell")), /allowlist/)
    assert.throws(() => assertTierProfile(tier,
      profile(tier).replace("model: opencode-go/", "model: opencode/")), /Unapproved/)
  }
})

test("profile checks enforce one exact Go scope and one max depth", () => {
  const home = mkdtempSync(join(tmpdir(), "usr-tier-policy-"))
  const agentDir = join(home, "agents")
  mkdirSync(agentDir)
  try {
    for (const tier of TIERS) writeFileSync(join(agentDir, tier + ".md"), profile(tier))
    for (const tier of ["scout", "mechanic"] as const)
      writeFileSync(join(agentDir, MUSE_AGENT_NAMES[tier] + ".md"), profile(tier, "muse"))
    const settings = profileSettings()
    writeFileSync(join(home, "settings.json"), JSON.stringify(settings))
    mkdirSync(join(home, "extensions", "subagent"), { recursive: true })
    writeFileSync(join(home, "extensions", "subagent", "config.json"), JSON.stringify({ maxSubagentDepth: 2 }))
    assert.doesNotThrow(() => assertTierProfiles(home))
    const zen = structuredClone(settings) as { subagents: { modelScope: { allow: string[] } } }
    zen.subagents.modelScope.allow.push("opencode/muse-ember-1.0")
    writeFileSync(join(home, "settings.json"), JSON.stringify(zen))
    assert.throws(() => assertTierProfiles(home), /allowlist/)
    zen.subagents.modelScope.allow.pop()
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

test("Muse opt-in pins and nested tiers fail closed", () => {
  for (const tier of ["scout", "mechanic", "worker"] as const) {
    assert.equal(museSubscriptionSelected(tier), true)
    assert.equal(tierForModel((MUSE_TIER_MODELS as any)[tier], tier === "scout"), tier)
  }
  assert.equal(museSubscriptionSelected("expert"), false)
  assert.throws(() => tierForModel({ providerID: "muse-sdk", id: "muse-spark-1.3", variant: "max" }, false), /Unapproved/)
  assert.equal(nestedCallRefusal("scout", "subagent", { agent: "muse-scout", task: "Research",
    options: { agentScope: "user" } }, "muse"), undefined)
  assert.equal(nestedCallRefusal("mechanic", "subagent", { agent: "muse-mechanic", task: "Fix",
    options: { agentScope: "user" } }, "muse"), undefined)
})
