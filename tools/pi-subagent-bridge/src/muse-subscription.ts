import { accessSync, constants, readFileSync } from "node:fs"
import { createRequire } from "node:module"
import { dirname, isAbsolute, join } from "node:path"

const require = createRequire(import.meta.url)
export const MUSE_PROVIDER = "muse-sdk" as const

/** Resolve only the bridge's exact npm-pinned provider. */
export function museExtensionPath(): string {
  const manifest = require.resolve("pi-muse-subscription/package.json")
  const pkg = JSON.parse(readFileSync(manifest, "utf8"))
  const entry: unknown = pkg.pi?.extensions?.[0]
  if (entry !== "./src/index.ts" && entry !== "./src/index.js") throw new Error("Unsupported Muse extension entry point")
  return require.resolve(join(dirname(manifest), entry))
}

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
