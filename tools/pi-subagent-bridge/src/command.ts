import { spawn, type ChildProcess } from "node:child_process"
import { appendFileSync, closeSync, openSync, readFileSync, readSync, statSync } from "node:fs"
import { randomUUID } from "node:crypto"

export const COMMAND_MODEL = "deepseek/deepseek-v4.1-flash"
export const COMMAND_EMBER_MODEL = "meta/muse-ember"
export type Effort = "low" | "medium" | "high" | "xhigh" | "max"
export type CommandRun = { pid: number; output: string; errors: string; started_at: string }
export type CommandResult = {
  subtype: "success" | "error" | "max_turns"
  sessionId?: string
  stopReason?: string
  usage?: unknown
  finalText?: string
  error?: unknown
}

const children = new Map<number, ChildProcess>()
const MAX_TURNS: Record<Effort, number> = { low: 150, medium: 300, high: 500, xhigh: 650, max: 800 }
const READ_ONLY_MAX_TURNS = 100

export function startCommand(directory: string, logDirectory: string, text: string,
  effort: Effort, readOnly: boolean, resume?: string, model: string = COMMAND_MODEL): CommandRun {
  if (model !== COMMAND_MODEL && model !== COMMAND_EMBER_MODEL) throw new Error("Unapproved Command Code model")
  const suffix = randomUUID()
  const output = `${logDirectory}/${suffix}.ndjson`
  const errors = `${logDirectory}/${suffix}.stderr`
  const stdout = openSync(output, "wx", 0o600)
  const stderr = openSync(errors, "wx", 0o600)
  const args = [
    "-p", text,
    "--model", model,
    "--effort", effort,
    "--output-format", "json",
    "--max-turns", String(readOnly ? READ_ONLY_MAX_TURNS : MAX_TURNS[effort]),
    "--skip-onboarding", "--no-auto-update", "--trust", "--no-skills",
    ...(readOnly ? ["--plan"] : ["--yolo"]),
    ...(resume ? ["--resume", resume] : []),
  ]
  try {
    const child = spawn("cmd", args, {
      cwd: directory, detached: true,
      stdio: ["ignore", stdout, stderr],
    })
    const pid = child.pid
    child.on("error", (error: Error) => {
      if (pid !== undefined) children.delete(pid)
      appendFileSync(errors, "spawn error: " + error.message + "\n")
    })
    child.on("close", () => {
      if (pid !== undefined) children.delete(pid)
    })
    if (pid === undefined) throw new Error("Cannot start Command Code: cmd missing or not executable")
    children.set(pid, child)
    child.unref()
    return { pid, output, errors, started_at: new Date().toISOString() }
  } finally {
    closeSync(stdout)
    closeSync(stderr)
  }
}

export function commandResult(run: CommandRun): { state: string; result: CommandResult | null; stderr: string | null } {
  let tail = ""
  try {
    const fs = statSync(run.output)
    const max = 1024 * 1024
    const size = Math.min(max, fs.size)
    const fh = openSync(run.output, "r")
    try {
      const buf = Buffer.alloc(size)
      const got = readSync(fh, buf, 0, buf.length, fs.size - size)
      tail = buf.subarray(0, got).toString("utf8")
    } finally { closeSync(fh) }
  } catch { /* A failed spawn can produce no stdout. */ }
  let last: CommandResult | null = null
  for (const line of tail.split("\n")) {
    if (!line.trim().startsWith("{")) continue
    try {
      const raw: unknown = JSON.parse(line)
      if (raw && typeof raw === "object" && "type" in raw && raw.type === "result" &&
        "subtype" in raw && (raw.subtype === "success" || raw.subtype === "error" || raw.subtype === "max_turns")) {
        last = raw as CommandResult
      }
    } catch { /* Unfinished stream write. */ }
  }
  let stderr: string | null = null
  if (last === null) {
    try { stderr = readFileSync(run.errors, "utf8").slice(-2000) || null } catch { /* No stderr yet. */ }
  }
  if (last) {
    const state = last.subtype === "success" ? "succeeded" : last.subtype === "max_turns" ? "turn_limit" : "failed"
    return { state, result: last, stderr }
  }
  if (children.has(run.pid) || processAlive(run.pid)) return { state: "running", result: null, stderr }
  if (stderr?.includes("spawn error:")) return { state: "failed", result: null, stderr }
  return { state: "unknown_or_interrupted", result: null, stderr }
}

function processAlive(pid: number): boolean {
  try {
    process.kill(pid, 0)
    return true
  } catch (error) {
    return (error as NodeJS.ErrnoException).code === "EPERM"
  }
}

export function cancelCommand(run: CommandRun): boolean {
  const child = children.get(run.pid)
  if (!child) return false
  return child.kill("SIGTERM")
}
