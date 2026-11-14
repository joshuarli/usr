import { randomUUID } from "node:crypto"
import { accessSync, constants, mkdirSync, readFileSync, renameSync, rmdirSync, rmSync, writeFileSync } from "node:fs"
import { dirname, join, resolve } from "node:path"
import { PreAdmissionError, checkedWorktree, makeWorkerBridge, type OpenCodePort, type ModelRef } from "./bridge.ts"
import { cancelCommand, commandResult, commandSession, startCommand, type CommandRun, type Effort } from "./command.ts"
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
  STEER_LIMIT, TURN_LIMIT_CONTINUATIONS, activatePi, activateProcess, antigravityPin, backendOf, commandPin,
  decodeSession, encodeSession, isSessionId, primaryFor, processRun, transition, type Session,
} from "./session.ts"
import { rootPlan, type Executor, type RootPlan } from "./policy.ts"
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
function fallbackModelFor(s: Session): string { return commandPin(s).model }
function fallbackEffortFor(s: Session): Effort { return commandPin(s).effort }
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
    ...(s.tier === "scout" && (backendOf(s) === "codex" || backendOf(s) === "codex-transition") ? ["Use bridge_scout tools to inspect the actual files. Never claim a shell command ran; report only tool output you observed."] : []),
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
  resolvePolicy: (tier: Tier) => RootPlan = rootPlan) {
  const inspection: InspectionDeps = { api, command, codex, antigravity }
  function runnerFor(executor: Exclude<Executor, "pi">) {
    switch (executor) {
      case "antigravity": return antigravity
      case "codex": return codex
      case "command-code": return command
    }
  }
  function observe(s: Session, executor: Exclude<Executor, "pi">, run: CommandRun) {
    return runnerStatus(inspection, s, executor, run)
  }
  function launch(s: Session, executor: Exclude<Executor, "pi">, text: string, resume?: string): CommandRun {
    const dir = stateDir(s.cwd)
    switch (executor) {
      case "antigravity": {
        const pin = antigravityPin(s)
        return antigravity.start(s.cwd, dir, text, pin.effort, false, resume, pin.model, pin)
      }
      case "codex":
        if (!s.codex_model || !s.codex_effort) throw new Error("Missing admitted Codex pin; manual reconciliation required")
        return codex.start(s.cwd, dir, text, s.codex_effort, s.tier === "scout", resume, s.codex_model, !!s.scope.network, { model: s.codex_model, effort: s.codex_effort })
      case "command-code":
        return command.start(s.cwd, dir, text, fallbackEffortFor(s), s.tier === "scout", resume, fallbackModelFor(s), commandPin(s))
    }
  }
  function fallbackToCommand(s: Session, reason: string, detail?: unknown): Session {
    if (!command.available()) throw new Error(reason + "; Command Code cmd unavailable")
    if (!untouched(s)) throw new Error("Fallback forbidden after partial edits; inspect the worktree")
    ensureWorktree(stateDir(s.cwd), s.cwd, s.id)
    const dir = stateDir(s.cwd)
    const pin = commandPin(s)
    transition(s, "command-code")
    s.fallback_reason = reason
    if (detail !== undefined) s.fallback_detail = (typeof detail === "string" ? detail : JSON.stringify(detail)).slice(0, 2000)
    s.attempts = 1
    save(s)
    activateProcess(s, "command-code", command.start(s.cwd, dir, prompt(s), pin.effort, s.tier === "scout", undefined, pin.model, pin))
    save(s)
    return s
  }
  async function fallbackToPi(s: Session, reason: string, detail?: unknown): Promise<Session> {
    if (!untouched(s)) throw new Error("Fallback forbidden after partial edits; inspect the worktree")
    // An in-flight, interrupted, or ambiguous Command Code process must never be duplicated.
    const previousRun = processRun(s)
    if (previousRun && command.status(previousRun).state !== "failed")
      throw new Error("Command Code is not known terminal; OpenCode Go fallback refused")
    ensureWorktree(stateDir(s.cwd), s.cwd, s.id)
    if (!s.pi_candidates && s.remaining_pi?.length)
      throw new Error("Legacy Pi fallback has no exact model snapshot; manual reconciliation required")
    if (s.pi_candidates) {
      let selected: ModelRef | undefined
      while (s.pi_candidates.length) {
        const candidate = s.pi_candidates.shift()!
        if (candidate.providerID === "muse-sdk") process.env.PI_MUSE_SDK_CONTRIBUTOR = "on"
        try {
          if ((await makeWorkerBridge(api, candidate).modelCheck(s.cwd)).available) {
            selected = candidate
            break
          }
        } catch { }
      }
      if (!selected) {
        save(s)
        throw new Error("Pinned Pi fallback models are unavailable")
      }
      s.primary_model = selected
    }
    const worker = makeWorkerBridge(api, primaryFor(s))
    if (!s.pi_candidates && !(await worker.modelCheck(s.cwd)).available)
      throw new Error("Pinned Pi fallback model is unavailable")
    transition(s, "pi", true)
    s.fallback_reason = reason
    if (detail !== undefined)
      s.fallback_detail = (typeof detail === "string" ? detail : JSON.stringify(detail)).slice(0, 2000)
    s.attempts = 1
    save(s)
    try {
      const admitted = await worker.start(s.cwd, s.title, prompt(s), s.tier === "scout")
      activatePi(s, admitted.session_id)
      save(s)
      return s
    } catch (error) {
      if (error instanceof PreAdmissionError && s.pi_candidates?.length) {
        transition(s, "command-code")
        save(s)
        return fallbackToPi(s, reason, detail)
      }
      if (String(error).includes("created but prompt admission failed"))
        throw new Error(String(error) + "; worktree lease retained for session " + s.id)
      throw error
    }
  }
  async function advance(cwd: unknown, id: unknown): Promise<{ session: Session; known?: Known }> {
    return withSessionLock(cwd, id, async (s) => {
      const observation = await observeExecution(s, stateDir(s.cwd), inspection)
      const source = fallbackSource(s, observation)
      const clean = source === null || untouched(s)
      let state = settledState(s, observation, clean).state
      let known: Known | undefined = { observation }
      if (source === "pi" && clean) {
        fallbackToCommand(s, "Primary Pi runner unavailable during execution (provider usage limit); no edits existed, so the task continued on Command Code.", observation.error)
        state = "running"
        known = undefined
      } else if (source === "codex" && clean) {
        try {
          transition(s, "codex")
          save(s)
          if (command.available()) fallbackToCommand(s, "Codex provider/model unavailable; continued on Command Code before edits.", observation.error)
          else await fallbackToPi(s, "Codex and Command Code unavailable; continued on an approved Pi provider.", observation.error)
          state = "running"
          known = undefined
        } catch (fallbackError) {
          s.fallback_blocked = "Fallback blocked: " + String(fallbackError)
          save(s)
          const backend = backendOf(s)
          state = backend === "pi-transition" || backend === "command-transition" || backend === "codex-transition" ? "blocked_admission" : "blocked_fallback"
          known = { observation, blocked: { state, notice: s.fallback_blocked } }
        }
      } else if (source === "command-code" && clean) {
        try {
          await fallbackToPi(s,
            "Primary Command Code provider/model unavailable; continued on an approved Pi provider before edits.", observation.error)
          state = "running"
          known = undefined
        } catch (fallbackError) {
          s.fallback_blocked = "Pi fallback blocked: " + String(fallbackError)
          save(s)
          state = backendOf(s) === "pi-transition" ? "blocked_admission" : "blocked_fallback"
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
    if ("fault" in i.route) throw new Error(i.route.fault)
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
        return { primary: { backend: "antigravity", ...plan.pin, available: antigravity.available(plan.pin) },
          fallback: null, command_code: null, pi_fallback: null, muse: undefined, opencode_go: null }
      }
      const firstPi = plan.pi[0]
      if (!firstPi) throw new Error("Policy has no Pi fallback")
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
        if (!antigravity.available(plan.pin))
          throw new Error("Pinned Antigravity model " + plan.pin.model + " unavailable; run agy models and check account access. No fallback.")
        const s: Session = { wire_version: 1, id: "usrw_" + randomUUID(), cwd: dir, tier: tierInput,
          title: required(title, "title", 100), scope: scopeFor(scopeInput, tierInput, dir),
          task, execution: { kind: "transition", executor: "antigravity" }, attempts: 0, antigravity_pin: { ...plan.pin } }
        const leaseDir = stateDir(dir)
        claimWorktree(leaseDir, dir, s.id)
        try { save(s) } catch (error) {
          releaseWorktree(leaseDir, dir, s.id)
          throw error
        }
        activateProcess(s, "antigravity", antigravity.start(s.cwd, leaseDir, prompt(s), plan.pin.effort, false, undefined, plan.pin.model, plan.pin))
        s.attempts = 1
        save(s)
        return admission(s)
      }
      const s: Session = { wire_version: 1, id: "usrw_" + randomUUID(), cwd: dir, tier: tierInput,
        title: required(title, "title", 100), scope: scopeFor(scopeInput, tierInput, dir),
        task, execution: { kind: "transition", executor: "codex" }, attempts: 0,
        execution_order: "codex-first" as const,
        codex_model: plan.codex.model, codex_effort: plan.codex.effort,
        pi_candidates: plan.pi.map(pin => ({ ...pin })),
        command_model: plan.command.model, command_effort: plan.command.effort }
      const leaseDir = stateDir(dir)
      claimWorktree(leaseDir, dir, s.id)
      try { save(s) } catch (error) {
        releaseWorktree(leaseDir, dir, s.id)
        throw error
      }
      if (codex.available()) {
        activateProcess(s, "codex", codex.start(s.cwd, leaseDir, prompt(s), plan.codex.effort, s.tier === "scout", undefined, plan.codex.model, !!s.scope.network, plan.codex))
        s.attempts = 1
        save(s)
        return admission(s)
      }
      s.fallback_reason = "Codex subscription unavailable; continued on the next approved provider."
      if (command.available()) {
        transition(s, "command-code")
        save(s)
        // Commit an admission transition before spawning. If the launch is ambiguous, retain the lease.
        activateProcess(s, "command-code", command.start(s.cwd, leaseDir, prompt(s),
          fallbackEffortFor(s), s.tier === "scout", undefined, fallbackModelFor(s), commandPin(s)))
        s.attempts = 1
        save(s)
        return admission(s)
      }
      await fallbackToPi(s, "Command Code CLI is unavailable; continued on an approved Pi provider.")
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
        const sessionId = s.execution.session_id
        ensureWorktree(stateDir(s.cwd), s.cwd, s.id)
        s.attempts++
        transition(s, "pi", true)
        save(s)
        await makeWorkerBridge(api, primaryFor(s)).resume(s.cwd, sessionId, "Same-scope correction only: " + correction)
        activatePi(s, sessionId)
        save(s)
      } else {
        const { executor: backend, run } = s.execution
        const previous = observe(s, backend, run)
        if (previous.state === "running" || previous.state === "unknown_or_interrupted" || previous.state === "interrupted")
          throw new Error("Command Code run not known complete")
        if (!previous.result?.sessionId) throw new Error("No resumable Command Code session")
        ensureWorktree(stateDir(s.cwd), s.cwd, s.id)
        if (continuation) s.continuations = (s.continuations ?? 0) + 1
        else s.attempts++
        transition(s, backend)
        s.cancel_requested = false
        save(s)
        const text = prompt(s) + (continuation ? "\nCONTINUE THE SAME TASK FROM WHERE THE TURN LIMIT STOPPED IT: " :
          "\nSAME-SCOPE CORRECTION ONLY: ") + correction
        activateProcess(s, backend, launch(s, backend, text, previous.result.sessionId))
        save(s)
      }
      return { session_id: s.id, backend: backendOf(s), status: "admitted", watch: watchCommand(s) }
      })
    },
    async cancel(cwd: unknown, id: unknown) {
      return withSessionLock(cwd, id, async (s) => {
      let interrupted = false
      if (s.execution.kind === "pi") {
        interrupted = (await makeWorkerBridge(api, primaryFor(s)).cancel(s.cwd, s.execution.session_id)).interrupted
      } else {
        const run = processRun(s)
        const executor = s.execution.executor
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
        const worker = makeWorkerBridge(api, primaryFor(s))
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
      const { executor: backend, run } = s.execution
      const runner = runnerFor(backend)
      const previous = observe(s, backend, run)
      if (previous.state !== "running")
        throw new Error("Command Code run is not running (state " + previous.state +
          "); use worker_resume for a finished session")
      const sessionId = backend === "antigravity" ? antigravity.session(run) : backend === "codex" ? codex.session(run) : commandSession(run)
      if (!sessionId)
        throw new Error("Command Code session identity is not recorded; cannot restart after steering")
      ensureWorktree(stateDir(s.cwd), s.cwd, s.id)
      if (!runner.cancel(run))
        throw new Error("Command Code run is not owned by this bridge process; refusing to signal an unverified PID")
      let state = observe(s, backend, run).state
      const deadline = Date.now() + TERMINATION_WAIT_MS
      while (state === "running" && Date.now() < deadline) {
        await new Promise((resolve) => setTimeout(resolve, 100))
        state = observe(s, backend, run).state
      }
      if (state === "running")
        throw new Error("Command Code process did not terminate after interruption; inspect it before retrying")
      s.steers = (s.steers ?? 0) + 1
      transition(s, backend)
      save(s)
      activateProcess(s, backend, launch(s, backend,
        prompt(s) + "\nPARENT STEERING (same scope and write boundaries): " + steering, sessionId))
      save(s)
      return { session_id: s.id, backend: backendOf(s), status: "steered", interrupted: true,
        steers: s.steers, steer_limit: STEER_LIMIT }
      })
    },
  }
}
