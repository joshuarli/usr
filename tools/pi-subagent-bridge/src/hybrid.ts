import { fxResult, type FxAdapter } from "./fx.ts"
import type { PiAdapter } from "./pi-adapter.ts"
import { randomUUID } from "node:crypto"
import { execFileSync } from "node:child_process"
import { accessSync, constants, existsSync, mkdirSync, readFileSync, renameSync, rmdirSync, rmSync, statSync, writeFileSync } from "node:fs"
import { dirname, join, resolve } from "node:path"
import { PreAdmissionError, checkedWorktree } from "./bridge.ts"
import { cancelCommand, commandResult, commandSession, processStartTime, startCommand, type CommandRun } from "./command.ts"
import { codexAvailable, codexResult, codexSession, cancelCodex, startCodex } from "./codex.ts"
import { activeWorktreeOwner, claimWorktree, ensureWorktree, releaseWorktree } from "./worktree-lease.ts"

import { isBridgeTier, type BridgeTier } from "./tier-policy.ts"
import { piInstalled, diagnoseGoModel } from "./optional-pi.ts"
import { musePreflight, museVersion } from "./muse-subscription.ts"
import { devinPreflight } from "./devin-provider.ts"
import { changes, currentBranch, git, laneHead, outside, readStateDir, stateDir } from "./git.ts"
import {
  fallbackNotice, fallbackSource, inspectSession, observeExecution, runnerStatus, settledState,
  type Inspection, type InspectionDeps, type Known,
} from "./inspect.ts"
import {
  STEER_LIMIT, TURN_LIMIT_CONTINUATIONS, activatePi, activateProcess, backendOf, decodeSession, encodeSession,
  executorOf, isSessionId, piFallbackPlan, processRun, processTarget, targetOf, transition, type PiFallbackPlan, type ProcessExecution,
  type ProcessTarget, type ExecutionPlan, type Session, type SessionOwner,
} from "./session.ts"
import { PI_RUN_DEADLINE_MS } from "./tier-policy.ts"
import type { Access, PlannedRun } from "./launch.ts"
import { ROOT_PLANS, type CliExecutor, type CliPin, type PiSelection, type RootPlan } from "./policy.ts"
import { parseScope, requiredText as required, type Scope } from "./scope.ts"
import { beforeDeadline, deadlineTimeout, steerCleanup, steerDeadline, SteerDeadlineError } from "./steer-deadline.ts"
export type RoutedTier = BridgeTier
export type { Scope } from "./scope.ts"
const TERMINATION_WAIT_MS = 2000

function scopeFor(value: unknown, tier: RoutedTier, cwd: string, checkHead = true): Scope {
  return parseScope(value, tier, checkHead ? git(cwd, "rev-parse", "HEAD") : undefined)
}
/** The effective wall-clock budget: explicit for Pi, unbounded elsewhere. */
function runDeadlineMs(s: Session): number | null {
  return targetOf(s).executor === "pi" ? PI_RUN_DEADLINE_MS : null
}
/** The command that blocks until the session's executor finishes; run it as a background task. */
function watchCommand(s: Session): string {
  return "pi-subagent-bridge watch " + JSON.stringify(dirname(dirname(stateDir(s.cwd)))) + " " + s.id
}
function pathFor(cwd: string, id: string): string {
  if (!isSessionId(id)) throw new Error("Invalid worker ID")
  return join(stateDir(cwd), id + ".json")
}
function save(s: Session): void {
  const path = pathFor(s.cwd, s.id), tmp = path + "." + randomUUID() + ".tmp"
  try {
    writeFileSync(tmp, JSON.stringify(encodeSession(s)), { mode: 0o600 })
    renameSync(tmp, path)
  } finally {
    rmSync(tmp, { force: true })
  }
}
function load(cwd: unknown, id: unknown): Session {
  const dir = checkedWorktree(cwd)
  const sessionId = required(id, "session_id", 64)
  const raw: unknown = JSON.parse(readFileSync(pathFor(dir, sessionId), "utf8"))
  return decodeSession(raw, dir, sessionId)
}
function callerAlive(pid: number): boolean {
  try { process.kill(pid, 0); return true } catch (error) { return (error as NodeJS.ErrnoException).code !== "ESRCH" }
}
function finishSteer(s: Session, outcome: "completed" | "failed"): void {
  if (!s.pending_steer) return
  const pending = s.pending_steer, previous = s.last_steer
  const { note, requested_at } = pending
  s.last_steer = { note, requested_at, outcome, at: new Date().toISOString() }
  delete s.pending_steer
  try { save(s) } catch (error) {
    s.pending_steer = pending
    if (previous) s.last_steer = previous
    else delete s.last_steer
    throw error
  }
}
function recoveredRun(planned: PlannedRun): CommandRun | null {
  const readPid = () => { try { return Number(readFileSync(planned.output + ".pid", "utf8").trim()) } catch { return 0 } }
  let pid = readPid()
  if (!pid) {
    try {
      const processes = execFileSync("ps", ["-eo", "pid=,args="], { encoding: "utf8", timeout: deadlineTimeout(2000), maxBuffer: 4_000_000 })
      const marker = "bridge-launch " + planned.output + ".pid "
      const line = processes.split("\n").find(value => value.includes(marker))
      pid = Number(line?.trim().split(/\s+/, 1)[0] ?? 0) || readPid()
    } catch { pid = readPid() }
  }
  if (!Number.isSafeInteger(pid) || pid <= 0) return null
  let events = false
  try { events = statSync(planned.output).size > 0 } catch {}
  if (!callerAlive(pid) && !events) return null
  return { ...planned, pid, proc_start: processStartTime(pid) }
}

async function withSessionLock<T>(cwd: unknown, id: unknown, work: (session: Session) => Promise<T>): Promise<T> {
  const directory = checkedWorktree(cwd)
  const sessionID = required(id, "session_id", 64)
  const lock = pathFor(directory, sessionID) + ".lock"
  try {
    mkdirSync(lock, { mode: 0o700 })
  } catch (error) {
    if (error instanceof Error && "code" in error && error.code === "EEXIST") {
      const session = load(directory, sessionID)
      if (session.pending_steer && !callerAlive(session.pending_steer.caller_pid)) {
        rmdirSync(lock)
        return withSessionLock(directory, sessionID, work)
      }
      if (session.pending_steer) throw new Error("A steer is already pending for this session")
      throw new Error("Worker session transition in progress or interrupted; inspect and retry safely")
    }
    throw error
  }
  try {
    return await work(load(directory, sessionID))
  } finally {
    rmdirSync(lock)
  }
}
function cmdAvailable(): boolean {
  for (const part of (process.env.PATH || "").split(":")) {
    if (!part) continue
    try { accessSync(resolve(part, "cmd"), constants.X_OK); return true } catch { /* continue */ }
  }
  return false
}
function prompt(s: Session): string {
  return [
    "You execute a single scoped task using the pinned tier model. The parent harness coordinates.",
    "Tier: " + s.tier + ". Task: " + s.task,
    "Use only worktree " + s.cwd + " at base revision " + s.scope.base_revision,
    "Writable paths: " + (s.scope.writable_paths.join(", ") || "NONE: READ ONLY"),
    "Required acceptance proof: " + s.scope.acceptance_proof,
    "Attempt limit: " + s.scope.attempt_limit + ". Stop on: " + s.scope.stop_on,
    ...(s.tier === "scout" && executorOf(s) === "codex" ? ["Use bridge_scout tools to inspect the actual files. Never claim a shell command ran; report only tool output you observed."] : []),
    "Native Pi workers may delegate at most one generation to equal-or-weaker typed tiers within the assigned worktree and scope.",
    "A nested child may not delegate again; never launch a new pi-subagent-bridge CLI/MCP session yourself.",
    "Codex and Command Code workers remain leaves: do not spawn subagents.",
    s.tier === "scout" ? "Do not commit, switch branches, merge, push, add dependencies, or edit outside writable paths." :
      "You may commit your work on the current branch of this worktree (Conventional Commits, explaining why); do not amend or rewrite commits that existed at admission, merge, rebase, switch branches, push, add dependencies, or edit outside writable paths.",
    "The brief's acceptance proof is the goal: keep working until it is met or a listed stop condition truly applies. Resolve ambiguity from the brief, code, or repository conventions; that ambiguity is not a stop condition. A needed commit, missing scratch directory, slow command, or recoverable tool error is not a blocker. Stopping early without a named stop condition from the brief counts as an incomplete run.",
    "Stop if blocked or if the requirements demand more scope. Do not broaden the task.",
    "A slow or still-running required command is not a blocker: run it detached, poll its log until it exits, and never end your turn while a required command is still running.",
    "Rerun a command once after an environmental failure such as a toolchain crash or interruption before reporting it as a blocker.",
    "Return a PROOF RECORD instead of a summary: changed paths; exact commands, exit codes and decisive output;",
    "file:line evidence for research; and explicit unverified cases and blockers. Never invent a passing check.",
    "End with exactly one final line: `ACCEPTANCE: met` only when every required acceptance command ran and passed, otherwise `ACCEPTANCE: not met`.",
    "When acceptance is not met, put `STOPPED_ON: <the stop condition, quoted verbatim from the scope's stop_on>` immediately before that final line.",
  ].join("\n")
}
function untouched(s: Session): boolean {
  return git(s.cwd, "rev-parse", "HEAD") === s.scope.base_revision &&
    changes(s.cwd, s.scope.base_revision).length === 0
}
/** Name each condition that blocks a resume or steer. */
function describeDrift(s: Session): string {
  const details: string[] = []
  const lane = laneHead(s)
  if (lane.drift) details.push(lane.drift)
  const paths = outside(changes(s.cwd, s.scope.base_revision), s.scope.writable_paths)
  if (paths.length) details.push("out-of-scope: " + paths.slice(0, 5).join(", ") + (paths.length > 5 ? " (+" + (paths.length - 5) + " more)" : ""))
  return details.join("; ") || "work drifted from the admitted scope"
}
export type OwnerResolver = (stateDirectory: string) => Promise<SessionOwner | undefined> | SessionOwner | undefined
export type OwnerEffectAdmit = () => Promise<void> | void
export type OwnerPrecheckReason = "not-running"
export class OwnerPrecheckError extends Error {
  readonly reason: OwnerPrecheckReason
  constructor(reason: OwnerPrecheckReason, message: string) {
    super(message)
    this.reason = reason
  }
}
export type HybridOwnerOps = {
  readonly inspection: InspectionDeps
  setOwnerResolver(resolver: OwnerResolver | undefined): void
  resumeForOwner(cwd: unknown, id: unknown, feedback: unknown, admitEffect: OwnerEffectAdmit): Promise<unknown>
  steerForOwner(cwd: unknown, id: unknown, note: unknown, admitEffect: OwnerEffectAdmit): Promise<unknown>
  cancelForOwner(cwd: unknown, id: unknown, admitEffect: OwnerEffectAdmit): Promise<{ interrupted: boolean }>
}

const ownerOpsRegistry = new WeakMap<object, HybridOwnerOps>()

export function hybridOwnerOps(bridge: object): HybridOwnerOps | undefined {
  return ownerOpsRegistry.get(bridge)
}

export function makeHybridBridge(api: PiAdapter, command = {
  start: startCommand, status: commandResult, cancel: cancelCommand, available: cmdAvailable,
}, codex = { start: startCodex, status: codexResult, cancel: cancelCodex, available: codexAvailable, session: codexSession },
  resolvePolicy: (tier: BridgeTier) => ExecutionPlan = tier => ROOT_PLANS[tier], fx?: FxAdapter) {
  const inspection: InspectionDeps = { api, command, codex, fx: { status: fxResult } }
  let ownerResolver: OwnerResolver | undefined
  function runnerFor(executor: CliExecutor) {
    switch (executor) {
      case "fx": { if (!fx) throw new Error("FX adapter unavailable"); return fx }
      case "codex": return codex
      case "command-code": return command
    }
  }
  function targetAvailable(target: ProcessTarget): boolean {
    if (target.executor === "fx") return fx?.available(target.selection) === true
    return target.executor === "codex" ? codex.available() : command.available()
  }
  function observe(execution: ProcessExecution) {
    return runnerStatus(inspection, execution)
  }
  function accessFor(s: Session): Access {
    return s.tier === "scout" ? { kind: "read-only" } : { kind: "write" }
  }
  function launch(s: Session, target: ProcessTarget, text: string, resume?: string, planned_run?: PlannedRun): CommandRun {
    const request = { directory: s.cwd, logDirectory: stateDir(s.cwd), prompt: text, selection: target.selection, resume, ...(planned_run ? { planned_run } : {}) }
    switch (target.executor) {
      case "fx": { if (!fx) throw new Error("FX adapter unavailable"); return fx.start({ ...request, selection: target.selection, access: accessFor(s) }) }
      case "codex": return codex.start({ ...request, access: accessFor(s) })
      case "command-code": return command.start({ ...request, access: accessFor(s) })
    }
  }
  function fallbackToProcess(s: Session, target: ProcessTarget, reason: string, detail?: unknown): Session {
    if (!targetAvailable(target)) throw new Error(reason + "; " + target.executor + " unavailable")
    if (!untouched(s)) throw new Error("Fallback forbidden after partial edits; inspect the worktree")
    ensureWorktree(stateDir(s.cwd), s.cwd, s.id)
    transition(s, target)
    s.fallback_reason = reason
    if (detail !== undefined) s.fallback_detail = (typeof detail === "string" ? detail : JSON.stringify(detail)).slice(0, 2000)
    s.attempts = 1
    save(s)
    activateProcess(s, target, launch(s, target, prompt(s)))
    save(s)
    return s
  }
  function fallbackToCommand(s: Session, pin: CliPin, reason: string, detail?: unknown): Session {
    return fallbackToProcess(s, { executor: "command-code", selection: pin }, reason, detail)
  }
  async function availablePi(plan: PiFallbackPlan, from: number, cwd: string): Promise<{ selection: PiSelection; next: number } | null> {
    for (let index = from; index < plan.pi.length; index++) {
      const candidate = plan.pi[index]
      if (candidate.providerID === "muse-sdk") process.env.PI_MUSE_SDK_CONTRIBUTOR = "on"
      try {
        if ((await api(candidate).modelCheck(cwd)).available) return { selection: candidate, next: index + 1 }
      } catch { }
    }
    return null
  }
  async function fallbackToPi(s: Session, plan: PiFallbackPlan, reason: string, detail?: unknown): Promise<Session> {
    if (!untouched(s)) throw new Error("Fallback forbidden after partial edits; inspect the worktree")
    // An in-flight, interrupted, or ambiguous Command Code process must never be duplicated.
    const previousRun = processRun(s)
    if (previousRun && command.status(previousRun).state !== "failed")
      throw new Error("Command Code is not known terminal; OpenCode Go fallback refused")
    ensureWorktree(stateDir(s.cwd), s.cwd, s.id)
    let next = 0
    for (;;) {
      const available = await availablePi(plan, next, s.cwd)
      if (!available) throw new Error("Pinned Pi fallback models are unavailable")
      const { selection } = available
      next = available.next
      const worker = api(selection)
      transition(s, { executor: "pi", selection }, true)
      s.fallback_reason = reason
      if (detail !== undefined)
        s.fallback_detail = (typeof detail === "string" ? detail : JSON.stringify(detail)).slice(0, 2000)
      s.attempts = 1
      save(s)
      try {
        const admitted = await worker.start(s.cwd, s.title, prompt(s), s.tier === "scout")
        activatePi(s, selection, admitted.session_id)
        save(s)
        return s
      } catch (error) {
        if (error instanceof PreAdmissionError && next < plan.pi.length) {
          transition(s, { executor: "command-code", selection: plan.command })
          save(s)
          continue
        }
        if (String(error).includes("created but prompt admission failed"))
          throw new Error(String(error) + "; worktree lease retained for session " + s.id)
        throw error
      }
    }
  }
  /** Refreshes the worktree's lease holder so a session that already ended releases its lease before a new admission. */
  async function settleHolder(leaseDir: string, dir: string): Promise<void> {
    const holder = activeWorktreeOwner(leaseDir, dir)
    if (holder === null) return
    try { await advance(dir, holder) } catch { /* claimWorktree reports the holder */ }
  }
  async function advance(cwd: unknown, id: unknown, reconcileDetached = false): Promise<{ session: Session; known?: Known }> {
    return withSessionLock(cwd, id, async (s) => {
      if (s.pending_steer && (!callerAlive(s.pending_steer.caller_pid) || (reconcileDetached && s.pending_steer.phase === "relaunching"))) {
        const pending = s.pending_steer
        const recovered = pending.planned_run && s.execution.kind === "process" && s.execution.run.output === pending.previous_output
          ? recoveredRun(pending.planned_run) : null
        if (recovered && s.execution.kind === "process") activateProcess(s, processTarget(s.execution), recovered)
        const completed = recovered !== null || (s.execution.kind === "process" && pending.previous_output !== null && s.execution.run.output !== pending.previous_output)
        if (completed) s.steers = (s.steers ?? 0) + 1
        finishSteer(s, completed ? "completed" : "failed")
      }
      const observation = await observeExecution(s, stateDir(s.cwd), inspection)
      const source = fallbackSource(s, observation)
      const clean = source === null || untouched(s)
      let state = settledState(s, observation, clean).state
      let known: Known | undefined = { observation }
      if (source?.kind === "pi" && clean) {
        fallbackToCommand(s, source.plan.command, "Primary Pi runner unavailable during execution (provider usage limit); no edits existed, so the task continued on Command Code.", observation.error)
        state = "running"
        known = undefined
      } else if (source?.kind === "fx" && clean) {
        try {
          transition(s, source.from)
          save(s)
          const codexTarget: ProcessTarget = { executor: "codex", selection: source.plan.codex }
          if (codex.available()) fallbackToProcess(s, codexTarget, "FX provider/model exhausted or unavailable; continued on Codex before edits.", observation.error)
          else if (command.available()) fallbackToCommand(s, source.plan.command, "FX provider/model exhausted or unavailable and Codex is unavailable; continued on Command Code before edits.", observation.error)
          else await fallbackToPi(s, source.plan, "FX, Codex and Command Code unavailable; continued on an approved Pi provider.", observation.error)
          state = "running"
          known = undefined
        } catch (fallbackError) {
          s.fallback_blocked = "Fallback blocked: " + String(fallbackError)
          save(s)
          state = s.execution.kind === "transition" ? "blocked_admission" : "blocked_fallback"
          known = { observation, blocked: { state, notice: s.fallback_blocked } }
        }
      } else if (source?.kind === "codex" && clean) {
        try {
          transition(s, source.from)
          save(s)
          if (command.available()) fallbackToCommand(s, source.plan.command, "Codex provider/model unavailable; continued on Command Code before edits.", observation.error)
          else await fallbackToPi(s, piFallbackPlan(source.plan), "Codex and Command Code unavailable; continued on an approved Pi provider.", observation.error)
          state = "running"
          known = undefined
        } catch (fallbackError) {
          s.fallback_blocked = "Fallback blocked: " + String(fallbackError)
          save(s)
          state = s.execution.kind === "transition" ? "blocked_admission" : "blocked_fallback"
          known = { observation, blocked: { state, notice: s.fallback_blocked } }
        }
      } else if (source?.kind === "command-code" && clean) {
        try {
          await fallbackToPi(s, piFallbackPlan(source.plan),
            "Primary Command Code provider/model unavailable; continued on an approved Pi provider before edits.", observation.error)
          state = "running"
          known = undefined
        } catch (fallbackError) {
          s.fallback_blocked = "Pi fallback blocked: " + String(fallbackError)
          save(s)
          state = s.execution.kind === "transition" && s.execution.to.executor === "pi" ? "blocked_admission" : "blocked_fallback"
          known = { observation, blocked: { state, notice: s.fallback_blocked } }
        }
      }
      if (["succeeded", "failed", "turn_limit", "cancelled", "canceled", "interrupted", "timed_out"].includes(state)) {
        const directory = stateDir(s.cwd)
        if (activeWorktreeOwner(directory, s.cwd) === s.id)
          releaseWorktree(directory, s.cwd, s.id)
      }
      return { session: s, ...(known ? { known } : {}) }
    })
  }
  function statusResponse(i: Inspection) {
    const s = i.session
    if (i.worktree.kind !== "read") throw new Error(i.worktree.kind === "unreadable" ? i.worktree.reason : "Worktree inspection omitted")
    const { head, changed_paths, out_of_scope_paths } = i.worktree
    const head_unchanged = head === s.scope.base_revision
    const { head_on_lane, commits_since_base } = laneHead(s)
    const last_assistant_text = i.observation.final_text?.slice(-5000) ?? null
    const state = i.state === "succeeded" && i.acceptance_claim !== "met" ? "incomplete" : i.state
    return {
      session_id: s.id, backend: backendOf(s), tier: s.tier, model: i.route.model, effort: i.route.effort,
      state, last_assistant_text, error: i.observation.error, usage: i.observation.usage,
      run_deadline_ms: runDeadlineMs(s),
      changed_paths, out_of_scope_paths, head_unchanged, head_on_lane, commits_since_base,
      acceptance_claim: i.acceptance_claim, stopped_on: i.stopped_on, stop_condition_valid: i.stop_condition_valid,
      reason: i.notice === "stopped without a listed stop condition" ? i.notice : null,
      acceptance_blocked: !head_on_lane || out_of_scope_paths.length > 0 || i.acceptance_claim !== "met",
      continuations: s.continuations ?? 0, continuation_limit: TURN_LIMIT_CONTINUATIONS,
      attempt_extensions: (s.attempt_extensions ?? []).reduce((sum, entry) => sum + entry.added, 0),
      steers: s.steers ?? 0, steer_limit: STEER_LIMIT, pending_steer: s.pending_steer ?? null, last_steer: s.last_steer ?? null,
      fallback_reason: s.fallback_reason ?? null,
      fallback_notice: i.notice,
      fallback_detail: s.fallback_detail ?? null,
      note: "Proof must be checked independently. Review the diff once before integration.",
    }
  }
  function admission(s: Session) {
    return {
      session_id: s.id, backend: backendOf(s), status: "admitted", watch: watchCommand(s),
      run_deadline_ms: runDeadlineMs(s),
      fallback_reason: s.fallback_reason ?? null,
      fallback_notice: s.fallback_reason ? fallbackNotice(s) : null,
    }
  }
  const bridge = {
    async modelCheck(cwd: unknown, tierInput: unknown) {
      const dir = checkedWorktree(cwd)
      if (!isBridgeTier(tierInput)) throw new Error("Unknown bridge tier")
      const plan = resolvePolicy(tierInput)
      if (plan.kind === "leaf") return { primary: { backend: plan.target.executor, ...plan.target.selection, available: targetAvailable(plan.target) }, fallback: null }
      const [firstPi] = plan.pi
      const museModel = plan.pi.find(pin => pin.providerID === "muse-sdk")
      const goModel = plan.pi.find(pin => pin.providerID === "opencode-go")
      const devinModel = plan.pi.find(pin => pin.providerID === "devin")
      let museAvailable = false, museIssue: string | null = null
      if (museModel) {
        try {
          museAvailable = (await api(museModel).modelCheck(dir)).available
        } catch (e) { museIssue = String(e) }
        if (!museAvailable && !museIssue)
          museIssue = musePreflight().issue ?? "Muse subscription model unavailable; check Muse Code login"
      }
      let goAvailable = false, goIssue: string | null = null
      if (goModel) {
        try { goAvailable = (await api(goModel).modelCheck(dir)).available }
        catch (e) { goIssue = String(e) }
      }
      if (goModel && !goAvailable && !goIssue) goIssue = await diagnoseGoModel(goModel)
      let devinAvailable = false, devinIssue: string | null = null
      if (devinModel) {
        try { devinAvailable = (await api(devinModel).modelCheck(dir)).available }
        catch (e) { devinIssue = String(e) }
        if (!devinAvailable && !devinIssue)
          devinIssue = devinPreflight().issue ?? "Devin SWE-2 Flash is not authenticated in the Pi SDK"
      }
      const devinInfo = { available: devinAvailable, issue: devinIssue }
      const museInfo = museModel ? { available: museAvailable, issue: museIssue, version: piInstalled() ? museVersion() : null } : { available: false, issue: null, version: null }
      const goInfo = { available: goAvailable, issue: goIssue }
      const piLane = { backend: "pi", model: firstPi,
        available: firstPi.providerID === "muse-sdk" ? museInfo.available : firstPi.providerID === "devin" ? devinInfo.available : goInfo.available,
        issue: firstPi.providerID === "muse-sdk" ? museInfo.issue : firstPi.providerID === "devin" ? devinInfo.issue : goInfo.issue }
      const commandLane = { backend: "command-code", ...plan.command, available: command.available() }
      const codexLane = { backend: "codex", ...plan.codex, available: codex.available() }
      return {
        primary: plan.kind === "fx-fallback"
          ? { backend: "fx", ...plan.fx, available: targetAvailable({ executor: "fx", selection: plan.fx }) }
          : codexLane,
        fallback: plan.kind === "fx-fallback" ? codexLane : commandLane,
        command_code: commandLane,
        pi_fallback: piLane,
        muse: museModel ? { backend: "pi", model: museModel, available: museInfo.available, issue: museInfo.issue, version: museInfo.version } : undefined,
        opencode_go: goModel ? { backend: "pi", model: goModel, available: goInfo.available, issue: goInfo.issue } : null,
        devin: devinModel ? { backend: "pi", model: devinModel, available: devinInfo.available, issue: devinInfo.issue } : null,
      }
    },
    async start(cwd: unknown, title: unknown, tierInput: unknown, scopeInput: unknown, brief: unknown) {
      const dir = checkedWorktree(cwd, true)
      if (!isBridgeTier(tierInput)) throw new Error("Unknown bridge tier")
      if (git(dir, "status", "--porcelain", "--untracked-files=all")) throw new Error("Worker worktree must start clean")
      const task = required(brief, "brief", 32000)
      const plan = resolvePolicy(tierInput)
      if (plan.kind === "leaf") {
        if (activeWorktreeOwner(stateDir(dir), dir)) throw new Error("Worktree already has an active worker")
        const target: ProcessTarget = plan.target
        const available = targetAvailable(target)
        if (!available) throw new Error("Pinned leaf runtime/model unavailable. No fallback.")
        const s: Session = { id: "usrw_" + randomUUID(), cwd: dir, tier: tierInput,
          title: required(title, "title", 100), scope: scopeFor(scopeInput, tierInput, dir),
          task, lane_branch: currentBranch(dir), plan, execution: { kind: "transition", to: target }, attempts: 0 }
        const leaseDir = stateDir(dir)
        await settleHolder(leaseDir, dir)
        claimWorktree(leaseDir, dir, s.id)
        try {
          const owner = await ownerResolver?.(leaseDir)
          if (owner) s.owner = owner
          save(s)
        } catch (error) {
          releaseWorktree(leaseDir, dir, s.id)
          throw error
        }
        activateProcess(s, target, launch(s, target, prompt(s)))
        s.attempts = 1
        save(s)
        return admission(s)
      }
      const codexTarget: ProcessTarget = { executor: "codex", selection: plan.codex }
      const fxTarget: ProcessTarget | undefined = plan.kind === "fx-fallback" ? { executor: "fx", selection: plan.fx } : undefined
      const first: ProcessTarget = fxTarget ?? codexTarget
      const s: Session = { id: "usrw_" + randomUUID(), cwd: dir, tier: tierInput,
        title: required(title, "title", 100), scope: scopeFor(scopeInput, tierInput, dir),
        task, lane_branch: currentBranch(dir), plan, execution: { kind: "transition", to: first }, attempts: 0 }
      const leaseDir = stateDir(dir)
      await settleHolder(leaseDir, dir)
      claimWorktree(leaseDir, dir, s.id)
      try {
        const owner = await ownerResolver?.(leaseDir)
        if (owner) s.owner = owner
        save(s)
      } catch (error) {
        releaseWorktree(leaseDir, dir, s.id)
        throw error
      }
      if (targetAvailable(first)) {
        activateProcess(s, first, launch(s, first, prompt(s)))
        s.attempts = 1
        save(s)
        return admission(s)
      }
      s.fallback_reason = fxTarget
        ? "Pinned FX runtime/provider unavailable; continued on the next approved provider."
        : "Codex subscription unavailable; continued on the next approved provider."
      const commandTarget: ProcessTarget = { executor: "command-code", selection: plan.command }
      for (const target of fxTarget ? [codexTarget, commandTarget] : [commandTarget]) {
        if (!targetAvailable(target)) continue
        transition(s, target)
        save(s)
        // Commit an admission transition before spawning. If the launch is ambiguous, retain the lease.
        activateProcess(s, target, launch(s, target, prompt(s)))
        s.attempts = 1
        save(s)
        return admission(s)
      }
      await fallbackToPi(s, plan, fxTarget
        ? "FX, Codex and Command Code are unavailable; continued on an approved Pi provider."
        : "Command Code CLI is unavailable; continued on an approved Pi provider.")
      return admission(s)
    },
    async status(cwd: unknown, id: unknown) {
      const current = load(cwd, id)
      const alive = current.pending_steer && callerAlive(current.pending_steer.caller_pid)
      const detached = alive && current.pending_steer?.phase === "relaunching" && !existsSync(pathFor(current.cwd, current.id) + ".lock")
      if (alive && !detached) return statusResponse(await inspectSession(current, readStateDir(current.cwd), inspection))
      const advanced = await advance(cwd, id, !!detached)
      return statusResponse(await inspectSession(advanced.session, readStateDir(advanced.session.cwd), inspection, advanced.known))
    },
    async resume(cwd: unknown, id: unknown, feedback: unknown, extension?: { extend_attempts: number; extension_reason: string }) {
      return runResume(cwd, id, feedback, undefined, extension)
    },
    async cancel(cwd: unknown, id: unknown) {
      return runCancel(cwd, id, false)
    },
    async steer(cwd: unknown, id: unknown, note: unknown) {
      return runSteer(cwd, id, note)
    },
  }
  async function runResume(cwd: unknown, id: unknown, feedback: unknown, admitEffect?: OwnerEffectAdmit, extension?: { extend_attempts: number; extension_reason: string }) {
    return withSessionLock(cwd, id, async (s) => {
      const correction = required(feedback, "feedback", 32000)
      const added = extension?.extend_attempts ?? 0
      if (extension && (added !== 1 && added !== 2)) throw new Error("extend_attempts must be 1 or 2")
      const reason = extension ? required(extension.extension_reason, "extension_reason", 2000) : undefined
      const total = (s.attempt_extensions ?? []).reduce((sum, entry) => sum + entry.added, 0)
      if (total + added > 2) throw new Error("Attempt extension limit reached")
      const continuation = s.execution.kind === "process" && s.execution.executor === "command-code" &&
        command.status(s.execution.run).state === "turn_limit"
      if (continuation && (s.continuations ?? 0) >= TURN_LIMIT_CONTINUATIONS)
        throw new Error("Turn-limit continuation limit reached")
      if (!laneHead(s).head_on_lane ||
        outside(changes(s.cwd, s.scope.base_revision), s.scope.writable_paths).length)
        throw new Error("Cannot resume changed HEAD or out-of-scope work: " + describeDrift(s))
      if (s.execution.kind === "transition" || s.fallback_blocked)
        throw new Error("Worker transition interrupted; inspect session before resuming")
      if (!continuation && s.attempts >= s.scope.attempt_limit + total + added) throw new Error("Task attempt limit reached")
      if (s.execution.kind === "pi") {
        const { selection, session_id: sessionId } = s.execution
        const dispatch = await api(selection).preflightResume(s.cwd, sessionId, "Same-scope correction only: " + correction)
        await admitEffect?.()
        ensureWorktree(stateDir(s.cwd), s.cwd, s.id)
        if (reason) s.attempt_extensions = [...s.attempt_extensions ?? [], { added, reason, at: new Date().toISOString() }]
        s.attempts++
        transition(s, { executor: "pi", selection }, true)
        save(s)
        await dispatch()
        activatePi(s, selection, sessionId)
        save(s)
      } else {
        const execution = s.execution
        const previous = observe(execution)
        if (previous.state === "running" || previous.state === "unknown_or_interrupted" || previous.state === "interrupted")
          throw new Error("Command Code run not known complete")
        if (!previous.result?.sessionId) throw new Error("No resumable Command Code session")
        runnerFor(execution.executor)
        if (execution.executor === "fx" && !fx?.available(execution.selection)) throw new Error("Pinned FX runtime unavailable; cannot resume")
        await admitEffect?.()
        ensureWorktree(stateDir(s.cwd), s.cwd, s.id)
        if (reason) s.attempt_extensions = [...s.attempt_extensions ?? [], { added, reason, at: new Date().toISOString() }]
        if (continuation) s.continuations = (s.continuations ?? 0) + 1
        else s.attempts++
        const target: ProcessTarget = processTarget(execution)
        transition(s, target)
        s.cancel_requested = false
        save(s)
        const text = prompt(s) + (continuation ? "\nCONTINUE THE SAME TASK FROM WHERE THE TURN LIMIT STOPPED IT: " :
          "\nSAME-SCOPE CORRECTION ONLY: ") + correction
        activateProcess(s, target, launch(s, target, text, previous.result.sessionId))
        save(s)
      }
      return { session_id: s.id, backend: backendOf(s), status: "admitted", watch: watchCommand(s) }
    })
  }
  async function runCancel(cwd: unknown, id: unknown, ownerMode: boolean, admitEffect?: OwnerEffectAdmit) {
    return withSessionLock(cwd, id, async (s) => {
      const observation = await observeExecution(s, stateDir(s.cwd), inspection)
      const state = settledState(s, observation, untouched(s)).state
      if (!ownerMode && state === "blocked_partial_work") {
        s.cancel_requested = true
        save(s)
        const leaseDir = stateDir(s.cwd)
        const released = activeWorktreeOwner(leaseDir, s.cwd) === s.id
          ? releaseWorktree(leaseDir, s.cwd, s.id)
          : false
        return { session_id: s.id, interrupted: false, released,
          note: "Worker already ended at a provider usage limit with partial edits; the worktree lease is released and the edits are left untouched. Preserve the work before dispatching again." }
      }
      if (ownerMode && state !== "running" && state !== "queued") {
        throw new OwnerPrecheckError("not-running", "Worker run is not running (state " + state + ")")
      }
      let interrupted = false
      if (s.execution.kind === "pi") {
        await admitEffect?.()
        interrupted = (await api(s.execution.selection).cancel(s.cwd, s.execution.session_id)).interrupted
      } else {
        const run = processRun(s)
        const executor = executorOf(s)
        if (run && executor !== "pi") {
          const runner = runnerFor(executor)
          await admitEffect?.()
          s.cancel_requested = true
          save(s)
          interrupted = runner.cancel(run, s.cwd)
          if (!interrupted) { s.cancel_requested = false; save(s) }
        } else if (ownerMode) {
          throw new OwnerPrecheckError("not-running", "Worker run is not running")
        }
      }
      return { session_id: s.id, interrupted,
        note: "A run is signaled only while its recorded PID identity still matches; an unverified or reused PID is never signaled." }
    })
  }
  async function runSteer(cwd: unknown, id: unknown, note: unknown, admitEffect?: OwnerEffectAdmit) {
    return steerDeadline(() => withSessionLock(cwd, id, async (s) => {
      const steering = required(note, "note", 32000)
      if (s.pending_steer) throw new Error("A steer is already pending for this session")
      if (s.execution.kind === "transition" || s.fallback_blocked)
        throw new Error("Worker transition interrupted; inspect session before steering")
      if ((s.steers ?? 0) >= STEER_LIMIT) throw new Error("Steer limit reached for this session")
      if (!laneHead(s).head_on_lane ||
        outside(changes(s.cwd, s.scope.base_revision), s.scope.writable_paths).length)
        throw new Error("Cannot steer changed HEAD or out-of-scope work: " + describeDrift(s))
      if (s.execution.kind === "pi") {
        const sessionId = s.execution.session_id
        const worker = api(s.execution.selection)
        const observed = await beforeDeadline(worker.status(s.cwd, sessionId))
        const observedState = typeof observed.state === "string" ? observed.state : "unknown"
        if (observedState !== "running" && observedState !== "queued")
          throw new Error("Pi worker is not running (state " + observedState + "); use worker_resume for a finished session")
        await beforeDeadline(admitEffect?.())
        ensureWorktree(stateDir(s.cwd), s.cwd, s.id)
        s.pending_steer = { note: steering, requested_at: new Date().toISOString(), phase: "signaling", caller_pid: process.pid, previous_output: null }
        save(s)
        let receipt: Awaited<ReturnType<typeof worker.steer>>
        try {
          receipt = await beforeDeadline(worker.steer(s.cwd, sessionId, steering))
          if (receipt.receipt.accepted === false) return { session_id: s.id, backend: backendOf(s), status: "pending", interrupted: false,
            steers: s.steers ?? 0, steer_limit: STEER_LIMIT, receipt }
          s.steers = (s.steers ?? 0) + 1
          finishSteer(s, "completed")
        } catch (error) {
          if (error instanceof SteerDeadlineError) return { session_id: s.id, backend: backendOf(s), status: "pending", interrupted: false,
            steers: s.steers ?? 0, steer_limit: STEER_LIMIT }
          finishSteer(s, "failed"); throw error
        }
        return { session_id: s.id, backend: backendOf(s), status: "steered", interrupted: false,
          steers: s.steers, steer_limit: STEER_LIMIT, receipt }
      }
      const execution = s.execution
      const { executor: backend, run } = execution
      const runner = runnerFor(backend)
      const previous = observe(execution)
      if (previous.state !== "running")
        throw new Error("Command Code run is not running (state " + previous.state +
          "); use worker_resume for a finished session")
      const sessionId = execution.executor === "fx" ? fx?.session(run, execution.selection) : backend === "command-code" ? commandSession(run) : codex.session(run)
      if (!sessionId)
        throw new Error(execution.executor === "fx" ? "FX native session identity is not bound; steering is unavailable until it is recorded" : "Command Code session identity is not recorded; cannot restart after steering")
      await beforeDeadline(admitEffect?.())
      ensureWorktree(stateDir(s.cwd), s.cwd, s.id)
      s.pending_steer = { note: steering, requested_at: new Date().toISOString(), phase: "signaling", caller_pid: process.pid, previous_output: run.output }
      save(s)
      let plannedSaved = false, counted = false, planned: PlannedRun | undefined
      try {
      if (!runner.cancel(run, s.cwd))
        throw new Error("Command Code run is not owned by this bridge process; refusing to signal an unverified PID")
      let state = observe(execution).state
      const deadline = Date.now() + TERMINATION_WAIT_MS
      while (state === "running" && Date.now() < deadline) {
        await beforeDeadline(new Promise((resolve) => setTimeout(resolve, Math.min(100, deadlineTimeout(100)))))
        state = observe(execution).state
      }
      if (state === "running")
        throw new Error("Command Code process did not terminate after interruption; inspect it before retrying")
      s.pending_steer.phase = "relaunching"
      const target: ProcessTarget = processTarget(execution)
      const output = join(stateDir(s.cwd), randomUUID() + (target.executor === "fx" ? ".fx.json" : ".ndjson"))
      planned = { output, errors: output + ".stderr", started_at: new Date().toISOString() }
      s.pending_steer.planned_run = planned
      save(s)
      plannedSaved = true
      activateProcess(s, target, launch(s, target,
        prompt(s) + "\nPARENT STEERING (same scope and write boundaries): " + steering, sessionId, planned))
      save(s)
      s.steers = (s.steers ?? 0) + 1
      counted = true
      finishSteer(s, "completed")
      return { session_id: s.id, backend: backendOf(s), status: "steered", interrupted: true,
        steers: s.steers, steer_limit: STEER_LIMIT }
      } catch (error) {
        if (plannedSaved && s.pending_steer?.phase === "relaunching" && (error instanceof SteerDeadlineError || (error as NodeJS.ErrnoException).code === "ETIMEDOUT"))
          return { session_id: s.id, backend: backendOf(s), status: "steering", interrupted: true,
            steers: s.steers ?? 0, steer_limit: STEER_LIMIT }
        const replacement = plannedSaved && planned ?
          (s.execution.kind === "process" && s.execution.run.output === planned.output ? s.execution.run : recoveredRun(planned)) : null
        if (replacement && s.execution.kind === "process") {
          activateProcess(s, processTarget(s.execution), replacement)
          if (!counted) s.steers = (s.steers ?? 0) + 1
          steerCleanup(() => finishSteer(s, "completed"))
          return { session_id: s.id, backend: backendOf(s), status: "steered", interrupted: true,
            steers: s.steers, steer_limit: STEER_LIMIT }
        }
        steerCleanup(() => finishSteer(s, "failed")); throw error
      }
    }))
  }
  ownerOpsRegistry.set(bridge, {
    inspection,
    setOwnerResolver(resolver) {
      ownerResolver = resolver
    },
    resumeForOwner(cwd, id, feedback, admitEffect) {
      return runResume(cwd, id, feedback, admitEffect)
    },
    steerForOwner(cwd, id, note, admitEffect) {
      return runSteer(cwd, id, note, admitEffect)
    },
    async cancelForOwner(cwd, id, admitEffect) {
      const result = await runCancel(cwd, id, true, admitEffect)
      return { interrupted: result.interrupted }
    },
  })
  return bridge
}
