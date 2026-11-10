import { accessSync, constants } from "node:fs"
import { createRequire } from "node:module"
import { isAbsolute, join } from "node:path"

const require = createRequire(import.meta.url)
export const MUSE_PROVIDER = "muse-sdk" as const
const EXTENSION = "pi-muse-subscription/src/index.ts" as const

/** Resolve only the bridge's exact npm-pinned provider. */
export function museExtensionPath(): string { return require.resolve(EXTENSION) }

/** Checks local dependencies only; the first real SDK turn proves subscription entitlement. */
export function musePreflight(env: NodeJS.ProcessEnv = process.env): { available: boolean; issue: string | null } {
  try { museExtensionPath() }
  catch { return { available: false, issue: "Pinned pi-muse-subscription dependency missing; run sh sync" } }
  const bin = env.PI_MUSE_SDK_MUSE_PATH || "muse"
  const paths = isAbsolute(bin) ? [bin] :
    (env.PATH ?? "").split(":").filter(Boolean).map(dir => join(dir, bin))
  for (const path of paths) {
    try { accessSync(path, constants.X_OK); return { available: true, issue: null } }
    catch { /* try next */ }
  }
  return { available: false, issue: "Muse Code executable missing; install muse and sign in via muse /login" }
}
