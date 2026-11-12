import { execFileSync } from "node:child_process"
import { realpathSync } from "node:fs"
import { dirname, isAbsolute, relative, resolve, sep } from "node:path"

export type ModelRef = { id: string; providerID: string; variant?: string }
export type SessionArgs = { sessionID: string; cwd?: string }
export type OpenCodePort = {
  create(input: { title: string; agent: "build" | "plan"; model: ModelRef; location: { directory: string }; metadata: { usr_worker_v1: { directory: string; model: ModelRef } } }): Promise<unknown>
  prompt(input: SessionArgs & { text: string }): Promise<unknown>
  steer(input: SessionArgs & { text: string }): Promise<unknown>
  get(input: SessionArgs): Promise<unknown>
  active(input?: { cwd?: string }): Promise<unknown>
  inbox(input: SessionArgs): Promise<unknown>
  messages(input: SessionArgs & { order: "desc"; limit: number }): Promise<unknown>
  interrupt(input: SessionArgs): Promise<unknown>
  models(input: { location: { directory: string } }): Promise<unknown>
}

export class PreAdmissionError extends Error {}

const SESSION_PREFIX = "usr-worker: "
const MAX_BRIEF = 32_000
export const GO_MODEL: ModelRef = { providerID: "opencode-go", id: "deepseek-v4.1-flash", variant: "high" }
export const DEFAULT_MODEL = GO_MODEL
const SESSION_METADATA_KEY = "usr_worker_v1" as const
export function selectedModel(value = process.env.USR_PI_SUBAGENT_MODEL): ModelRef {
  if (value === undefined || value === "go") return GO_MODEL
  throw new Error("Only the pinned OpenCode Go model is permitted; no silent model fallback")
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === "object" && !Array.isArray(value)
}
function object(value: unknown): Record<string, unknown> {
  if (!isRecord(value)) throw new Error("Unexpected OpenCode response")
  return value
}
function unbox(value: unknown): unknown {
  if (Array.isArray(value)) return value
  const record = object(value)
  return Object.hasOwn(record, "data") ? record.data : record
}
function field(value: unknown, key: string): unknown {
  return object(value)[key]
}
function requiredText(value: unknown, label: string, max = MAX_BRIEF): string {
  if (typeof value !== "string" || !value.trim() || value.length > max) {
    throw new Error(`${label} must be nonempty and at most ${max} characters`)
  }
  return value
}
function git(cwd: string, ...args: string[]): string {
  return execFileSync("git", ["-C", cwd, ...args], { encoding: "utf8", timeout: 10_000, maxBuffer: 1_000_000 }).trim()
}

/** Never create, reset, clean, merge, or delete a worktree here: the parent owns that lifecycle. */
export function checkedWorktree(directory: unknown, requireClean = false): string {
  const input = requiredText(directory, "cwd", 4096)
  if (!isAbsolute(input)) throw new Error("cwd must be an absolute path to a dedicated Git worktree")
  const cwd = realpathSync(input)
  const top = realpathSync(git(cwd, "rev-parse", "--show-toplevel"))
  if (cwd !== top) throw new Error("cwd must be the worktree root, not a subdirectory")
  const commonDir = realpathSync(git(cwd, "rev-parse", "--path-format=absolute", "--git-common-dir"))
  const gitDir = realpathSync(git(cwd, "rev-parse", "--path-format=absolute", "--git-dir"))
  if (commonDir === gitDir) throw new Error("Refusing the primary worktree")
  const worktreesRoot = resolve(dirname(commonDir), ".work", "wt")
  const name = relative(worktreesRoot, cwd)
  if (!name || name === "." || name === ".." || name.startsWith(`..${sep}`) || name.includes(sep)) {
    throw new Error("Worker worktrees must be immediate children of <repo>/.work/wt/")
  }
  if (requireClean && git(cwd, "status", "--porcelain", "--untracked-files=all")) {
    throw new Error("New worker worktree must be clean; preserve or review existing changes first")
  }
  return cwd
}

function statusLines(cwd: string): string[] {
  const output = git(cwd, "status", "--short", "--untracked-files=all")
  return output ? output.split("\n").slice(0, 100) : []
}
function sameModel(actual: unknown, expected: ModelRef): boolean {
  if (!actual || typeof actual !== "object") return false
  const record = object(actual)
  return record.id === expected.id && record.providerID === expected.providerID &&
    (expected.variant === undefined || record.variant === expected.variant)
}
function modelAvailable(value: unknown, model: ModelRef): boolean {
  const response = unbox(value)
  const models = Array.isArray(response) ? response : field(response, "items")
  if (!Array.isArray(models)) throw new Error("Unexpected OpenCode model list")
  return models.some((item) => {
    if (!item || typeof item !== "object") return false
    const record = object(item)
    const variants = record.variants
    return (record.id === model.id || record.modelID === model.id) && record.providerID === model.providerID &&
      (model.variant === undefined || (Array.isArray(variants) && variants.some((v) => field(v, "id") === model.variant))) &&
      record.enabled !== false && record.status !== "deprecated"
  })
}
function queuedInputs(value: unknown): number {
  const result = unbox(value)
  const queue = Array.isArray(result) ? result : field(result, "items")
  if (!Array.isArray(queue)) throw new Error("Unexpected OpenCode session inbox")
  return queue.length
}
function activeSession(value: unknown, sessionID: string): boolean {
  const result = unbox(value)
  if (Array.isArray(result)) return result.some((item) => item === sessionID || (item && typeof item === "object" && field(item, "id") === sessionID))
  return Object.hasOwn(object(result), sessionID)
}
function latestAssistant(value: unknown): string | null {
  const result = unbox(value)
  const items = Array.isArray(result) ? result : field(result, "items")
  if (!Array.isArray(items)) return null
  for (const item of items) {
    if (!item || typeof item !== "object") continue
    const record = object(item)
    const info = isRecord(record.info) ? record.info : record
    if (info.role !== "assistant" && record.type !== "assistant") continue
    const parts = Array.isArray(record.parts) ? record.parts : record.content
    if (!Array.isArray(parts)) continue
    const text = parts.filter((p) => p && typeof p === "object" && field(p, "type") === "text")
      .map((p) => field(p, "text")).filter((s): s is string => typeof s === "string").join("\n")
    if (text) return text.slice(-5000)
  }
  return null
}

function latestAssistantError(value: unknown): unknown {
  const response = unbox(value)
  const items = Array.isArray(response) ? response : field(response, "items")
  if (!Array.isArray(items)) return null
  for (const item of items) {
    if (!isRecord(item)) continue
    const info = isRecord(item.info) ? item.info : item
    if ((info.role === "assistant" || item.type === "assistant") && info.error) return info.error
  }
  return null
}

export function makeWorkerBridge(api: OpenCodePort, model = selectedModel()) {
  async function ownedSession(sessionID: unknown, cwd: unknown): Promise<{ id: string; directory: string; info: Record<string, unknown> }> {
    const id = requiredText(sessionID, "session_id", 128)
    if (!/^ses_[a-zA-Z0-9_-]+$/.test(id)) throw new Error("Invalid OpenCode session ID")
    const directory = checkedWorktree(cwd)
    const info = object(unbox(await api.get({ sessionID: id, cwd: directory })))
    const location = object(info.location)
    const metadata = object(info.metadata)
    const ownership = object(metadata[SESSION_METADATA_KEY])
    if (info.title !== undefined && (typeof info.title !== "string" || !info.title.startsWith(SESSION_PREFIX))) {
      throw new Error("Refusing a session not started by usr worker bridge")
    }
    if (info.title === undefined || location.directory !== directory || !sameModel(info.model, model) ||
      ownership.directory !== directory || !sameModel(ownership.model, model)) {
      throw new Error("Session ownership, worktree, or model mismatch; refusing to act")
    }
    return { id, directory, info }
  }
  return {
    async modelCheck(cwd: unknown) {
      const directory = checkedWorktree(cwd)
      return { model, available: modelAvailable(await api.models({ location: { directory } }), model) }
    },
    async start(cwd: unknown, title: unknown, brief: unknown, readOnly = false) {
      const directory = checkedWorktree(cwd, true)
      const name = requiredText(title, "title", 100)
      const text = requiredText(brief, "brief")
      try {
        if (!modelAvailable(await api.models({ location: { directory } }), model))
          throw new Error(`Pinned model ${model.providerID}/${model.id}${model.variant ? "#" + model.variant : ""} unavailable. No fallback.`)
      } catch (error) {
        throw new PreAdmissionError(String(error), { cause: error })
      }
      const result = object(unbox(await api.create({
        title: SESSION_PREFIX + name, agent: readOnly ? "plan" : "build", model, location: { directory },
        metadata: { [SESSION_METADATA_KEY]: { directory, model } },
      })))
      const id = requiredText(result.id, "OpenCode session ID", 128)
      const prompt = [
        "You are the normal implementation worker for usr/orchestrate, not the orchestrator.",
        "Work only inside this Git worktree and the assigned write boundary. Do not spawn subagents.",
        "No commits, merges, branch changes, worktree cleanup, or edits outside the brief.",
        "Run only the specified acceptance checks; stop and report any blocker, missing authority, or ambiguous design decision.",
        "Report changed files, checks with results, and unverified work. The parent will review and integrate.",
        "", text,
      ].join("\n")
      try {
        await api.prompt({ sessionID: id, cwd: directory, text: prompt })
      } catch (error) {
        throw new Error(`OpenCode session ${id} created but prompt admission failed: ${String(error)}. Inspect before retrying.`)
      }
      return { session_id: id, cwd: directory, model, status: "admitted", note: "Prompt admitted; use worker_status for durable execution outcome." }
    },
    async status(cwd: unknown, sessionID: unknown) {
      const { id, directory, info } = await ownedSession(sessionID, cwd)
      const [active, inbox, messages] = await Promise.all([
        api.active({ cwd: directory }), api.inbox({ sessionID: id, cwd: directory }), api.messages({ sessionID: id, cwd: directory, order: "desc", limit: 30 }),
      ])
      const running = activeSession(active, id)
      const pending = queuedInputs(inbox)
      return {
        session_id: id, cwd: directory, model, state: running ? "running" : pending ? "queued" : (info.outcome ?? "idle_or_queued"),
        pending_inputs: pending,
        cost_reported_usd: info.cost ?? null, tokens: info.tokens ?? null, error: info.error ?? latestAssistantError(messages),
        last_assistant_text: latestAssistant(messages), git_status: statusLines(directory),
        note: "Status is observational; verify the diff and acceptance checks before integration.",
      }
    },
    async resume(cwd: unknown, sessionID: unknown, feedback: unknown) {
      const { id, directory } = await ownedSession(sessionID, cwd)
      requiredText(feedback, "feedback")
      const [active, inbox] = await Promise.all([api.active({ cwd: directory }), api.inbox({ sessionID: id, cwd: directory })])
      if (activeSession(active, id) || queuedInputs(inbox)) throw new Error("Worker is running or has queued input; do not enqueue competing feedback")
      await api.prompt({ sessionID: id, cwd: directory, text: `Parent feedback (same scope and write boundaries):\n${feedback}` })
      return { session_id: id, cwd: directory, status: "admitted" }
    },
    async steer(cwd: unknown, sessionID: unknown, note: unknown) {
      const { id, directory } = await ownedSession(sessionID, cwd)
      const text = "PARENT STEERING (same scope and write boundaries):\n" + requiredText(note, "note")
      const receipt = object(unbox(await api.steer({ sessionID: id, cwd: directory, text })))
      return { session_id: id, cwd: directory, receipt }
    },
    async cancel(cwd: unknown, sessionID: unknown) {
      const { id, directory } = await ownedSession(sessionID, cwd)
      const reply = object(unbox(await api.interrupt({ sessionID: id, cwd: directory })))
      return { session_id: id, interrupted: reply.interrupted === true, note: "Inspect status and worktree; do not delete it." }
    },
  }
}
