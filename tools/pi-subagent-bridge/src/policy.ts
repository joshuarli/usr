/** Operational model policy. Pure data: safe to import in runtime, tests and generators. */
import {
  DELEGATION, GO_TIER_MODELS, MAX_SUBAGENT_DEPTH,
  DEVIN_TIER_MODELS, DEVIN_AGENT_NAMES, DEVIN_DELEGATION,
  PI_MODEL_ALLOWLIST, TIER_TOOLS, BRIDGE_TIERS, type Effort, type Tier, type BridgeTier,
} from "./tier-policy.ts"

export type { Effort } from "./tier-policy.ts"
export type Executor = "codex" | "command-code" | "pi" | "fx"
export type CliExecutor = Exclude<Executor, "pi">
export type CliPin = { readonly model: string; readonly effort: Effort }
export type PiSelection = { readonly providerID: string; readonly id: string; readonly variant: Effort }
export type PiDestinations = readonly [PiSelection, ...PiSelection[]]
export type Route =
  | (CliPin & { readonly executor: Exclude<CliExecutor, "fx"> })
  | (CliPin & { readonly executor: "pi"; readonly providerID: string })

/** Command Code first, then the Pi ladder, then Codex as the final route. */
export type RootPlan = {
  readonly kind: "codex-last"
  readonly command: CliPin
  readonly pi: PiDestinations
  readonly codex: CliPin
}

/**
 * A pi-only plan admits exactly its ordered Pi destinations and nothing else:
 * no Command Code, Codex or FX route exists, so an unavailable provider blocks
 * admission and an execution-time provider failure never falls back.
 */
export type PiOnlyPlan = {
  readonly kind: "pi-only"
  readonly pi: PiDestinations
}
export type AdmissionPlan = RootPlan | PiOnlyPlan
/** Tiers whose root plan is the codex-last CLI/Pi ladder. Expert is pi-only and has no ladder. */
export type LadderTier = Exclude<BridgeTier, "expert">

/** Antigravity CLI native target allocation. The custom-agent schema only admits flash/pro tier hints. */
export const ANTIGRAVITY_DIRECT = {
  models: ["gemini-4-neon-high", "gemini-4-neon-xhigh", "gemini-4-neon-low", "gemini-4-hydrogen-low"],
  main: { model: "gemini-4-neon-high", effort: "high" },
  god: { model: "gemini-4-neon-xhigh", effort: "xhigh" },
  tiers: {
    scout: { name: "usr-scout", model: "gemini-4-hydrogen-low", effort: "low", selector: "flash" },
    mechanic: { name: "usr-mechanic", model: "gemini-4-hydrogen-low", effort: "low", selector: "flash" },
    worker: { name: "usr-worker", model: "gemini-4-neon-low", effort: "low", selector: "pro" },
    expert: { name: "usr-expert", model: "gemini-4-neon-high", effort: "high", selector: "pro" },
  },
  manualCarbon: "gemini-4-carbon-high",
  retired: ["gemini-3.8-flash", "gemini-4-argon"],
} as const

const codexModels = { small: "gpt-6-luna", coding: "gpt-6.1-terra" } as const
export const CODEX_TIER_MODELS = {
  scout: { model: codexModels.small, effort: "medium" },
  mechanic: { model: codexModels.small, effort: "high" },
  worker: { model: codexModels.coding, effort: "high" },
} as const satisfies Record<LadderTier, CliPin>

/** Native Command Code parent agents; HY4 medium is an explicit comparison lane. */
export const COMMAND_NATIVE = {
  scout: { name: "usr-scout", model: "thinkingmachines/inkling-2-small:free" },
  mechanic: { name: "usr-mechanic", model: "tencent/hy4-flash", effort: "high" },
  worker: { name: "usr-worker", model: "deepseek/deepseek-v4.1-flash", effort: "high" },
  expert: { name: "usr-expert", model: "tencent/hy4", effort: "high" },
  pilot: { name: "usr-worker-hy4", model: "tencent/hy4", effort: "medium" },
} as const


function devinNativeModel(tier: keyof typeof DEVIN_TIER_MODELS): string {
  const pin = DEVIN_TIER_MODELS[tier]
  return `${pin.id.replace(".", "-")}-${pin.variant}`
}
export const DEVIN_NATIVE = {
  scout: { name: "usr-scout", model: devinNativeModel("scout"), effort: DEVIN_TIER_MODELS.scout.variant },
  mechanic: { name: "usr-mechanic", model: devinNativeModel("mechanic"), effort: DEVIN_TIER_MODELS.mechanic.variant },
  worker: { name: "usr-worker", model: devinNativeModel("worker"), effort: DEVIN_TIER_MODELS.worker.variant },
  expert: { name: "usr-expert", model: devinNativeModel("expert"), effort: DEVIN_TIER_MODELS.expert.variant },
} as const satisfies Record<Tier, CliPin & { name: string }>

export const COPILOT_NATIVE = {
  scout: { name: "usr-scout", model: "mai-code-2-flash", effort: "low" },
  mechanic: { name: "usr-mechanic", model: "mai-code-2-flash", effort: "low" },
  worker: { name: "usr-worker", model: "mai-code-2", effort: "medium" },
  expert: { name: "usr-expert", model: "mai-code-2", effort: "high" },
} as const satisfies Record<Tier, CliPin & { name: string }>

export const COMMAND_MODEL = "deepseek/deepseek-v4.1-flash"
export const COMMAND_EMBER_MODEL = "meta/muse-ember"
export const COMMAND_TIER_MODELS = {
  scout: { model: COMMAND_EMBER_MODEL, effort: "medium" },
  mechanic: { model: COMMAND_EMBER_MODEL, effort: "xhigh" },
  worker: { model: COMMAND_MODEL, effort: "high" },
} as const satisfies Record<LadderTier, CliPin>

/**
 * Ordered admission plan per admitted bridge tier. The lower tiers climb the
 * codex-last ladder without Devin; expert is pi-only on the pinned Devin SWE-2.1
 * max lane, which DEVIN_BRIDGE_DISABLED keeps blocked.
 */
export const ROOT_PLANS = {
  scout: {
    kind: "codex-last", command: COMMAND_TIER_MODELS.scout,
    pi: [GO_TIER_MODELS.scout], codex: CODEX_TIER_MODELS.scout,
  },
  mechanic: {
    kind: "codex-last", command: COMMAND_TIER_MODELS.mechanic,
    pi: [GO_TIER_MODELS.mechanic], codex: CODEX_TIER_MODELS.mechanic,
  },
  worker: {
    kind: "codex-last", command: COMMAND_TIER_MODELS.worker,
    pi: [GO_TIER_MODELS.worker], codex: CODEX_TIER_MODELS.worker,
  },
  expert: { kind: "pi-only", pi: [DEVIN_TIER_MODELS.expert] },
} as const satisfies Record<BridgeTier, AdmissionPlan>

function piRoute(pin: PiSelection) {
  return { executor: "pi", providerID: pin.providerID, model: pin.id, effort: pin.variant } as const
}
export function routesOf(plan: AdmissionPlan): readonly [Route, ...Route[]] {
  if (plan.kind === "pi-only") return [piRoute(plan.pi[0]), ...plan.pi.slice(1).map(piRoute)]
  return [
    { executor: "command-code", ...plan.command },
    ...plan.pi.map(piRoute),
    { executor: "codex", ...plan.codex },
  ]
}

export const OPENCODE_NATIVE = {
  model: "opencode/hy4-flash-free",
  efforts: { scout: "high", mechanic: "high", worker: "high", expert: "high" },
} as const satisfies { model: string; efforts: Record<Tier, Effort> }
export const NATIVE_FALLBACK = {
  tiers: ["scout", "mechanic", "worker"],
  claudeModels: { scout: "haiku", mechanic: "sonnet", worker: "sonnet" },
} as const
/** Family prefixes are prohibited, including all effort-suffixed variants. */
export const BANNED_MODELS = [
  "gemini-3.8", "gemini-4-argon", "gemini-4-carbon", "gpt-6-astra", "gpt-6.1-astra", "gpt-6.2-astra", "claude-fable", "fable",
] as const
export function isBannedModel(model: string, families: readonly string[] = BANNED_MODELS): boolean {
  const id = model.slice(model.lastIndexOf("/") + 1)
  return families.some(family => id === family || id.startsWith(family + "-"))
}

/** Build-time JSON projection for Python/harness consumers; never read generated data here. */
export const POLICY = {
  schema_version: 1,
  tiers: BRIDGE_TIERS,
  rootRoutes: {
    scout: routesOf(ROOT_PLANS.scout),
    mechanic: routesOf(ROOT_PLANS.mechanic),
    worker: routesOf(ROOT_PLANS.worker),
    expert: routesOf(ROOT_PLANS.expert),
  },
  nativePi: {
    goModels: GO_TIER_MODELS,
    devinModels: DEVIN_TIER_MODELS,
    devinAgentNames: DEVIN_AGENT_NAMES,
    delegation: DELEGATION,
    devinDelegation: DEVIN_DELEGATION,
    tools: TIER_TOOLS,
    maxSubagentDepth: MAX_SUBAGENT_DEPTH,
    modelAllowlist: PI_MODEL_ALLOWLIST,
  },
  opencode: OPENCODE_NATIVE,
  commandNative: COMMAND_NATIVE,
  devinNative: DEVIN_NATIVE,
  copilotNative: COPILOT_NATIVE,
  nativeFallback: NATIVE_FALLBACK,
  antigravityDirect: ANTIGRAVITY_DIRECT,
  bannedModels: BANNED_MODELS,
} as const
