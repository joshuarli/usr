import { readFileSync } from "node:fs"
import { join } from "node:path"
import { parseDocument } from "yaml"
import {
  DELEGATION, GO_TIER_MODELS, isDevinTier, isMuseTier, MUSE_AGENT_NAMES, MUSE_DELEGATION, MUSE_TIER_MODELS,
  DEVIN_AGENT_NAMES, DEVIN_DELEGATION, DEVIN_TIER_MODELS,
  MAX_SUBAGENT_DEPTH, PI_MODEL_ALLOWLIST, PI_RUN_DEADLINE_MS, TIER_TOOLS, TIERS, type Tier,
} from "./tier-policy.ts"

const TIER_GUARDS = {
  scout: new URL("./guards/scout.ts", import.meta.url),
  mechanic: new URL("./guards/mechanic.ts", import.meta.url),
  worker: new URL("./guards/worker.ts", import.meta.url),
  expert: new URL("./guards/expert.ts", import.meta.url),
} as const satisfies Record<Tier, URL>

const MUSE_GUARDS = {
  worker: new URL("./guards/muse-worker.ts", import.meta.url),
} as const
const DEVIN_GUARDS = {
  worker: new URL("./guards/devin-worker.ts", import.meta.url),
} as const
export function tierGuardPath(tier: Tier, model?: { providerID: string }): URL {
  if (model?.providerID === "muse-sdk") {
    if (!isMuseTier(tier)) throw new Error("Muse cannot execute this tier")
    return MUSE_GUARDS[tier]
  }
  if (model?.providerID === "devin") {
    if (!isDevinTier(tier)) throw new Error("Devin cannot execute this tier")
    return DEVIN_GUARDS[tier]
  }
  return TIER_GUARDS[tier]
}

function record(value: unknown): Record<string, unknown> {
  if (!value || typeof value !== "object" || Array.isArray(value))
    throw new Error("Expected a policy object")
  return value as Record<string, unknown>
}

function exactList(value: unknown, expected: readonly string[], description: string): void {
  if (!Array.isArray(value) || value.length !== expected.length ||
      !value.every((item, index) => item === expected[index]))
    throw new Error(`Delegation policy drift in ${description}: expected exact typed allowlist`)
}

/**
 * A profile is a runtime contract consumed by pi-subagents, not a guideline.
 * Validate the parsed YAML against the code-owned tier graph before admitting
 * a new root worker. A locally edited/synced profile cannot widen authority.
 */
export function assertTierProfile(tier: Tier, markdown: string, family: "go" | "muse" | "devin" = "go"): void {
  const match = /^---\r?\n([\s\S]*?)\r?\n---(?:\r?\n|$)/.exec(markdown)
  if (!match) throw new Error(`Missing Pi agent frontmatter: ${tier}`)
  const parsed = parseDocument(match[1]!, { uniqueKeys: true })
  if (parsed.errors.length) throw new Error(`Invalid Pi agent YAML ${tier}: ${parsed.errors[0]?.message}`)
  const config = record(parsed.toJS())
  let pinned: { readonly providerID: string; readonly id: string; readonly variant: string }
  let name: string
  let children: readonly string[]
  if (family === "devin" && isDevinTier(tier)) {
    pinned = DEVIN_TIER_MODELS[tier]
    name = DEVIN_AGENT_NAMES[tier]
    children = DEVIN_DELEGATION[tier]
  } else if (family === "muse" && isMuseTier(tier)) {
    pinned = MUSE_TIER_MODELS.worker
    name = MUSE_AGENT_NAMES.worker
    children = MUSE_DELEGATION.worker
  } else {
    if (family !== "go") throw new Error("Unapproved special provider tier")
    pinned = GO_TIER_MODELS[tier]
    name = tier
    children = DELEGATION[tier]
  }
  if (config.name !== name ||
      config.model !== pinned.providerID + "/" + pinned.id ||
      config.thinking !== pinned.variant ||
      config.maxSubagentDepth !== MAX_SUBAGENT_DEPTH ||
      config.allowNestedSubagents !== true ||
      config.timeoutMs !== PI_RUN_DEADLINE_MS)
    throw new Error(`Unapproved Pi tier profile for ${tier}`)
  exactList(config.tools, TIER_TOOLS[tier], `${tier}.tools`)
  exactList(config.allowedAgents, children, `${name}.allowedAgents`)
  // Arbitrary extension, runner, model-scope, or tool overrides are not part of
  // the bridge's delegation surface. Fail closed rather than ignore them.
  const allowedFields = new Set([
    "name", "description", "model", "thinking", "tools",
    "maxSubagentDepth", "allowNestedSubagents", "allowedAgents", "timeoutMs",
  ])
  if (Object.keys(config).some((field) => !allowedFields.has(field)))
    throw new Error(`Unapproved Pi agent profile setting for ${tier}`)
}

export function assertTierProfiles(agentDir: string): void {
  const settings = record(JSON.parse(readFileSync(join(agentDir, "settings.json"), "utf8")))
  const sub = record(settings.subagents)
  const modelScope = record(sub.modelScope)
  const extensionConfig = record(JSON.parse(readFileSync(join(agentDir, "extensions", "subagent", "config.json"), "utf8")))
  if (extensionConfig.maxSubagentDepth !== MAX_SUBAGENT_DEPTH ||
      modelScope.enforce !== true || modelScope.strict !== true)
    throw new Error("Pi subagent depth/model scope must be enforced")
  exactList(modelScope.allow, PI_MODEL_ALLOWLIST, "global.modelScope.allow")
  const overrides = record(sub.agentOverrides)
  const agents = record(modelScope.agents)
  for (const tier of TIERS) {
    assertTierProfile(tier, readFileSync(join(agentDir, "agents", tier + ".md"), "utf8"))
    const expected = GO_TIER_MODELS[tier]
    const override = record(overrides[tier])
    if (override.model !== expected.providerID + "/" + expected.id ||
        override.thinking !== expected.variant)
      throw new Error(`Unapproved Pi model override for ${tier}`)
    exactList(record(agents[tier]).allow, [expected.providerID + "/" + expected.id],
      `${tier}.modelScope.allow`)
  }
  const musePin = MUSE_TIER_MODELS.worker
  const museName = MUSE_AGENT_NAMES.worker
  assertTierProfile("worker", readFileSync(join(agentDir, "agents", museName + ".md"), "utf8"), "muse")
  const museOverride = record(overrides[museName])
  if (museOverride.model !== musePin.providerID + "/" + musePin.id ||
      museOverride.thinking !== musePin.variant)
    throw new Error(`Unapproved Pi model override for ${museName}`)
  exactList(record(agents[museName]).allow, [musePin.providerID + "/" + musePin.id],
    `${museName}.modelScope.allow`)
  for (const tier of Object.keys(DEVIN_TIER_MODELS) as (keyof typeof DEVIN_TIER_MODELS)[]) {
    const devinPin = DEVIN_TIER_MODELS[tier]
    const devinName = DEVIN_AGENT_NAMES[tier]
    assertTierProfile(tier, readFileSync(join(agentDir, "agents", devinName + ".md"), "utf8"), "devin")
    const devinOverride = record(overrides[devinName])
    if (devinOverride.model !== devinPin.providerID + "/" + devinPin.id ||
        devinOverride.thinking !== devinPin.variant)
      throw new Error("Unapproved Devin model override for " + devinName)
    exactList(record(agents[devinName]).allow, [devinPin.providerID + "/" + devinPin.id],
      devinName + ".modelScope.allow")
  }
  const allowedNames: readonly string[] = [...TIERS, ...Object.values(MUSE_AGENT_NAMES), ...Object.values(DEVIN_AGENT_NAMES)]
  if (Object.keys(overrides).some(name => !allowedNames.includes(name)) ||
      Object.keys(agents).some(name => !allowedNames.includes(name)))
    throw new Error("Unapproved additional Pi subagent tier override")
}
