import { makeWorkerBridge, type ModelRef, type OpenCodePort } from "./bridge.ts"

export type PiAdapter = (selection: ModelRef) => ReturnType<typeof makeWorkerBridge>

export function piAdapter(wire: OpenCodePort): PiAdapter {
  return selection => makeWorkerBridge(wire, selection)
}
