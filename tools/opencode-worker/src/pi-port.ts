import { execFileSync, spawn, type ChildProcess } from "node:child_process"
import { randomUUID } from "node:crypto"
import { appendFileSync, closeSync, mkdirSync, openSync, readFileSync, readdirSync, readSync, statSync, writeFileSync } from "node:fs"
import { dirname, join } from "node:path"
import type { ModelRef, OpenCodePort } from "./bridge.ts"

type StoredRun = { pid: number; output: string; errors: string }
type Stored = {
  id: string; title: string; model: ModelRef; directory: string
  metadata: { usr_worker_v1: { directory: string; model: ModelRef } }
  readOnly: boolean; run?: StoredRun
}
type Outcome = { state: string; text: string | null; error: unknown; usage: unknown }

const children = new Map<number, ChildProcess>()
const supported: Record<string, string[]> = {
  "deepseek-v4.1-flash": ["high", "max"],
  "muse-spark-1.3-contributor": ["medium", "high"],
}
function stateDirectory(cwd: string): string {
  const common = execFileSync("git", ["-C", cwd, "rev-parse", "--path-format=absolute", "--git-common-dir"],
    { encoding: "utf8", timeout: 10000 }).trim()
  const directory = join(dirname(common), ".work", "worker-bridge")
  execFileSync("git", ["-C", dirname(common), "check-ignore", "-q", ".work/worker-bridge/state"],
    { timeout: 10000, stdio: "ignore" })
  mkdirSync(directory, { recursive: true, mode: 0o700 })
  return directory
}
function recordPath(cwd: string, id: string): string {
  if (!/^ses_[a-z0-9]{32}$/.test(id)) throw new Error("Invalid Pi worker session ID")
  return join(stateDirectory(cwd), id + ".pi.json")
}
function load(cwd: string | undefined, id: string): Stored {
  if (!cwd) throw new Error("Pi worker needs an explicit worktree path")
  const s: Stored = JSON.parse(readFileSync(recordPath(cwd, id), "utf8"))
  if (s.id !== id || s.directory !== cwd) throw new Error("Pi worker session ownership mismatch")
  return s
}
function save(s: Stored): void {
  writeFileSync(recordPath(s.directory, s.id), JSON.stringify(s), { mode: 0o600 })
}
function tail(path: string): string {
  try {
    const size = statSync(path).size, count = Math.min(size, 2_000_000)
    const fd = openSync(path, "r")
    try {
      const bytes = Buffer.alloc(count), got = readSync(fd, bytes, 0, count, size - count)
      return bytes.subarray(0, got).toString("utf8")
    } finally { closeSync(fd) }
  } catch { return "" }
}
function alive(pid: number): boolean {
  if (children.has(pid)) return true
  try { process.kill(pid, 0); return true }
  catch (error) { return (error as NodeJS.ErrnoException).code === "EPERM" }
}
function observe(s: Stored): Outcome {
  if (!s.run) return { state: "queued", text: null, error: null, usage: null }
  let settled: boolean | null = null, text: string | null = null, error: unknown = null, usage: unknown = null
  for (const line of tail(s.run.output).split("\n")) {
    if (!line.startsWith("{")) continue
    let event: Record<string, unknown>
    try {
      const parsed: unknown = JSON.parse(line)
      if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) continue
      event = parsed as Record<string, unknown>
    } catch { continue }
    if (event.type === "message_end" && event.message && typeof event.message === "object") {
      const message = event.message as Record<string, unknown>
      if (message.role !== "assistant") continue
      if (Array.isArray(message.content)) {
        const blocks = message.content as Array<{ type?: string; text?: string }>
        const combined = blocks.filter((part) => part?.type === "text" && typeof part.text === "string")
          .map((part) => part.text).join("")
        if (combined) text = combined.slice(-5000)
      }
      if (message.usage) usage = message.usage
      error = message.errorMessage ?? message.error ??
        (message.stopReason === "error" ? "Pi provider error" : null)
    }
    if (event.type === "auto_retry_end" && event.success === false)
      error = event.finalError ?? "Pi provider retry exhausted"
    if (event.type === "agent_settled") settled = event.aborted === true
  }
  if (settled !== null) {
    if (settled) return { state: "cancelled", text, error: error ?? "Pi aborted", usage }
    if (error) return { state: "failed", text, error, usage }
    return text ? { state: "succeeded", text, error: null, usage } :
      { state: "failed", text, error: "Pi settled without assistant text", usage }
  }
  if (alive(s.run.pid)) return { state: "running", text, error: null, usage }
  return { state: "unknown_or_interrupted", text, error: tail(s.run.errors) || "Pi stopped without agent_settled", usage }
}
function start(s: Stored, prompt: string): StoredRun {
  const { model } = s, directory = stateDirectory(s.directory)
  const name = randomUUID(), output = join(directory, name + ".pi.jsonl")
  const errors = join(directory, name + ".pi.stderr")
  const stdout = openSync(output, "wx", 0o600), stderr = openSync(errors, "wx", 0o600)
  const args = [
    "--mode", "json", "--no-extensions", "--no-mcp", "--no-skills",
    "--no-context-files", "--no-prompt-templates", "--no-themes", "--no-approve",
    "--provider", model.providerID, "--model", model.providerID + "/" + model.id,
    "--thinking", model.variant ?? "high", "--session-id", s.id,
    "--tools", s.readOnly ? "read,grep,find,ls" : "read,bash,edit,write,grep,find,ls",
    "--", prompt,
  ]
  try {
    const child = spawn("pi", args, { cwd: s.directory, detached: true, stdio: ["ignore", stdout, stderr] })
    const pid = child.pid
    child.on("error", (error) => {
      if (pid !== undefined) children.delete(pid)
      try { appendFileSync(errors, "spawn error: " + error.message + "\n") } catch { /* preserve admission error */ }
    })
    child.on("close", () => { if (pid !== undefined) children.delete(pid) })
    if (pid === undefined) throw new Error("Cannot launch pi")
    children.set(pid, child)
    child.unref()
    return { pid, output, errors }
  } finally { closeSync(stdout); closeSync(stderr) }
}
function catalog(): string {
  return execFileSync("pi", ["--list-models", "opencode-go"],
    { encoding: "utf8", timeout: 15000, maxBuffer: 4_000_000 })
}
function modelsAvailable(): { id: string; providerID: string; variants: { id: string }[] }[] {
  const output = catalog()
  return Object.entries(supported).filter(([id]) => output.includes(id)).map(([id, variants]) =>
    ({ id, providerID: "opencode-go", variants: variants.map((variant) => ({ id: variant })) }))
}
export function piPort(): OpenCodePort {
  return {
    async models() {
      return { data: modelsAvailable() }
    },
    async create(input) {
      const id = "ses_" + randomUUID().replaceAll("-", "")
      const s: Stored = {
        id, title: input.title, model: input.model, directory: input.location.directory,
        metadata: input.metadata, readOnly: input.agent === "plan",
      }
      save(s)
      return { data: { id } }
    },
    async prompt(input) {
      const s = load(input.cwd, input.sessionID)
      if (s.run) {
        const result = observe(s)
        if (!["succeeded", "failed", "cancelled"].includes(result.state))
          throw new Error("Pi worker is not terminal; refusing overlapping prompt")
      }
      s.run = start(s, input.text)
      save(s)
      return { data: { admitted: true } }
    },
    async get(input) {
      const s = load(input.cwd, input.sessionID), result = observe(s)
      return { data: {
        id: s.id, title: s.title, model: s.model, location: { directory: s.directory },
        metadata: s.metadata, outcome: result.state, error: result.error, tokens: result.usage,
      } }
    },
    async active(input) {
      if (!input?.cwd) return { data: {} }
      const directory = stateDirectory(input.cwd), sessions: Record<string, boolean> = {}
      for (const name of readdirSync(directory)) {
        if (!/^ses_[a-z0-9]{32}\.pi\.json$/.test(name)) continue
        const id = name.slice(0, -8), s = load(input.cwd, id)
        if (observe(s).state === "running") sessions[id] = true
      }
      return { data: sessions }
    },
    async inbox() { return { data: [] } },
    async messages(input) {
      const result = observe(load(input.cwd, input.sessionID))
      return { data: [{ info: { role: "assistant", error: result.error },
        parts: result.text ? [{ type: "text", text: result.text }] : [] }] }
    },
    async interrupt(input) {
      const s = load(input.cwd, input.sessionID), child = s.run && children.get(s.run.pid)
      return { data: { interrupted: child ? child.kill("SIGTERM") : false } }
    },
  }
}
