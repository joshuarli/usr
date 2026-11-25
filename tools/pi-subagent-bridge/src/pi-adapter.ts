import type { HarnessSwitches } from "./harnesses.ts"
import { makeWorkerBridge, type ModelRef, type OpenCodePort } from "./bridge.ts"

export type PiAdapter = (selection: ModelRef) => ReturnType<typeof makeWorkerBridge>

export function piAdapter(wire: OpenCodePort, switches?: HarnessSwitches): PiAdapter {
  return selection => makeWorkerBridge(wire, selection, switches)
}
