import { spawn, execFileSync, type ChildProcess } from "node:child_process"
import { randomUUID, createHash } from "node:crypto"
import { mkdirSync, readFileSync, readdirSync, writeFileSync, realpathSync, openSync, readSync, closeSync, statSync, copyFileSync, chmodSync, existsSync } from "node:fs"
import { join, relative, isAbsolute } from "node:path"
import { fileURLToPath } from "node:url"
import { processStartTime, processIdentity, workerAlive, type CommandRun, type CommandResult } from "./command.ts"
import { plannedCommand, type LaunchRequest } from "./launch.ts"
import { isRecord } from "./scope.ts"
import { isBannedModel, type CliPin } from "./policy.ts"
import { deadlineTimeout } from "./steer-deadline.ts"

export const FX_CAPABILITIES = { steering: "interrupt-resume", resume: "bound native session and worktree", nativeNesting: "denied", readOnly: "tool permission prevention", hostContainment: false } as const

export type FxSelection = CliPin & { readonly provider: string; readonly runtimeVersion: "0.0.17" }
export type FxLaunch = Omit<LaunchRequest, "selection"> & { readonly selection: FxSelection }
/** `cli` runs one `fx ask --json` per turn; `acp` drives `fx acp` over stdio from the supervisor. */
export type FxTransport = "cli" | "acp"
export type FxOptions = {
  transport: FxTransport
  binary: string; binarySha256: string; home: string; provider: string
  /** Custom connection settings; omit for FX built-in providers (gateway, codex, grok). */
  connection?: object | null
  allowedCommands: string[]; wallMs?: number
  /** Extra PATH entries for the qualified toolchain; defaults to the minimal fixture PATH. */
  pathEnv?: string
  /** Environment variables delivered through 0600 files so job records never serialize secrets. */
  secretEnvFiles?: Record<string, string>
  /** Credential files copied into each fresh FX profile home (e.g. chatgpt-auth.json). */
  authFiles?: string[]
  /** Additional non-secret environment for the qualified toolchain (e.g. CARGO_HOME). Never secrets. */
  extraEnv?: Record<string, string>
}
type Job = { transport: FxTransport; nonce: string; cwd: string; fxHome: string; selection: FxSelection; output: string; errors: string; resume?: string }
export const FX_PILOT_MAX_STEPS = 20
const children = new Map<number, { child: ChildProcess; run: CommandRun }>()
const RESERVED_ENV_PREFIX = /^(?:FX_|LD_|DYLD_|GIT_)/
const RESERVED_ENV_NAMES = new Set(["HOME", "PATH", "SHELL", "TMPDIR", "BASH_ENV", "ENV", "ZDOTDIR", "NODE_OPTIONS", "PYTHONPATH", "PYTHONSTARTUP", "PYTHONHOME", "PERL5OPT", "RUBYOPT", "USR_SCOPED_WORKER"])
function invalidEnvName(name: string): boolean {
  return !/^[A-Z_][A-Z0-9_]*$/.test(name) || RESERVED_ENV_PREFIX.test(name) || RESERVED_ENV_NAMES.has(name)
}
const read = (path: string): unknown => {
  if (statSync(path).size > 16_777_216) throw new Error("Oversized FX record")
  return JSON.parse(readFileSync(path, "utf8"))
}
function jobFor(run: CommandRun): Job {
  const value = read(run.output + ".job.json")
  if (!isRecord(value) || typeof value.nonce !== "string" || typeof value.cwd !== "string" || typeof value.fxHome !== "string" || (value.output !== run.output || value.errors !== run.errors) || !isRecord(value.selection)) throw new Error("Invalid FX admission record")
  const selection = value.selection
  if (typeof selection.model !== "string" || !selection.model || typeof selection.provider !== "string" || !selection.provider || selection.runtimeVersion !== "0.0.17" || !["low", "medium", "high", "xhigh", "max"].includes(String(selection.effort)) || !isAbsolute(value.cwd) || !isAbsolute(value.fxHome)) throw new Error("Invalid FX identity/pin record")
  return { ...(value as Job), transport: value.transport === "acp" ? "acp" : "cli" }
}
const SESSION_ID = /^[a-zA-Z0-9_-]{1,128}$/
function nativeSession(job: Job): string | null {
  try {
    const sessions = join(job.fxHome, "sessions/v2")
    const names = readdirSync(sessions, { withFileTypes: true }).filter(entry => entry.isDirectory() && entry.name !== ".tmp").map(entry => entry.name)
    return names.length === 1 ? boundSession(job, names[0]!) : null
  } catch { return null }
}
/** The saved FX session exists, is a root session and was created for this job's worktree. */
function boundSession(job: Job, id: string): string | null {
  try {
    if (!SESSION_ID.test(id)) return null
    const sessions = join(job.fxHome, "sessions/v2")
    const fd = openSync(join(sessions, id, "log.jsonl"), "r"), buffer = Buffer.alloc(8192)
    let line: string
    try { line = buffer.subarray(0, readSync(fd, buffer, 0, buffer.length, 0)).toString("utf8").split("\n")[0]! } finally { closeSync(fd) }
    const first = JSON.parse(line) as Record<string, unknown>
    return first.v === 1 && first.kind === "session_created" && first.id === id && first.workspace === job.cwd && first.role === "root" ? id : null
  } catch { return null }
}
function token(job: Job, id: string): string {
  return "fx:0.0.17:" + Buffer.from(JSON.stringify({ cwd: job.cwd, fxHome: job.fxHome, selection: job.selection, id })).toString("base64url")
}
/** The ACP supervisor publishes the session it opened; only that exact identity is ever used. */
function acpSession(run: CommandRun, job: Job): string | null {
  try {
    const value = read(run.output + ".native.json")
    if (!isRecord(value) || value.nonce !== job.nonce || value.supervisor_pid !== run.pid || typeof value.session_id !== "string") return null
    if (job.resume !== undefined && value.session_id !== job.resume) return null
    return boundSession(job, value.session_id)
  } catch { return null }
}
function ownSession(run: CommandRun, job: Job): string | null {
  return job.transport === "acp" ? acpSession(run, job) : nativeSession(job)
}
export function fxSession(run: CommandRun, expected: FxSelection): string | null {
  const job = jobFor(run), id = ownSession(run, job)
  if (!sameSelection(job.selection, expected)) throw new Error("FX admitted pin mismatch")
  return id ? token(job, id) : null
}
function continuation(run: CommandRun, job: Job): string | undefined {
  const id = ownSession(run, job)
  return id && (job.resume === undefined || job.resume === id) ? token(job, id) : undefined
}
/** Budgets persisted at admission; records written before budgets were persisted report null. */
export function fxBudget(run: CommandRun): { run_deadline_ms: number | null; run_step_limit: number | null } {
  const limit = (value: unknown) => Number.isSafeInteger(value) && (value as number) > 0 ? value as number : null
  try {
    const value = read(run.output + ".job.json")
    return isRecord(value) ? { run_deadline_ms: limit(value.wallMs), run_step_limit: limit(value.maxSteps) } : { run_deadline_ms: null, run_step_limit: null }
  } catch { return { run_deadline_ms: null, run_step_limit: null } }
}
export function fxResult(run: CommandRun, expected: FxSelection): Status {
  if (workerAlive(run, false)) return { state: "running", result: null, stderr: null }
  try {
    const job = jobFor(run), receipt = read(run.output)
    if (!sameSelection(job.selection, expected)) throw new Error("FX admitted pin mismatch")
    if (job.transport === "acp") return acpResult(run, job, receipt)
    if (!isRecord(receipt) || receipt.schema !== 1 || receipt.nonce !== job.nonce || receipt.supervisor_pid !== run.pid || typeof receipt.stdout !== "string" || typeof receipt.stderr !== "string") throw new Error("Invalid FX termination receipt")
    const stderr = receipt.stderr
    const stopped = (state: "cancelled" | "timed_out" | "failed", error: string) => {
      const sessionId = continuation(run, job)
      const result: CommandResult = { subtype: "error", error, finalText: "", ...(sessionId ? { sessionId } : {}) }
      return { state, result, stderr }
    }
    if (receipt.reason === "cancelled") return stopped("cancelled", "FX run cancelled; supervisor verified termination")
    if (receipt.reason === "deadline") return stopped("timed_out", `FX run reached its ${String(fxBudget(run).run_deadline_ms)} ms wall deadline and was stopped`)
    if (receipt.reason === "exhausted") return stopped("failed", "provider quota exhaustion: FX reported a quota failure or a retry delay beyond this job's bound; terminated early")
    if (receipt.reason !== "exit" || receipt.signal !== null || receipt.code !== 0) return stopped("failed", `${String(receipt.reason)}: FX exited ${String(receipt.code)} with signal ${String(receipt.signal)}`)
    const value: unknown = JSON.parse(receipt.stdout)
    const id = nativeSession(job)
    if (!isRecord(value) || value.exit_code !== receipt.code || value.model !== job.selection.model || !id || value.session_id !== id || (job.resume !== undefined && job.resume !== id) || typeof value.final_output !== "string" || !value.final_output.trim()) throw new Error("FX result/native session mismatch or missing final response")
    const result: CommandResult = { subtype: "success", sessionId: token(job, id), finalText: value.final_output, usage: value.usage }
    return { state: "succeeded", result, stderr: receipt.stderr }
  } catch (error) { return { state: "unknown_or_interrupted", result: null, stderr: String(error) } }
}
type Status = { state: string; result: CommandResult | null; stderr: string | null }
function acpResult(run: CommandRun, job: Job, receipt: unknown): Status {
  if (!isRecord(receipt) || receipt.schema !== 2 || receipt.transport !== "acp" || receipt.nonce !== job.nonce || receipt.supervisor_pid !== run.pid || typeof receipt.final_text !== "string" || typeof receipt.stderr !== "string" || typeof receipt.reason !== "string")
    throw new Error("Invalid FX ACP termination receipt")
  const stderr = receipt.stderr
  if (receipt.termination !== "verified") return { state: "unknown_or_interrupted", result: null, stderr: "FX process tree termination unverified; inspect before resuming. " + stderr }
  const id = continuation(run, job)
  if (receipt.session_id !== null && (typeof receipt.session_id !== "string" || (id !== undefined && receipt.session_id !== ownSession(run, job))))
    throw new Error("FX ACP receipt names a different native session")
  const withSession = (result: CommandResult): CommandResult => id ? { ...result, sessionId: id } : result
  const stopped = (state: string, error: string): Status => ({ state, result: withSession({ subtype: "error", error, finalText: receipt.final_text as string }), stderr })
  const steps = fxBudget(run).run_step_limit
  switch (receipt.reason) {
    case "end_turn":
      if (!id) throw new Error("FX ACP completed without a bound native session")
      return { state: "succeeded", result: withSession({ subtype: "success", finalText: receipt.final_text, usage: receipt.usage }), stderr }
    case "step_limit": return { state: "turn_limit", result: withSession({ subtype: "max_turns", error: `FX reached its ${String(steps)}-step budget before finishing`, finalText: receipt.final_text, usage: receipt.usage }), stderr }
    case "cancelled": return stopped("cancelled", "FX run cancelled; supervisor verified termination")
    case "deadline": return stopped("timed_out", `FX run reached its ${String(fxBudget(run).run_deadline_ms)} ms wall deadline and was stopped`)
    case "exhausted": return stopped("failed", "provider quota exhaustion: FX reported a quota failure or a retry delay beyond this job's bound; terminated early")
    case "permission": return stopped("failed", "FX requested interactive permission; the request was denied and the run stopped as blocked")
    case "pin_mismatch": return stopped("failed", "FX effective provider/model/effort differed from the admitted pins; stopped before prompting")
    default: return stopped("failed", `${receipt.reason}: FX ACP run ended without completing (stop reason ${String(receipt.stop_reason)})`)
  }
}
export function makeFxAdapter(options: FxOptions) {
  if (options.transport !== "cli" && options.transport !== "acp") throw new Error("Unknown FX transport")
  const home = realpathSync(options.home), wallMs = options.wallMs ?? 900000
  if (!isAbsolute(options.binary) || !Number.isSafeInteger(wallMs) || wallMs < 1 || wallMs > 900000) throw new Error("Invalid FX qualification configuration")
  const pathEnv = options.pathEnv ?? "/usr/bin:/bin"
  if (!pathEnv.split(":").every(part => isAbsolute(part))) throw new Error("FX PATH entries must be absolute")
  const secretEnvFiles = options.secretEnvFiles ?? {}
  for (const [name, path] of Object.entries(secretEnvFiles)) {
    if (invalidEnvName(name) || !isAbsolute(path)) throw new Error("Invalid FX secret env file mapping")
  }
  const authFiles = options.authFiles ?? []
  for (const path of authFiles) if (!isAbsolute(path)) throw new Error("FX auth files must be absolute")
  for (const name of Object.keys(options.extraEnv ?? {})) {
    if (invalidEnvName(name)) throw new Error("Invalid FX extra env name: " + name)
  }
  const env: NodeJS.ProcessEnv = { HOME: home, PATH: pathEnv, SHELL: "/bin/sh", FX_AUTO_UPGRADE: "0", FX_DISABLE_KEYCHAIN: "1", FX_HERDR: "0", FX_SOUND: "off", FX_MAX_AGENT_STEPS: String(FX_PILOT_MAX_STEPS), USR_SCOPED_WORKER: "1", ...options.extraEnv }
  for (const name of Object.keys(secretEnvFiles)) {
    if (name in env || name === "FX_HOME" || name === "TMPDIR") throw new Error("FX secret env name collides with the qualified environment: " + name)
  }
  function available(selection: FxSelection): boolean {
    if (isBannedModel(selection.model) || selection.provider !== options.provider || selection.runtimeVersion !== "0.0.17") return false
    try { return createHash("sha256").update(readFileSync(options.binary)).digest("hex") === options.binarySha256 && execFileSync(options.binary, ["--version"], { env, encoding: "utf8", timeout: deadlineTimeout(5000) }).trim() === selection.runtimeVersion } catch { return false }
  }
  function admitted(request: Omit<FxLaunch, "prompt">): { cwd: string; settings: string } {
    if (!available(request.selection)) throw new Error("Pinned FX binary/provider unavailable")
    const cwd = realpathSync(request.directory), underHome = relative(home, cwd)
    if (!underHome || underHome.startsWith("..") || isAbsolute(underHome)) throw new Error("FX qualification worktree must be beneath its private HOME")
    const readOnly = request.access.kind === "read-only"
    const connection = options.connection == null ? {} : { providers: { [options.provider]: options.connection } }
    const settings = JSON.stringify({ auto_upgrade: false, cache_warming: false, session_titles: false, max_agent_steps: FX_PILOT_MAX_STEPS, provider: options.provider, models: { [options.provider]: request.selection.model }, ...connection, permission: { "*": "deny", read: "allow", glob: "allow", grep: "allow", edit: readOnly ? "deny" : "allow", bash: readOnly ? "deny" : Object.fromEntries(options.allowedCommands.map(command => [command, "allow"])), subagent: "deny", toolbox: "deny" }, workspaces: { [cwd]: { enableAllProjectMcpServers: false } } })
    return { cwd, settings }
  }
  /** Validates a continuation without effects: token, worktree, pins and the saved private configuration. */
  function preflightResume(request: Omit<FxLaunch, "prompt"> & { resume: string }): { cwd: string; settings: string; fxHome: string; resume: string } {
    const { cwd, settings } = admitted(request)
    if (!request.resume.startsWith("fx:0.0.17:")) throw new Error("Unsupported FX resume token")
    const saved: unknown = JSON.parse(Buffer.from(request.resume.slice("fx:0.0.17:".length), "base64url").toString("utf8"))
    if (!isRecord(saved) || saved.cwd !== cwd || (!isRecord(saved.selection) || saved.selection.model !== request.selection.model || saved.selection.effort !== request.selection.effort || saved.selection.provider !== request.selection.provider || saved.selection.runtimeVersion !== request.selection.runtimeVersion) || typeof saved.id !== "string" || !SESSION_ID.test(saved.id) || typeof saved.fxHome !== "string" || !saved.fxHome.startsWith(request.logDirectory + "/")) throw new Error("FX resume identity/worktree/pin mismatch")
    let current: string
    try { current = readFileSync(join(saved.fxHome, "settings.json"), "utf8") } catch { throw new Error("FX saved configuration is missing; refusing to resume") }
    if (current !== settings) throw new Error("FX saved connection/control configuration changed; refusing to resume")
    return { cwd, settings, fxHome: saved.fxHome, resume: saved.id }
  }
  function start(request: FxLaunch): CommandRun {
    const continued = request.resume ? preflightResume({ ...request, resume: request.resume }) : null
    const { cwd, settings } = continued ?? admitted(request)
    const nonce = randomUUID(), output = request.planned_run?.output ?? join(request.logDirectory, nonce + ".fx.json"), errors = request.planned_run?.errors ?? output + ".stderr"
    const fxHome = continued?.fxHome ?? join(request.logDirectory, nonce + ".fx-home"), resume = continued?.resume
    if (!continued) {
      mkdirSync(fxHome, { mode: 0o700 })
      writeFileSync(join(fxHome, "settings.json"), settings, { mode: 0o600 })
      for (const path of authFiles) {
        const target = join(fxHome, path.split("/").pop()!)
        if (existsSync(target)) continue
        copyFileSync(path, target)
        chmodSync(target, 0o600)
      }
    }
    const job: Job = { transport: options.transport, nonce, cwd, fxHome, selection: request.selection, output, errors, ...(resume ? { resume } : {}) }
    const acpLog = output + ".acp.log"
    // FX 0.0.17 `acp --provider <configured name>` fails session/new with -32603; the private settings select the provider instead,
    // and the supervisor verifies the effective provider/model/effort from session configOptions before prompting.
    const acp = { args: ["acp", "--model", request.selection.model, "--effort", request.selection.effort, "--log-file", acpLog], prompt: request.prompt, acp_log: acpLog, events: output + ".events.ndjson" }
    const cliArgs = ["ask", "--json", "--provider", request.selection.provider, "--model", request.selection.model, "--effort", request.selection.effort, "--config", "max_agent_steps=" + FX_PILOT_MAX_STEPS, ...(resume ? ["--resume", resume] : []), "--", request.prompt]
    const jobPath = output + ".job.json"
    const transport = options.transport === "acp" ? acp : { args: cliArgs }
    writeFileSync(jobPath, JSON.stringify({ ...job, ...transport, executable: options.binary, env: { ...env, FX_HOME: fxHome, TMPDIR: request.logDirectory }, env_files: secretEnvFiles, wallMs, maxSteps: FX_PILOT_MAX_STEPS, exhaustion: { dir: join(fxHome, "sessions/v2"), retry_after_seconds: Math.max(1, Math.floor(wallMs / 1000)) } }), { mode: 0o600 })
    const invocation = plannedCommand(process.execPath, [fileURLToPath(new URL(options.transport === "acp" ? "./fx-acp-supervisor.ts" : "./process-supervisor.ts", import.meta.url)), jobPath], request.planned_run)
    const child = spawn(invocation.executable, invocation.args, { detached: true, stdio: "ignore", env: { ...env, PATH: process.env.PATH }, cwd })
    child.once("error", error => writeFileSync(errors, error.message))
    if (!child.pid) throw new Error("FX supervisor admission uncertain")
    const pid = child.pid
    const run: CommandRun = { pid, output, errors, started_at: request.planned_run?.started_at ?? new Date().toISOString(), proc_start: processStartTime(pid) }
    const ownership = { child, run: { ...run } }
    children.set(pid, ownership)
    child.once("close", () => { if (children.get(pid) === ownership) children.delete(pid) })
    child.unref()
    return run
  }
  return { capabilities: FX_CAPABILITIES, available, preflightResume, start, status: fxResult, session: fxSession, cancel(run: CommandRun) {
    const owned = children.get(run.pid)?.run
    if (!owned || owned.output !== run.output || owned.started_at !== run.started_at || owned.proc_start !== run.proc_start || processIdentity(run) !== "same") return false
    try { process.kill(-run.pid, "SIGTERM"); return true } catch { return false }
  } }
}
export type FxAdapter = ReturnType<typeof makeFxAdapter>

function sameSelection(a: FxSelection, b: FxSelection): boolean {
  return a.model === b.model && a.effort === b.effort && a.provider === b.provider && a.runtimeVersion === b.runtimeVersion
}
