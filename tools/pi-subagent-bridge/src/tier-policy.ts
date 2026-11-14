/**
 * Authoritative, typed tier lattice for nested Pi delegation.
 * No God tier exists in this bridge. A child can have only one more generation.
 */
export const TIERS = ["scout", "mechanic", "worker", "expert"] as const
export type Tier = (typeof TIERS)[number]
export type Effort = "low" | "medium" | "high" | "xhigh" | "max"

export const MAX_SUBAGENT_DEPTH = 2 as const

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
  museSpark: { providerID: "muse-sdk", id: "muse-spark-1.3" },
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

export const MUSE_TIER_MODELS = {
  worker: { ...PI_MODELS.museSpark, variant: "xhigh" },
} as const satisfies {
  readonly worker: { readonly providerID: "muse-sdk"; readonly id: string; readonly variant: Effort }
}
export const MUSE_AGENT_NAMES = { worker: "muse-worker" } as const
export const MUSE_DELEGATION = {
  worker: DELEGATION.worker.map(tier => tier === "worker" ? MUSE_AGENT_NAMES.worker : tier),
} as const satisfies { readonly worker: readonly string[] }
export function isMuseTier(tier: Tier): tier is "worker" {
  return tier === "worker"
}
export function museSubscriptionSelected(tier: Tier, _enabled?: boolean): tier is "worker" {
  return isMuseTier(tier)
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
  if (model.providerID === MUSE_TIER_MODELS.worker.providerID &&
      model.id === MUSE_TIER_MODELS.worker.id &&
      model.variant === MUSE_TIER_MODELS.worker.variant && !readOnly)
    return "worker"
  const tier = TIERS.find((candidate) => {
    const expected = GO_TIER_MODELS[candidate]
    return expected.providerID === model.providerID &&
      expected.id === model.id && expected.variant === model.variant
  })
  if (tier && readOnly === (tier === "scout")) return tier
  throw new Error("Unapproved Pi tier, model/effort or tool scope")
}
