import type { CommandRun, Effort } from "./command.ts"
import {
  isBannedModel, type CliExecutor, type CliPin, type Executor, type FallbackPlan, type PiDestinations, type PiSelection,
  type RootPlan,
} from "./policy.ts"
import { isRecord, parseScope, requiredText, type Scope } from "./scope.ts"
import { isTier, type Tier } from "./tier-policy.ts"

export const TURN_LIMIT_CONTINUATIONS = 2
export const STEER_LIMIT = 2
export const SESSION_VERSION = 2

const SESSION_ID = /^usrw_[a-f0-9-]{36}$/
export function isSessionId(value: string): boolean {
  return SESSION_ID.test(value)
}

export type ProcessTarget = { readonly executor: CliExecutor; readonly selection: CliPin }
/** `admitting` is the historical Pi admission state; only legacy records carry it. */
export type PiTarget = { readonly executor: "pi"; readonly selection: PiSelection; readonly admitting?: true }
export type Target = ProcessTarget | PiTarget

export type Execution =
  | { kind: "process"; executor: CliExecutor; selection: CliPin; run: CommandRun }
  | { kind: "pi"; selection: PiSelection; session_id: string }
  | { kind: "transition"; to: Target; previous_run?: CommandRun; pi_id?: string }
export type ProcessExecution = Extract<Execution, { kind: "process" }>

export type FallbackUnresolvedPiPlan = { readonly kind: "fallback-unresolved-pi"; readonly codex: CliPin; readonly command: CliPin }
export type CommandFirstPlan = { readonly kind: "command-first"; readonly command: CliPin; readonly pi: PiDestinations }
export type CommandFirstUnresolvedPiPlan = { readonly kind: "command-first-unresolved-pi"; readonly command: CliPin }
export type PiFirstPlan = { readonly kind: "pi-first"; readonly command: CliPin }
/** Root plans plus the legacy arrangements records still carry; only resolved Pi plans can fall back to Pi. */
export type AdmittedPlan =
  | RootPlan | FallbackUnresolvedPiPlan | CommandFirstPlan | CommandFirstUnresolvedPiPlan | PiFirstPlan
export type PiFallbackPlan = FallbackPlan | CommandFirstPlan
export type LadderPlan = FallbackPlan | FallbackUnresolvedPiPlan | CommandFirstPlan | CommandFirstUnresolvedPiPlan

const UNRESOLVED_PI = "Legacy Pi fallback has no exact model snapshot; manual reconciliation required"
export function piFallbackPlan(plan: LadderPlan): PiFallbackPlan {
  if (plan.kind === "fallback" || plan.kind === "command-first") return plan
  throw new Error(UNRESOLVED_PI)
}

export type Session = {
  id: string; cwd: string; title: string; tier: Tier; scope: Scope; task: string
  plan: AdmittedPlan; execution: Execution; attempts: number
  fallback_reason?: string; fallback_detail?: string; fallback_blocked?: string
  continuations?: number; steers?: number; cancel_requested?: boolean
}

export function executorOf(s: Session): Executor {
  const execution = s.execution
  return execution.kind === "pi" ? "pi" : execution.kind === "process" ? execution.executor : execution.to.executor
}
export function backendOf(s: Session): string {
  const execution = s.execution
  if (execution.kind === "pi") return "pi"
  if (execution.kind === "process") return execution.executor
  const to = execution.to
  if (to.executor === "pi") return to.admitting ? "pi-admitting" : "pi-transition"
  return to.executor === "command-code" ? "command-transition" : to.executor + "-transition"
}
function destinationOf(execution: Execution): Target {
  if (execution.kind === "transition") return execution.to
  if (execution.kind === "pi") return { executor: "pi", selection: execution.selection }
  return { executor: execution.executor, selection: execution.selection }
}
export function targetOf(s: Session): Target {
  return destinationOf(s.execution)
}
export function processRun(s: Session): CommandRun | undefined {
  return s.execution.kind === "process" ? s.execution.run :
    s.execution.kind === "transition" ? s.execution.previous_run : undefined
}
export function piId(s: Session): string | undefined {
  return s.execution.kind === "pi" ? s.execution.session_id :
    s.execution.kind === "transition" ? s.execution.pi_id : undefined
}
export function transition(s: Session, to: Target, keepPrevious = false): void {
  const previous_run = keepPrevious ? processRun(s) : undefined
  const pi_id = to.executor === "pi" ? piId(s) : undefined
  s.execution = { kind: "transition", to, ...(previous_run ? { previous_run } : {}), ...(pi_id ? { pi_id } : {}) }
}
export function activateProcess(s: Session, target: ProcessTarget, run: CommandRun): void {
  s.execution = { kind: "process", executor: target.executor, selection: target.selection, run }
}
export function activatePi(s: Session, selection: PiSelection, session_id: string): void {
  s.execution = { kind: "pi", selection, session_id }
}
export function admittedModel(s: Session): string | PiSelection {
  const target = targetOf(s)
  return target.executor === "pi" ? target.selection : target.selection.model
}
export function admittedEffort(s: Session): Effort {
  const target = targetOf(s)
  return target.executor === "pi" ? target.selection.variant : target.selection.effort
}

/** Flat watcher fields stay as derived projections; decoding ignores them. */
export function encodeSession(s: Session) {
  return { schema_version: SESSION_VERSION, ...s, backend: backendOf(s), command_run: processRun(s), pi_id: piId(s) }
}

function optionalText(value: unknown, name: string): string | undefined {
  return value === undefined ? undefined : requiredText(value, name, 32000)
}
function counter(value: unknown, name: string): number {
  if (typeof value !== "number" || !Number.isSafeInteger(value) || value < 0)
    throw new Error("Invalid persisted " + name)
  return value
}
function effort(value: unknown): Effort {
  if (value !== "low" && value !== "medium" && value !== "high" && value !== "xhigh" && value !== "max")
    throw new Error("Invalid persisted effort")
  return value
}
function model(value: unknown): string {
  const id = requiredText(value, "persisted model", 512)
  if (isBannedModel(id)) throw new Error("Prohibited persisted model; manual reconciliation required: " + id)
  return id
}
function pin(value: unknown): CliPin {
  if (!isRecord(value)) throw new Error("Invalid persisted model pin")
  return { model: model(value.model), effort: effort(value.effort) }
}
function piSelection(value: unknown): PiSelection {
  if (!isRecord(value)) throw new Error("Invalid persisted Pi model")
  if (value.variant === undefined) throw new Error("Missing admitted Pi effort; manual reconciliation required")
  return { providerID: requiredText(value.providerID, "Pi provider", 512), id: model(value.id), variant: effort(value.variant) }
}
function commandRun(value: unknown): CommandRun {
  if (!isRecord(value) || typeof value.pid !== "number" || !Number.isSafeInteger(value.pid) || value.pid <= 0 ||
      (value.proc_start !== undefined && value.proc_start !== null && typeof value.proc_start !== "string"))
    throw new Error("Invalid persisted worker process")
  return { pid: value.pid, output: requiredText(value.output, "process output", 4096),
    errors: requiredText(value.errors, "process errors", 4096), started_at: requiredText(value.started_at, "process start"),
    ...(value.proc_start === undefined ? {} : { proc_start: value.proc_start }) }
}
function piSelections(value: unknown): PiSelection[] {
  if (!Array.isArray(value) || value.length > 8) throw new Error("Invalid persisted Pi plan")
  return value.map(piSelection)
}
function piList(selections: readonly PiSelection[]): [PiSelection, ...PiSelection[]] {
  const [first, ...rest] = selections
  if (!first) throw new Error("Invalid persisted Pi plan")
  return [first, ...rest]
}
function cliExecutor(value: unknown): CliExecutor {
  if (value !== "codex" && value !== "command-code" && value !== "antigravity")
    throw new Error("Invalid persisted worker lifecycle; manual reconciliation required")
  return value
}

function samePin(a: CliPin, b: CliPin): boolean {
  return a.model === b.model && a.effort === b.effort
}
function samePi(a: PiSelection, b: PiSelection): boolean {
  return a.providerID === b.providerID && a.id === b.id && a.variant === b.variant
}
function coherent(plan: AdmittedPlan, to: Target): boolean {
  switch (plan.kind) {
    case "exclusive": return to.executor === "antigravity" && samePin(to.selection, plan.target)
    case "fallback":
      return to.executor === "codex" ? samePin(to.selection, plan.codex) :
        to.executor === "command-code" ? samePin(to.selection, plan.command) :
        to.executor === "pi" && plan.pi.some(candidate => samePi(candidate, to.selection))
    case "fallback-unresolved-pi":
      return to.executor === "codex" ? samePin(to.selection, plan.codex) :
        to.executor === "command-code" && samePin(to.selection, plan.command)
    case "command-first":
      return to.executor === "command-code" ? samePin(to.selection, plan.command) :
        to.executor === "pi" && plan.pi.some(candidate => samePi(candidate, to.selection))
    case "command-first-unresolved-pi": return to.executor === "command-code" && samePin(to.selection, plan.command)
    case "pi-first": return to.executor === "pi" || (to.executor === "command-code" && samePin(to.selection, plan.command))
  }
}

function decodePlan(value: unknown): AdmittedPlan {
  if (!isRecord(value)) throw new Error("Invalid persisted worker plan")
  switch (value.kind) {
    case "exclusive": return { kind: "exclusive", target: pin(value.target) }
    case "fallback":
      return { kind: "fallback", codex: pin(value.codex), command: pin(value.command), pi: piList(piSelections(value.pi)) }
    case "fallback-unresolved-pi": return { kind: "fallback-unresolved-pi", codex: pin(value.codex), command: pin(value.command) }
    case "command-first": return { kind: "command-first", command: pin(value.command), pi: piList(piSelections(value.pi)) }
    case "command-first-unresolved-pi": return { kind: "command-first-unresolved-pi", command: pin(value.command) }
    case "pi-first": return { kind: "pi-first", command: pin(value.command) }
    default: throw new Error("Invalid persisted worker plan")
  }
}
function decodeTarget(value: unknown): Target {
  if (!isRecord(value)) throw new Error("Invalid persisted worker lifecycle; manual reconciliation required")
  if (value.executor === "pi")
    return { executor: "pi", selection: piSelection(value.selection), ...(value.admitting === true ? { admitting: true } : {}) }
  return { executor: cliExecutor(value.executor), selection: pin(value.selection) }
}
function decodeExecution(value: unknown): Execution {
  if (!isRecord(value)) throw new Error("Invalid persisted worker lifecycle; manual reconciliation required")
  switch (value.kind) {
    case "process":
      return { kind: "process", executor: cliExecutor(value.executor), selection: pin(value.selection), run: commandRun(value.run) }
    case "pi":
      return { kind: "pi", selection: piSelection(value.selection), session_id: requiredText(value.session_id, "Pi session", 32000) }
    case "transition": {
      const previous_run = value.previous_run === undefined ? undefined : commandRun(value.previous_run)
      const pi_id = optionalText(value.pi_id, "Pi session")
      return { kind: "transition", to: decodeTarget(value.to), ...(previous_run ? { previous_run } : {}), ...(pi_id ? { pi_id } : {}) }
    }
    default: throw new Error("Invalid persisted worker lifecycle; manual reconciliation required")
  }
}

// These are historical wire meanings, not defaults for new sessions. Never update
// them when the current policy changes: unversioned Hydrogen records omitted pins.
const LEGACY_HYDROGEN_PIN = { model: "gemini-4-hydrogen-xhigh", effort: "xhigh" } as const

const LEGACY_BACKENDS = new Map<string, { executor: Executor; transition: boolean; admitting: boolean }>([
  ["pi", { executor: "pi", transition: false, admitting: false }],
  ["pi-admitting", { executor: "pi", transition: true, admitting: true }],
  ["pi-transition", { executor: "pi", transition: true, admitting: false }],
  ["codex", { executor: "codex", transition: false, admitting: false }],
  ["codex-transition", { executor: "codex", transition: true, admitting: false }],
  ["command-code", { executor: "command-code", transition: false, admitting: false }],
  ["command-transition", { executor: "command-code", transition: true, admitting: false }],
  ["antigravity", { executor: "antigravity", transition: false, admitting: false }],
  ["antigravity-transition", { executor: "antigravity", transition: true, admitting: false }],
])

function legacyPin(value: Record<string, unknown>, modelKey: string, effortKey: string): CliPin | undefined {
  const selected = value[modelKey], effortValue = value[effortKey]
  if (selected === undefined && effortValue === undefined) return undefined
  if (selected === undefined || effortValue === undefined) throw new Error("Incomplete persisted model pin; manual reconciliation required")
  return { model: model(selected), effort: effort(effortValue) }
}
function admitted<T>(value: T | undefined, label: string): T {
  if (value === undefined) throw new Error("Missing admitted " + label + "; manual reconciliation required")
  return value
}

function legacyPlan(
  value: Record<string, unknown>, to: Target,
  lanes: { codex: CliPin | undefined; command: CliPin | undefined; primary: PiSelection | undefined; pending: PiSelection[] | undefined },
): AdmittedPlan {
  if (to.executor === "antigravity") return { kind: "exclusive", target: to.selection }
  const { codex, primary, pending } = lanes
  const command = admitted(lanes.command, "Command Code pin")
  const symbolic = Array.isArray(value.remaining_pi) && value.remaining_pi.length > 0
  const pi: PiSelection[] = to.executor === "pi" ? [to.selection, ...(pending ?? [])] :
    pending !== undefined ? pending : primary && !symbolic ? [primary] : []
  const [first, ...rest] = pi
  const destinations: PiDestinations | undefined = first ? [first, ...rest] : undefined
  if (value.execution_order === undefined && !codex) return { kind: "pi-first", command }
  if (codex) return destinations ? { kind: "fallback", codex, command, pi: destinations } : { kind: "fallback-unresolved-pi", codex, command }
  return destinations ? { kind: "command-first", command, pi: destinations } : { kind: "command-first-unresolved-pi", command }
}

function decodeLegacy(value: Record<string, unknown>, tier: Tier): { plan: AdmittedPlan; execution: Execution } {
  let backend = typeof value.backend === "string" ? value.backend : undefined
  let antigravity = value.antigravity_pin === undefined ? undefined : pin(value.antigravity_pin)
  if (value.schema_version === undefined && (backend === "hydrogen" || backend === "hydrogen-transition")) {
    if (antigravity && !samePin(antigravity, LEGACY_HYDROGEN_PIN))
      throw new Error("Ambiguous legacy Antigravity pin; manual reconciliation required")
    antigravity = { ...LEGACY_HYDROGEN_PIN }
    backend = backend === "hydrogen" ? "antigravity" : "antigravity-transition"
  }
  const lifecycle = backend === undefined ? undefined : LEGACY_BACKENDS.get(backend)
  if (!lifecycle) throw new Error("Invalid persisted worker lifecycle; manual reconciliation required")
  const previous_run = value.command_run === undefined ? undefined : commandRun(value.command_run)
  const pi_id = optionalText(value.pi_id, "Pi session")
  if (lifecycle.executor === "antigravity" && (!antigravity || tier !== "expert"))
    throw new Error("Invalid admitted Antigravity route; manual reconciliation required")
  if (value.schema_version === 1 && tier === "expert" && lifecycle.executor !== "antigravity")
    throw new Error("Invalid versioned expert route; manual reconciliation required")
  if (value.remaining_pi !== undefined &&
      !(Array.isArray(value.remaining_pi) && value.remaining_pi.every(item => item === "muse" || item === "go")))
    throw new Error("Invalid legacy Pi destinations")
  if (value.execution_order !== undefined && value.execution_order !== "command-first" && value.execution_order !== "codex-first")
    throw new Error("Invalid execution order")

  const codex = legacyPin(value, "codex_model", "codex_effort")
  const command = legacyPin(value, "command_model", "command_effort")
  const primary = value.primary_model === undefined ? undefined : piSelection(value.primary_model)
  const pending = value.pi_candidates === undefined ? undefined : piSelections(value.pi_candidates)
  let to: Target
  switch (lifecycle.executor) {
    case "antigravity": to = { executor: "antigravity", selection: admitted(antigravity, "Antigravity pin") }; break
    case "codex": to = { executor: "codex", selection: admitted(codex, "Codex pin") }; break
    case "command-code": to = { executor: "command-code", selection: admitted(command, "Command Code pin") }; break
    case "pi":
      to = { executor: "pi", selection: admitted(primary, "Pi pin"), ...(lifecycle.admitting ? { admitting: true as const } : {}) }
      break
  }
  const plan = legacyPlan(value, to, { codex, command, primary, pending })
  if (lifecycle.transition)
    return { plan, execution: { kind: "transition", to, ...(previous_run ? { previous_run } : {}), ...(pi_id ? { pi_id } : {}) } }
  if (to.executor === "pi") {
    if (!pi_id) throw new Error("Missing persisted Pi session")
    return { plan, execution: { kind: "pi", selection: to.selection, session_id: pi_id } }
  }
  if (!previous_run) throw new Error("Missing persisted worker process")
  return { plan, execution: { kind: "process", executor: to.executor, selection: to.selection, run: previous_run } }
}

function decodeCurrent(value: Record<string, unknown>): { plan: AdmittedPlan; execution: Execution } {
  return { plan: decodePlan(value.plan), execution: decodeExecution(value.execution) }
}

export function decodeSession(value: unknown, cwd: string, id: string): Session {
  if (!isRecord(value)) throw new Error("Invalid persisted worker session")
  const version = value.schema_version
  if (version !== undefined && version !== 1 && version !== SESSION_VERSION)
    throw new Error("Unsupported worker session version; manual reconciliation required")
  if (value.cwd !== cwd || value.id !== id || !isTier(value.tier)) throw new Error("Session/worktree mismatch")
  const { plan, execution } = version === SESSION_VERSION ? decodeCurrent(value) : decodeLegacy(value, value.tier)
  if ((plan.kind === "exclusive" && value.tier !== "expert") || !coherent(plan, destinationOf(execution)))
    throw new Error("Execution leaves the admitted plan; manual reconciliation required")
  const s: Session = {
    id, cwd, tier: value.tier, title: requiredText(value.title, "title", 100), task: requiredText(value.task, "task", 32000),
    scope: parseScope(value.scope, value.tier), plan, execution, attempts: counter(value.attempts, "attempts"),
  }
  for (const key of ["fallback_reason", "fallback_detail", "fallback_blocked"] as const) {
    if (value[key] !== undefined) {
      if (typeof value[key] !== "string" || value[key].length > 32000) throw new Error("Invalid persisted " + key)
      s[key] = value[key]
    }
  }
  for (const key of ["continuations", "steers"] as const) {
    if (value[key] !== undefined) s[key] = counter(value[key], key)
  }
  if (value.cancel_requested !== undefined) {
    if (typeof value.cancel_requested !== "boolean") throw new Error("Invalid persisted cancellation state")
    s.cancel_requested = value.cancel_requested
  }
  return s
}
