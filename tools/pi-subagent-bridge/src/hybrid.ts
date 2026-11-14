import { randomUUID } from "node:crypto"
import { accessSync, constants, mkdirSync, readFileSync, renameSync, rmdirSync, rmSync, writeFileSync } from "node:fs"
import { dirname, join, resolve } from "node:path"
import { PreAdmissionError, checkedWorktree, makeWorkerBridge, type OpenCodePort } from "./bridge.ts"
import { cancelCommand, commandResult, commandSession, startCommand, type CommandRun } from "./command.ts"
import { codexAvailable, codexResult, codexSession, cancelCodex, startCodex } from "./codex.ts"
import { antigravityAvailable, antigravityResult, antigravitySession, cancelAntigravity, startAntigravity } from "./antigravity.ts"
import { activeWorktreeOwner, claimWorktree, ensureWorktree, releaseWorktree } from "./worktree-lease.ts"

import { isTier as isBridgeTier, type Tier } from "./tier-policy.ts"
import { musePreflight } from "./muse-subscription.ts"
import { changes, git, outside, readStateDir, stateDir } from "./git.ts"
import {
  fallbackNotice, fallbackSource, inspectSession, observeExecution, runnerStatus, settledState,
  type Inspection, type InspectionDeps, type Known,
} from "./inspect.ts"
import {
  STEER_LIMIT, TURN_LIMIT_CONTINUATIONS, activatePi, activateProcess, backendOf, decodeSession, encodeSession,
  executorOf, isSessionId, piFallbackPlan, processRun, transition, type PiFallbackPlan, type ProcessExecution,
  type ProcessTarget, type Session,
} from "./session.ts"
import type { Access } from "./launch.ts"
import { ROOT_PLANS, type CliExecutor, type CliPin, type PiSelection, type RootPlan } from "./policy.ts"
import { parseScope, requiredText as required, type Scope } from "./scope.ts"
export type { Tier } from "./tier-policy.ts"
export type RoutedTier = Tier
export type { Scope } from "./scope.ts"
const TERMINATION_WAIT_MS = 2000

const isTier = isBridgeTier
function scopeFor(value: unknown, tier: RoutedTier, cwd: string, checkHead = true): Scope {
  return parseScope(value, tier, checkHead ? git(cwd, "rev-parse", "HEAD") : undefined)
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

async function withSessionLock<T>(cwd: unknown, id: unknown, work: (session: Session) => Promise<T>): Promise<T> {
  const directory = checkedWorktree(cwd)
  const sessionID = required(id, "session_id", 64)
  const lock = pathFor(directory, sessionID) + ".lock"
  try {
    mkdirSync(lock, { mode: 0o700 })
  } catch (error) {
    if (error instanceof Error && "code" in error && error.code === "EEXIST") {
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
    "Do not commit, switch branches, merge, push, add dependencies, or edit outside writable paths.",
    "Stop if blocked or if the requirements demand more scope. Do not broaden the task.",
    "Return a PROOF RECORD instead of a summary: changed paths; exact commands, exit codes and decisive output;",
    "file:line evidence for research; and explicit unverified cases and blockers. Never invent a passing check.",
    "End with exactly one final line: `ACCEPTANCE: met` only when every required acceptance command ran and passed, otherwise `ACCEPTANCE: not met`.",
  ].join("\n")
}
function untouched(s: Session): boolean {
  return git(s.cwd, "rev-parse", "HEAD") === s.scope.base_revision &&
    changes(s.cwd, s.scope.base_revision).length === 0
}
export function makeHybridBridge(api: OpenCodePort, command = {
  start: startCommand, status: commandResult, cancel: cancelCommand, available: cmdAvailable,
}, codex = { start: startCodex, status: codexResult, cancel: cancelCodex, available: codexAvailable, session: codexSession },
  antigravity = { start: startAntigravity, status: antigravityResult, cancel: cancelAntigravity, available: antigravityAvailable, session: antigravitySession },
  resolvePolicy: (tier: Tier) => RootPlan = tier => ROOT_PLANS[tier]) {
  const inspection: InspectionDeps = { api, command, codex, antigravity }
  function runnerFor(executor: CliExecutor) {
    switch (executor) {
      case "antigravity": return antigravity
      case "codex": return codex
      case "command-code": return command
    }
  }
  function observe(execution: ProcessExecution) {
    return runnerStatus(inspection, execution)
  }
  function accessFor(s: Session): Access {
    return s.tier === "scout" ? { kind: "read-only" } : { kind: "write" }
  }
  function launch(s: Session, target: ProcessTarget, text: string, resume?: string): CommandRun {
    const request = { directory: s.cwd, logDirectory: stateDir(s.cwd), prompt: text, selection: target.selection, resume }
    switch (target.executor) {
      case "antigravity": return antigravity.start({ ...request, access: { kind: "write" } })
      case "codex": return codex.start({ ...request, access: accessFor(s) })
      case "command-code": return command.start({ ...request, access: accessFor(s) })
    }
  }
  function fallbackToCommand(s: Session, pin: CliPin, reason: string, detail?: unknown): Session {
    if (!command.available()) throw new Error(reason + "; Command Code cmd unavailable")
    if (!untouched(s)) throw new Error("Fallback forbidden after partial edits; inspect the worktree")
    ensureWorktree(stateDir(s.cwd), s.cwd, s.id)
    const target: ProcessTarget = { executor: "command-code", selection: pin }
    transition(s, target)
    s.fallback_reason = reason
    if (detail !== undefined) s.fallback_detail = (typeof detail === "string" ? detail : JSON.stringify(detail)).slice(0, 2000)
    s.attempts = 1
    save(s)
    activateProcess(s, target, launch(s, target, prompt(s)))
    save(s)
    return s
  }
  async function availablePi(plan: PiFallbackPlan, from: number, cwd: string): Promise<{ selection: PiSelection; next: number } | null> {
    for (let index = from; index < plan.pi.length; index++) {
      const candidate = plan.pi[index]
      if (candidate.providerID === "muse-sdk") process.env.PI_MUSE_SDK_CONTRIBUTOR = "on"
      try {
        if ((await makeWorkerBridge(api, candidate).modelCheck(cwd)).available) return { selection: candidate, next: index + 1 }
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
      const worker = makeWorkerBridge(api, selection)
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
  async function advance(cwd: unknown, id: unknown): Promise<{ session: Session; known?: Known }> {
    return withSessionLock(cwd, id, async (s) => {
      const observation = await observeExecution(s, stateDir(s.cwd), inspection)
      const source = fallbackSource(s, observation)
      const clean = source === null || untouched(s)
      let state = settledState(s, observation, clean).state
      let known: Known | undefined = { observation }
      if (source?.kind === "pi" && clean) {
        fallbackToCommand(s, source.plan.command, "Primary Pi runner unavailable during execution (provider usage limit); no edits existed, so the task continued on Command Code.", observation.error)
        state = "running"
        known = undefined
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
      if (["succeeded", "failed", "turn_limit", "cancelled", "canceled", "interrupted"].includes(state)) {
        const directory = stateDir(s.cwd)
        if (activeWorktreeOwner(directory, s.cwd) === s.id)
          releaseWorktree(directory, s.cwd, s.id)
      }
      return { session: s, ...(known ? { known } : {}) }
    })
  }
  function statusResponse(i: Inspection) {
    const s = i.session
    if (i.worktree.kind === "unreadable") throw new Error(i.worktree.reason)
    const { head, changed_paths, out_of_scope_paths } = i.worktree
    const head_unchanged = head === s.scope.base_revision
    const last_assistant_text = i.observation.final_text?.slice(-5000) ?? null
    const state = i.state === "succeeded" && i.acceptance_claim !== "met" ? "incomplete" : i.state
    return {
      session_id: s.id, backend: backendOf(s), tier: s.tier, model: i.route.model, effort: i.route.effort,
      state, last_assistant_text, error: i.observation.error, usage: i.observation.usage,
      changed_paths, out_of_scope_paths, head_unchanged,
      acceptance_claim: i.acceptance_claim,
      acceptance_blocked: !head_unchanged || out_of_scope_paths.length > 0 || i.acceptance_claim !== "met",
      continuations: s.continuations ?? 0, continuation_limit: TURN_LIMIT_CONTINUATIONS,
      steers: s.steers ?? 0, steer_limit: STEER_LIMIT,
      fallback_reason: s.fallback_reason ?? null,
      fallback_notice: i.notice,
      fallback_detail: s.fallback_detail ?? null,
      note: "Proof must be checked independently. Review the diff once before integration.",
    }
  }
  function admission(s: Session) {
    return {
      session_id: s.id, backend: backendOf(s), status: "admitted", watch: watchCommand(s),
      fallback_reason: s.fallback_reason ?? null,
      fallback_notice: s.fallback_reason ? fallbackNotice(s) : null,
    }
  }
  return {
    async modelCheck(cwd: unknown, tierInput: unknown) {
      const dir = checkedWorktree(cwd)
      if (!isTier(tierInput)) throw new Error("Unknown Pi tier")
      const plan = resolvePolicy(tierInput)
      if (plan.kind === "exclusive") {
        return { primary: { backend: "antigravity", ...plan.target, available: antigravity.available(plan.target) },
          fallback: null, command_code: null, pi_fallback: null, muse: undefined, opencode_go: null }
      }
      const [firstPi] = plan.pi
      const museModel = plan.pi.find(pin => pin.providerID === "muse-sdk")
      const goModel = plan.pi.find(pin => pin.providerID === "opencode-go")
      let museAvailable = false, museIssue: string | null = null
      if (museModel) {
        try {
          museAvailable = (await makeWorkerBridge(api, museModel).modelCheck(dir)).available
        } catch (e) { museIssue = String(e) }
        if (!museAvailable && !museIssue)
          museIssue = musePreflight().issue ?? "Muse subscription model unavailable; check Muse Code login"
      }
      let goAvailable = false, goIssue: string | null = null
      if (goModel) {
        try { goAvailable = (await makeWorkerBridge(api, goModel).modelCheck(dir)).available }
        catch (e) { goIssue = String(e) }
      }
      if (goModel && !goAvailable && !goIssue) {
        try {
          const { ensureOpenCodeApiKey } = await import("./opencode-auth.ts")
          ensureOpenCodeApiKey()
          const { ModelRuntime } = await import("@earendil-works/pi-coding-agent")
          const runtime = await ModelRuntime.create()
          const model = goModel
          if (!runtime.getModel(model.providerID, model.id))
            goIssue = `Pinned OpenCode Go model ${model.providerID}/${model.id} is not in the Pi SDK catalog`
          else if (!runtime.hasConfiguredAuth(model.providerID))
            goIssue = `No configured auth for ${model.providerID} in Pi SDK; sign in with opencode2 or set OPENCODE_API_KEY`
        } catch { /* keep issue null if diagnosis unavailable */ }
      }
      const museInfo = museModel ? { available: museAvailable, issue: museIssue } : { available: false, issue: null }
      const goInfo = { available: goAvailable, issue: goIssue }
      const piLane = { backend: "pi", model: firstPi,
        available: firstPi.providerID === "muse-sdk" ? museInfo.available : goInfo.available,
        issue: firstPi.providerID === "muse-sdk" ? museInfo.issue : goInfo.issue }
      const commandLane = { backend: "command-code", ...plan.command, available: command.available() }
      return {
        primary: { backend: "codex", ...plan.codex, available: codex.available() },
        fallback: commandLane,
        command_code: commandLane,
        pi_fallback: piLane,
        muse: museModel ? { backend: "pi", model: museModel, available: museInfo.available, issue: museInfo.issue } : undefined,
        opencode_go: goModel ? { backend: "pi", model: goModel, available: goInfo.available, issue: goInfo.issue } : null,
      }
    },
    async start(cwd: unknown, title: unknown, tierInput: unknown, scopeInput: unknown, brief: unknown) {
      const dir = checkedWorktree(cwd, true)
      if (!isTier(tierInput)) throw new Error("Unknown Pi tier")
      if (git(dir, "status", "--porcelain", "--untracked-files=all")) throw new Error("Worker worktree must start clean")
      const task = required(brief, "brief", 32000)
      const plan = resolvePolicy(tierInput)
      if (plan.kind === "exclusive") {
        if (activeWorktreeOwner(stateDir(dir), dir)) throw new Error("Worktree already has an active worker")
        if (!antigravity.available(plan.target))
          throw new Error("Pinned Antigravity model " + plan.target.model + " unavailable; run agy models and check account access. No fallback.")
        const target: ProcessTarget = { executor: "antigravity", selection: plan.target }
        const s: Session = { id: "usrw_" + randomUUID(), cwd: dir, tier: tierInput,
          title: required(title, "title", 100), scope: scopeFor(scopeInput, tierInput, dir),
          task, plan, execution: { kind: "transition", to: target }, attempts: 0 }
        const leaseDir = stateDir(dir)
        claimWorktree(leaseDir, dir, s.id)
        try { save(s) } catch (error) {
          releaseWorktree(leaseDir, dir, s.id)
          throw error
        }
        activateProcess(s, target, launch(s, target, prompt(s)))
        s.attempts = 1
        save(s)
        return admission(s)
      }
      const codexTarget: ProcessTarget = { executor: "codex", selection: plan.codex }
      const s: Session = { id: "usrw_" + randomUUID(), cwd: dir, tier: tierInput,
        title: required(title, "title", 100), scope: scopeFor(scopeInput, tierInput, dir),
        task, plan, execution: { kind: "transition", to: codexTarget }, attempts: 0 }
      const leaseDir = stateDir(dir)
      claimWorktree(leaseDir, dir, s.id)
      try { save(s) } catch (error) {
        releaseWorktree(leaseDir, dir, s.id)
        throw error
      }
      if (codex.available()) {
        activateProcess(s, codexTarget, launch(s, codexTarget, prompt(s)))
        s.attempts = 1
        save(s)
        return admission(s)
      }
      s.fallback_reason = "Codex subscription unavailable; continued on the next approved provider."
      if (command.available()) {
        const commandTarget: ProcessTarget = { executor: "command-code", selection: plan.command }
        transition(s, commandTarget)
        save(s)
        // Commit an admission transition before spawning. If the launch is ambiguous, retain the lease.
        activateProcess(s, commandTarget, launch(s, commandTarget, prompt(s)))
        s.attempts = 1
        save(s)
        return admission(s)
      }
      await fallbackToPi(s, plan, "Command Code CLI is unavailable; continued on an approved Pi provider.")
      return admission(s)
    },
    async status(cwd: unknown, id: unknown) {
      const advanced = await advance(cwd, id)
      return statusResponse(await inspectSession(advanced.session, readStateDir(advanced.session.cwd), inspection, advanced.known))
    },
    async resume(cwd: unknown, id: unknown, feedback: unknown) {
      return withSessionLock(cwd, id, async (s) => {
      const correction = required(feedback, "feedback", 32000)
      const continuation = s.execution.kind === "process" && s.execution.executor === "command-code" &&
        command.status(s.execution.run).state === "turn_limit"
      if (continuation && (s.continuations ?? 0) >= TURN_LIMIT_CONTINUATIONS)
        throw new Error("Turn-limit continuation limit reached")
      if (git(s.cwd, "rev-parse", "HEAD") !== s.scope.base_revision ||
        outside(changes(s.cwd, s.scope.base_revision), s.scope.writable_paths).length)
        throw new Error("Cannot resume changed HEAD or out-of-scope work")
      if (s.execution.kind === "transition" || s.fallback_blocked)
        throw new Error("Worker transition interrupted; inspect session before resuming")
      if (!continuation && s.attempts >= s.scope.attempt_limit) throw new Error("Task attempt limit reached")
      if (s.execution.kind === "pi") {
        const { selection, session_id: sessionId } = s.execution
        ensureWorktree(stateDir(s.cwd), s.cwd, s.id)
        s.attempts++
        transition(s, { executor: "pi", selection }, true)
        save(s)
        await makeWorkerBridge(api, selection).resume(s.cwd, sessionId, "Same-scope correction only: " + correction)
        activatePi(s, selection, sessionId)
        save(s)
      } else {
        const execution = s.execution
        const previous = observe(execution)
        if (previous.state === "running" || previous.state === "unknown_or_interrupted" || previous.state === "interrupted")
          throw new Error("Command Code run not known complete")
        if (!previous.result?.sessionId) throw new Error("No resumable Command Code session")
        ensureWorktree(stateDir(s.cwd), s.cwd, s.id)
        if (continuation) s.continuations = (s.continuations ?? 0) + 1
        else s.attempts++
        const target: ProcessTarget = { executor: execution.executor, selection: execution.selection }
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
    },
    async cancel(cwd: unknown, id: unknown) {
      return withSessionLock(cwd, id, async (s) => {
      let interrupted = false
      if (s.execution.kind === "pi") {
        interrupted = (await makeWorkerBridge(api, s.execution.selection).cancel(s.cwd, s.execution.session_id)).interrupted
      } else {
        const run = processRun(s)
        const executor = executorOf(s)
        if (run && executor !== "pi") {
          s.cancel_requested = true
          save(s)
          interrupted = runnerFor(executor).cancel(run)
          if (!interrupted) { s.cancel_requested = false; save(s) }
        }
      }
      return { session_id: s.id, interrupted,
        note: "Never signal a Command Code PID left by an earlier MCP process; it may have been reused." }
      })
    },
    async steer(cwd: unknown, id: unknown, note: unknown) {
      return withSessionLock(cwd, id, async (s) => {
      const steering = required(note, "note", 32000)
      if (s.execution.kind === "transition" || s.fallback_blocked)
        throw new Error("Worker transition interrupted; inspect session before steering")
      if ((s.steers ?? 0) >= STEER_LIMIT) throw new Error("Steer limit reached for this session")
      if (git(s.cwd, "rev-parse", "HEAD") !== s.scope.base_revision ||
        outside(changes(s.cwd, s.scope.base_revision), s.scope.writable_paths).length)
        throw new Error("Cannot steer changed HEAD or out-of-scope work")
      if (s.execution.kind === "pi") {
        const sessionId = s.execution.session_id
        const worker = makeWorkerBridge(api, s.execution.selection)
        const observed = await worker.status(s.cwd, sessionId)
        const observedState = typeof observed.state === "string" ? observed.state : "unknown"
        if (observedState !== "running" && observedState !== "queued")
          throw new Error("Pi worker is not running (state " + observedState + "); use worker_resume for a finished session")
        ensureWorktree(stateDir(s.cwd), s.cwd, s.id)
        const receipt = await worker.steer(s.cwd, sessionId, steering)
        s.steers = (s.steers ?? 0) + 1
        save(s)
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
      const sessionId = backend === "antigravity" ? antigravity.session(run) : backend === "codex" ? codex.session(run) : commandSession(run)
      if (!sessionId)
        throw new Error("Command Code session identity is not recorded; cannot restart after steering")
      ensureWorktree(stateDir(s.cwd), s.cwd, s.id)
      if (!runner.cancel(run))
        throw new Error("Command Code run is not owned by this bridge process; refusing to signal an unverified PID")
      let state = observe(execution).state
      const deadline = Date.now() + TERMINATION_WAIT_MS
      while (state === "running" && Date.now() < deadline) {
        await new Promise((resolve) => setTimeout(resolve, 100))
        state = observe(execution).state
      }
      if (state === "running")
        throw new Error("Command Code process did not terminate after interruption; inspect it before retrying")
      s.steers = (s.steers ?? 0) + 1
      const target: ProcessTarget = { executor: backend, selection: execution.selection }
      transition(s, target)
      save(s)
      activateProcess(s, target, launch(s, target,
        prompt(s) + "\nPARENT STEERING (same scope and write boundaries): " + steering, sessionId))
      save(s)
      return { session_id: s.id, backend: backendOf(s), status: "steered", interrupted: true,
        steers: s.steers, steer_limit: STEER_LIMIT }
      })
    },
  }
}
