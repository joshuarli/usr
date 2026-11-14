import { execFileSync, spawn, type ChildProcess } from "node:child_process"
import { appendFileSync, closeSync, openSync, readFileSync, readSync, statSync } from "node:fs"
import { randomUUID } from "node:crypto"

import { COMMAND_MODEL, COMMAND_EMBER_MODEL, isBannedModel, type CliPin, type Effort } from "./policy.ts"
export { COMMAND_MODEL, COMMAND_EMBER_MODEL, type Effort } from "./policy.ts"
export type CommandRun = { pid: number; output: string; errors: string; started_at: string; proc_start?: string | null }
export type CommandResult = {
  subtype: "success" | "error" | "max_turns"
  sessionId?: string
  stopReason?: string
  usage?: unknown
  finalText?: string
  error?: unknown
}

const children = new Map<number, ChildProcess>()
const MAX_TURNS = 100_000

export function startCommand(directory: string, logDirectory: string, text: string,
  effort: Effort, readOnly: boolean, resume?: string, model: string = COMMAND_MODEL, admittedPin?: CliPin): CommandRun {
  const approved = admittedPin
    ? admittedPin.model === model && admittedPin.effort === effort
    : model === COMMAND_MODEL || model === COMMAND_EMBER_MODEL
  if (!model || isBannedModel(model) || !approved)
    throw new Error("Unapproved Command Code model and effort" + (admittedPin ? "; preserve the admitted pin or reconcile the session" : ""))
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
    "--verbose",
    "--max-turns", String(MAX_TURNS),
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
    return { pid, output, errors, started_at: new Date().toISOString(), proc_start: processStartTime(pid) }
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
  const identity = children.has(run.pid) ? "same" : processIdentity(run)
  if (identity === "same" || identity === "unknown") return { state: "running", result: null, stderr }
  if (stderr?.includes("spawn error:")) return { state: "failed", result: null, stderr }
  return { state: "interrupted", result: null, stderr }
}

export function processStartTime(pid: number): string | null {
  if (process.platform === "linux") {
    try {
      const stat = readFileSync("/proc/" + pid + "/stat", "utf8")
      const end = stat.lastIndexOf(")")
      if (end < 0) return null
      return stat.slice(end + 1).trim().split(/\s+/)[19] || null
    } catch { return null }
  }
  try {
    const value = execFileSync("ps", ["-o", "lstart=", "-p", String(pid)], {
      encoding: "utf8", timeout: 5000,
    }).trim()
    return value || null
  } catch { return null }
}

export function processIdentity(run: CommandRun): "same" | "different" | "gone" | "unknown" {
  if (!processAlive(run.pid)) return "gone"
  if (!run.proc_start) return "unknown"
  const current = processStartTime(run.pid)
  if (current === null) return "unknown"
  return current === run.proc_start ? "same" : "different"
}

export function commandSession(run: CommandRun): string | null {
  const result = commandResult(run).result
  if (result?.sessionId) return result.sessionId
  try {
    return /^session:[ \t]*(\S+)[ \t]*$/m.exec(readFileSync(run.errors, "utf8"))?.[1] ?? null
  } catch { return null }
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
