/** Operational model policy. Pure data: safe to import in runtime, tests and generators. */
import {
  DELEGATION, GO_TIER_MODELS, MAX_SUBAGENT_DEPTH, MUSE_AGENT_NAMES, MUSE_DELEGATION,
  MUSE_TIER_MODELS, PI_MODEL_ALLOWLIST, TIER_TOOLS, TIERS, type Effort, type Tier,
} from "./tier-policy.ts"

export type { Effort } from "./tier-policy.ts"
export type Executor = "antigravity" | "codex" | "command-code" | "pi"
export type CliExecutor = Exclude<Executor, "pi">
export type CliPin = { readonly model: string; readonly effort: Effort }
export type PiSelection = { readonly providerID: string; readonly id: string; readonly variant: Effort }
export type PiDestinations = readonly [PiSelection, ...PiSelection[]]
export type Route =
  | (CliPin & { readonly executor: CliExecutor })
  | (CliPin & { readonly executor: "pi"; readonly providerID: string })

export type RootPlan =
  | { readonly kind: "exclusive"; readonly target: CliPin }
  | {
    readonly kind: "fallback"
    readonly codex: CliPin
    readonly command: CliPin
    readonly pi: PiDestinations
  }
export type ExclusivePlan = Extract<RootPlan, { kind: "exclusive" }>
export type FallbackPlan = Extract<RootPlan, { kind: "fallback" }>

const antigravityFamily = "gemini-4-hydrogen"
function antigravityPin<E extends "low" | "medium" | "high" | "xhigh">(effort: E) {
  return { model: `${antigravityFamily}-${effort}`, effort } as const
}
export const ANTIGRAVITY_PIN = antigravityPin("xhigh")
export const ANTIGRAVITY_DIRECT = {
  models: [antigravityPin("high").model, antigravityPin("medium").model],
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

/** Ordered admission plan per tier. Native Pi/legacy expert profiles are deliberately separate. */
export const ROOT_PLANS = {
  scout: {
    kind: "fallback", codex: CODEX_TIER_MODELS.scout, command: COMMAND_TIER_MODELS.scout, pi: [GO_TIER_MODELS.scout],
  },
  mechanic: {
    kind: "fallback", codex: CODEX_TIER_MODELS.mechanic, command: COMMAND_TIER_MODELS.mechanic, pi: [GO_TIER_MODELS.mechanic],
  },
  worker: {
    kind: "fallback", codex: CODEX_TIER_MODELS.worker, command: COMMAND_TIER_MODELS.worker,
    pi: [MUSE_TIER_MODELS.worker, GO_TIER_MODELS.worker],
  },
  expert: { kind: "exclusive", target: ANTIGRAVITY_PIN },
} as const satisfies Record<Tier, RootPlan>

function piRoute(pin: PiSelection) {
  return { executor: "pi", providerID: pin.providerID, model: pin.id, effort: pin.variant } as const
}
export function routesOf(plan: RootPlan): readonly [Route, ...Route[]] {
  if (plan.kind === "exclusive") return [{ executor: "antigravity", ...plan.target }]
  return [
    { executor: "codex", ...plan.codex },
    { executor: "command-code", ...plan.command },
    ...plan.pi.map(piRoute),
  ]
}

export const OPENCODE_NATIVE = {
  model: "opencode/inkling-2-small-free",
  efforts: { scout: "low", mechanic: "medium", worker: "high", expert: "max" },
} as const satisfies { model: string; efforts: Record<Tier, Effort> }
export const NATIVE_FALLBACK = {
  tiers: ["scout", "mechanic", "worker"],
  claudeModels: { scout: "haiku", mechanic: "sonnet", worker: "sonnet" },
} as const
/** Family prefixes are prohibited, including all effort-suffixed variants. */
export const BANNED_MODELS = ["gemini-4-argon", "gemini-4-carbon"] as const
export function isBannedModel(model: string, families: readonly string[] = BANNED_MODELS): boolean {
  const id = model.slice(model.lastIndexOf("/") + 1)
  return families.some(family => id === family || id.startsWith(family + "-"))
}

/** Build-time JSON projection for Python/harness consumers; never read generated data here. */
export const POLICY = {
  schema_version: 1,
  tiers: TIERS,
  rootRoutes: {
    scout: routesOf(ROOT_PLANS.scout),
    mechanic: routesOf(ROOT_PLANS.mechanic),
    worker: routesOf(ROOT_PLANS.worker),
    expert: routesOf(ROOT_PLANS.expert),
  },
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
