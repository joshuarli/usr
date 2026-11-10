import { readFileSync } from "node:fs"
import { join } from "node:path"
import { parseDocument } from "yaml"
import {
  DELEGATION, GO_TIER_MODELS, MAX_SUBAGENT_DEPTH, TIER_TOOLS, TIERS, type Tier,
} from "./tier-policy.ts"

const TIER_GUARDS = {
  scout: new URL("./guards/scout.ts", import.meta.url),
  mechanic: new URL("./guards/mechanic.ts", import.meta.url),
  worker: new URL("./guards/worker.ts", import.meta.url),
  expert: new URL("./guards/expert.ts", import.meta.url),
} as const satisfies Record<Tier, URL>

export function tierGuardPath(tier: Tier): URL { return TIER_GUARDS[tier] }

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
export function assertTierProfile(tier: Tier, markdown: string): void {
  const match = /^---\r?\n([\s\S]*?)\r?\n---(?:\r?\n|$)/.exec(markdown)
  if (!match) throw new Error(`Missing Pi agent frontmatter: ${tier}`)
  const parsed = parseDocument(match[1]!, { uniqueKeys: true })
  if (parsed.errors.length) throw new Error(`Invalid Pi agent YAML ${tier}: ${parsed.errors[0]?.message}`)
  const config = record(parsed.toJS())
  const pinned = GO_TIER_MODELS[tier]
  if (config.name !== tier ||
      config.model !== pinned.providerID + "/" + pinned.id ||
      config.thinking !== pinned.variant ||
      config.maxSubagentDepth !== MAX_SUBAGENT_DEPTH ||
      config.allowNestedSubagents !== true)
    throw new Error(`Unapproved Pi tier profile for ${tier}`)
  exactList(config.tools, TIER_TOOLS[tier], `${tier}.tools`)
  exactList(config.allowedAgents, DELEGATION[tier], `${tier}.allowedAgents`)
  // Arbitrary extension, runner, model-scope, or tool overrides are not part of
  // the bridge's delegation surface. Fail closed rather than ignore them.
  const allowed = new Set([
    "name", "description", "model", "thinking", "tools",
    "maxSubagentDepth", "allowNestedSubagents", "allowedAgents",
  ])
  if (Object.keys(config).some((field) => !allowed.has(field)))
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
  exactList(modelScope.allow, [
    "opencode-go/deepseek-v4.1-flash",
    "opencode-go/muse-spark-1.3-contributor",
  ], "global.modelScope.allow")
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
  if (Object.keys(overrides).some((tier) => !TIERS.some((allowed) => allowed === tier)))
    throw new Error("Unapproved additional Pi subagent tier override")
}
