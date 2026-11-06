import { execFileSync } from "node:child_process"
import { randomUUID } from "node:crypto"
import { accessSync, constants, mkdirSync, readFileSync, renameSync, writeFileSync } from "node:fs"
import { dirname, join, resolve } from "node:path"
import { checkedWorktree, GO_MODEL, makeWorkerBridge, type OpenCodePort } from "./bridge.ts"
import { cancelCommand, COMMAND_MODEL, commandResult, startCommand, type CommandRun, type Effort } from "./command.ts"

export type Tier = "scout" | "mechanic" | "worker" | "expert" | "god"
export type Scope = {
  base_revision: string
  writable_paths: string[]
  acceptance_proof: string
  attempt_limit: 1 | 2
  stop_on: string
}
type Session = {
  id: string; cwd: string; title: string; tier: Tier; scope: Scope; task: string
  backend: "opencode" | "command-code"; attempts: number
  opencode_id?: string; command_run?: CommandRun; fallback_reason?: string
}
const EFFORT: Record<Tier, Effort> = {
  scout: "low", mechanic: "low", worker: "high", expert: "max", god: "max",
}
const QUOTA = /\b(429|rate[ -]?limit(ed)?|quota|usage[ -]?limit|allowance exhausted|insufficient credits|credits? exhausted|resource_exhausted|too many requests)\b/i

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
  const path = pathFor(s.cwd, s.id), tmp = path + ".tmp"
  writeFileSync(tmp, JSON.stringify(s), { mode: 0o600 })
  renameSync(tmp, path)
}
function load(cwd: unknown, id: unknown): Session {
  const dir = checkedWorktree(cwd)
  const s = JSON.parse(readFileSync(pathFor(dir, required(id, "session_id", 64)), "utf8")) as Session
  if (s.cwd !== dir || !isTier(s.tier)) throw new Error("Session/worktree mismatch")
  scopeFor(s.scope, s.tier, dir, false)
  return s
}
function modelFor(tier: Tier) { return { ...GO_MODEL, variant: EFFORT[tier] } }
function cmdAvailable(): boolean {
  for (const part of (process.env.PATH || "").split(":")) {
    if (!part) continue
    try { accessSync(resolve(part, "cmd"), constants.X_OK); return true } catch { /* continue */ }
  }
  return false
}
function prompt(s: Session): string {
  return [
    "You execute a single scoped task on DeepSeek V4.1 Flash. Claude Opus only coordinates.",
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

export function makeHybridBridge(api: OpenCodePort, command = {
  start: startCommand, status: commandResult, cancel: cancelCommand, available: cmdAvailable,
}) {
  function fallback(s: Session, reason: string): Session {
    if (!command.available()) throw new Error("OpenCode " + reason + "; Command Code cmd unavailable")
    if (!untouched(s)) throw new Error("Fallback forbidden after partial edits; inspect the worktree")
    const dir = stateDir(s.cwd)
    s.command_run = command.start(s.cwd, dir, prompt(s), EFFORT[s.tier], s.tier === "scout")
    s.backend = "command-code"
    s.fallback_reason = reason
    s.attempts = 1
    save(s)
    return s
  }
  return {
    async modelCheck(cwd: unknown, tierInput: unknown) {
      const dir = checkedWorktree(cwd)
      if (!isTier(tierInput)) throw new Error("Unknown DeepSeek tier")
      let available = false, issue: string | null = null
      try { available = (await makeWorkerBridge(api, modelFor(tierInput)).modelCheck(dir)).available }
      catch (e) { issue = String(e) }
      return {
        primary: { backend: "opencode", model: modelFor(tierInput), available, issue },
        fallback: { backend: "command-code", model: COMMAND_MODEL, effort: EFFORT[tierInput], installed: command.available() },
      }
    },
    async start(cwd: unknown, title: unknown, tierInput: unknown, scopeInput: unknown, brief: unknown) {
      const dir = checkedWorktree(cwd, true)
      if (!isTier(tierInput)) throw new Error("Unknown DeepSeek tier")
      if (git(dir, "status", "--porcelain", "--untracked-files=all")) throw new Error("Worker worktree must start clean")
      const task = required(brief, "brief", 32000)
      const s: Session = { id: "usrw_" + randomUUID(), cwd: dir, tier: tierInput,
        title: required(title, "title", 100), scope: scopeFor(scopeInput, tierInput, dir),
        task, backend: "opencode", attempts: 0 }
      const worker = makeWorkerBridge(api, modelFor(tierInput))
      let available: boolean
      try { available = (await worker.modelCheck(dir)).available }
      catch (e) {
        if (!quota(e)) throw e
        fallback(s, "quota-limited model check")
        return { session_id: s.id, backend: s.backend, status: "admitted" }
      }
      if (!available) {
        fallback(s, "pinned OpenCode model unavailable")
        return { session_id: s.id, backend: s.backend, status: "admitted" }
      }
      try {
        const admitted = await worker.start(dir, s.title, prompt(s), tierInput === "scout")
        s.opencode_id = admitted.session_id
        s.attempts = 1
        save(s)
        return { session_id: s.id, backend: s.backend, status: "admitted", model: modelFor(s.tier) }
      } catch (e) {
        if (!quota(e)) throw e
        fallback(s, "OpenCode quota-limited admission")
        return { session_id: s.id, backend: s.backend, status: "admitted" }
      }
    },
    async status(cwd: unknown, id: unknown) {
      const s = load(cwd, id)
      let state: string, last_assistant_text: string | null, error: unknown = null, usage: unknown = null
      if (s.backend === "opencode") {
        if (!s.opencode_id) throw new Error("Missing OpenCode session")
        const response = await makeWorkerBridge(api, modelFor(s.tier)).status(s.cwd, s.opencode_id)
        state = typeof response.state === "string" ? response.state : "unknown"
        last_assistant_text = response.last_assistant_text
        error = response.error
        usage = { cost_reported_usd: response.cost_reported_usd, tokens: response.tokens }
        if (state !== "running" && state !== "queued" && state !== "succeeded" &&
          quota(error)) {
          if (!untouched(s)) state = "blocked_partial_work"
          else {
            fallback(s, "OpenCode quota/usage failure")
            state = "running"
            last_assistant_text = null
          }
        }
      } else {
        if (!s.command_run) throw new Error("Missing Command Code process")
        const response = command.status(s.command_run)
        state = response.state
        last_assistant_text = response.result?.finalText?.slice(-5000) ?? null
        error = response.result?.error ?? response.stderr
        usage = response.result?.usage ?? null
      }
      const changed_paths = changes(s.cwd, s.scope.base_revision)
      const out_of_scope_paths = outside(changed_paths, s.scope.writable_paths)
      const head_unchanged = git(s.cwd, "rev-parse", "HEAD") === s.scope.base_revision
      return {
        session_id: s.id, backend: s.backend, tier: s.tier,
        model: s.backend === "opencode" ? modelFor(s.tier) : COMMAND_MODEL,
        effort: EFFORT[s.tier], state, last_assistant_text, error, usage,
        changed_paths, out_of_scope_paths, head_unchanged,
        acceptance_blocked: !head_unchanged || out_of_scope_paths.length > 0,
        fallback_reason: s.fallback_reason ?? null,
        note: "Proof must be checked independently. Review the diff once before integration.",
      }
    },
    async resume(cwd: unknown, id: unknown, feedback: unknown) {
      const s = load(cwd, id)
      const correction = required(feedback, "feedback", 32000)
      if (s.attempts >= s.scope.attempt_limit) throw new Error("Task attempt limit reached")
      if (git(s.cwd, "rev-parse", "HEAD") !== s.scope.base_revision ||
        outside(changes(s.cwd, s.scope.base_revision), s.scope.writable_paths).length)
        throw new Error("Cannot resume changed HEAD or out-of-scope work")
      if (s.backend === "opencode") {
        if (!s.opencode_id) throw new Error("Missing OpenCode session")
        await makeWorkerBridge(api, modelFor(s.tier)).resume(s.cwd, s.opencode_id, "Same-scope correction only: " + correction)
      } else {
        if (!s.command_run) throw new Error("Missing Command Code process")
        const previous = command.status(s.command_run)
        if (previous.state === "running" || previous.state === "unknown_or_interrupted")
          throw new Error("Command Code run not known complete")
        if (!previous.result?.sessionId) throw new Error("No resumable Command Code session")
        s.command_run = command.start(s.cwd, stateDir(s.cwd),
          prompt(s) + "\nSAME-SCOPE CORRECTION ONLY: " + correction,
          EFFORT[s.tier], s.tier === "scout", previous.result.sessionId)
      }
      s.attempts++
      save(s)
      return { session_id: s.id, backend: s.backend, status: "admitted" }
    },
    async cancel(cwd: unknown, id: unknown) {
      const s = load(cwd, id)
      let interrupted = false
      if (s.backend === "opencode") {
        if (!s.opencode_id) throw new Error("Missing OpenCode session")
        interrupted = (await makeWorkerBridge(api, modelFor(s.tier)).cancel(s.cwd, s.opencode_id)).interrupted
      } else if (s.command_run) interrupted = command.cancel(s.command_run)
      return { session_id: s.id, interrupted,
        note: "Never signal a Command Code PID left by an earlier MCP process; it may have been reused." }
    },
  }
}
