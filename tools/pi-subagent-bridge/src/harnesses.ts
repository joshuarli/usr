/** One checkout-wide switch per harness or provider. No credentials or provider probes. */
import { readFileSync } from "node:fs"

export const HARNESS_IDS = [
  "claude", "codex", "command-code", "pi", "opencode", "opencode-go",
  "devin", "antigravity", "copilot", "fx", "muse", "deepseek",
] as const
export type HarnessId = (typeof HARNESS_IDS)[number]
export type HarnessSwitches = Readonly<Record<HarnessId, boolean>>

export const HARNESS_LABELS: Readonly<Record<HarnessId, string>> = {
  claude: "Claude Code", codex: "Codex", "command-code": "Command Code", pi: "Pi",
  opencode: "OpenCode", "opencode-go": "OpenCode Go", devin: "Devin",
  antigravity: "Antigravity", copilot: "Copilot CLI", fx: "FX", muse: "Muse", deepseek: "DeepSeek Harness",
}
export const HARNESS_CONFIG = new URL("../../../harnesses.json", import.meta.url)

export function parseHarnessSwitches(value: unknown): HarnessSwitches {
  if (typeof value !== "object" || value === null || Array.isArray(value))
    throw new Error("harnesses.json must contain an object of boolean switches")
  const entries = Object.entries(value)
  for (const [id, enabled] of entries) {
    if (!HARNESS_IDS.some(known => known === id)) throw new Error(`Unknown harness in harnesses.json: ${id}`)
    if (typeof enabled !== "boolean") throw new Error(`harnesses.json: ${id} must be a boolean`)
  }
  for (const id of HARNESS_IDS)
    if (!Object.hasOwn(value, id)) throw new Error(`Missing harness in harnesses.json: ${id}`)
  return Object.freeze(Object.fromEntries(entries)) as HarnessSwitches
}

export function readHarnessSwitches(): HarnessSwitches {
  return parseHarnessSwitches(JSON.parse(readFileSync(HARNESS_CONFIG, "utf8")))
}

/** Snapshot for deterministic projections. Operation guards read the current switches instead. */
export const HARNESS_SWITCHES: HarnessSwitches = readHarnessSwitches()

export function harnessEnabled(id: HarnessId, switches: HarnessSwitches = readHarnessSwitches()): boolean {
  return switches[id]
}

/** Pi is a harness; its subscription backends can be disabled independently. */
export function piProviderEnabled(providerID: string, switches: HarnessSwitches = readHarnessSwitches()): boolean {
  return switches.pi && (providerID === "opencode-go" || providerID === "devin") && switches[providerID]
}

export function assertHarnessEnabled(id: HarnessId, switches?: HarnessSwitches): void {
  if (!harnessEnabled(id, switches)) throw new Error(`${HARNESS_LABELS[id]} is disabled in harnesses.json`)
}
