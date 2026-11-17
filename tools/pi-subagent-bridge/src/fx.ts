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
export type FxOptions = {
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
type Job = { nonce: string; cwd: string; fxHome: string; selection: FxSelection; output: string; errors: string; resume?: string }
const children = new Map<number, { child: ChildProcess; run: CommandRun }>()
const RESERVED_ENV_PREFIX = /^(?:FX_|LD_|DYLD_|GIT_)/
const RESERVED_ENV_NAMES = new Set(["HOME", "PATH", "SHELL", "TMPDIR", "BASH_ENV", "ENV", "ZDOTDIR", "NODE_OPTIONS", "PYTHONPATH", "PYTHONSTARTUP", "PYTHONHOME", "PERL5OPT", "RUBYOPT"])
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
  return value as Job
}
function nativeSession(job: Job): string | null {
  try {
    const sessions = join(job.fxHome, "sessions/v2")
    const names = readdirSync(sessions, { withFileTypes: true }).filter(entry => entry.isDirectory() && entry.name !== ".tmp").map(entry => entry.name)
    if (names.length !== 1) return null
    const id = names[0]!
    if (!/^[a-zA-Z0-9_-]{1,128}$/.test(id)) return null
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
export function fxSession(run: CommandRun, expected: FxSelection): string | null {
  const job = jobFor(run), id = nativeSession(job)
  if (!sameSelection(job.selection, expected)) throw new Error("FX admitted pin mismatch")
  return id ? token(job, id) : null
}
export function fxResult(run: CommandRun, expected: FxSelection) {
  if (workerAlive(run, false)) return { state: "running", result: null, stderr: null }
  try {
    const job = jobFor(run), receipt = read(run.output)
    if (!sameSelection(job.selection, expected)) throw new Error("FX admitted pin mismatch")
    if (!isRecord(receipt) || receipt.schema !== 1 || receipt.nonce !== job.nonce || receipt.supervisor_pid !== run.pid || typeof receipt.stdout !== "string" || typeof receipt.stderr !== "string") throw new Error("Invalid FX termination receipt")
    if (receipt.reason === "cancelled") return { state: "interrupted", result: null, stderr: receipt.stderr }
    if (receipt.reason === "exhausted") return { state: "failed", result: { subtype: "error" as const, error: "provider quota exhaustion: FX reported a quota failure or a retry delay beyond this job's bound; terminated early", finalText: "" }, stderr: receipt.stderr }
    if (receipt.reason !== "exit" || receipt.signal !== null || receipt.code !== 0) return { state: "failed", result: { subtype: "error" as const, error: `${String(receipt.reason)}: FX exited ${String(receipt.code)} with signal ${String(receipt.signal)}`, finalText: "" }, stderr: receipt.stderr }
    const value: unknown = JSON.parse(receipt.stdout)
    const id = nativeSession(job)
    if (!isRecord(value) || value.exit_code !== receipt.code || value.model !== job.selection.model || !id || value.session_id !== id || (job.resume !== undefined && job.resume !== id) || typeof value.final_output !== "string" || !value.final_output.trim()) throw new Error("FX result/native session mismatch or missing final response")
    const result: CommandResult = { subtype: "success", sessionId: token(job, id), finalText: value.final_output, usage: value.usage }
    return { state: "succeeded", result, stderr: receipt.stderr }
  } catch (error) { return { state: "unknown_or_interrupted", result: null, stderr: String(error) } }
}
export function makeFxAdapter(options: FxOptions) {
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
  const env: NodeJS.ProcessEnv = { HOME: home, PATH: pathEnv, SHELL: "/bin/sh", FX_AUTO_UPGRADE: "0", FX_DISABLE_KEYCHAIN: "1", FX_HERDR: "0", FX_SOUND: "off", FX_MAX_AGENT_STEPS: "20", ...options.extraEnv }
  for (const name of Object.keys(secretEnvFiles)) {
    if (name in env || name === "FX_HOME" || name === "TMPDIR") throw new Error("FX secret env name collides with the qualified environment: " + name)
  }
  function available(selection: FxSelection): boolean {
    if (isBannedModel(selection.model) || selection.provider !== options.provider || selection.runtimeVersion !== "0.0.17") return false
    try { return createHash("sha256").update(readFileSync(options.binary)).digest("hex") === options.binarySha256 && execFileSync(options.binary, ["--version"], { env, encoding: "utf8", timeout: deadlineTimeout(5000) }).trim() === selection.runtimeVersion } catch { return false }
  }
  function start(request: FxLaunch): CommandRun {
    if (!available(request.selection)) throw new Error("Pinned FX binary/provider unavailable")
    const cwd = realpathSync(request.directory), underHome = relative(home, cwd)
    if (!underHome || underHome.startsWith("..") || isAbsolute(underHome)) throw new Error("FX qualification worktree must be beneath its private HOME")
    const nonce = randomUUID(), output = request.planned_run?.output ?? join(request.logDirectory, nonce + ".fx.json"), errors = request.planned_run?.errors ?? output + ".stderr"
    let fxHome = join(request.logDirectory, nonce + ".fx-home"), resume: string | undefined
    if (request.resume) {
      if (!request.resume.startsWith("fx:0.0.17:")) throw new Error("Unsupported FX resume token")
      const saved: unknown = JSON.parse(Buffer.from(request.resume.slice("fx:0.0.17:".length), "base64url").toString("utf8"))
      if (!isRecord(saved) || saved.cwd !== cwd || (!isRecord(saved.selection) || saved.selection.model !== request.selection.model || saved.selection.effort !== request.selection.effort || saved.selection.provider !== request.selection.provider || saved.selection.runtimeVersion !== request.selection.runtimeVersion) || typeof saved.id !== "string" || !/^[a-zA-Z0-9_-]{1,128}$/.test(saved.id) || typeof saved.fxHome !== "string" || !saved.fxHome.startsWith(request.logDirectory + "/")) throw new Error("FX resume identity/worktree/pin mismatch")
      fxHome = saved.fxHome; resume = saved.id
    } else mkdirSync(fxHome, { mode: 0o700 })
    const readOnly = request.access.kind === "read-only"
    const connection = options.connection == null ? {} : { providers: { [options.provider]: options.connection } }
    const settings = JSON.stringify({ auto_upgrade: false, cache_warming: false, session_titles: false, max_agent_steps: 20, provider: options.provider, models: { [options.provider]: request.selection.model }, ...connection, permission: { "*": "deny", read: "allow", glob: "allow", grep: "allow", edit: readOnly ? "deny" : "allow", bash: readOnly ? "deny" : Object.fromEntries(options.allowedCommands.map(command => [command, "allow"])), subagent: "deny", toolbox: "deny" }, workspaces: { [cwd]: { enableAllProjectMcpServers: false } } })
    if (resume) {
      if (readFileSync(join(fxHome, "settings.json"), "utf8") !== settings) throw new Error("FX saved connection/control configuration changed; refusing to resume")
    } else {
      writeFileSync(join(fxHome, "settings.json"), settings, { mode: 0o600 })
      for (const path of authFiles) {
        const target = join(fxHome, path.split("/").pop()!)
        if (existsSync(target)) continue
        copyFileSync(path, target)
        chmodSync(target, 0o600)
      }
    }
    const job: Job = { nonce, cwd, fxHome, selection: request.selection, output, errors, ...(resume ? { resume } : {}) }
    const args = ["ask", "--json", "--provider", request.selection.provider, "--model", request.selection.model, "--effort", request.selection.effort, "--config", "max_agent_steps=20", ...(resume ? ["--resume", resume] : []), "--", request.prompt]
    const jobPath = output + ".job.json"
    writeFileSync(jobPath, JSON.stringify({ ...job, executable: options.binary, args, env: { ...env, FX_HOME: fxHome, TMPDIR: request.logDirectory }, env_files: secretEnvFiles, wallMs, exhaustion: { dir: join(fxHome, "sessions/v2"), retry_after_seconds: Math.max(1, Math.floor(wallMs / 1000)) } }), { mode: 0o600 })
    const invocation = plannedCommand(process.execPath, [fileURLToPath(new URL("./process-supervisor.ts", import.meta.url)), jobPath], request.planned_run)
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
  return { capabilities: FX_CAPABILITIES, available, start, status: fxResult, session: fxSession, cancel(run: CommandRun) {
    const owned = children.get(run.pid)?.run
    if (!owned || owned.output !== run.output || owned.started_at !== run.started_at || owned.proc_start !== run.proc_start || processIdentity(run) !== "same") return false
    try { process.kill(-run.pid, "SIGTERM"); return true } catch { return false }
  } }
}
export type FxAdapter = ReturnType<typeof makeFxAdapter>

function sameSelection(a: FxSelection, b: FxSelection): boolean {
  return a.model === b.model && a.effort === b.effort && a.provider === b.provider && a.runtimeVersion === b.runtimeVersion
}
