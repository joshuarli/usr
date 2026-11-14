import { execFileSync } from "node:child_process"
import { randomUUID } from "node:crypto"
import { accessSync, constants, mkdirSync, readFileSync, renameSync, rmdirSync, rmSync, writeFileSync } from "node:fs"
import { dirname, join, resolve } from "node:path"
import { PreAdmissionError, checkedWorktree, makeWorkerBridge, type OpenCodePort, type ModelRef } from "./bridge.ts"
import { cancelCommand, COMMAND_MODEL, COMMAND_EMBER_MODEL, commandResult, commandSession, startCommand, type CommandRun, type Effort } from "./command.ts"
import { CODEX_TIER_MODELS, codexAvailable, codexResult, codexSession, cancelCodex, startCodex } from "./codex.ts"
import { HYDROGEN_MODEL, HYDROGEN_EFFORT, hydrogenAvailable, hydrogenResult, hydrogenSession, cancelHydrogen, startHydrogen } from "./antigravity.ts"
import { activeWorktreeOwner, claimWorktree, ensureWorktree, releaseWorktree } from "./worktree-lease.ts"

import { GO_TIER_MODELS, MUSE_TIER_MODELS, museSubscriptionSelected, isTier as isBridgeTier, type Tier } from "./tier-policy.ts"
import { musePreflight } from "./muse-subscription.ts"
export type { Tier } from "./tier-policy.ts"
export type RoutedTier = Tier
export type Scope = {
  base_revision: string
  writable_paths: string[]
  acceptance_proof: string
  attempt_limit: 1 | 2
  stop_on: string
  network?: boolean
}
type Session = {
  id: string; cwd: string; title: string; tier: RoutedTier; scope: Scope; task: string
  backend: "pi" | "pi-admitting" | "pi-transition" | "command-code" | "command-transition" | "codex" | "codex-transition" | "hydrogen" | "hydrogen-transition"; attempts: number
  pi_id?: string; command_run?: CommandRun; fallback_reason?: string; fallback_detail?: string
  continuations?: number; steers?: number
  primary_model?: ModelRef; command_model?: string; command_effort?: Effort
  remaining_pi?: Array<"muse" | "go">
  execution_order?: "command-first" | "codex-first"; fallback_blocked?: string
  codex_model?: string; codex_effort?: Effort; cancel_requested?: boolean
}
function currentBackend(s: Session): Session["backend"] { return s.backend }
const EFFORT: Record<Tier, Effort> = {
  scout: "medium", mechanic: "xhigh", worker: "high", expert: "max",
}
// Sessions admitted before the Contributor-Spark pin migration must retain their original pins.
const LEGACY_EFFORT: Record<Tier, Effort> = {
  scout: "low", mechanic: "high", worker: "high", expert: "max",
}
const COMMAND_MODELS: Record<Tier, string> = {
  scout: COMMAND_EMBER_MODEL, mechanic: COMMAND_EMBER_MODEL, worker: COMMAND_MODEL, expert: COMMAND_MODEL,
}
export const TURN_LIMIT_CONTINUATIONS = 2
export const STEER_LIMIT = 2
const TERMINATION_WAIT_MS = 2000
const QUOTA =/\b(429|rate[ -]?limit(ed)?|quota|usage[ -]?limit|allowance exhausted|insufficient credits|credits? exhausted|resource_exhausted|too many requests)\b/i

function git(cwd: string, ...args: string[]): string {
  return execFileSync("git", ["-C", cwd, ...args], { encoding: "utf8", timeout: 10000 }).trim()
}
function required(value: unknown, name: string, max = 2000): string {
  if (typeof value !== "string" || !value.trim() || value.length > max) throw new Error("Invalid " + name)
  return value
}
const isTier = isBridgeTier
function scopeFor(value: unknown, tier: RoutedTier, cwd: string, checkHead = true): Scope {
  if (!value || typeof value !== "object" || Array.isArray(value)) throw new Error("scope must be an object")
  const raw = value as Record<string, unknown>
  const base_revision = required(raw.base_revision, "base_revision", 40)
  if (!/^[a-f0-9]{40}$/.test(base_revision)) throw new Error("base_revision must be 40 hex characters")
  if (checkHead && base_revision !== git(cwd, "rev-parse", "HEAD")) throw new Error("base_revision differs from HEAD")
  if (!Array.isArray(raw.writable_paths) || raw.writable_paths.length > 20 ||
      !raw.writable_paths.every((x) => typeof x === "string")) throw new Error("writable_paths must name at most 20 exact files or directories")
  const writable_paths = raw.writable_paths as string[]
  if (tier === "scout" ? writable_paths.length > 0 : writable_paths.length === 0)
    throw new Error("scouts are read-only; writers need specific writable_paths")
  for (const p of writable_paths) {
    const segments = (p.endsWith("/") ? p.slice(0, -1) : p).split("/")
    if (p.startsWith("/") || p.length > 512 || p.includes("\\") || /[*?[\]\u0000]/.test(p) ||
      segments.some((x) => !x || x === "." || x === ".." || x === ".git" || x === ".work"))
      throw new Error("Invalid writable path: " + p)
  }
  if (new Set(writable_paths).size !== writable_paths.length) throw new Error("Duplicate writable_paths")
  const acceptance_proof = required(raw.acceptance_proof, "acceptance_proof")
  const stop_on = required(raw.stop_on, "stop_on")
  if (raw.attempt_limit !== 1 && raw.attempt_limit !== 2) throw new Error("attempt_limit must be 1 or 2")
  if (raw.network !== undefined && typeof raw.network !== "boolean") throw new Error("network must be a boolean")
  if (raw.network && tier === "scout") throw new Error("scouts are read-only and get no network")
  return { base_revision, writable_paths, acceptance_proof, attempt_limit: raw.attempt_limit, stop_on, ...(raw.network ? { network: true } : {}) }
}
function changes(cwd: string, base: string): string[] {
  const diff = execFileSync("git", ["-C", cwd, "diff", "--no-renames", "--name-only", "-z", base, "--"], { encoding: "utf8" })
  const newFiles = execFileSync("git", ["-C", cwd, "ls-files", "--others", "--exclude-standard", "-z"], { encoding: "utf8" })
  return [...new Set((diff + newFiles).split("\0").filter(Boolean))].sort()
}
function outside(paths: string[], owned: string[]): string[] {
  return paths.filter((p) => !owned.some((w) => w.endsWith("/") ? p.startsWith(w) : p === w))
}
/** The command that blocks until the session's executor finishes; run it as a background task. */
function watchCommand(s: Session): string {
  return "worker-watch " + JSON.stringify(dirname(dirname(stateDir(s.cwd)))) + " " + s.id
}
function stateDir(cwd: string): string {
  const root = dirname(git(cwd, "rev-parse", "--path-format=absolute", "--git-common-dir"))
  execFileSync("git", ["-C", root, "check-ignore", "-q", ".work/worker-bridge/state"], { stdio: "ignore", timeout: 10000 })
  const dir = join(root, ".work", "worker-bridge")
  mkdirSync(dir, { recursive: true, mode: 0o700 })
  return dir
}
function pathFor(cwd: string, id: string): string {
  if (!/^usrw_[a-f0-9-]{36}$/.test(id)) throw new Error("Invalid worker ID")
  return join(stateDir(cwd), id + ".json")
}
function save(s: Session): void {
  const path = pathFor(s.cwd, s.id), tmp = path + "." + randomUUID() + ".tmp"
  try {
    writeFileSync(tmp, JSON.stringify(s), { mode: 0o600 })
    renameSync(tmp, path)
  } finally {
    rmSync(tmp, { force: true })
  }
}
function load(cwd: unknown, id: unknown): Session {
  const dir = checkedWorktree(cwd)
  const s = JSON.parse(readFileSync(pathFor(dir, required(id, "session_id", 64)), "utf8")) as Session
  if (s.cwd !== dir || !isTier(s.tier)) throw new Error("Session/worktree mismatch")
  scopeFor(s.scope, s.tier, dir, false)
  if (!Number.isInteger(s.attempts) || s.attempts < 0 ||
    (s.steers !== undefined && (!Number.isInteger(s.steers) || s.steers < 0)) ||
    (s.backend === "pi" && typeof s.pi_id !== "string") ||
    ((s.backend === "command-code" || s.backend === "codex" || s.backend === "hydrogen") && (!s.command_run || !Number.isInteger(s.command_run.pid))) ||
    !["pi", "pi-admitting", "pi-transition", "command-code", "command-transition", "codex", "codex-transition", "hydrogen", "hydrogen-transition"].includes(s.backend)) {
    throw new Error("Invalid persisted worker lifecycle; manual reconciliation required")
  }
  return s
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
function modelFor(tier: Tier): ModelRef {
  return museSubscriptionSelected(tier) ? MUSE_TIER_MODELS.worker : GO_TIER_MODELS[tier]
}
function primaryFor(s: Session): ModelRef { return s.primary_model ?? modelFor(s.tier) }
function fallbackModelFor(s: Session): string {
  return s.command_model ?? (s.primary_model ? COMMAND_MODELS[s.tier] : COMMAND_MODEL)
}
function fallbackEffortFor(s: Session): Effort {
  return s.command_effort ?? (s.primary_model ? EFFORT[s.tier] : LEGACY_EFFORT[s.tier])
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
    ...(s.tier === "scout" && (s.backend === "codex" || s.backend === "codex-transition") ? ["Use bridge_scout tools to inspect the actual files. Never claim a shell command ran; report only tool output you observed."] : []),
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
/** The worker's own verdict from the final `ACCEPTANCE:` line of its proof record. */
export function acceptanceClaim(text: string | null): "met" | "not_met" | "missing" {
  const last = text?.trimEnd().split("\n").at(-1)?.replace(/[`*]/g, "").trim().toLowerCase()
  return last === "acceptance: met" ? "met" : last === "acceptance: not met" ? "not_met" : "missing"
}
function untouched(s: Session): boolean {
  return git(s.cwd, "rev-parse", "HEAD") === s.scope.base_revision &&
    changes(s.cwd, s.scope.base_revision).length === 0
}
function quota(value: unknown): boolean {
  return QUOTA.test(typeof value === "string" ? value : JSON.stringify(value ?? ""))
}
function providerUnavailable(value: unknown): boolean {
  const message = typeof value === "string" ? value : JSON.stringify(value ?? "")
  return /\b(model (?:is |was )?(?:unavailable|not available|not found|unsupported)|unknown model|unsupported model|no such model|model does not exist|provider unavailable|provider not found|not logged in|not authenticated|authentication required|missing credentials)\b/i.test(message)
}
function fallbackNotice(s: Session): string {
  return [
    s.fallback_reason,
    "Automatic fallback is expected and needs no parent action.",
    "The worktree was verified untouched before switching, so no work was lost or replayed.",
    "The task continues on " + (s.backend === "pi"
      ? (primaryFor(s).providerID === "muse-sdk" ? "Muse subscription via the Pi SDK" : "OpenCode Go via the Pi SDK")
      : "Command Code") +
      " with the same scope and approved tier pins; verify it normally with worker_status.",
    "Do not retry and do not start a duplicate worker.",
  ].join(" ")
}
function blockedPartialNotice(): string {
  return [
    "The primary runner hit a provider usage limit, but the worktree already has edits, so no automatic switch happened.",
    "Inspect the worktree and decide manually; do not start a duplicate worker.",
  ].join(" ")
}

export function makeHybridBridge(api: OpenCodePort, command = {
  start: startCommand, status: commandResult, cancel: cancelCommand, available: cmdAvailable,
}, codex = { start: startCodex, status: codexResult, cancel: cancelCodex, available: codexAvailable, session: codexSession },
  hydrogen = { start: startHydrogen, status: hydrogenResult, cancel: cancelHydrogen, available: hydrogenAvailable, session: hydrogenSession }) {
  function fallbackToCommand(s: Session, reason: string, detail?: unknown): Session {
    if (!command.available()) throw new Error(reason + "; Command Code cmd unavailable")
    if (!untouched(s)) throw new Error("Fallback forbidden after partial edits; inspect the worktree")
    ensureWorktree(stateDir(s.cwd), s.cwd, s.id)
    const dir = stateDir(s.cwd)
    s.backend = "command-transition"
    s.command_run = undefined
    s.command_model = fallbackModelFor(s)
    s.command_effort = fallbackEffortFor(s)
    s.fallback_reason = reason
    if (detail !== undefined) s.fallback_detail = (typeof detail === "string" ? detail : JSON.stringify(detail)).slice(0, 2000)
    s.attempts = 1
    save(s)
    s.command_run = command.start(s.cwd, dir, prompt(s), fallbackEffortFor(s), s.tier === "scout", undefined, fallbackModelFor(s))
    s.backend = "command-code"
    save(s)
    return s
  }
  async function fallbackToPi(s: Session, reason: string, detail?: unknown): Promise<Session> {
    if (!untouched(s)) throw new Error("Fallback forbidden after partial edits; inspect the worktree")
    // An in-flight, interrupted, or ambiguous Command Code process must never be duplicated.
    if (s.command_run && command.status(s.command_run).state !== "failed")
      throw new Error("Command Code is not known terminal; OpenCode Go fallback refused")
    ensureWorktree(stateDir(s.cwd), s.cwd, s.id)
    if (s.remaining_pi) {
      let selected: ModelRef | undefined
      while (s.remaining_pi.length) {
        const destination = s.remaining_pi.shift()!
        const candidate = destination === "muse" && museSubscriptionSelected(s.tier)
          ? MUSE_TIER_MODELS.worker
          : destination === "go"
            ? GO_TIER_MODELS[s.tier]
            : undefined
        if (destination === "muse") process.env.PI_MUSE_SDK_CONTRIBUTOR = "on"
        if (!candidate) continue
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
    if (!s.remaining_pi && !(await worker.modelCheck(s.cwd)).available)
      throw new Error("Pinned Pi fallback model is unavailable")
    s.backend = "pi-transition"
    s.fallback_reason = reason
    if (detail !== undefined)
      s.fallback_detail = (typeof detail === "string" ? detail : JSON.stringify(detail)).slice(0, 2000)
    s.attempts = 1
    save(s)
    try {
      const admitted = await worker.start(s.cwd, s.title, prompt(s), s.tier === "scout")
      s.pi_id = admitted.session_id
      s.backend = "pi"
      save(s)
      return s
    } catch (error) {
      if (error instanceof PreAdmissionError && s.remaining_pi?.length) {
        s.backend = "command-transition"
        save(s)
        return fallbackToPi(s, reason, detail)
      }
      if (String(error).includes("created but prompt admission failed"))
        throw new Error(String(error) + "; worktree lease retained for session " + s.id)
      throw error
    }
  }
  function admission(s: Session) {
    return {
      session_id: s.id, backend: s.backend, status: "admitted", watch: watchCommand(s),
      fallback_reason: s.fallback_reason ?? null,
      fallback_notice: s.fallback_reason ? fallbackNotice(s) : null,
    }
  }
  return {
    async modelCheck(cwd: unknown, tierInput: unknown) {
      const dir = checkedWorktree(cwd)
      if (!isTier(tierInput)) throw new Error("Unknown Pi tier")
      if (tierInput === "expert") {
        return { primary: { backend: "hydrogen", model: HYDROGEN_MODEL, effort: HYDROGEN_EFFORT, available: hydrogen.available() },
          fallback: null, command_code: null, pi_fallback: null, muse: undefined, opencode_go: null }
      }
      let museAvailable = false, museIssue: string | null = null
      if (museSubscriptionSelected(tierInput)) {
        try {
          museAvailable = (await makeWorkerBridge(api, modelFor(tierInput)).modelCheck(dir)).available
        } catch (e) { museIssue = String(e) }
        if (!museAvailable && !museIssue)
          museIssue = musePreflight().issue ?? "Muse subscription model unavailable; check Muse Code login"
      }
      let goAvailable = false, goIssue: string | null = null
      try {
        goAvailable = (await makeWorkerBridge(api, GO_TIER_MODELS[tierInput]).modelCheck(dir)).available
      } catch (e) { goIssue = String(e) }
      if (!goAvailable && !goIssue) {
        try {
          const { ensureOpenCodeApiKey } = await import("./opencode-auth.ts")
          ensureOpenCodeApiKey()
          const { ModelRuntime } = await import("@earendil-works/pi-coding-agent")
          const runtime = await ModelRuntime.create()
          const model = GO_TIER_MODELS[tierInput]
          if (!runtime.getModel(model.providerID, model.id))
            goIssue = `Pinned OpenCode Go model ${model.providerID}/${model.id} is not in the Pi SDK catalog`
          else if (!runtime.hasConfiguredAuth(model.providerID))
            goIssue = `No configured auth for ${model.providerID} in Pi SDK; sign in with opencode2 or set OPENCODE_API_KEY`
        } catch { /* keep issue null if diagnosis unavailable */ }
      }
      const museInfo = museSubscriptionSelected(tierInput) ? { available: museAvailable, issue: museIssue } : { available: false, issue: null }
      const goInfo = { available: goAvailable, issue: goIssue }
      const piLane = { backend: "pi", model: modelFor(tierInput),
        available: museSubscriptionSelected(tierInput) ? museInfo.available : goInfo.available,
        issue: museSubscriptionSelected(tierInput) ? museInfo.issue : goInfo.issue }
      const commandLane = { backend: "command-code", model: COMMAND_MODELS[tierInput], effort: EFFORT[tierInput], available: command.available() }
      return {
        primary: { backend: "codex", ...CODEX_TIER_MODELS[tierInput], available: codex.available() },
        fallback: commandLane,
        command_code: commandLane,
        pi_fallback: piLane,
        muse: museSubscriptionSelected(tierInput) ? { backend: "pi", model: modelFor(tierInput), available: museInfo.available, issue: museInfo.issue } : undefined,
        opencode_go: { backend: "pi", model: GO_TIER_MODELS[tierInput], available: goInfo.available, issue: goInfo.issue },
      }
    },
    async start(cwd: unknown, title: unknown, tierInput: unknown, scopeInput: unknown, brief: unknown) {
      const dir = checkedWorktree(cwd, true)
      if (!isTier(tierInput)) throw new Error("Unknown Pi tier")
      if (git(dir, "status", "--porcelain", "--untracked-files=all")) throw new Error("Worker worktree must start clean")
      const task = required(brief, "brief", 32000)
      if (tierInput === "expert") {
        if (activeWorktreeOwner(stateDir(dir), dir)) throw new Error("Worktree already has an active worker")
        if (!hydrogen.available())
          throw new Error("Pinned Gemini 4 Hydrogen XHigh unavailable in Antigravity CLI; run agy models and check account access. No fallback.")
        const s: Session = { id: "usrw_" + randomUUID(), cwd: dir, tier: tierInput,
          title: required(title, "title", 100), scope: scopeFor(scopeInput, tierInput, dir),
          task, backend: "hydrogen-transition", attempts: 0 }
        const leaseDir = stateDir(dir)
        claimWorktree(leaseDir, dir, s.id)
        try { save(s) } catch (error) {
          releaseWorktree(leaseDir, dir, s.id)
          throw error
        }
        s.command_run = hydrogen.start(s.cwd, leaseDir, prompt(s), HYDROGEN_EFFORT, false, undefined, HYDROGEN_MODEL)
        s.backend = "hydrogen"
        s.attempts = 1
        save(s)
        return admission(s)
      }
      const s: Session = { id: "usrw_" + randomUUID(), cwd: dir, tier: tierInput,
        title: required(title, "title", 100), scope: scopeFor(scopeInput, tierInput, dir),
        task, backend: "codex-transition", attempts: 0,
        execution_order: "codex-first" as const,
        codex_model: CODEX_TIER_MODELS[tierInput].model, codex_effort: CODEX_TIER_MODELS[tierInput].effort,
        remaining_pi: museSubscriptionSelected(tierInput) ? ["muse", "go"] : ["go"],
        command_model: COMMAND_MODELS[tierInput],
        command_effort: EFFORT[tierInput] }
      const leaseDir = stateDir(dir)
      claimWorktree(leaseDir, dir, s.id)
      try { save(s) } catch (error) {
        releaseWorktree(leaseDir, dir, s.id)
        throw error
      }
      if (codex.available()) {
        s.command_run = codex.start(s.cwd, leaseDir, prompt(s), s.codex_effort!, s.tier === "scout", undefined, s.codex_model, !!s.scope.network)
        s.backend = "codex"
        s.attempts = 1
        save(s)
        return admission(s)
      }
      s.fallback_reason = "Codex subscription unavailable; continued on the next approved provider."
      if (command.available()) {
        s.backend = "command-transition"
        save(s)
        // Commit an admission transition before spawning. If the launch is ambiguous, retain the lease.
        s.command_run = command.start(s.cwd, leaseDir, prompt(s),
          fallbackEffortFor(s), s.tier === "scout", undefined, fallbackModelFor(s))
        s.backend = "command-code"
        s.attempts = 1
        save(s)
        return admission(s)
      }
      await fallbackToPi(s, "Command Code CLI is unavailable; continued on an approved Pi provider.")
      return admission(s)
    },
    async status(cwd: unknown, id: unknown) {
      return withSessionLock(cwd, id, async (s) => {
      let state: string, last_assistant_text: string | null, error: unknown = null, usage: unknown = null
      let notice: string | null = null
      if (s.backend === "pi-admitting" || s.backend === "pi-transition") {
        state = "blocked_admission"
        last_assistant_text = null
        error = "Pi admission interrupted or uncertain; inspect this session before recovery"
      } else if (s.backend === "pi") {
        if (!s.pi_id) throw new Error("Missing Pi session")
        const response = await makeWorkerBridge(api, primaryFor(s)).status(s.cwd, s.pi_id)
        state = typeof response.state === "string" ? response.state : "unknown"
        last_assistant_text = response.last_assistant_text
        error = response.error
        usage = { cost_reported_usd: response.cost_reported_usd, tokens: response.tokens }
        if (s.execution_order === undefined &&
            state !== "running" && state !== "queued" && state !== "succeeded" && quota(error)) {
          if (!untouched(s)) {
            state = "blocked_partial_work"
            notice = blockedPartialNotice()
          } else {
            fallbackToCommand(s, "Primary Pi runner unavailable during execution (provider usage limit); no edits existed, so the task continued on Command Code.", error)
            state = "running"
            last_assistant_text = null
            error = null
          }
        }
      } else if (s.backend === "hydrogen-transition") {
        state = "blocked_transition"
        last_assistant_text = null
        error = "Hydrogen transition interrupted; inspect persisted state and worktree before recovery"
      } else if (s.backend === "codex-transition") {
        state = "blocked_transition"
        last_assistant_text = null
        error = "Codex transition interrupted; inspect persisted state and worktree before recovery"
      } else if (s.backend === "command-transition") {
        state = "blocked_transition"
        last_assistant_text = null
        error = "Command Code transition interrupted; inspect persisted state and worktree before recovery"
      } else {
        if (!s.command_run) throw new Error("Missing Command Code process")
        const response = s.backend === "hydrogen" ? hydrogen.status(s.command_run) :
          s.backend === "codex" ? codex.status(s.command_run) : command.status(s.command_run)
        state = response.state
        last_assistant_text = response.result?.finalText?.slice(-5000) ?? null
        error = response.state === "interrupted"
          ? "Worker process is gone or its recorded PID identity changed; the run is terminal and cannot be replayed"
          : response.state === "failed"
            ? response.result?.error ?? response.stderr : null
        usage = response.result?.usage ?? null
        if (s.cancel_requested && (state === "failed" || state === "interrupted")) { state = "cancelled"; error = null }
        if (s.fallback_blocked) {
          state = "blocked_fallback"
          notice = s.fallback_blocked
        } else if (s.backend === "codex" && !s.cancel_requested && state === "failed" && (quota(error) || providerUnavailable(error))) {
          if (!untouched(s)) {
            state = "blocked_partial_work"
            notice = blockedPartialNotice()
          } else {
            try {
              s.backend = "codex-transition"
              s.command_run = undefined
              save(s)
              if (command.available()) fallbackToCommand(s, "Codex provider/model unavailable; continued on Command Code before edits.", error)
              else await fallbackToPi(s, "Codex and Command Code unavailable; continued on an approved Pi provider.", error)
              state = "running"
              last_assistant_text = null
              error = null
              usage = null
            } catch (fallbackError) {
              s.fallback_blocked = "Fallback blocked: " + String(fallbackError)
              save(s)
              state = currentBackend(s) === "pi-transition" || currentBackend(s) === "command-transition" || currentBackend(s) === "codex-transition" ? "blocked_admission" : "blocked_fallback"
              notice = s.fallback_blocked
            }
          }
        } else if (s.backend === "command-code" && !s.cancel_requested && s.execution_order !== undefined && state === "failed" &&
                   (quota(error) || providerUnavailable(error))) {
          if (!untouched(s)) {
            state = "blocked_partial_work"
            notice = blockedPartialNotice()
          } else {
            try {
              await fallbackToPi(s,
                "Primary Command Code provider/model unavailable; continued on an approved Pi provider before edits.", error)
              state = "running"
              last_assistant_text = null
              error = null
              usage = null
            } catch (fallbackError) {
              s.fallback_blocked = "Pi fallback blocked: " + String(fallbackError)
              save(s)
              state = currentBackend(s) === "pi-transition" ? "blocked_admission" : "blocked_fallback"
              notice = s.fallback_blocked
            }
          }
        }
      }
      const changed_paths = changes(s.cwd, s.scope.base_revision)
      const out_of_scope_paths = outside(changed_paths, s.scope.writable_paths)
      const head_unchanged = git(s.cwd, "rev-parse", "HEAD") === s.scope.base_revision
      if (s.fallback_reason && !notice) {
        if (state.startsWith("blocked")) {
          notice = "Provider transition blocked; inspect the owned session before retrying."
        } else if ((s.backend === "pi" || s.backend === "pi-admitting" || s.backend === "pi-transition") &&
                   ["failed", "interrupted", "cancelled", "canceled"].includes(state)) {
          const provider = primaryFor(s).providerID === "muse-sdk" ? "the pinned Muse SDK fallback" : "the pinned OpenCode Go fallback"
          notice = "The task was admitted to " + provider + " via Command Code's absence or failure, but that Pi run ended in " + state +
            " (see error; it may have left partial edits). The worktree is retained and the lease is released. No automatic retry will occur: a fresh dispatch" +
            " re-admits with the best available lane, and a provider usage-limit error (for example 429) means every pinned lane is exhausted —" +
            " per the orchestrate quota-fallback rule, delegate to the harness's native subagents instead of restarting the bridge."
        } else {
          notice = fallbackNotice(s)
        }
      }
      // A verified terminal response releases worktree admission, not session history.
      if (["succeeded", "failed", "turn_limit", "cancelled", "canceled", "interrupted"].includes(state)) {
        const directory = stateDir(s.cwd)
        if (activeWorktreeOwner(directory, s.cwd) === s.id)
          releaseWorktree(directory, s.cwd, s.id)
      }
      const acceptance_claim = acceptanceClaim(last_assistant_text)
      if (state === "succeeded" && acceptance_claim !== "met") state = "incomplete"
      return {
        session_id: s.id, backend: s.backend, tier: s.tier,
        model: s.backend === "hydrogen" || s.backend === "hydrogen-transition" ? HYDROGEN_MODEL :
          s.backend === "pi" || s.backend === "pi-admitting" || s.backend === "pi-transition" ? primaryFor(s) :
          s.backend === "codex" || s.backend === "codex-transition" ? s.codex_model : fallbackModelFor(s),
        effort: s.backend === "hydrogen" || s.backend === "hydrogen-transition" ? HYDROGEN_EFFORT :
          s.backend === "pi" || s.backend === "pi-admitting" || s.backend === "pi-transition" ? primaryFor(s).variant :
          s.backend === "codex" || s.backend === "codex-transition" ? s.codex_effort : fallbackEffortFor(s), state, last_assistant_text, error, usage,
        changed_paths, out_of_scope_paths, head_unchanged,
        acceptance_claim, acceptance_blocked: !head_unchanged || out_of_scope_paths.length > 0 || acceptance_claim !== "met",
        continuations: s.continuations ?? 0, continuation_limit: TURN_LIMIT_CONTINUATIONS,
        steers: s.steers ?? 0, steer_limit: STEER_LIMIT,
        fallback_reason: s.fallback_reason ?? null,
        fallback_notice: notice,
        fallback_detail: s.fallback_detail ?? null,
        note: "Proof must be checked independently. Review the diff once before integration.",
      }
      })
    },
    async resume(cwd: unknown, id: unknown, feedback: unknown) {
      return withSessionLock(cwd, id, async (s) => {
      const correction = required(feedback, "feedback", 32000)
      const continuation = s.backend === "command-code" && !!s.command_run &&
        command.status(s.command_run).state === "turn_limit"
      if (continuation && (s.continuations ?? 0) >= TURN_LIMIT_CONTINUATIONS)
        throw new Error("Turn-limit continuation limit reached")
      if (git(s.cwd, "rev-parse", "HEAD") !== s.scope.base_revision ||
        outside(changes(s.cwd, s.scope.base_revision), s.scope.writable_paths).length)
        throw new Error("Cannot resume changed HEAD or out-of-scope work")
      if (s.backend === "codex-transition" || s.backend === "command-transition" || s.backend === "hydrogen-transition" || s.backend === "pi-admitting" || s.backend === "pi-transition" || s.fallback_blocked)
        throw new Error("Worker transition interrupted; inspect session before resuming")
      if (!continuation && s.attempts >= s.scope.attempt_limit) throw new Error("Task attempt limit reached")
      if (s.backend === "pi") {
        if (!s.pi_id) throw new Error("Missing Pi session")
        ensureWorktree(stateDir(s.cwd), s.cwd, s.id)
        s.attempts++
        s.backend = "pi-transition"
        save(s)
        await makeWorkerBridge(api, primaryFor(s)).resume(s.cwd, s.pi_id, "Same-scope correction only: " + correction)
        s.backend = "pi"
        save(s)
      } else {
        if (!s.command_run) throw new Error("Missing Command Code process")
        const runner = s.backend === "hydrogen" ? hydrogen : s.backend === "codex" ? codex : command
        const backend = s.backend
        const previous = runner.status(s.command_run)
        if (previous.state === "running" || previous.state === "unknown_or_interrupted" || previous.state === "interrupted")
          throw new Error("Command Code run not known complete")
        if (!previous.result?.sessionId) throw new Error("No resumable Command Code session")
        ensureWorktree(stateDir(s.cwd), s.cwd, s.id)
        if (continuation) s.continuations = (s.continuations ?? 0) + 1
        else s.attempts++
        s.backend = backend === "hydrogen" ? "hydrogen-transition" : backend === "codex" ? "codex-transition" : "command-transition"
        s.command_run = undefined
        s.cancel_requested = false
        save(s)
        const text = prompt(s) + (continuation ? "\nCONTINUE THE SAME TASK FROM WHERE THE TURN LIMIT STOPPED IT: " :
          "\nSAME-SCOPE CORRECTION ONLY: ") + correction
        s.command_run = backend === "codex"
          ? codex.start(s.cwd, stateDir(s.cwd), text, s.codex_effort!, s.tier === "scout", previous.result.sessionId, s.codex_model, !!s.scope.network)
          : runner.start(s.cwd, stateDir(s.cwd), text, backend === "hydrogen" ? HYDROGEN_EFFORT : fallbackEffortFor(s), s.tier === "scout",
            previous.result.sessionId, backend === "hydrogen" ? HYDROGEN_MODEL : fallbackModelFor(s))
        s.backend = backend
        save(s)
      }
      return { session_id: s.id, backend: s.backend, status: "admitted", watch: watchCommand(s) }
      })
    },
    async cancel(cwd: unknown, id: unknown) {
      return withSessionLock(cwd, id, async (s) => {
      let interrupted = false
      if (s.backend === "pi") {
        if (!s.pi_id) throw new Error("Missing Pi session")
        interrupted = (await makeWorkerBridge(api, primaryFor(s)).cancel(s.cwd, s.pi_id)).interrupted
      } else if (s.command_run) {
        s.cancel_requested = true
        save(s)
        interrupted = s.backend === "hydrogen" ? hydrogen.cancel(s.command_run) : s.backend === "codex" ? codex.cancel(s.command_run) : command.cancel(s.command_run)
        if (!interrupted) { s.cancel_requested = false; save(s) }
      }
      return { session_id: s.id, interrupted,
        note: "Never signal a Command Code PID left by an earlier MCP process; it may have been reused." }
      })
    },
    async steer(cwd: unknown, id: unknown, note: unknown) {
      return withSessionLock(cwd, id, async (s) => {
      const steering = required(note, "note", 32000)
      if (s.backend === "codex-transition" || s.backend === "command-transition" || s.backend === "hydrogen-transition" || s.backend === "pi-admitting" ||
          s.backend === "pi-transition" || s.fallback_blocked)
        throw new Error("Worker transition interrupted; inspect session before steering")
      if ((s.steers ?? 0) >= STEER_LIMIT) throw new Error("Steer limit reached for this session")
      if (git(s.cwd, "rev-parse", "HEAD") !== s.scope.base_revision ||
        outside(changes(s.cwd, s.scope.base_revision), s.scope.writable_paths).length)
        throw new Error("Cannot steer changed HEAD or out-of-scope work")
      if (s.backend === "pi") {
        if (!s.pi_id) throw new Error("Missing Pi session")
        const worker = makeWorkerBridge(api, primaryFor(s))
        const observed = await worker.status(s.cwd, s.pi_id)
        const observedState = typeof observed.state === "string" ? observed.state : "unknown"
        if (observedState !== "running" && observedState !== "queued")
          throw new Error("Pi worker is not running (state " + observedState + "); use worker_resume for a finished session")
        ensureWorktree(stateDir(s.cwd), s.cwd, s.id)
        const receipt = await worker.steer(s.cwd, s.pi_id, steering)
        s.steers = (s.steers ?? 0) + 1
        save(s)
        return { session_id: s.id, backend: s.backend, status: "steered", interrupted: false,
          steers: s.steers, steer_limit: STEER_LIMIT, receipt }
      }
      if (!s.command_run) throw new Error("Missing Command Code process")
      const runner = s.backend === "hydrogen" ? hydrogen : s.backend === "codex" ? codex : command
      const backend = s.backend
      const previous = runner.status(s.command_run)
      if (previous.state !== "running")
        throw new Error("Command Code run is not running (state " + previous.state +
          "); use worker_resume for a finished session")
      const sessionId = backend === "hydrogen" ? hydrogen.session(s.command_run) : backend === "codex" ? codex.session(s.command_run) : commandSession(s.command_run)
      if (!sessionId)
        throw new Error("Command Code session identity is not recorded; cannot restart after steering")
      ensureWorktree(stateDir(s.cwd), s.cwd, s.id)
      if (!runner.cancel(s.command_run))
        throw new Error("Command Code run is not owned by this bridge process; refusing to signal an unverified PID")
      let state = runner.status(s.command_run).state
      const deadline = Date.now() + TERMINATION_WAIT_MS
      while (state === "running" && Date.now() < deadline) {
        await new Promise((resolve) => setTimeout(resolve, 100))
        state = runner.status(s.command_run).state
      }
      if (state === "running")
        throw new Error("Command Code process did not terminate after interruption; inspect it before retrying")
      s.steers = (s.steers ?? 0) + 1
      s.backend = backend === "hydrogen" ? "hydrogen-transition" : backend === "codex" ? "codex-transition" : "command-transition"
      s.command_run = undefined
      save(s)
      s.command_run = runner.start(s.cwd, stateDir(s.cwd),
        prompt(s) + "\nPARENT STEERING (same scope and write boundaries): " + steering,
        (backend === "hydrogen" ? HYDROGEN_EFFORT : backend === "codex" ? s.codex_effort! : fallbackEffortFor(s)), s.tier === "scout", sessionId, backend === "hydrogen" ? HYDROGEN_MODEL : backend === "codex" ? s.codex_model : fallbackModelFor(s))
      s.backend = backend
      save(s)
      return { session_id: s.id, backend: s.backend, status: "steered", interrupted: true,
        steers: s.steers, steer_limit: STEER_LIMIT }
      })
    },
  }
}
