import { spawn } from "node:child_process"
import { readFileSync, writeFileSync, renameSync, openSync, readSync, closeSync, readdirSync, statSync } from "node:fs"
import { join } from "node:path"

const job = JSON.parse(readFileSync(process.argv[2]!, "utf8")) as {
  nonce: string; executable: string; args: string[]; cwd: string; env: NodeJS.ProcessEnv; env_files?: Record<string, string>; wallMs: number; output: string; errors: string
  exhaustion?: { dir: string; retry_after_seconds: number }
}
const MAX_BYTES = 1_048_576
const MAX_SECRET_BYTES = 16_384
let reason: "exit" | "cancelled" | "deadline" | "oversized" | "spawn" | "supervision" | "exhausted" = "exit"
let stdout = "", stderr = ""
const errorFd = openSync(job.errors, "wx", 0o600)
function secretEnv(): NodeJS.ProcessEnv {
  const env = { ...job.env }
  for (const [name, path] of Object.entries(job.env_files ?? {})) {
    const content = readFileSync(path, "utf8")
    if (Buffer.byteLength(content) > MAX_SECRET_BYTES) throw new Error("secret env file too large: " + name)
    env[name] = content.trimEnd()
  }
  return env
}
let childEnv: NodeJS.ProcessEnv
try { childEnv = secretEnv() } catch (error) {
  closeSync(errorFd)
  const temporary = job.output + ".tmp"
  writeFileSync(temporary, JSON.stringify({ schema: 1, nonce: job.nonce, supervisor_pid: process.pid, child_pid: null, code: null, signal: null, reason: "spawn", stdout: "", stderr: String(error).slice(0, 4096) }), { mode: 0o600 })
  renameSync(temporary, job.output)
  process.exit(1)
}
const child = (() => {
  try { return spawn(job.executable, job.args, { cwd: job.cwd, env: childEnv, stdio: ["ignore", "pipe", "pipe"] }) }
  catch (error) { closeSync(errorFd); throw error }
})()
let escalation: NodeJS.Timeout | undefined
function stop(why: typeof reason) {
  if (reason !== "exit") return
  reason = why
  child.kill("SIGTERM")
  escalation = setTimeout(() => process.kill(-process.pid, "SIGKILL"), 2000)
}
for (const signal of ["SIGTERM", "SIGINT", "SIGHUP", "SIGQUIT"] as const) process.on(signal, () => stop("cancelled"))
const deadline = setTimeout(() => stop("deadline"), job.wallMs)
// Optional provider-exhaustion watch: scan appended session-log records for a
// quota failure or a provider-declared retry delay beyond this job's bound.
// Content predating the job (resumed sessions) is baselined, never matched.
const exhaustion = job.exhaustion
const exhaustionOffsets = new Map<string, number>()
const jobStartedMs = Date.now()
function exhaustionHit(): boolean {
  if (!exhaustion) return false
  let entries
  try { entries = readdirSync(exhaustion.dir, { withFileTypes: true }) } catch { return false }
  for (const entry of entries) {
    if (!entry.isDirectory()) continue
    const path = join(exhaustion.dir, entry.name, "log.jsonl")
    let stat
    try { stat = statSync(path) } catch { continue }
    let offset = exhaustionOffsets.get(path)
    if (offset === undefined) {
      offset = stat.mtimeMs < jobStartedMs ? stat.size : 0
      exhaustionOffsets.set(path, offset)
    }
    if (stat.size <= offset) { if (stat.size < offset) exhaustionOffsets.set(path, 0); continue }
    let chunk = ""
    try {
      const fd = openSync(path, "r")
      try {
        const buffer = Buffer.alloc(stat.size - offset)
        const got = readSync(fd, buffer, 0, buffer.length, offset)
        chunk = buffer.subarray(0, got).toString("utf8")
      } finally { closeSync(fd) }
    } catch { continue }
    const lastNewline = chunk.lastIndexOf("\n")
    if (lastNewline < 0) continue
    exhaustionOffsets.set(path, offset + lastNewline + 1)
    for (const line of chunk.slice(0, lastNewline).split("\n")) {
      if (line.includes('"failure":"quota"')) return true
      const retry = /"retry_after_s":(\d+)/.exec(line)
      if (retry && Number(retry[1]) > exhaustion.retry_after_seconds) return true
    }
  }
  return false
}
const exhaustionTimer = exhaustion ? setInterval(() => { if (exhaustionHit()) stop("exhausted") }, 2000) : undefined
child.stdout.setEncoding("utf8")
child.stderr.setEncoding("utf8")
child.stdout.on("data", (chunk: string) => {
  if (Buffer.byteLength(stdout) + Buffer.byteLength(chunk) > MAX_BYTES) stop("oversized")
  else stdout += chunk
})
child.stderr.on("data", (chunk: string) => {
  if (Buffer.byteLength(stderr) + Buffer.byteLength(chunk) > MAX_BYTES) stop("oversized")
  else {
    stderr += chunk
    try { writeFileSync(errorFd, chunk) } catch { stop("supervision") }
  }
})
child.once("error", (error: Error) => { reason = "spawn"; stderr = error.message.slice(0, 4096) })
child.once("close", (code, signal) => {
  clearTimeout(deadline); if (escalation) clearTimeout(escalation); if (exhaustionTimer) clearInterval(exhaustionTimer)
  try { closeSync(errorFd) } catch { reason = "supervision" }
  const temporary = job.output + ".tmp"
  writeFileSync(temporary, JSON.stringify({ schema: 1, nonce: job.nonce, supervisor_pid: process.pid, child_pid: child.pid ?? null, code, signal, reason, stdout, stderr }), { mode: 0o600 })
  renameSync(temporary, job.output)
})
if (child.pid) {
  try { writeFileSync(job.output + ".native.json", JSON.stringify({ nonce: job.nonce, supervisor_pid: process.pid, child_pid: child.pid }), { mode: 0o600 }) }
  catch { stop("supervision") }
}
