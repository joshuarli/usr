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

/** The sole permitted Zen pin: free, declared in ~/.pi/agent/models.json. */
export const ZEN_TIER_MODELS = {
  scout: { providerID: "opencode", id: "inkling-2-small-free", variant: "low" },
  mechanic: { providerID: "opencode", id: "inkling-2-small-free", variant: "high" },
} as const satisfies { readonly [P in "scout" | "mechanic"]: {
  readonly providerID: "opencode"
  readonly id: "inkling-2-small-free"
  readonly variant: "low" | "high"
} }
export type ZenTier = keyof typeof ZEN_TIER_MODELS
export function isZenTier(tier: Tier): tier is ZenTier {
  return tier === "scout" || tier === "mechanic"
}

export const GO_TIER_MODELS = {
  worker: { providerID: "opencode-go", id: "deepseek-v4.1-flash", variant: "high" },
  expert: { providerID: "opencode-go", id: "deepseek-v4.1-flash", variant: "max" },
} as const satisfies { readonly [P in "worker" | "expert"]: {
  readonly providerID: "opencode-go"
  readonly id: "deepseek-v4.1-flash"
  readonly variant: "high" | "max"
} }

export const MUSE_TIER_MODELS = {
  worker: { providerID: "muse-sdk", id: "muse-spark-1.3", variant: "xhigh" },
} as const satisfies {
  readonly worker: { readonly providerID: "muse-sdk"; readonly id: "muse-spark-1.3"; readonly variant: "xhigh" }
}
export const MUSE_AGENT_NAMES = { worker: "muse-worker" } as const
export const MUSE_DELEGATION = {
  worker: ["scout", "mechanic", "muse-worker"],
} as const satisfies { readonly worker: readonly string[] }
export function isMuseTier(tier: Tier): tier is "worker" {
  return tier === "worker"
}
export function museSubscriptionSelected(tier: Tier, _enabled?: boolean): tier is "worker" {
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

/** Exact pins admitted for nested spawns, per tier. */
export type GoModelRef = { providerID: string; id: string; variant?: string }
export function tierForModel(model: GoModelRef, readOnly: boolean): Tier {
  for (const candidate of TIERS) {
    const expected = candidate === "scout" || candidate === "mechanic"
      ? ZEN_TIER_MODELS[candidate]
      : candidate === "worker" ? MUSE_TIER_MODELS.worker : undefined
    if (expected && model.providerID === expected.providerID &&
        model.id === expected.id && model.variant === expected.variant &&
        readOnly === (candidate === "scout"))
      return candidate
  }
  for (const candidate of ["worker", "expert"] as const) {
    const expected = GO_TIER_MODELS[candidate]
    if (model.providerID === expected.providerID && model.id === expected.id &&
        model.variant === expected.variant && !readOnly)
      return candidate
  }
  throw new Error("Unapproved Pi tier, model/effort or tool scope")
}
