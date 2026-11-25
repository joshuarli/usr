import { assertHarnessEnabled, harnessEnabled, piProviderEnabled, type HarnessSwitches } from "./harnesses.ts"
import { piAdapter } from "./pi-adapter.ts"
import { existsSync } from "node:fs"
import type { ModelRef, OpenCodePort } from "./bridge.ts"

export function piInstalled(switches?: HarnessSwitches): boolean {
  if (!harnessEnabled("pi", switches)) return false
  return existsSync(new URL("../node_modules/@earendil-works/pi-coding-agent/package.json", import.meta.url))
}

/** Pi state and credentials are opened only by an operation requiring Pi. */
export function optionalPiPort(switches?: HarnessSwitches): OpenCodePort {
  let loaded: Promise<OpenCodePort> | undefined
  const load = (requirement: "sdk" | "files" = "files") => {
    if (requirement === "sdk") assertHarnessEnabled("pi", switches)
    if (requirement === "sdk" && !piInstalled(switches)) throw new Error("Optional Pi adapter is not installed; install the pinned Pi runtime")
    const modulePath: string = "./pi-port.ts"
    return loaded ??= import(modulePath).then((module: { piPort(hooks?: { switches?: HarnessSwitches }): OpenCodePort }) => module.piPort({ switches }))
  }
  return {
    create: async input => {
      if (!piProviderEnabled(input.model.providerID, switches)) throw new Error(`Pi provider ${input.model.providerID} is disabled in harnesses.json`)
      return (await load("sdk")).create(input)
    },
    prompt: async input => (await load("sdk")).prompt(input),
    steer: async input => (await load()).steer(input),
    get: async input => (await load()).get(input),
    active: async input => (await load()).active(input),
    inbox: async input => (await load()).inbox(input),
    messages: async input => (await load()).messages(input),
    interrupt: async input => (await load()).interrupt(input),
    models: async input => !piProviderEnabled("opencode-go", switches) && !piProviderEnabled("devin", switches)
      ? { data: [] } : (await load("sdk")).models(input),
  }
}

export async function diagnoseGoModel(model: ModelRef, switches?: HarnessSwitches): Promise<string | null> {
  if (!piProviderEnabled(model.providerID, switches)) return `Pi provider ${model.providerID} is disabled in harnesses.json`
  if (!piInstalled(switches)) return "Optional Pi adapter is not installed; install the pinned Pi runtime"
  const modulePath: string = "./pi-port.ts"
  const adapter: { diagnoseGoModel(model: ModelRef, switches?: HarnessSwitches): Promise<string | null> } = await import(modulePath)
  return adapter.diagnoseGoModel(model, switches)
}

export function optionalPiAdapter(switches?: HarnessSwitches) {
  return piAdapter(optionalPiPort(switches), switches)
}
