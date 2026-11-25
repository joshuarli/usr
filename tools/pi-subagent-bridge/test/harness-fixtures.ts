/** Explicit all-enabled configuration for lifecycle fixtures; production always reads harnesses.json. */
import { HARNESS_IDS, parseHarnessSwitches } from "../src/harnesses.ts"
import { makeHybridBridge as makeRuntimeBridge } from "../src/hybrid.ts"
import { startCommand as startRuntimeCommand } from "../src/command.ts"
import type { LaunchRequest } from "../src/launch.ts"
export type { Scope } from "../src/hybrid.ts"
export { hybridOwnerOps } from "../src/hybrid.ts"

export const ALL_HARNESSES = parseHarnessSwitches(Object.fromEntries(HARNESS_IDS.map(id => [id, true])))
export const NO_HARNESSES = parseHarnessSwitches(Object.fromEntries(HARNESS_IDS.map(id => [id, false])))
export function makeHybridBridge(...args: Parameters<typeof makeRuntimeBridge>) {
  return makeRuntimeBridge(args[0], args[1], args[2], args[3], args[4], args[5] ?? ALL_HARNESSES)
}
export function startCommand(request: LaunchRequest) {
  return startRuntimeCommand(request, ALL_HARNESSES)
}
