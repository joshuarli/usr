import { assertHarnessEnabled } from "./harnesses.ts"
import { spawn, execFileSync } from "node:child_process"
import { appendFileSync, closeSync, openSync, readFileSync, readSync, statSync, writeFileSync } from "node:fs"
import { exhaustionWatcher, secretEnvironment, writeReceipt, type ExhaustionWatch } from "./fx-supervision.ts"

type AcpJob = {
  nonce: string; executable: string; args: string[]; cwd: string; env: NodeJS.ProcessEnv; env_files?: Record<string, string>
  wallMs: number; output: string; errors: string; prompt: string; resume?: string; acp_log: string; events: string
  selection: { provider: string; model: string; effort: string }; exhaustion?: ExhaustionWatch; ungated_tools: string[]
  mcp_servers?: Array<{ name: string; command: string; args: string[]; env: Array<{ name: string; value: string }> }>
}
type Reason = "end_turn" | "step_limit" | "refused" | "max_tokens" | "max_turn_requests" | "cancelled" | "deadline" | "exhausted"
  | "permission" | "policy" | "pin_mismatch" | "protocol" | "crash" | "spawn" | "supervision"

const job = JSON.parse(readFileSync(process.argv[2]!, "utf8")) as AcpJob
const MAX_LINE = 8_388_608, MAX_FINAL = 1_048_576, MAX_EVENTS = 16_777_216, MAX_STDERR = 65_536
const CANCEL_WAIT_MS = 5000, EXIT_WAIT_MS = 2000
let reason: Reason | null = null, stopReason: string | null = null, sessionId: string | null = null
let finalText = "", usage: unknown = null, stderr = "", eventBytes = 0, permissionRequests = 0, finished = false
let policyViolation: string | null = null

function receipt(termination: "verified" | "unverified", childPid: number | null) {
  writeReceipt(job.output, { schema: 2, transport: "acp", nonce: job.nonce, supervisor_pid: process.pid, child_pid: childPid, session_id: sessionId,
    reason, stop_reason: stopReason, final_text: finalText, usage, termination, permission_requests: permissionRequests, policy_violation: policyViolation, stderr: stderr.slice(-4096) })
}

try { assertHarnessEnabled("fx") } catch (error) {
  reason = "spawn"; stderr = String(error)
  receipt("verified", null); process.exit(1)
}
const errorFd = openSync(job.errors, "wx", 0o600)
let env: NodeJS.ProcessEnv
try { env = secretEnvironment(job.env, job.env_files) } catch (error) {
  reason = "spawn"; stderr = String(error)
  closeSync(errorFd); receipt("verified", null); process.exit(1)
}
const child = spawn(job.executable, job.args, { cwd: job.cwd, env, detached: true, stdio: ["pipe", "pipe", "pipe"] })
const childPid = child.pid ?? null
const exited = new Promise<void>(resolve => child.once("close", () => resolve()))
child.once("error", error => { if (!reason) reason = "spawn"; stderr += error.message })
child.stderr.setEncoding("utf8")
child.stderr.on("data", (chunk: string) => {
  if (stderr.length < MAX_STDERR) stderr += chunk
  try { writeFileSync(errorFd, chunk) } catch { void stop("supervision") }
})

let nextId = 0
const pending = new Map<number, { resolve(value: Record<string, unknown>): void }>()
let buffer = ""
child.stdout.setEncoding("utf8")
child.stdout.on("data", (chunk: string) => {
  buffer += chunk
  if (buffer.length > MAX_LINE && !buffer.includes("\n")) { void stop("protocol"); return }
  let index: number
  while ((index = buffer.indexOf("\n")) >= 0) {
    const line = buffer.slice(0, index); buffer = buffer.slice(index + 1)
    if (!line.trim()) continue
    let message: Record<string, unknown>
    try { message = JSON.parse(line) as Record<string, unknown> } catch { void stop("protocol"); return }
    handle(message)
  }
})
function send(message: Record<string, unknown>): void {
  if (child.stdin.writable) child.stdin.write(JSON.stringify({ jsonrpc: "2.0", ...message }) + "\n")
}
function call(method: string, params: unknown): Promise<Record<string, unknown>> {
  const id = ++nextId
  return new Promise(resolve => { pending.set(id, { resolve }); send({ id, method, params }) })
}
function record(update: unknown): void {
  const line = JSON.stringify({ at: Date.now(), update }) + "\n"
  if (eventBytes + line.length > MAX_EVENTS) return
  eventBytes += line.length
  try { appendFileSync(job.events, line, { mode: 0o600 }) } catch { void stop("supervision") }
}
function handle(message: Record<string, unknown>): void {
  const id = message.id, method = message.method
  if (typeof method !== "string") {
    if (typeof id === "number") { pending.get(id)?.resolve(message); pending.delete(id) }
    return
  }
  if (id !== undefined) {
    if (method === "session/request_permission") {
      permissionRequests++
      record({ sessionUpdate: "permission_request_denied", params: message.params })
      send({ id, result: { outcome: { outcome: "cancelled" } } })
      void stop("permission")
    } else send({ id, error: { code: -32601, message: "Client method not provided: " + method } })
    return
  }
  if (method !== "session/update") return
  const params = message.params as { update?: Record<string, unknown> } | undefined
  const update = params?.update
  if (!update) return
  record(update)
  if (update.sessionUpdate === "tool_call") {
    finalText = ""
    if (typeof update.name === "string" && job.ungated_tools.includes(update.name)) { policyViolation = update.name; void stop("policy") }
  }
  else if (update.sessionUpdate === "agent_message_chunk") {
    const content = update.content as { type?: string; text?: unknown } | undefined
    if (content?.type === "text" && typeof content.text === "string" && finalText.length + content.text.length <= MAX_FINAL) finalText += content.text
  }
}

function descendants(root: number): Map<number, string> {
  const found = new Map<number, string>()
  try {
    const rows = execFileSync("ps", ["-A", "-o", "pid=,ppid=,lstart="], { encoding: "utf8", timeout: 2000, maxBuffer: 8_000_000 })
    const children = new Map<number, Array<{ pid: number; start: string }>>()
    for (const row of rows.split("\n")) {
      const match = /^\s*(\d+)\s+(\d+)\s+(.+?)\s*$/.exec(row)
      if (!match) continue
      const list = children.get(Number(match[2])) ?? []
      list.push({ pid: Number(match[1]), start: match[3]! })
      children.set(Number(match[2]), list)
    }
    const queue = [root]
    while (queue.length) for (const entry of children.get(queue.shift()!) ?? []) { found.set(entry.pid, entry.start); queue.push(entry.pid) }
  } catch { /* an empty snapshot leaves termination to the group check */ }
  return found
}
function startOf(pid: number): string | null {
  try { return execFileSync("ps", ["-o", "lstart=", "-p", String(pid)], { encoding: "utf8", timeout: 2000 }).trim() || null } catch { return null }
}
function groupAlive(pgid: number): boolean {
  try { process.kill(-pgid, 0); return true } catch (error) { return (error as NodeJS.ErrnoException).code === "EPERM" }
}
const wait = (ms: number) => new Promise<void>(resolve => setTimeout(resolve, ms))
async function settle(promise: Promise<unknown>, ms: number): Promise<boolean> {
  return Promise.race([promise.then(() => true), wait(ms).then(() => false)])
}

let promptCall: Promise<Record<string, unknown>> | null = null
let stopping: Promise<void> | null = null
function stop(why: Reason): Promise<void> {
  if (!reason) reason = why
  stopping ??= shutdown()
  return stopping
}
async function shutdown(): Promise<void> {
  clearTimeout(deadline); if (exhaustionTimer) clearInterval(exhaustionTimer)
  const tree = childPid ? descendants(childPid) : new Map<number, string>()
  if (promptCall && !finished && sessionId) {
    send({ method: "session/cancel", params: { sessionId } })
    const answered = await settle(promptCall, CANCEL_WAIT_MS)
    if (answered) finished = true
  }
  child.stdin.end()
  if (!await settle(exited, EXIT_WAIT_MS) && childPid) {
    try { process.kill(-childPid, "SIGTERM") } catch { /* already gone */ }
    if (!await settle(exited, EXIT_WAIT_MS)) {
      try { process.kill(-childPid, "SIGKILL") } catch { /* already gone */ }
      await settle(exited, EXIT_WAIT_MS)
    }
  }
  for (const [pid, start] of tree) if (startOf(pid) === start) { try { process.kill(pid, "SIGKILL") } catch { /* exited */ } }
  await wait(100)
  const survivors = [...tree].filter(([pid, start]) => startOf(pid) === start)
  const verified = child.exitCode !== null || child.signalCode !== null
  try { closeSync(errorFd) } catch { /* closed */ }
  receipt(verified && survivors.length === 0 && !(childPid && groupAlive(childPid)) ? "verified" : "unverified", childPid)
  process.exit(0)
}

for (const signal of ["SIGTERM", "SIGINT", "SIGHUP", "SIGQUIT"] as const) process.on(signal, () => void stop("cancelled"))
const deadline = setTimeout(() => void stop("deadline"), job.wallMs)
const exhaustionHit = job.exhaustion ? exhaustionWatcher(job.exhaustion, Date.now()) : null
const exhaustionTimer = exhaustionHit ? setInterval(() => { if (exhaustionHit()) void stop("exhausted") }, 2000) : undefined
void exited.then(() => { if (!finished) void stop("crash") })

function logSize(): number { try { return statSync(job.acp_log).size } catch { return 0 } }
function logSince(offset: number): string {
  try {
    const fd = openSync(job.acp_log, "r")
    try {
      const length = Math.min(Math.max(0, logSize() - offset), MAX_LINE)
      const bytes = Buffer.alloc(length)
      return bytes.subarray(0, readSync(fd, bytes, 0, length, offset)).toString("utf8")
    } finally { closeSync(fd) }
  } catch { return "" }
}

async function run(): Promise<void> {
  const init = await call("initialize", { protocolVersion: 1, clientCapabilities: { fs: { readTextFile: false, writeTextFile: false }, terminal: false } })
  const info = (init.result as { agentInfo?: { version?: unknown } } | undefined)?.agentInfo
  if (info?.version !== "0.0.17") { stderr += "unexpected ACP agent: " + JSON.stringify(init).slice(0, 500); return stop("protocol") }
  const opened = job.resume
    ? await call("session/resume", { sessionId: job.resume, cwd: job.cwd, mcpServers: job.mcp_servers ?? [] })
    : await call("session/new", { cwd: job.cwd, mcpServers: job.mcp_servers ?? [] })
  const result = opened.result as { sessionId?: unknown; configOptions?: Array<{ id?: unknown; currentValue?: unknown }> } | undefined
  if (!result) { stderr += "ACP session admission failed: " + JSON.stringify(opened.error ?? opened).slice(0, 500); return stop("protocol") }
  const id = job.resume ?? result.sessionId
  if (typeof id !== "string" || !/^[a-zA-Z0-9_-]{1,128}$/.test(id)) { stderr += "ACP session identity missing"; return stop("protocol") }
  sessionId = id
  writeFileSync(job.output + ".native.json", JSON.stringify({ nonce: job.nonce, supervisor_pid: process.pid, child_pid: childPid, session_id: id }), { mode: 0o600 })
  const effective = Object.fromEntries((result.configOptions ?? []).map(option => [String(option.id), option.currentValue]))
  for (const key of ["provider", "model", "effort"] as const) if (effective[key] !== job.selection[key]) {
    stderr += `ACP effective ${key} ${JSON.stringify(effective[key])} differs from admitted ${JSON.stringify(job.selection[key])}`
    return stop("pin_mismatch")
  }
  const offset = logSize()
  promptCall = call("session/prompt", { sessionId: id, prompt: [{ type: "text", text: job.prompt }] })
  const response = await promptCall
  finished = true
  const outcome = response.result as { stopReason?: unknown; usage?: unknown } | undefined
  if (!outcome || typeof outcome.stopReason !== "string") { stderr += "ACP prompt failed: " + JSON.stringify(response.error ?? response).slice(0, 500); return stop("protocol") }
  stopReason = outcome.stopReason; usage = outcome.usage ?? null
  if (stopReason === "refused" && /outcome_kind=step_limit/.test(logSince(offset))) return stop("step_limit")
  const known: Record<string, Reason> = { end_turn: "end_turn", refused: "refused", max_tokens: "max_tokens", max_turn_requests: "max_turn_requests", cancelled: "cancelled" }
  return stop(known[stopReason] ?? "protocol")
}
run().catch(error => { stderr += String(error); void stop("supervision") })
