import { readFileSync, renameSync, writeFileSync } from "node:fs"
import { join } from "node:path"
import { processIdentity, type CommandRun } from "./command.ts"
import type { FxOptions, FxSelection } from "./fx.ts"
import { isRecord } from "./scope.ts"
import type { BridgeTier } from "./tier-policy.ts"

/** Bounds on one root's controlled children: total admissions and simultaneous runs. */
export type FxChildLimits = { readonly maxChildren: number; readonly maxConcurrent: number }

/**
 * Written once when a root FX worker is first admitted, beside its private FX home, and never rewritten:
 * resumptions of the root keep the authority snapshot they started with.
 */
export type FxChildConfig = {
  schema: 1
  adapter: Omit<FxOptions, "delegation">
  /** Exact pins for each tier the root may delegate to; absent tiers cannot be spawned. */
  selections: Partial<Record<BridgeTier, FxSelection>>
  limits: FxChildLimits
  cwd: string
  logDirectory: string
}

export type FxChildEntry = {
  child_id: string
  intent_id: string
  tier: BridgeTier
  selection: FxSelection
  task: string
  /** Absent only while a spawn intent is recorded but the run identity is not yet known. */
  run?: CommandRun
  spawn: "recorded" | "started" | "uncertain"
  resumes: number
}
export type FxChildLedger = { schema: 1; children: FxChildEntry[] }

export const CHILD_TOOLS = ["spawn", "status", "wait", "cancel", "steer", "resume"] as const
export const CHILD_SERVER = "children"

export function childConfigPath(fxHome: string): string { return join(fxHome, "children.json") }
export function childLedgerPath(fxHome: string): string { return join(fxHome, "children-ledger.json") }

export function readChildLedger(fxHome: string): FxChildLedger {
  let raw: string
  try { raw = readFileSync(childLedgerPath(fxHome), "utf8") } catch (error) {
    if ((error as NodeJS.ErrnoException).code === "ENOENT") return { schema: 1, children: [] }
    throw error
  }
  const value: unknown = JSON.parse(raw)
  if (!isRecord(value) || value.schema !== 1 || !Array.isArray(value.children)) throw new Error("Invalid FX child ledger")
  return value as FxChildLedger
}
export function writeChildLedger(fxHome: string, ledger: FxChildLedger): void {
  const path = childLedgerPath(fxHome), temporary = path + ".tmp"
  writeFileSync(temporary, JSON.stringify(ledger), { mode: 0o600 })
  renameSync(temporary, path)
}

const TERMINAL = new Set(["succeeded", "failed", "turn_limit", "cancelled", "timed_out"])
export function childTerminal(state: string): boolean { return TERMINAL.has(state) }

/**
 * A root's worktree may be released only when every child it ever spawned has a verified terminal state.
 * An uncertain spawn, a running child or an unknown termination keeps the lease.
 */
export function childrenQuiescent(fxHome: string, status: (run: CommandRun, selection: FxSelection) => { state: string }): { quiescent: boolean; active: string[] } {
  let ledger: FxChildLedger
  try { ledger = readChildLedger(fxHome) } catch { return { quiescent: false, active: ["ledger-unreadable"] } }
  const active = ledger.children.filter(child => child.spawn !== "started" || !child.run || !childTerminal(status(child.run, child.selection).state)).map(child => child.child_id)
  return { quiescent: active.length === 0, active }
}

/** Signal a child supervisor only while its recorded PID still names the same process. */
export function cancelChildRun(run: CommandRun): boolean {
  if (processIdentity(run) !== "same") return false
  try { process.kill(-run.pid, "SIGTERM"); return true } catch { return false }
}
