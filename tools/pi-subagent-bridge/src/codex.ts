import { spawnSync, spawn, type ChildProcess } from "node:child_process"
import { appendFileSync, closeSync, openSync, readSync, fstatSync } from "node:fs"
import { randomUUID } from "node:crypto"
import { processIdentity, processStartTime, type CommandResult, type CommandRun, type Effort } from "./command.ts"
import { fileURLToPath } from "node:url"
import { homedir } from "node:os"
import { join } from "node:path"
import { CODEX_TIER_MODELS, isBannedModel, type CliPin } from "./policy.ts"
export { CODEX_TIER_MODELS } from "./policy.ts"
const children = new Map<number, ChildProcess>()
function cargoHome(): string {
  return process.env.CARGO_HOME || join(homedir(), ".cargo")
}
export function codexAvailable(): boolean {
  try {
    const env = { ...process.env }
    delete env.OPENAI_API_KEY
    delete env.CODEX_API_KEY
    const result = spawnSync("codex", ["login", "status"], { encoding: "utf8", timeout: 5000, env, stdio: ["ignore", "pipe", "pipe"] })
    return result.status === 0 && (result.stdout + result.stderr).includes("Logged in using ChatGPT")
  } catch { return false }
}
export function startCodex(directory: string, logDirectory: string, text: string,
  effort: Effort, readOnly: boolean, resume?: string, model?: string, network = false, admittedPin?: CliPin): CommandRun {
  const approved = admittedPin
    ? admittedPin.model === model && admittedPin.effort === effort
    : Object.values(CODEX_TIER_MODELS).some(pin => pin.model === model && pin.effort === effort)
  if (!model || isBannedModel(model) || !approved)
    throw new Error("Unapproved Codex model and effort" + (admittedPin ? "; preserve the admitted pin or reconcile the session" : ""))
  const suffix = randomUUID(), output = `${logDirectory}/${suffix}.codex.ndjson`, errors = `${logDirectory}/${suffix}.codex.stderr`
  const stdout = openSync(output, "wx", 0o600), stderr = openSync(errors, "wx", 0o600)
  const args = ["exec", "--json", "--ignore-user-config", "--disable", "multi_agent", "-c", 'model_provider="openai"',
    "-c", `model_reasoning_effort="${effort}"`, "-c", 'approval_policy="never"',
    "--sandbox", readOnly ? "read-only" : "workspace-write", "--model", model,
    ...(network && !readOnly ? ["-c", "sandbox_workspace_write.network_access=true", "--add-dir", cargoHome()] : []),
    ...(readOnly ? ["--disable", "shell_tool", "--disable", "unified_exec",
      "-c", `mcp_servers.bridge_scout.command=${JSON.stringify(process.execPath)}`,
      "-c", `mcp_servers.bridge_scout.args=${JSON.stringify(["--experimental-strip-types", fileURLToPath(new URL("./codex-scout.ts", import.meta.url))])}`] : []),
    ...(resume ? ["resume", resume, text] : [text])]
  const env = { ...process.env }
  delete env.OPENAI_API_KEY
  delete env.CODEX_API_KEY
  try {
    const child = spawn("codex", args, { cwd: directory, env, detached: true, stdio: ["ignore", stdout, stderr] })
    const pid = child.pid
    child.on("error", (error) => {
      if (pid !== undefined) children.delete(pid)
      appendFileSync(errors, "spawn error: " + error.message + "\n")
    })
    child.on("close", () => { if (pid !== undefined) children.delete(pid) })
    if (pid === undefined) throw new Error("Cannot start Codex")
    children.set(pid, child)
    child.unref()
    return { pid, output, errors, started_at: new Date().toISOString(), proc_start: processStartTime(pid) }
  } finally { closeSync(stdout); closeSync(stderr) }
}
type Event = { type?: string; thread_id?: string; item?: { type?: string; text?: string }; error?: unknown; usage?: unknown }
function events(run: CommandRun): Event[] {
  let content: string
  try {
    const fd = openSync(run.output, "r")
    try {
      const size = fstatSync(fd).size, prefixSize = Math.min(size, 65536), tailStart = Math.max(prefixSize, size - 1024 * 1024)
      const prefix = Buffer.alloc(prefixSize), tail = Buffer.alloc(size - tailStart)
      const prefixRead = readSync(fd, prefix, 0, prefix.length, 0)
      const tailRead = readSync(fd, tail, 0, tail.length, tailStart)
      content = prefix.subarray(0, prefixRead).toString("utf8") + "\n" + tail.subarray(0, tailRead).toString("utf8")
    } finally { closeSync(fd) }
  } catch { return [] }
  return content.split("\n").flatMap((line) => {
    try { const event: unknown = JSON.parse(line); return event && typeof event === "object" ? [event as Event] : [] }
    catch { return [] }
  })
}
export function codexSession(run: CommandRun): string | null {
  return events(run).find((event) => event.type === "thread.started")?.thread_id ?? null
}
function groupAlive(pid: number): boolean {
  try { process.kill(-pid, 0); return true }
  catch (error) { return (error as NodeJS.ErrnoException).code !== "ESRCH" }
}
export function codexResult(run: CommandRun): { state: string; result: CommandResult | null; stderr: string | null } {
  const identity = children.has(run.pid) ? "same" : processIdentity(run)
  if (identity === "same" || identity === "unknown" || groupAlive(run.pid)) return { state: "running", result: null, stderr: null }
  const stream = events(run), terminal = stream.findLast((event) => event.type === "turn.completed" || event.type === "turn.failed")
  if (!terminal) return { state: "interrupted", result: null, stderr: null }
  const sessionId = stream.find((event) => event.type === "thread.started")?.thread_id
  if (!sessionId) return { state: "interrupted", result: null, stderr: null }
  const finalText = stream.findLast((event) => event.type === "item.completed" && event.item?.type === "agent_message")?.item?.text
  const success = terminal.type === "turn.completed"
  const result: CommandResult = { subtype: success ? "success" : "error", sessionId, finalText, error: terminal.error, usage: terminal.usage }
  return { state: success ? "succeeded" : "failed", result, stderr: null }
}
export function cancelCodex(run: CommandRun): boolean {
  const child = children.get(run.pid)
  if (!child) return false
  try { process.kill(-run.pid, "SIGTERM"); return true }
  catch { return false }
}
