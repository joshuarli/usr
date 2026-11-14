import { randomUUID } from "node:crypto"
import { spawn, spawnSync, type ChildProcess } from "node:child_process"
import { appendFileSync, closeSync, fstatSync, openSync, readSync } from "node:fs"
import { groupAlive, processIdentity, processStartTime, type CommandResult, type CommandRun, type Effort } from "./command.ts"

import { ANTIGRAVITY_PIN, isBannedModel, type CliPin } from "./policy.ts"

const children = new Map<number, ChildProcess>()

export function antigravityAvailable(pin: CliPin = ANTIGRAVITY_PIN): boolean {
  try {
    const check = spawnSync("agy", ["models"], { encoding: "utf8", timeout: 5000, stdio: ["ignore", "pipe", "pipe"] })
    return check.status === 0 && check.stdout.split("\n").some(line => line.trim().split(/\s+/)[0] === pin.model)
  } catch { return false }
}

export function startAntigravity(directory: string, logDirectory: string, prompt: string, effort: Effort,
  readOnly: boolean, resume?: string, model?: string, pin: CliPin = ANTIGRAVITY_PIN): CommandRun {
  if (model !== pin.model || effort !== pin.effort || readOnly || isBannedModel(pin.model))
    throw new Error("Unapproved Antigravity model, effort, or tool scope; expected " + pin.model + " (" + pin.effort + ")")
  if (resume && !/^[a-f0-9-]{36}$/i.test(resume)) throw new Error("Invalid Antigravity conversation ID")
  const suffix = randomUUID()
  const output = logDirectory + "/" + suffix + ".agy.ndjson"
  const errors = logDirectory + "/" + suffix + ".agy.stderr"
  const stdout = openSync(output, "wx", 0o600)
  const stderr = openSync(errors, "wx", 0o600)
  const args = [
    "-p", prompt, "--output-format", "stream-json", "--model", pin.model,
    "--dangerously-skip-permissions",
    ...(resume ? ["--conversation", resume] : []),
  ]
  try {
    const child = spawn("agy", args, { cwd: directory, detached: true, stdio: ["ignore", stdout, stderr] })
    const pid = child.pid
    child.on("error", (error: Error) => {
      if (pid !== undefined) children.delete(pid)
      appendFileSync(errors, "spawn error: " + error.message + "\n")
    })
    child.on("close", () => { if (pid !== undefined) children.delete(pid) })
    if (pid === undefined) throw new Error("Cannot launch Antigravity CLI")
    children.set(pid, child)
    child.unref()
    return { pid, output, errors, started_at: new Date().toISOString(), proc_start: processStartTime(pid) }
  } finally {
    closeSync(stdout)
    closeSync(stderr)
  }
}

type Event = {
  event?: string
  conversation_id?: string
  init?: { model?: string }
  result?: { conversation_id?: string; status?: string; response?: string; error?: string; usage?: unknown }
}

function events(run: CommandRun): Event[] {
  try {
    const fd = openSync(run.output, "r")
    try {
      const size = fstatSync(fd).size
      const prefixSize = Math.min(size, 65536)
      const tailStart = Math.max(prefixSize, size - 1024 * 1024)
      const prefix = Buffer.alloc(prefixSize)
      const tail = Buffer.alloc(size - tailStart)
      const a = readSync(fd, prefix, 0, prefix.length, 0)
      const b = readSync(fd, tail, 0, tail.length, tailStart)
      return (prefix.subarray(0, a).toString("utf8") + "\n" + tail.subarray(0, b).toString("utf8"))
        .split("\n").flatMap(line => {
          try {
            const value: unknown = JSON.parse(line)
            return value && typeof value === "object" ? [value as Event] : []
          } catch { return [] }
        })
    } finally { closeSync(fd) }
  } catch { return [] }
}

export function antigravitySession(run: CommandRun): string | null {
  const event = events(run).find(value => value.event === "init")
  const id = event?.conversation_id
  return typeof id === "string" && /^[a-f0-9-]{36}$/i.test(id) ? id : null
}

export function antigravityResult(run: CommandRun, pin: CliPin = ANTIGRAVITY_PIN): { state: string; result: CommandResult | null; stderr: string | null } {
  const identity = children.has(run.pid) ? "same" : processIdentity(run)
  if (identity === "same" || identity === "unknown" || groupAlive(run.pid))
    return { state: "running", result: null, stderr: null }
  const stream = events(run)
  const init = stream.find(value => value.event === "init")
  const terminal = stream.findLast(value => value.event === "result")?.result
  if (!terminal) return { state: "interrupted", result: null, stderr: null }
  const pinMatches = init?.init?.model === pin.model && !isBannedModel(pin.model)
  const succeeded = terminal.status === "SUCCESS" && pinMatches
  const result: CommandResult = {
    subtype: succeeded ? "success" : "error",
    sessionId: terminal.conversation_id ?? antigravitySession(run) ?? undefined,
    finalText: terminal.response,
    error: pinMatches ? terminal.error ?? (succeeded ? undefined : "Antigravity ended with " + terminal.status) :
      "Antigravity failed to confirm the admitted model " + pin.model,
    usage: terminal.usage,
  }
  return { state: succeeded ? "succeeded" : "failed", result, stderr: null }
}

export function cancelAntigravity(run: CommandRun): boolean {
  const child = children.get(run.pid)
  if (!child) return false
  try { process.kill(-run.pid, "SIGTERM"); return true }
  catch { return false }
}
