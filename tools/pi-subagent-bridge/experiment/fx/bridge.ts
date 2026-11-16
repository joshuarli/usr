import { makeHybridBridge } from "../../src/hybrid.ts"
import { optionalPiAdapter } from "../../src/optional-pi.ts"
import type { FxAdapter, FxSelection } from "../../src/fx.ts"
import type { ExecutionPlan } from "../../src/session.ts"
import type { Tier } from "../../src/tier-policy.ts"

export const FIXTURE_SELECTION: FxSelection = { model: "fixture-model", effort: "high", provider: "fixture", runtimeVersion: "0.0.17" }

export function qualificationBridge(fx: FxAdapter) {
  const resolvePolicy = (tier: Tier): ExecutionPlan => {
    if (tier !== "scout" && tier !== "worker") throw new Error("FX qualification supports only its fixture scout and worker")
    return { kind: "leaf", target: { executor: "fx", selection: FIXTURE_SELECTION } }
  }
  return makeHybridBridge(optionalPiAdapter(), undefined, undefined, resolvePolicy, fx)
}
