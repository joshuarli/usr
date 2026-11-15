import { spawn } from "node:child_process"
import { readFileSync, writeFileSync, renameSync, openSync, closeSync } from "node:fs"

const job = JSON.parse(readFileSync(process.argv[2]!, "utf8")) as {
  nonce: string; executable: string; args: string[]; cwd: string; env: NodeJS.ProcessEnv; env_files?: Record<string, string>; wallMs: number; output: string; errors: string
}
const MAX_BYTES = 1_048_576
const MAX_SECRET_BYTES = 16_384
let reason: "exit" | "cancelled" | "deadline" | "oversized" | "spawn" | "supervision" = "exit"
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
  clearTimeout(deadline); if (escalation) clearTimeout(escalation)
  try { closeSync(errorFd) } catch { reason = "supervision" }
  const temporary = job.output + ".tmp"
  writeFileSync(temporary, JSON.stringify({ schema: 1, nonce: job.nonce, supervisor_pid: process.pid, child_pid: child.pid ?? null, code, signal, reason, stdout, stderr }), { mode: 0o600 })
  renameSync(temporary, job.output)
})
if (child.pid) {
  try { writeFileSync(job.output + ".native.json", JSON.stringify({ nonce: job.nonce, supervisor_pid: process.pid, child_pid: child.pid }), { mode: 0o600 }) }
  catch { stop("supervision") }
}
