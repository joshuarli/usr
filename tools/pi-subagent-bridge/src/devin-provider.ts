/** A read-only Devin CLI credential/catalog gate for deterministic scoped workers. */
import { existsSync, readFileSync, statSync } from "node:fs"
import { createRequire } from "node:module"
import { homedir } from "node:os"
import { dirname, isAbsolute, join } from "node:path"
import { DEVIN_TIER_MODELS } from "./tier-policy.ts"

const require = createRequire(import.meta.url)
export const DEVIN_PROVIDER = "devin" as const
const PINNED_MODEL_UIDS = Object.values(DEVIN_TIER_MODELS).map(pin => `${pin.id.replace(".", "-")}-${pin.variant}`)

/** Resolve only the pi-build-pinned provider, never a workspace package. */
export function devinExtensionPath(): string {
  const manifest = require.resolve("pi-devin-local/package.json")
  const pkg: { name?: string; pi?: { extensions?: string[] } } = JSON.parse(readFileSync(manifest, "utf8"))
  const entry = pkg.pi?.extensions
  if (pkg.name !== "pi-devin-local" || !entry || entry.length !== 1 ||
      (entry[0] !== "./extensions/index.js" && entry[0] !== "./extensions/index.ts"))
    throw new Error("Unsupported pinned Devin extension entry point")
  const resolved = join(dirname(manifest), entry[0])
  if (!existsSync(resolved)) throw new Error("Pinned Devin provider entry point missing")
  return resolved
}

export function devinCatalogPath(env: NodeJS.ProcessEnv = process.env, home = homedir()): string {
  const xdg = env.XDG_CACHE_HOME
  return join(xdg && isAbsolute(xdg) ? xdg : join(home, ".cache"), "pi-devin", "models.json")
}

export function devinPreflight(
  env: NodeJS.ProcessEnv = process.env, home = homedir(),
  resolveExtension: () => string = devinExtensionPath,
): { available: boolean; issue: string | null } {
  try { resolveExtension() }
  catch { return { available: false, issue: "Pinned pi-devin-local missing; release and sync the updated pi-build runtime" } }
  const credentials = join(home, ".local/share/devin/credentials.toml")
  try {
    if (!statSync(credentials).isFile()) throw new Error("not a file")
  } catch {
    return { available: false, issue: "Devin CLI credentials missing; run devin auth login and /login devin in Pi" }
  }
  try {
    const cache: unknown = JSON.parse(readFileSync(devinCatalogPath(env, home), "utf8"))
    if (!cache || typeof cache !== "object" || Array.isArray(cache))
      throw new Error("invalid cache")
    const value = cache as { version?: unknown; catalog?: { families?: unknown } }
    if (value.version !== 1 || !Array.isArray(value.catalog?.families)) throw new Error("invalid catalog")
    const family = value.catalog.families.find((family: unknown) => {
      if (!family || typeof family !== "object" || Array.isArray(family)) return false
      const found = family as { slug?: string; variants?: Array<{ model_uid?: string }> }
      const variants = found.variants
      return found.slug === "swe-2.1" && Array.isArray(variants) &&
        PINNED_MODEL_UIDS.every(uid => variants.some(variant => variant.model_uid === uid))
    })
    if (!family) throw new Error("SWE-2.1 pinned variants absent")
    return { available: true, issue: null }
  } catch {
    return { available: false, issue: "SWE-2.1 model catalog absent; run /devin-refresh in an authenticated Pi session" }
  }
}
