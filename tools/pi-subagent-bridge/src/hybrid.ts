import { execFileSync } from "node:child_process"
import { randomUUID } from "node:crypto"
import { accessSync, constants, mkdirSync, readFileSync, renameSync, rmdirSync, rmSync, writeFileSync } from "node:fs"
import { dirname, join, resolve } from "node:path"
import { checkedWorktree, makeWorkerBridge, type OpenCodePort, type ModelRef } from "./bridge.ts"
import { cancelCommand, COMMAND_MODEL, COMMAND_EMBER_MODEL, commandResult, startCommand, type CommandRun, type Effort } from "./command.ts"
import { activeWorktreeOwner, claimWorktree, ensureWorktree, releaseWorktree } from "./worktree-lease.ts"

export type Tier = "scout" | "mechanic" | "worker" | "expert"
export type Scope = {
  base_revision: string
  writable_paths: string[]
  acceptance_proof: string
  attempt_limit: 1 | 2
  stop_on: string
}
type Session = {
  id: string; cwd: string; title: string; tier: Tier; scope: Scope; task: string
  backend: "pi" | "pi-admitting" | "pi-transition" | "command-code" | "command-transition"; attempts: number
  pi_id?: string; command_run?: CommandRun; fallback_reason?: string; fallback_detail?: string; continuations?: number
  primary_model?: ModelRef; command_model?: string; command_effort?: Effort
}
const EFFORT: Record<Tier, Effort> = {
  scout: "medium", mechanic: "xhigh", worker: "high", expert: "max",
}
// Sessions admitted before the Ember migration must retain their original pins.
const LEGACY_EFFORT: Record<Tier, Effort> = {
  scout: "low", mechanic: "high", worker: "high", expert: "max",
}
const COMMAND_MODELS: Record<Tier, string> = {
  scout: COMMAND_EMBER_MODEL, mechanic: COMMAND_EMBER_MODEL, worker: COMMAND_MODEL, expert: COMMAND_MODEL,
}
const TURN_LIMIT_CONTINUATIONS = 2
const ADMISSION_POLLS = 10
const ADMISSION_POLL_MS = 500
const QUOTA =/\b(429|rate[ -]?limit(ed)?|quota|usage[ -]?limit|allowance exhausted|insufficient credits|credits? exhausted|resource_exhausted|too many requests)\b/i

function git(cwd: string, ...args: string[]): string {
  return execFileSync("git", ["-C", cwd, ...args], { encoding: "utf8", timeout: 10000 }).trim()
}
function required(value: unknown, name: string, max = 2000): string {
  if (typeof value !== "string" || !value.trim() || value.length > max) throw new Error("Invalid " + name)
  return value
}
function isTier(value: unknown): value is Tier {
  return typeof value === "string" && Object.hasOwn(EFFORT, value)
}
function scopeFor(value: unknown, tier: Tier, cwd: string, checkHead = true): Scope {
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
  return { base_revision, writable_paths, acceptance_proof, attempt_limit: raw.attempt_limit, stop_on }
}
function changes(cwd: string, base: string): string[] {
  const diff = execFileSync("git", ["-C", cwd, "diff", "--no-renames", "--name-only", "-z", base, "--"], { encoding: "utf8" })
  const newFiles = execFileSync("git", ["-C", cwd, "ls-files", "--others", "--exclude-standard", "-z"], { encoding: "utf8" })
  return [...new Set((diff + newFiles).split("\0").filter(Boolean))].sort()
}
function outside(paths: string[], owned: string[]): string[] {
  return paths.filter((p) => !owned.some((w) => w.endsWith("/") ? p.startsWith(w) : p === w))
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
    (s.backend === "pi" && typeof s.pi_id !== "string") ||
    (s.backend === "command-code" && (!s.command_run || !Number.isInteger(s.command_run.pid))) ||
    !["pi", "pi-admitting", "pi-transition", "command-code", "command-transition"].includes(s.backend)) {
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
const PI_MODELS: Record<Tier, ModelRef> = {
  scout: { providerID: "opencode", id: "muse-ember-1.0", variant: "medium" },
  mechanic: { providerID: "opencode", id: "muse-ember-1.0", variant: "xhigh" },
  worker: { providerID: "opencode-go", id: "deepseek-v4.1-flash", variant: "high" },
  expert: { providerID: "opencode-go", id: "deepseek-v4.1-flash", variant: "max" },
}
const LEGACY_PI_MODELS: Partial<Record<Tier, ModelRef>> = {
  scout: { providerID: "opencode-go", id: "muse-spark-1.3-contributor", variant: "medium" },
  mechanic: { providerID: "opencode-go", id: "muse-spark-1.3-contributor", variant: "high" },
}
function modelFor(tier: Tier) { return PI_MODELS[tier] }
function primaryFor(s: Session): ModelRef { return s.primary_model ?? LEGACY_PI_MODELS[s.tier] ?? modelFor(s.tier) }
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
    "Do not spawn children, commit, switch branches, merge, push, add dependencies, or edit outside writable paths.",
    "Stop if blocked or if the requirements demand more scope. Do not broaden the task.",
    "Return a PROOF RECORD instead of a summary: changed paths; exact commands, exit codes and decisive output;",
    "file:line evidence for research; and explicit unverified cases and blockers. Never invent a passing check.",
  ].join("\n")
}
function untouched(s: Session): boolean {
  return git(s.cwd, "rev-parse", "HEAD") === s.scope.base_revision &&
    changes(s.cwd, s.scope.base_revision).length === 0
}
function quota(value: unknown): boolean {
  return QUOTA.test(typeof value === "string" ? value : JSON.stringify(value ?? ""))
}
function fallbackNotice(reason: string): string {
  return [
    reason,
    "Automatic fallback is expected and needs no parent action.",
    "The worktree was verified untouched before switching, so no work was lost or replayed.",
    "The task continues on Command Code with the same scope, model and effort; verify it normally with worker_status.",
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
}) {
  function fallback(s: Session, reason: string, detail?: unknown): Session {
    if (!command.available()) throw new Error("Pi " + reason + "; Command Code cmd unavailable")
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
  function admission(s: Session) {
    return {
      session_id: s.id, backend: s.backend, status: "admitted",
      fallback_reason: s.fallback_reason ?? null,
      fallback_notice: s.fallback_reason ? fallbackNotice(s.fallback_reason) : null,
    }
  }
  return {
    async modelCheck(cwd: unknown, tierInput: unknown) {
      const dir = checkedWorktree(cwd)
      if (!isTier(tierInput)) throw new Error("Unknown Pi tier")
      let available = false, issue: string | null = null
      try { available = (await makeWorkerBridge(api, modelFor(tierInput)).modelCheck(dir)).available }
      catch (e) { issue = String(e) }
      if (!available && !issue) {
        try {
          const { ensureOpenCodeApiKey } = await import("./opencode-auth.ts")
          ensureOpenCodeApiKey()
          const { ModelRuntime } = await import("@earendil-works/pi-coding-agent")
          const runtime = await ModelRuntime.create()
          const model = modelFor(tierInput)
          if (!runtime.getModel(model.providerID, model.id))
            issue = `Pinned primary model ${model.providerID}/${model.id} is not in the Pi SDK catalog`
          else if (!runtime.hasConfiguredAuth(model.providerID))
            issue = `No configured auth for ${model.providerID} in Pi SDK; sign in with opencode2 or set OPENCODE_API_KEY`
        } catch { /* keep issue null if diagnosis unavailable */ }
      }
      if (!available && issue)
        issue = `Primary ${modelFor(tierInput).providerID}/${modelFor(tierInput).id} is temporarily unavailable: ${issue}. Fallback ${COMMAND_MODELS[tierInput]} is installed and ready.`
      return {
        primary: { backend: "pi", model: modelFor(tierInput), available, issue },
        fallback: { backend: "command-code", model: COMMAND_MODELS[tierInput], effort: EFFORT[tierInput], installed: command.available() },
      }
    },
    async start(cwd: unknown, title: unknown, tierInput: unknown, scopeInput: unknown, brief: unknown) {
      const dir = checkedWorktree(cwd, true)
      if (!isTier(tierInput)) throw new Error("Unknown Pi tier")
      if (git(dir, "status", "--porcelain", "--untracked-files=all")) throw new Error("Worker worktree must start clean")
      const task = required(brief, "brief", 32000)
      const s: Session = { id: "usrw_" + randomUUID(), cwd: dir, tier: tierInput,
        title: required(title, "title", 100), scope: scopeFor(scopeInput, tierInput, dir),
        task, backend: "pi-admitting", attempts: 0, primary_model: modelFor(tierInput) }
      const leaseDir = stateDir(dir)
      claimWorktree(leaseDir, dir, s.id)
      try { save(s) } catch (error) {
        releaseWorktree(leaseDir, dir, s.id)
        throw error
      }
      const worker = makeWorkerBridge(api, modelFor(tierInput))
      let available: boolean
      try { available = (await worker.modelCheck(dir)).available }
      catch (e) {
        fallback(s, "Primary Pi runner unavailable at model check; continued on Command Code.", e)
        return admission(s)
      }
      if (!available) {
        fallback(s, "Pinned primary model unavailable; continued on Command Code.")
        return admission(s)
      }
      try {
        const admitted = await worker.start(dir, s.title, prompt(s), tierInput === "scout")
        s.pi_id = admitted.session_id
        s.backend = "pi"
        s.attempts = 1
        save(s)
        for (let poll = 0; poll < ADMISSION_POLLS; poll++) {
          const early = await worker.status(dir, admitted.session_id).catch(() => null)
          if (!early) break
          if (early.state === "running" || early.state === "queued") {
            await new Promise((done) => setTimeout(done, ADMISSION_POLL_MS))
            continue
          }
          if (early.state !== "succeeded" && quota(early.error) && untouched(s)) {
            fallback(s, "Primary Pi runner unavailable at admission (provider usage limit); continued on Command Code.", early.error)
            return admission(s)
          }
          break
        }
        return { ...admission(s), model: modelFor(s.tier) }
      } catch (e) {
        // A created Pi session may still execute; never start a second worker without proving it did not.
        if (String(e).includes("created but prompt admission failed"))
          throw new Error(String(e) + "; worktree lease retained for session " + s.id)
        if (!quota(e)) throw e
        fallback(s, "Primary Pi runner unavailable at admission (provider usage limit); continued on Command Code.", e)
        return admission(s)
      }
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
        if (state !== "running" && state !== "queued" && state !== "succeeded" &&
          quota(error)) {
          if (!untouched(s)) {
            state = "blocked_partial_work"
            notice = blockedPartialNotice()
          } else {
            fallback(s, "Primary Pi runner unavailable during execution (provider usage limit); no edits existed, so the task continued on Command Code.", error)
            state = "running"
            last_assistant_text = null
            error = null
          }
        }
      } else if (s.backend === "command-transition") {
        state = "blocked_transition"
        last_assistant_text = null
        error = "Command Code transition interrupted; inspect persisted state and worktree before recovery"
      } else {
        if (!s.command_run) throw new Error("Missing Command Code process")
        const response = command.status(s.command_run)
        state = response.state
        last_assistant_text = response.result?.finalText?.slice(-5000) ?? null
        error = response.state === "failed" || response.state === "unknown_or_interrupted"
          ? response.result?.error ?? response.stderr : null
        usage = response.result?.usage ?? null
      }
      const changed_paths = changes(s.cwd, s.scope.base_revision)
      const out_of_scope_paths = outside(changed_paths, s.scope.writable_paths)
      const head_unchanged = git(s.cwd, "rev-parse", "HEAD") === s.scope.base_revision
      if (s.fallback_reason && !notice) notice = fallbackNotice(s.fallback_reason)
      // A verified terminal response releases worktree admission, not session history.
      // Unknown/interrupted/queued work remains leased until explicitly inspected.
      if (["succeeded", "failed", "turn_limit", "cancelled", "canceled"].includes(state)) {
        const directory = stateDir(s.cwd)
        if (activeWorktreeOwner(directory, s.cwd) === s.id)
          releaseWorktree(directory, s.cwd, s.id)
      }
      return {
        session_id: s.id, backend: s.backend, tier: s.tier,
        model: s.backend === "pi" || s.backend === "pi-admitting" || s.backend === "pi-transition" ? primaryFor(s) : fallbackModelFor(s),
        effort: s.backend === "pi" || s.backend === "pi-admitting" || s.backend === "pi-transition" ? primaryFor(s).variant : fallbackEffortFor(s), state, last_assistant_text, error, usage,
        changed_paths, out_of_scope_paths, head_unchanged,
        acceptance_blocked: !head_unchanged || out_of_scope_paths.length > 0,
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
      if (s.backend === "command-transition" || s.backend === "pi-admitting" || s.backend === "pi-transition")
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
        const previous = command.status(s.command_run)
        if (previous.state === "running" || previous.state === "unknown_or_interrupted")
          throw new Error("Command Code run not known complete")
        if (!previous.result?.sessionId) throw new Error("No resumable Command Code session")
        ensureWorktree(stateDir(s.cwd), s.cwd, s.id)
        if (continuation) s.continuations = (s.continuations ?? 0) + 1
        else s.attempts++
        s.backend = "command-transition"
        s.command_run = undefined
        save(s)
        s.command_run = command.start(s.cwd, stateDir(s.cwd),
          prompt(s) + (continuation ? "\nCONTINUE THE SAME TASK FROM WHERE THE TURN LIMIT STOPPED IT: " :
            "\nSAME-SCOPE CORRECTION ONLY: ") + correction,
          fallbackEffortFor(s), s.tier === "scout", previous.result.sessionId, fallbackModelFor(s))
        s.backend = "command-code"
        save(s)
      }
      return { session_id: s.id, backend: s.backend, status: "admitted" }
      })
    },
    async cancel(cwd: unknown, id: unknown) {
      return withSessionLock(cwd, id, async (s) => {
      let interrupted = false
      if (s.backend === "pi") {
        if (!s.pi_id) throw new Error("Missing Pi session")
        interrupted = (await makeWorkerBridge(api, primaryFor(s)).cancel(s.cwd, s.pi_id)).interrupted
      } else if (s.command_run) interrupted = command.cancel(s.command_run)
      return { session_id: s.id, interrupted,
        note: "Never signal a Command Code PID left by an earlier MCP process; it may have been reused." }
      })
    },
  }
}
