/**
 * Authoritative, typed tier lattice for nested Pi delegation.
 * No God tier exists in this bridge. A child can have only one more generation.
 */
export const TIERS = ["scout", "mechanic", "worker", "expert"] as const
export type Tier = (typeof TIERS)[number]
export type AllowedChild = {
  scout: "scout"
  mechanic: "scout" | "mechanic"
  worker: "scout" | "mechanic" | "worker"
  expert: Tier
}
export type ChildOf<P extends Tier> = AllowedChild[P]

export const MAX_SUBAGENT_DEPTH = 2 as const

export const DELEGATION = {
  scout: ["scout"],
  mechanic: ["scout", "mechanic"],
  worker: ["scout", "mechanic", "worker"],
  expert: ["scout", "mechanic", "worker", "expert"],
} as const satisfies { readonly [P in Tier]: readonly AllowedChild[P][] }

export const GO_TIER_MODELS = {
  scout: { providerID: "opencode-go", id: "muse-spark-1.3-contributor", variant: "medium" },
  mechanic: { providerID: "opencode-go", id: "muse-spark-1.3-contributor", variant: "high" },
  worker: { providerID: "opencode-go", id: "deepseek-v4.1-flash", variant: "high" },
  expert: { providerID: "opencode-go", id: "deepseek-v4.1-flash", variant: "max" },
} as const satisfies { readonly [P in Tier]: {
  readonly providerID: "opencode-go"
  readonly id: "muse-spark-1.3-contributor" | "deepseek-v4.1-flash"
  readonly variant: "medium" | "high" | "max"
} }

/** Exact subscription-backed Muse models */
export const MUSE_TIER_MODELS = {
  scout: { providerID: "muse-sdk", id: "muse-ember-1.0", variant: "medium" },
  mechanic: { providerID: "muse-sdk", id: "muse-ember-1.0", variant: "xhigh" },
  worker: { providerID: "muse-sdk", id: "muse-spark-1.3", variant: "xhigh" },
} as const satisfies Partial<Record<Tier, {
  readonly providerID: "muse-sdk"; readonly id: string; readonly variant: string
}>> & {
  scout: { providerID: "muse-sdk"; id: "muse-ember-1.0"; variant: "medium" }
  mechanic: { providerID: "muse-sdk"; id: "muse-ember-1.0"; variant: "xhigh" }
  worker: { providerID: "muse-sdk"; id: "muse-spark-1.3"; variant: "xhigh" }
}
export type MuseTier = keyof typeof MUSE_TIER_MODELS
export const MUSE_AGENT_NAMES = { scout: "muse-scout", mechanic: "muse-mechanic", worker: "muse-worker" } as const
export const MUSE_DELEGATION = {
  scout: ["muse-scout"],
  mechanic: ["muse-scout", "muse-mechanic"],
  worker: ["muse-scout", "muse-mechanic", "muse-worker"],
} as const satisfies { readonly [P in MuseTier]: readonly string[] }
export function isMuseTier(tier: Tier): tier is MuseTier {
  return tier === "scout" || tier === "mechanic" || tier === "worker"
}
export function museSubscriptionSelected(tier: Tier, _enabled?: boolean): tier is MuseTier {
  return isMuseTier(tier)
}

export const TIER_TOOLS = {
  scout: ["read", "grep", "find", "ls", "subagent", "subagent_supervisor"],
  mechanic: ["read", "bash", "edit", "write", "grep", "find", "ls", "subagent", "subagent_supervisor"],
  worker: ["read", "bash", "edit", "write", "grep", "find", "ls", "subagent", "subagent_supervisor"],
  expert: ["read", "bash", "edit", "write", "grep", "find", "ls", "subagent", "subagent_supervisor"],
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

export type GoModelRef = { providerID: string; id: string; variant?: string }
export function tierForModel(model: GoModelRef, readOnly: boolean): Tier {
  const tier = TIERS.find((candidate) => {
    const expected = GO_TIER_MODELS[candidate]
    return expected.providerID === model.providerID &&
      expected.id === model.id && expected.variant === model.variant
  })
  if (tier && readOnly === (tier === "scout")) return tier
  for (const candidate of ["scout", "mechanic", "worker"] as const) {
    const expected = MUSE_TIER_MODELS[candidate as keyof typeof MUSE_TIER_MODELS]
    if (!expected) continue
    if (model.providerID === expected.providerID && model.id === expected.id &&
        model.variant === expected.variant && readOnly === (candidate === "scout"))
      return candidate as Tier
  }
  throw new Error("Unapproved Pi tier, model/effort or tool scope")
}
