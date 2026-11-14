import { spawnSync, spawn, type ChildProcess } from "node:child_process"
import { appendFileSync, closeSync, openSync, readSync, fstatSync } from "node:fs"
import { randomUUID } from "node:crypto"
import { groupAlive, processIdentity, processStartTime, type CommandResult, type CommandRun } from "./command.ts"
import type { LaunchRequest } from "./launch.ts"
import { fileURLToPath } from "node:url"
import { isBannedModel } from "./policy.ts"
const children = new Map<number, ChildProcess>()
export function codexAvailable(): boolean {
  try {
    const env = { ...process.env }
    delete env.OPENAI_API_KEY
    delete env.CODEX_API_KEY
    const result = spawnSync("codex", ["login", "status"], { encoding: "utf8", timeout: 5000, env, stdio: ["ignore", "pipe", "pipe"] })
    return result.status === 0 && (result.stdout + result.stderr).includes("Logged in using ChatGPT")
  } catch { return false }
}
export function startCodex(request: LaunchRequest): CommandRun {
  const { directory, logDirectory, prompt: text, resume, selection: { model, effort }, access } = request
  if (isBannedModel(model)) throw new Error("Prohibited Codex model: " + model)
  const readOnly = access.kind === "read-only"
  const suffix = randomUUID(), output = `${logDirectory}/${suffix}.codex.ndjson`, errors = `${logDirectory}/${suffix}.codex.stderr`
  const stdout = openSync(output, "wx", 0o600), stderr = openSync(errors, "wx", 0o600)
  const args = ["exec", "--json", "--ignore-user-config", "--disable", "multi_agent", "-c", 'model_provider="openai"',
    "-c", `model_reasoning_effort="${effort}"`, "-c", 'approval_policy="never"',
    "--sandbox", "danger-full-access", "--model", model,
    ...(readOnly ? ["--disable", "shell_tool", "--disable", "unified_exec",
      "--disable", "computer_use", "--disable", "browser_use", "--disable", "in_app_browser",
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
