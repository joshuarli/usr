/** A read-only Devin CLI credential/catalog gate for deterministic scoped workers. */
import { existsSync, readFileSync, statSync } from "node:fs"
import { createRequire } from "node:module"
import { homedir } from "node:os"
import { dirname, isAbsolute, join } from "node:path"
import { DEVIN_AGENT_NAMES, DEVIN_TIER_MODELS } from "./tier-policy.ts"

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

/** Resolve the Pi agent dir the way the Pi runtime does: PI_CODING_AGENT_DIR (tilde-expanded), else ~/.pi/agent. */
export function piAgentDir(env: NodeJS.ProcessEnv = process.env, home = homedir()): string {
  const envDir = env.PI_CODING_AGENT_DIR
  if (envDir) {
    if (envDir === "~") return home
    if (envDir.startsWith("~/")) return join(home, envDir.slice(2))
    return envDir
  }
  return join(home, ".pi", "agent")
}

/**
 * The Pi runtime loads every agent override named in settings, so an override
 * synced into settings.json before its profile is linked into agents/ fails
 * every Devin worker at start. Never throws: unreadable or malformed settings
 * carry no overrides, and assertTierProfiles validates the synced layout.
 */
function missingDevinProfiles(env: NodeJS.ProcessEnv, home: string): string[] {
  const agentDir = piAgentDir(env, home)
  let settings: unknown
  try { settings = JSON.parse(readFileSync(join(agentDir, "settings.json"), "utf8")) }
  catch { return [] }
  if (!settings || typeof settings !== "object" || Array.isArray(settings)) return []
  const subagents = (settings as { subagents?: unknown }).subagents
  if (!subagents || typeof subagents !== "object" || Array.isArray(subagents)) return []
  const overrides = (subagents as { agentOverrides?: unknown }).agentOverrides
  if (!overrides || typeof overrides !== "object" || Array.isArray(overrides)) return []
  const devinNames: readonly string[] = Object.values(DEVIN_AGENT_NAMES)
  const missing: string[] = []
  for (const name of Object.keys(overrides as Record<string, unknown>)) {
    if (!devinNames.includes(name)) continue
    try {
      if (!statSync(join(agentDir, "agents", name + ".md")).isFile()) missing.push(name)
    } catch {
      missing.push(name)
    }
  }
  return missing
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
    const missing = missingDevinProfiles(env, home)
    if (missing.length)
      return { available: false, issue: missing.map(name => `Pi profile ${name}.md is not installed; run sh sync`).join("; ") }
    return { available: true, issue: null }
  } catch {
    return { available: false, issue: "SWE-2.1 model catalog absent; run /devin-refresh in an authenticated Pi session" }
  }
}
