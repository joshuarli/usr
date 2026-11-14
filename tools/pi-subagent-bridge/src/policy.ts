/** Operational model policy. Pure data: safe to import in runtime, tests and generators. */
import {
  DELEGATION, GO_TIER_MODELS, MAX_SUBAGENT_DEPTH, MUSE_AGENT_NAMES, MUSE_DELEGATION,
  MUSE_TIER_MODELS, PI_MODEL_ALLOWLIST, TIER_TOOLS, TIERS, type Effort, type Tier,
} from "./tier-policy.ts"

export type { Effort } from "./tier-policy.ts"
export type Executor = "antigravity" | "codex" | "command-code" | "pi"
export type CliPin = { readonly model: string; readonly effort: Effort }
export type Route =
  | (CliPin & { readonly executor: Exclude<Executor, "pi"> })
  | (CliPin & { readonly executor: "pi"; readonly providerID: string })

const antigravityFamily = "gemini-4-hydrogen"
function antigravityPin<E extends "low" | "medium" | "high" | "xhigh">(effort: E) {
  return { model: `${antigravityFamily}-${effort}`, effort } as const
}
export const ANTIGRAVITY_PIN = antigravityPin("xhigh")
export const ANTIGRAVITY_DIRECT = {
  models: [antigravityPin("high").model, antigravityPin("medium").model],
  requiresAvailabilityCheck: true,
} as const

const codexModels = { small: "gpt-6-luna", coding: "gpt-6.1-terra" } as const
export const CODEX_TIER_MODELS = {
  scout: { model: codexModels.small, effort: "medium" },
  mechanic: { model: codexModels.small, effort: "high" },
  worker: { model: codexModels.coding, effort: "medium" },
  expert: { model: codexModels.coding, effort: "xhigh" },
} as const satisfies Record<Tier, CliPin>

export const COMMAND_MODEL = "deepseek/deepseek-v4.1-flash"
export const COMMAND_EMBER_MODEL = "meta/muse-ember"
export const COMMAND_TIER_MODELS = {
  scout: { model: COMMAND_EMBER_MODEL, effort: "medium" },
  mechanic: { model: COMMAND_EMBER_MODEL, effort: "xhigh" },
  worker: { model: COMMAND_MODEL, effort: "high" },
  expert: { model: COMMAND_MODEL, effort: "max" },
} as const satisfies Record<Tier, CliPin>

function piRoute(pin: { readonly providerID: string; readonly id: string; readonly variant: Effort }) {
  return { executor: "pi", providerID: pin.providerID, model: pin.id, effort: pin.variant } as const
}
function lowerRoutes<T extends "scout" | "mechanic" | "worker">(tier: T) {
  return [
    { executor: "codex", ...CODEX_TIER_MODELS[tier] },
    { executor: "command-code", ...COMMAND_TIER_MODELS[tier] },
    ...(tier === "worker" ? [piRoute(MUSE_TIER_MODELS.worker)] : []),
    piRoute(GO_TIER_MODELS[tier]),
  ] as const
}
/** Ordered admission routes. Native Pi/legacy expert profiles are deliberately separate. */
export const ROOT_ROUTES = {
  scout: lowerRoutes("scout"),
  mechanic: lowerRoutes("mechanic"),
  worker: lowerRoutes("worker"),
  expert: [{ executor: "antigravity", ...ANTIGRAVITY_PIN }],
} as const satisfies Record<Tier, readonly [Route, ...Route[]]>

export const OPENCODE_NATIVE = {
  model: "opencode/inkling-2-small-free",
  efforts: { scout: "low", mechanic: "medium", worker: "high", expert: "max" },
  freeOnlyWhenParentFree: true,
  usesBridge: false,
} as const satisfies {
  model: string; efforts: Record<Tier, Effort>; freeOnlyWhenParentFree: boolean; usesBridge: false
}
export const NATIVE_FALLBACK = {
  tiers: ["scout", "mechanic", "worker"],
  reasons: ["bridge-unavailable", "host-access"],
  claudeModels: { scout: "haiku", mechanic: "sonnet", worker: "sonnet" },
} as const
/** Family prefixes are prohibited, including all effort-suffixed variants. */
export const BANNED_MODELS = ["gemini-4-argon", "gemini-4-carbon"] as const
export function isBannedModel(model: string, families: readonly string[] = BANNED_MODELS): boolean {
  const id = model.slice(model.lastIndexOf("/") + 1)
  return families.some(family => id === family || id.startsWith(family + "-"))
}

export type RootPlan =
  | { readonly kind: "exclusive"; readonly pin: CliPin }
  | {
    readonly kind: "fallback"
    readonly codex: CliPin
    readonly command: CliPin
    readonly pi: readonly { readonly providerID: string; readonly id: string; readonly variant: Effort }[]
  }

/** Resolve only supported executor arrangements, before performing admission effects. */
export function rootPlan(tier: Tier): RootPlan {
  const routes: readonly Route[] = ROOT_ROUTES[tier]
  for (const route of routes) {
    if (isBannedModel(route.model)) throw new Error(`Prohibited model in root route for ${tier}: ${route.model}`)
  }
  const first = routes[0]
  if (first?.executor === "antigravity" && routes.length === 1) {
    return { kind: "exclusive", pin: { model: first.model, effort: first.effort } }
  }
  const second = routes[1]
  if (first?.executor !== "codex" || second?.executor !== "command-code" || routes.length < 3) {
    throw new Error(`Unsupported executor order for ${tier}`)
  }
  const pi: Array<{ providerID: string; id: string; variant: Effort }> = []
  for (const route of routes.slice(2)) {
    if (route.executor !== "pi") throw new Error(`Unsupported fallback executor for ${tier}: ${route.executor}`)
    pi.push({ providerID: route.providerID, id: route.model, variant: route.effort })
  }
  return {
    kind: "fallback",
    codex: { model: first.model, effort: first.effort },
    command: { model: second.model, effort: second.effort },
    pi,
  }
}

/** Build-time JSON projection for Python/harness consumers; never read generated data here. */
export const POLICY = {
  schema_version: 1,
  tiers: TIERS,
  rootRoutes: ROOT_ROUTES,
  nativePi: {
    goModels: GO_TIER_MODELS,
    museModels: MUSE_TIER_MODELS,
    agentNames: MUSE_AGENT_NAMES,
    delegation: DELEGATION,
    museDelegation: MUSE_DELEGATION,
    tools: TIER_TOOLS,
    maxSubagentDepth: MAX_SUBAGENT_DEPTH,
    modelAllowlist: PI_MODEL_ALLOWLIST,
  },
  opencode: OPENCODE_NATIVE,
  nativeFallback: NATIVE_FALLBACK,
  antigravityDirect: ANTIGRAVITY_DIRECT,
  bannedModels: BANNED_MODELS,
} as const
