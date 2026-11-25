/**
 * Authoritative, typed tier lattice for nested Pi delegation.
 * No God tier exists in this bridge. A child can have only one more generation.
 */
export const TIERS = ["scout", "mechanic", "worker", "expert"] as const
export type Tier = (typeof TIERS)[number]
/** The bridge admits only these tiers. Expert is pi-only: its single route is the pinned Devin max lane. */
export const BRIDGE_TIERS = ["scout", "mechanic", "worker", "expert"] as const
export type BridgeTier = (typeof BRIDGE_TIERS)[number]
export type Effort = "low" | "medium" | "high" | "xhigh" | "max"

export const MAX_SUBAGENT_DEPTH = 2 as const
// pi-subagents silently defaults an unset run to 30 minutes; the deadline is explicit instead.
export const PI_RUN_DEADLINE_MS: number = 4 * 60 * 60 * 1000

export const DELEGATION = {
  scout: ["scout"],
  mechanic: ["scout", "mechanic"],
  worker: ["scout", "mechanic", "worker"],
  expert: ["scout", "mechanic", "worker", "expert"],
} as const satisfies Record<Tier, readonly Tier[]>
export type ChildOf<P extends Tier> = (typeof DELEGATION)[P][number]
export type AllowedChild = { readonly [P in Tier]: ChildOf<P> }

const PI_MODELS = {
  goDeepSeek: { providerID: "opencode-go", id: "deepseek-v4.1-flash" },
  goSpark: { providerID: "opencode-go", id: "muse-spark-1.3-contributor" },
  devinSwe21: { providerID: "devin", id: "swe-2.1" },
} as const
export const PI_MODEL_ALLOWLIST = Object.values(PI_MODELS).map(({ providerID, id }) => `${providerID}/${id}`)

/** OpenCode Go serves the subsidized Contributor-Spark models under the same subscription as DeepSeek. */
export const GO_TIER_MODELS = {
  scout: { ...PI_MODELS.goSpark, variant: "medium" },
  mechanic: { ...PI_MODELS.goSpark, variant: "high" },
  worker: { ...PI_MODELS.goDeepSeek, variant: "high" },
  expert: { ...PI_MODELS.goDeepSeek, variant: "max" },
} as const satisfies { readonly [P in Tier]: {
  readonly providerID: "opencode-go"
  readonly id: string
  readonly variant: Effort
} }

/** Devin Local lanes. Each bridge tier keeps its own free SWE-2.1 thinking level. */
export const DEVIN_TIER_MODELS = {
  scout: { ...PI_MODELS.devinSwe21, variant: "low" },
  mechanic: { ...PI_MODELS.devinSwe21, variant: "medium" },
  worker: { ...PI_MODELS.devinSwe21, variant: "high" },
  expert: { ...PI_MODELS.devinSwe21, variant: "max" },
} as const satisfies {
  readonly scout: { readonly providerID: "devin"; readonly id: "swe-2.1"; readonly variant: "low" }
  readonly mechanic: { readonly providerID: "devin"; readonly id: "swe-2.1"; readonly variant: "medium" }
  readonly worker: { readonly providerID: "devin"; readonly id: "swe-2.1"; readonly variant: "high" }
  readonly expert: { readonly providerID: "devin"; readonly id: "swe-2.1"; readonly variant: "max" }
}
export type DevinTier = keyof typeof DEVIN_TIER_MODELS
/**
 * Devin's free tier admits about one concurrent lane and throttles mid-run with
 * short resets, stopping lanes that already have edits. Until that changes, no
 * bridge tier routes to Devin: the lower tiers' ladders omit it and the expert
 * tier, whose only route is Devin, is blocked. Devin stays usable as a
 * top-level native harness.
 */
export const DEVIN_BRIDGE_DISABLED =
  "Devin free-tier bridge lanes are disabled: the free tier admits about one concurrent lane and throttles mid-run, stopping lanes with partial edits; use Devin only as a top-level native harness"
export const DEVIN_AGENT_NAMES = {
  scout: "devin-scout",
  mechanic: "devin-mechanic",
  worker: "devin-worker",
  expert: "devin-expert",
} as const satisfies Record<BridgeTier, string>
export const DEVIN_DELEGATION = {
  scout: DELEGATION.scout.map(tier => tier === "scout" ? DEVIN_AGENT_NAMES.scout : tier),
  mechanic: DELEGATION.mechanic.map(tier => tier === "mechanic" ? DEVIN_AGENT_NAMES.mechanic : tier),
  worker: DELEGATION.worker.map(tier => tier === "worker" ? DEVIN_AGENT_NAMES.worker : tier),
  expert: DELEGATION.expert.map(tier => tier === "expert" ? DEVIN_AGENT_NAMES.expert : tier),
} as const satisfies Record<BridgeTier, readonly string[]>
export function isDevinTier(tier: Tier): tier is DevinTier {
  return tier in DEVIN_TIER_MODELS
}

const DISCOVERY_TOOLS = ["grep", "find", "ls", "subagent", "subagent_supervisor"] as const
const WRITER_TOOLS = ["read", "bash", "edit", "write", ...DISCOVERY_TOOLS] as const
export const TIER_TOOLS = {
  scout: ["read", ...DISCOVERY_TOOLS],
  mechanic: WRITER_TOOLS,
  worker: WRITER_TOOLS,
  expert: WRITER_TOOLS,
} as const satisfies { readonly [P in Tier]: readonly string[] }

export function isTier(value: unknown): value is Tier {
  return typeof value === "string" && TIERS.some((tier) => tier === value)
}
export function isBridgeTier(value: unknown): value is BridgeTier {
  return typeof value === "string" && BRIDGE_TIERS.some((tier) => tier === value)
}

export function canDelegate<P extends Tier>(parent: P, child: Tier): child is ChildOf<P> {
  return DELEGATION[parent].some((tier: Tier) => tier === child)
}

export function assertDelegation<P extends Tier>(parent: P, child: unknown): asserts child is ChildOf<P> {
  if (!isTier(child) || !canDelegate(parent, child))
    throw new Error(`Tier ${parent} cannot delegate to ${String(child)}`)
}

/** Exact pins admitted for nested spawns, per tier. */
export type GoModelRef = { providerID: string; id: string; variant?: string }
export function tierForModel(model: GoModelRef, readOnly: boolean): Tier {
  const devinTier = (Object.keys(DEVIN_TIER_MODELS) as DevinTier[]).find((candidate) => {
    const expected = DEVIN_TIER_MODELS[candidate]
    return model.providerID === expected.providerID &&
      model.id === expected.id && model.variant === expected.variant &&
      readOnly === (candidate === "scout")
  })
  if (devinTier) return devinTier
  const tier = TIERS.find((candidate) => {
    const expected = GO_TIER_MODELS[candidate]
    return expected.providerID === model.providerID &&
      expected.id === model.id && expected.variant === model.variant
  })
  if (tier && readOnly === (tier === "scout")) return tier
  throw new Error("Unapproved Pi tier, model/effort or tool scope")
}
