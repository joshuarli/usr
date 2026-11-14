import { closeSync, fstatSync, openSync, readFileSync, readSync, statSync } from "node:fs"
import { join } from "node:path"
import { makeWorkerBridge, type ModelRef, type OpenCodePort } from "./bridge.ts"
import type { CommandResult, CommandRun } from "./command.ts"
import { changes, git, outside } from "./git.ts"
import type { CliPin, Executor } from "./policy.ts"
import { isRecord } from "./scope.ts"
import {
  STEER_LIMIT, TURN_LIMIT_CONTINUATIONS, admittedEffort, admittedModel, antigravityPin, backendOf,
  decodeSession, primaryFor, type Session,
} from "./session.ts"
import type { Tier } from "./tier-policy.ts"

const QUOTA = /\b(429|rate[ -]?limit(ed)?|quota|usage[ -]?limit|allowance exhausted|insufficient credits|credits? exhausted|resource_exhausted|too many requests)\b/i
const PROVIDER_UNAVAILABLE = /\b(model (?:is |was )?(?:unavailable|not available|not found|unsupported)|unknown model|unsupported model|no such model|model does not exist|provider unavailable|provider not found|not logged in|not authenticated|authentication required|missing credentials)\b/i
const PI_LOG_TAIL_BYTES = 500
const EVENT_LOG_TAIL_BYTES = 65536
const EVENT_LOG_TAIL_LINES = 50
const EVENT_DESCRIPTION_CHARS = 160

type CliExecutor = Exclude<Executor, "pi">
type OrUnknown<T> = T | "unknown"

export type RunnerStatus = { state: string; result: CommandResult | null; stderr: string | null }
export type InspectionDeps = {
  api: OpenCodePort
  command: { status(run: CommandRun): RunnerStatus }
  codex: { status(run: CommandRun): RunnerStatus }
  antigravity: { status(run: CommandRun, pin: CliPin): RunnerStatus }
}

export type Observation = {
  state: string
  final_text: string | null
  error: unknown
  usage: unknown
  pid: number | null
  last_activity_ms: number | null
  last_event: string
}
export type Claim = "met" | "not_met" | "missing"
export type FallbackSource = "pi" | "codex" | "command-code"
export type Known = { observation: Observation; blocked?: { state: string; notice: string } }

type Route = { model: string | ModelRef | undefined; effort: string | undefined } | { fault: string }
type Worktree =
  | { kind: "read"; head: string; changed_paths: string[]; out_of_scope_paths: string[] }
  | { kind: "unreadable"; reason: string }
export type Inspection = {
  observed_at: string
  session: Session
  observation: Observation
  state: string
  notice: string | null
  route: Route
  worktree: Worktree
  acceptance_claim: Claim
}
export type Snapshot = {
  observed_at: string
  id: string
  title: OrUnknown<string>
  tier: OrUnknown<Tier>
  worktree: OrUnknown<string>
  base_revision: OrUnknown<string>
  head: OrUnknown<string>
  backend: OrUnknown<string>
  model: OrUnknown<string | ModelRef>
  effort: OrUnknown<string>
  execution_state: string
  last_assistant_text: OrUnknown<string | null>
  error: unknown
  usage: unknown
  pid: OrUnknown<number>
  last_activity: OrUnknown<string>
  last_event: OrUnknown<string>
  changed_paths: OrUnknown<string[]>
  out_of_scope_paths: OrUnknown<string[]>
  head_unchanged: OrUnknown<boolean>
  acceptance_claim: OrUnknown<Claim>
  continuations: OrUnknown<number>
  continuation_limit: number
  steers: OrUnknown<number>
  steer_limit: number
  fallback_reason: OrUnknown<string | null>
  fallback_notice: OrUnknown<string | null>
  fallback_detail: OrUnknown<string | null>
  reason: string | null
}

export function quota(value: unknown): boolean {
  return QUOTA.test(typeof value === "string" ? value : JSON.stringify(value ?? ""))
}
function providerUnavailable(value: unknown): boolean {
  return PROVIDER_UNAVAILABLE.test(typeof value === "string" ? value : JSON.stringify(value ?? ""))
}

export function acceptanceClaim(text: string | null): Claim {
  const last = text?.trimEnd().split("\n").at(-1)?.replace(/[`*]/g, "").trim().toLowerCase()
  return last === "acceptance: met" ? "met" : last === "acceptance: not met" ? "not_met" : "missing"
}

export function fallbackNotice(s: Session): string {
  return [
    s.fallback_reason,
    "Automatic fallback is expected and needs no parent action.",
    "The worktree was verified untouched before switching, so no work was lost or replayed.",
    "The task continues on " + (backendOf(s) === "pi"
      ? (s.primary_model?.providerID === "muse-sdk" ? "Muse subscription via the Pi SDK" : "OpenCode Go via the Pi SDK")
      : "Command Code") +
      " with the same scope and approved tier pins; verify it normally with worker_status.",
    "Do not retry and do not start a duplicate worker.",
  ].join(" ")
}
export function blockedPartialNotice(): string {
  return [
    "The primary runner hit a provider usage limit, but the worktree already has edits, so no automatic switch happened.",
    "Inspect the worktree and decide manually; do not start a duplicate worker.",
  ].join(" ")
}

export function runnerStatus(deps: InspectionDeps, s: Session, executor: CliExecutor, run: CommandRun): RunnerStatus {
  if (executor === "antigravity") return deps.antigravity.status(run, antigravityPin(s))
  return (executor === "codex" ? deps.codex : deps.command).status(run)
}

function modifiedAt(path: string | undefined): number | null {
  if (!path) return null
  try { return statSync(path).mtimeMs } catch { return null }
}
function lastActivity(paths: Array<string | undefined>, sessionFile: string): number | null {
  const times = paths.map(modifiedAt).filter((time) => time !== null)
  return times.length ? Math.max(...times) : modifiedAt(sessionFile)
}
function readTail(path: string, bytes: number): string {
  try {
    const fd = openSync(path, "r")
    try {
      const size = fstatSync(fd).size, length = Math.min(size, bytes)
      const buffer = Buffer.alloc(length)
      const got = readSync(fd, buffer, 0, length, size - length)
      return buffer.subarray(0, got).toString("utf8")
    } finally { closeSync(fd) }
  } catch { return "" }
}
function lastToolEvent(output: string): string {
  const lines = readTail(output, EVENT_LOG_TAIL_BYTES).split("\n").filter(Boolean).slice(-EVENT_LOG_TAIL_LINES)
  for (const line of lines.reverse()) {
    let record: unknown
    try { record = JSON.parse(line) } catch { continue }
    if (!isRecord(record) || record.type !== "event" || !isRecord(record.event) || record.event.type !== "tool_queued") continue
    const input = isRecord(record.event.input) ? record.event.input : {}
    const detail = input.description ?? input.command ?? ""
    const text = typeof detail === "string" ? detail : JSON.stringify(detail)
    return String(record.event.toolName) + ": " + text.slice(0, EVENT_DESCRIPTION_CHARS)
  }
  return ""
}
function piRun(directory: string, piId: string): { pid: number | null; output?: string; errors?: string } | null {
  try {
    const record: unknown = JSON.parse(readFileSync(join(directory, piId + ".pi.json"), "utf8"))
    const run = isRecord(record) && isRecord(record.run) ? record.run : null
    if (!run) return null
    return {
      pid: typeof run.pid === "number" ? run.pid : null,
      ...(typeof run.output === "string" ? { output: run.output } : {}),
      ...(typeof run.errors === "string" ? { errors: run.errors } : {}),
    }
  } catch { return null }
}
function withheld(state: string, error: string, sessionFile: string): Observation {
  return { state, final_text: null, error, usage: null, pid: null, last_activity_ms: modifiedAt(sessionFile), last_event: "" }
}

export async function observeExecution(s: Session, directory: string, deps: InspectionDeps): Promise<Observation> {
  const sessionFile = join(directory, s.id + ".json")
  const execution = s.execution
  if (execution.kind === "transition" && execution.executor === "pi")
    return withheld("blocked_admission", "Pi admission interrupted or uncertain; inspect this session before recovery", sessionFile)
  if (execution.kind === "transition")
    return withheld("blocked_transition",
      execution.executor + " transition interrupted; inspect persisted state and worktree before recovery", sessionFile)
  if (execution.kind === "pi") {
    const response = await makeWorkerBridge(deps.api, primaryFor(s)).status(s.cwd, execution.session_id)
    const run = piRun(directory, execution.session_id)
    return {
      state: typeof response.state === "string" ? response.state : "unknown",
      final_text: response.last_assistant_text, error: response.error,
      usage: { cost_reported_usd: response.cost_reported_usd, tokens: response.tokens },
      pid: run?.pid ?? null,
      last_activity_ms: lastActivity([run?.output, run?.errors], sessionFile),
      last_event: run?.errors ? readTail(run.errors, PI_LOG_TAIL_BYTES).trimEnd() : "",
    }
  }
  const { run } = execution
  const response = runnerStatus(deps, s, execution.executor, run)
  let state = response.state, error: unknown = response.state === "interrupted"
    ? "Worker process is gone or its recorded PID identity changed; the run is terminal and cannot be replayed"
    : response.state === "failed" ? response.result?.error ?? response.stderr : null
  if (s.cancel_requested && (state === "failed" || state === "interrupted")) { state = "cancelled"; error = null }
  return {
    state, final_text: response.result?.finalText ?? null, error, usage: response.result?.usage ?? null,
    pid: run.pid, last_activity_ms: lastActivity([run.output, run.errors], sessionFile),
    last_event: lastToolEvent(run.output),
  }
}

export function fallbackSource(s: Session, observation: Observation): FallbackSource | null {
  const execution = s.execution
  if (execution.kind === "pi") {
    const finished = !["running", "queued", "succeeded"].includes(observation.state)
    return s.execution_order === undefined && finished && quota(observation.error) ? "pi" : null
  }
  if (execution.kind !== "process" || s.fallback_blocked) return null
  if (observation.state !== "failed" || !(quota(observation.error) || providerUnavailable(observation.error))) return null
  if (execution.executor === "codex") return "codex"
  return execution.executor === "command-code" && s.execution_order !== undefined ? "command-code" : null
}

export function settledState(s: Session, observation: Observation, clean: boolean | null): { state: string; notice: string | null } {
  if (s.execution.kind === "process" && s.fallback_blocked) return { state: "blocked_fallback", notice: s.fallback_blocked }
  if (fallbackSource(s, observation) !== null && clean === false)
    return { state: "blocked_partial_work", notice: blockedPartialNotice() }
  return { state: observation.state, notice: null }
}

function inheritedNotice(s: Session, state: string): string | null {
  if (!s.fallback_reason) return null
  if (state.startsWith("blocked")) return "Provider transition blocked; inspect the owned session before retrying."
  const backend = backendOf(s)
  if ((backend === "pi" || backend === "pi-admitting" || backend === "pi-transition") &&
      ["failed", "interrupted", "cancelled", "canceled"].includes(state)) {
    const provider = s.primary_model?.providerID === "muse-sdk" ? "the pinned Muse SDK fallback" : "the pinned OpenCode Go fallback"
    return "The task was admitted to " + provider + " via Command Code's absence or failure, but that Pi run ended in " + state +
      " (see error; it may have left partial edits). The worktree is retained and the lease is released. No automatic retry will occur: a fresh dispatch" +
      " re-admits with the best available lane, and a provider usage-limit error (for example 429) means every pinned lane is exhausted —" +
      " per the orchestrate quota-fallback rule, delegate to the harness's native subagents instead of restarting the bridge."
  }
  return fallbackNotice(s)
}

function readWorktree(s: Session): Worktree {
  try {
    const changed_paths = changes(s.cwd, s.scope.base_revision)
    return { kind: "read", head: git(s.cwd, "rev-parse", "HEAD"), changed_paths,
      out_of_scope_paths: outside(changed_paths, s.scope.writable_paths) }
  } catch (error) {
    return { kind: "unreadable", reason: error instanceof Error ? error.message : String(error) }
  }
}
function routeOf(s: Session): Route {
  try { return { model: admittedModel(s), effort: admittedEffort(s) } }
  catch (error) { return { fault: error instanceof Error ? error.message : String(error) } }
}

function compose(s: Session, observation: Observation, blocked?: Known["blocked"]): Inspection {
  const worktree = readWorktree(s)
  const clean = worktree.kind === "read" ? worktree.head === s.scope.base_revision && worktree.changed_paths.length === 0 : null
  const settled = blocked ?? settledState(s, observation, clean)
  return {
    observed_at: new Date().toISOString(), session: s, observation, state: settled.state,
    notice: settled.notice ?? inheritedNotice(s, settled.state), route: routeOf(s), worktree,
    acceptance_claim: acceptanceClaim(observation.final_text?.slice(-5000) ?? null),
  }
}

export async function inspectSession(s: Session, directory: string, deps: InspectionDeps, known?: Known): Promise<Inspection> {
  return compose(s, known?.observation ?? await observeExecution(s, directory, deps), known?.blocked)
}

export function sessionPath(directory: string, id: string): string {
  return join(directory, id + ".json")
}

function describe(error: unknown): string {
  return error instanceof Error ? error.message : String(error)
}
function inspectionReason(i: Inspection): string | null {
  if ("fault" in i.route) return i.route.fault
  if (i.worktree.kind === "unreadable") return i.worktree.reason
  return i.observation.state === "unknown" ? describe(i.observation.error ?? "execution state is unknown") : null
}

export function toSnapshot(i: Inspection): Snapshot {
  const s = i.session, route = i.route, worktree = i.worktree
  const read = worktree.kind === "read" ? worktree : null
  const activity = i.observation.last_activity_ms
  const model = "fault" in route ? undefined : route.model
  const effort = "fault" in route ? undefined : route.effort
  return {
    observed_at: i.observed_at, id: s.id, title: s.title, tier: s.tier, worktree: s.cwd,
    base_revision: s.scope.base_revision, head: read?.head ?? "unknown", backend: backendOf(s),
    model: model ?? "unknown", effort: effort ?? "unknown",
    execution_state: i.state, last_assistant_text: i.observation.final_text?.slice(-5000) ?? null,
    error: i.observation.error, usage: i.observation.usage,
    pid: i.observation.pid ?? "unknown", last_activity: activity === null ? "unknown" : new Date(activity).toISOString(),
    last_event: i.observation.last_event,
    changed_paths: read?.changed_paths ?? "unknown", out_of_scope_paths: read?.out_of_scope_paths ?? "unknown",
    head_unchanged: read ? read.head === s.scope.base_revision : "unknown",
    acceptance_claim: i.acceptance_claim,
    continuations: s.continuations ?? 0, continuation_limit: TURN_LIMIT_CONTINUATIONS,
    steers: s.steers ?? 0, steer_limit: STEER_LIMIT,
    fallback_reason: s.fallback_reason ?? null, fallback_notice: i.notice, fallback_detail: s.fallback_detail ?? null,
    reason: inspectionReason(i),
  }
}

function unreadableSnapshot(id: string, raw: unknown, reason: string): Snapshot {
  const record = isRecord(raw) ? raw : {}
  const text = (value: unknown) => typeof value === "string" && value ? value : "unknown"
  return {
    observed_at: new Date().toISOString(), id, title: text(record.title), tier: "unknown", worktree: text(record.cwd),
    base_revision: "unknown", head: "unknown", backend: text(record.backend), model: "unknown", effort: "unknown",
    execution_state: "unknown", last_assistant_text: "unknown", error: reason, usage: "unknown", pid: "unknown",
    last_activity: "unknown", last_event: "unknown", changed_paths: "unknown", out_of_scope_paths: "unknown",
    head_unchanged: "unknown", acceptance_claim: "unknown", continuations: "unknown",
    continuation_limit: TURN_LIMIT_CONTINUATIONS, steers: "unknown", steer_limit: STEER_LIMIT,
    fallback_reason: "unknown", fallback_notice: "unknown", fallback_detail: "unknown", reason,
  }
}

export async function inspectStored(directory: string, id: string, deps: InspectionDeps): Promise<Snapshot> {
  const path = sessionPath(directory, id)
  let raw: unknown
  try {
    raw = JSON.parse(readFileSync(path, "utf8"))
  } catch (error) {
    const missing = error instanceof Error && "code" in error && error.code === "ENOENT"
    return unreadableSnapshot(id, undefined, missing ? "no session record at " + path : "unreadable session record at " + path + ": " + describe(error))
  }
  let session: Session
  try {
    if (!isRecord(raw) || typeof raw.cwd !== "string") throw new Error("Invalid persisted worker session")
    session = decodeSession(raw, raw.cwd, id)
  } catch (error) {
    return unreadableSnapshot(id, raw, describe(error))
  }
  let observation: Observation
  try {
    observation = await observeExecution(session, directory, deps)
  } catch (error) {
    observation = withheld("unknown", describe(error), path)
  }
  return toSnapshot(compose(session, observation))
}
