import type { ModelRef } from "./bridge.ts"
import type { CommandRun, Effort } from "./command.ts"
import { isBannedModel, type CliPin, type Executor } from "./policy.ts"
import { isRecord, parseScope, requiredText, type Scope } from "./scope.ts"
import { isTier, type Tier } from "./tier-policy.ts"

export const TURN_LIMIT_CONTINUATIONS = 2
export const STEER_LIMIT = 2

const SESSION_ID = /^usrw_[a-f0-9-]{36}$/
export function isSessionId(value: string): boolean {
  return SESSION_ID.test(value)
}

type CliExecutor = Exclude<Executor, "pi">
/** Active executions carry their handle; interrupted admissions cannot look active. */
export type Execution =
  | { kind: "pi"; session_id: string }
  | { kind: "process"; executor: CliExecutor; run: CommandRun }
  | { kind: "transition"; executor: Executor; admitting?: boolean; previous_run?: CommandRun; pi_id?: string }

export type Session = {
  wire_version?: 1
  id: string; cwd: string; title: string; tier: Tier; scope: Scope; task: string
  execution: Execution; attempts: number
  fallback_reason?: string; fallback_detail?: string; continuations?: number; steers?: number
  primary_model?: ModelRef; command_model?: string; command_effort?: Effort
  pi_candidates?: ModelRef[]; remaining_pi?: Array<"muse" | "go">
  execution_order?: "command-first" | "codex-first"; fallback_blocked?: string
  codex_model?: string; codex_effort?: Effort; antigravity_pin?: CliPin; cancel_requested?: boolean
}

export function backendOf(s: Session) {
  const execution = s.execution
  if (execution.kind === "pi") return "pi"
  if (execution.kind === "process") return execution.executor
  if (execution.executor === "pi") return execution.admitting ? "pi-admitting" : "pi-transition"
  if (execution.executor === "command-code") return "command-transition"
  return execution.executor === "codex" ? "codex-transition" : "antigravity-transition"
}
export function processRun(s: Session): CommandRun | undefined {
  return s.execution.kind === "process" ? s.execution.run :
    s.execution.kind === "transition" ? s.execution.previous_run : undefined
}
export function piId(s: Session): string | undefined {
  return s.execution.kind === "pi" ? s.execution.session_id :
    s.execution.kind === "transition" ? s.execution.pi_id : undefined
}
export function transition(s: Session, executor: Executor, keepPrevious = false): void {
  const previous_run = keepPrevious ? processRun(s) : undefined
  const pi_id = executor === "pi" ? piId(s) : undefined
  s.execution = { kind: "transition", executor, ...(previous_run ? { previous_run } : {}), ...(pi_id ? { pi_id } : {}) }
}
export function activateProcess(s: Session, executor: CliExecutor, run: CommandRun): void {
  s.execution = { kind: "process", executor, run }
}
export function activatePi(s: Session, session_id: string): void {
  s.execution = { kind: "pi", session_id }
}
export function antigravityPin(s: Session): CliPin {
  if (!s.antigravity_pin) throw new Error("Missing admitted Antigravity pin; manual reconciliation required")
  return s.antigravity_pin
}

export function primaryFor(s: Session): ModelRef {
  if (!s.primary_model) throw new Error("Missing admitted Pi pin; manual reconciliation required")
  return s.primary_model
}
export function commandPin(s: Session): CliPin {
  if (!s.command_model || !s.command_effort) throw new Error("Missing admitted Command Code pin; manual reconciliation required")
  return { model: s.command_model, effort: s.command_effort }
}
export function admittedModel(s: Session): string | ModelRef | undefined {
  const backend = backendOf(s)
  if (backend === "antigravity" || backend === "antigravity-transition") return antigravityPin(s).model
  if (backend === "pi" || backend === "pi-admitting" || backend === "pi-transition") return primaryFor(s)
  if (backend === "codex" || backend === "codex-transition") return s.codex_model
  return commandPin(s).model
}
export function admittedEffort(s: Session): string | undefined {
  const backend = backendOf(s)
  if (backend === "antigravity" || backend === "antigravity-transition") return antigravityPin(s).effort
  if (backend === "pi" || backend === "pi-admitting" || backend === "pi-transition") return primaryFor(s).variant
  if (backend === "codex" || backend === "codex-transition") return s.codex_effort
  return commandPin(s).effort
}

/** Keep the flat watcher wire format; only this boundary translates lifecycle states. */
export function encodeSession(s: Session) {
  const { execution: _execution, wire_version, ...fields } = s
  return { ...(wire_version === undefined ? {} : { schema_version: wire_version }), ...fields,
    backend: backendOf(s), command_run: processRun(s), pi_id: piId(s) }
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
function piModel(value: unknown, requireEffort: boolean): ModelRef {
  if (!isRecord(value)) throw new Error("Invalid persisted Pi model")
  if (requireEffort && value.variant === undefined) throw new Error("Missing admitted Pi effort; manual reconciliation required")
  return { providerID: requiredText(value.providerID, "Pi provider", 512), id: model(value.id),
    ...(value.variant === undefined ? {} : { variant: effort(value.variant) }) }
}
function commandRun(value: unknown): CommandRun {
  if (!isRecord(value) || typeof value.pid !== "number" || !Number.isSafeInteger(value.pid) || value.pid <= 0 ||
      (value.proc_start !== undefined && value.proc_start !== null && typeof value.proc_start !== "string"))
    throw new Error("Invalid persisted worker process")
  return { pid: value.pid, output: requiredText(value.output, "process output", 4096),
    errors: requiredText(value.errors, "process errors", 4096), started_at: requiredText(value.started_at, "process start"),
    ...(value.proc_start === undefined ? {} : { proc_start: value.proc_start }) }
}

// These are historical wire meanings, not defaults for new sessions. Never update
// them when the current policy changes: unversioned Hydrogen records omitted pins.
const LEGACY_HYDROGEN_PIN = { model: "gemini-4-hydrogen-xhigh", effort: "xhigh" } as const

export function decodeSession(value: unknown, cwd: string, id: string): Session {
  if (!isRecord(value)) throw new Error("Invalid persisted worker session")
  if (value.schema_version !== undefined && value.schema_version !== 1)
    throw new Error("Unsupported worker session version; manual reconciliation required")
  if (value.cwd !== cwd || value.id !== id || !isTier(value.tier)) throw new Error("Session/worktree mismatch")
  let backend = value.backend
  let antigravity_pin = value.antigravity_pin === undefined ? undefined : pin(value.antigravity_pin)
  if (value.schema_version === undefined && (backend === "hydrogen" || backend === "hydrogen-transition")) {
    if (antigravity_pin && (antigravity_pin.model !== LEGACY_HYDROGEN_PIN.model || antigravity_pin.effort !== LEGACY_HYDROGEN_PIN.effort))
      throw new Error("Ambiguous legacy Antigravity pin; manual reconciliation required")
    antigravity_pin = { ...LEGACY_HYDROGEN_PIN }
    backend = backend === "hydrogen" ? "antigravity" : "antigravity-transition"
  }
  if ((backend === "antigravity" || backend === "antigravity-transition") && (!antigravity_pin || value.tier !== "expert"))
    throw new Error("Invalid admitted Antigravity route; manual reconciliation required")
  if (value.schema_version === 1 && value.tier === "expert" && backend !== "antigravity" && backend !== "antigravity-transition")
    throw new Error("Invalid versioned expert route; manual reconciliation required")
  const run = value.command_run === undefined ? undefined : commandRun(value.command_run)
  const pi_id = optionalText(value.pi_id, "Pi session")
  let execution: Execution
  switch (backend) {
    case "pi":
      if (!pi_id) throw new Error("Missing persisted Pi session")
      execution = { kind: "pi", session_id: pi_id }
      break
    case "codex": case "command-code": case "antigravity":
      if (!run) throw new Error("Missing persisted worker process")
      execution = { kind: "process", executor: backend, run }
      break
    case "pi-admitting": case "pi-transition": case "codex-transition": case "command-transition": case "antigravity-transition":
      execution = { kind: "transition", executor: backend.startsWith("pi-") ? "pi" :
        backend === "codex-transition" ? "codex" : backend === "command-transition" ? "command-code" : "antigravity",
        ...(backend === "pi-admitting" ? { admitting: true } : {}), ...(run ? { previous_run: run } : {}), ...(pi_id ? { pi_id } : {}) }
      break
    default: throw new Error("Invalid persisted worker lifecycle; manual reconciliation required")
  }
  const s: Session = {
    ...(value.schema_version === 1 ? { wire_version: 1 } : {}),
    id, cwd, tier: value.tier, title: requiredText(value.title, "title", 100), task: requiredText(value.task, "task", 32000),
    scope: parseScope(value.scope, value.tier), execution, attempts: counter(value.attempts, "attempts"),
  }
  if (antigravity_pin) s.antigravity_pin = antigravity_pin
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
  if (value.execution_order !== undefined) {
    if (value.execution_order !== "command-first" && value.execution_order !== "codex-first") throw new Error("Invalid execution order")
    s.execution_order = value.execution_order
  }
  for (const key of ["command_model", "codex_model"] as const) {
    if (value[key] !== undefined) s[key] = model(value[key])
  }
  for (const key of ["command_effort", "codex_effort"] as const) {
    if (value[key] !== undefined) s[key] = effort(value[key])
  }
  if ((s.command_model === undefined) !== (s.command_effort === undefined) ||
      (s.codex_model === undefined) !== (s.codex_effort === undefined))
    throw new Error("Incomplete persisted model pin; manual reconciliation required")
  if (value.primary_model !== undefined) s.primary_model = piModel(value.primary_model, value.schema_version === 1)
  if (value.pi_candidates !== undefined) {
    if (!Array.isArray(value.pi_candidates) || value.pi_candidates.length > 8) throw new Error("Invalid persisted Pi plan")
    s.pi_candidates = value.pi_candidates.map(candidate => piModel(candidate, value.schema_version === 1))
  }
  if (value.remaining_pi !== undefined) {
    if (!Array.isArray(value.remaining_pi) || !value.remaining_pi.every(item => item === "muse" || item === "go"))
      throw new Error("Invalid legacy Pi destinations")
    s.remaining_pi = value.remaining_pi.map(item => item === "muse" ? "muse" : "go")
  }
  if (value.schema_version === 1) {
    if ((backend === "codex" || backend === "codex-transition") && !s.codex_model)
      throw new Error("Missing admitted Codex pin; manual reconciliation required")
    if ((backend === "command-code" || backend === "command-transition") && !s.command_model)
      throw new Error("Missing admitted Command Code pin; manual reconciliation required")
    if (backend === "pi" && !s.primary_model) throw new Error("Missing admitted Pi pin; manual reconciliation required")
  }
  return s
}
