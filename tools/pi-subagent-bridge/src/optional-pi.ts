import { existsSync } from "node:fs"
import type { ModelRef, OpenCodePort } from "./bridge.ts"

export function piInstalled(): boolean {
  return existsSync(new URL("../node_modules/@earendil-works/pi-coding-agent/package.json", import.meta.url))
}

/** Pi state and credentials are opened only by an operation requiring Pi. */
export function optionalPiPort(): OpenCodePort {
  let loaded: Promise<OpenCodePort> | undefined
  const load = (requirement: "sdk" | "files" = "files") => {
    if (requirement === "sdk" && !piInstalled()) throw new Error("Optional Pi adapter is not installed; install the pinned Pi runtime")
    const modulePath: string = "./pi-port.ts"
    return loaded ??= import(modulePath).then((module: { piPort(): OpenCodePort }) => module.piPort())
  }
  return {
    create: async input => (await load("sdk")).create(input),
    prompt: async input => (await load("sdk")).prompt(input),
    steer: async input => (await load()).steer(input),
    get: async input => (await load()).get(input),
    active: async input => (await load()).active(input),
    inbox: async input => (await load()).inbox(input),
    messages: async input => (await load()).messages(input),
    interrupt: async input => (await load()).interrupt(input),
    models: async input => (await load("sdk")).models(input),
  }
}

export async function diagnoseGoModel(model: ModelRef): Promise<string | null> {
  if (!piInstalled()) return "Optional Pi adapter is not installed; install the pinned Pi runtime"
  const modulePath: string = "./pi-port.ts"
  const adapter: { diagnoseGoModel(model: ModelRef): Promise<string | null> } = await import(modulePath)
  return adapter.diagnoseGoModel(model)
}
