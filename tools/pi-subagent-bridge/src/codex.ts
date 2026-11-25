import { readBoundedLog } from "./bounded-log.ts"
import { spawnSync, spawn, type ChildProcess } from "node:child_process"
import { appendFileSync, closeSync, openSync } from "node:fs"
import { randomUUID } from "node:crypto"
import { workerAlive, processStartTime, verifiedSignal, type CommandResult, type CommandRun } from "./command.ts"
import { plannedCommand, type LaunchRequest } from "./launch.ts"
import { fileURLToPath } from "node:url"
import { isBannedModel } from "./policy.ts"
import { assertHarnessEnabled, harnessEnabled, type HarnessSwitches } from "./harnesses.ts"
import { workerEnvironment } from "./worker-env.ts"
const children = new Map<number, ChildProcess>()
export function codexAvailable(switches?: HarnessSwitches): boolean {
  if (!harnessEnabled("codex", switches)) return false
  try {
    const env = workerEnvironment()
    delete env.OPENAI_API_KEY
    delete env.CODEX_API_KEY
    const result = spawnSync("codex", ["login", "status"], { encoding: "utf8", timeout: 5000, env, stdio: ["ignore", "pipe", "pipe"] })
    return result.status === 0 && (result.stdout + result.stderr).includes("Logged in using ChatGPT")
  } catch { return false }
}
export function startCodex(request: LaunchRequest, switches?: HarnessSwitches): CommandRun {
  assertHarnessEnabled("codex", switches)
  const { directory, logDirectory, prompt: text, resume, selection: { model, effort }, access } = request
  if (isBannedModel(model)) throw new Error("Prohibited Codex model: " + model)
  const readOnly = access.kind === "read-only"
  const suffix = randomUUID(), output = request.planned_run?.output ?? `${logDirectory}/${suffix}.codex.ndjson`, errors = request.planned_run?.errors ?? `${logDirectory}/${suffix}.codex.stderr`
  const stdout = openSync(output, "wx", 0o600), stderr = openSync(errors, "wx", 0o600)
  // Write runs load the user's Codex config so its goals, memories and instructions apply; the
  // flags below still pin the model, effort, sandbox and approval, and keep the worker a leaf.
  // Read-only scouts ignore it: their guarantee rests on having no tools, and the user config can
  // add plugins and MCP servers.
  const userConfig = readOnly ? ["--ignore-user-config"] : ["--enable", "goals", "-c", "agents.enabled=false"]
  const args = ["exec", "--json", ...userConfig, "--disable", "multi_agent", "-c", 'model_provider="openai"',
    "-c", `model_reasoning_effort="${effort}"`, "-c", 'approval_policy="never"',
    "--sandbox", "danger-full-access", "--model", model,
    ...(readOnly ? ["--disable", "shell_tool", "--disable", "unified_exec",
      "--disable", "computer_use", "--disable", "browser_use", "--disable", "in_app_browser",
      "-c", `mcp_servers.bridge_scout.command=${JSON.stringify(process.execPath)}`,
      "-c", `mcp_servers.bridge_scout.args=${JSON.stringify(["--experimental-strip-types", fileURLToPath(new URL("./codex-scout.ts", import.meta.url))])}`] : []),
    ...(resume ? ["resume", resume, text] : [text])]
  const env = workerEnvironment()
  delete env.OPENAI_API_KEY
  delete env.CODEX_API_KEY
  try {
    const invocation = plannedCommand("codex", args, request.planned_run)
    const child = spawn(invocation.executable, invocation.args, { cwd: directory, env, detached: true, stdio: ["ignore", stdout, stderr] })
    const pid = child.pid
    child.on("error", (error) => {
      if (pid !== undefined) children.delete(pid)
      appendFileSync(errors, "spawn error: " + error.message + "\n")
    })
    child.on("close", () => { if (pid !== undefined) children.delete(pid) })
    if (pid === undefined) throw new Error("Cannot start Codex")
    children.set(pid, child)
    child.unref()
    return { pid, output, errors, started_at: request.planned_run?.started_at ?? new Date().toISOString(), proc_start: processStartTime(pid) }
  } finally { closeSync(stdout); closeSync(stderr) }
}
type Event = { type?: string; thread_id?: string; item?: { type?: string; text?: string }; error?: unknown; usage?: unknown }
function events(run: CommandRun): Event[] {
  let content: string
  try {
    content = readBoundedLog(run.output)
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
  if (workerAlive(run, children.has(run.pid))) return { state: "running", result: null, stderr: null }
  const stream = events(run), terminal = stream.findLast((event) => event.type === "turn.completed" || event.type === "turn.failed")
  if (!terminal) return { state: "interrupted", result: null, stderr: null }
  const sessionId = stream.find((event) => event.type === "thread.started")?.thread_id
  if (!sessionId) return { state: "interrupted", result: null, stderr: null }
  const finalText = stream.findLast((event) => event.type === "item.completed" && event.item?.type === "agent_message")?.item?.text
  const success = terminal.type === "turn.completed"
  const result: CommandResult = { subtype: success ? "success" : "error", sessionId, finalText, error: terminal.error, usage: terminal.usage }
  return { state: success ? "succeeded" : "failed", result, stderr: null }
}
export function cancelCodex(run: CommandRun, cwd?: string): boolean {
  return verifiedSignal(run, cwd, children, "codex")
}
