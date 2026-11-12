import { basename, join } from "node:path"
import { existsSync, readdirSync, readFileSync, renameSync, writeFileSync } from "node:fs"
import { tierForModel, type Tier } from "./tier-policy.ts"

export type Job = {
  cwd: string
  model: { providerID: string; id: string; variant?: string }
  readOnly: boolean
  prompt: string
  sessionDir: string
  priorSessionFile?: string
  priorRunId?: string
  resultPath: string
  controlPath?: string
  receiptPath?: string
}
export type Result = {
  state: "succeeded" | "failed" | "cancelled" | "unknown_or_interrupted"
  error: string | null
  text: string | null
  sessionFile: string | null
  runId: string | null
  usage: unknown
}
export type Reply = { success: boolean; data?: unknown; error?: { message?: string } }
export type Rpc = (method: string, params: Record<string, unknown>) => Promise<Reply>

export const REQUEST = "subagents:rpc:v1:request"
export const REPLY = "subagents:rpc:v1:reply:"
export const COMPLETE = "subagent:async-complete"

export function record(value: unknown): Record<string, unknown> | null {
  return value && typeof value === "object" && !Array.isArray(value) ? value as Record<string, unknown> : null
}
export function string(value: unknown): string | null {
  return typeof value === "string" && value.length > 0 ? value : null
}
export function role(job: Job): Tier {
  return tierForModel(job.model, job.readOnly)
}
export function persist(path: string, result: Result): void {
  const temporary = path + "." + process.pid + ".tmp"
  writeFileSync(temporary, JSON.stringify(result), { mode: 0o600, flag: "wx" })
  renameSync(temporary, path)
}
export function unwrap(reply: Reply): Record<string, unknown> {
  if (!reply.success) throw new Error("pi-subagents RPC rejected request: " + (reply.error?.message ?? "unknown error"))
  const data = record(reply.data)
  if (!data) throw new Error("pi-subagents RPC returned no data")
  return data
}
export async function steerNative(rpc: Rpc, id: string, message: string): Promise<Record<string, unknown> | null> {
  const reply = await rpc("steer", { id, message })
  if (!reply.success) throw new Error("pi-subagents RPC rejected steer: " + (reply.error?.message ?? "unknown error"))
  return record(reply.data)
}
export function runDetails(reply: Reply): { runId: string; asyncDir: string | null } {
  const data = unwrap(reply), details = record(data.details)
  const runId = string(details?.asyncId) ?? string(details?.runId)
  if (!runId || runId.length > 128 || !/^[a-zA-Z0-9._-]+$/.test(runId))
    throw new Error("pi-subagents RPC returned no trustworthy async run identity")
  return { runId, asyncDir: string(details?.asyncDir) }
}
export function runId(reply: Reply): string { return runDetails(reply).runId }
export function terminal(event: Record<string, unknown>, id: string, sessionFile: string): Result {
  const results = Array.isArray(event.results) ? event.results : []
  const child = results.length === 1 ? record(results[0]) : null
  const text = string(child?.output)
  const cancelled = event.state === "stopped" || event.state === "paused" || child?.stopped === true
  if (cancelled)
    return { state: "cancelled", error: string(child?.error) ?? "Native subagent stopped", text, sessionFile, runId: id, usage: null }
  if (event.success !== true || child?.success !== true)
    return { state: "failed", error: string(child?.error) ?? "Native subagent failed", text, sessionFile, runId: id, usage: null }
  if (!text)
    return { state: "failed", error: "Native subagent completed without a proof record", text, sessionFile, runId: id, usage: null }
  return { state: "succeeded", error: null, text, sessionFile, runId: id, usage: null }
}


export function artifactResult(sessionDir: string, asyncDir: string | null, runId: string, sessionFile: string): Result | null {
  if (!runId || !/^[a-zA-Z0-9._-]+$/.test(runId)) return null
  const roots = [asyncDir, join(sessionDir, "subagent-artifacts")].filter((v): v is string => !!v)
  for (const root of roots) {
    if (!existsSync(root)) continue
    let files: string[]
    try { files = readdirSync(root) } catch { continue }
    const metaName = files.find((f) => f.startsWith(runId + "_") && f.endsWith("_meta.json"))
      ?? (files.includes("meta.json") && basename(root) === runId ? "meta.json" : undefined)
    if (!metaName) continue
    try {
      const meta = JSON.parse(readFileSync(join(root, metaName), "utf8")) as Record<string, unknown>
      if (meta.runId !== runId) continue
      const outputName = metaName === "meta.json" ? "output.md" : metaName.replace(/_meta\.json$/, "_output.md")
      const output = outputName ? readFileSync(join(root, outputName), "utf8") : null
      const error = typeof meta.error === "string" && meta.error ? meta.error : null
      const text = typeof output === "string" && output.trim() ? output : null
      const usage = meta.usage ?? null
      if (meta.exitCode === 0 || meta.success === true) {
        if (text) return { state: "succeeded", error: null, text, sessionFile, runId, usage }
        return { state: "failed", error: error ?? "Native subagent completed without a proof record", text, sessionFile, runId, usage }
      }
      if (error || meta.exitCode !== undefined || meta.success === false) {
        return { state: "failed", error: error ?? text ?? "Native subagent failed", text, sessionFile, runId, usage }
      }
    } catch { /* keep polling */ }
  }
  return null
}


export type Admission = { runId: string; asyncDir: string | null; sessionFile: string }
export async function executeJob(job: Job, run: (
  job: Job, started: (admission: Admission) => void, dispatching: () => void,
) => Promise<Result>): Promise<boolean> {
  let admission: Admission | null = null
  let dispatched = false
  try {
    const result = await run(job, (value) => { admission = value }, () => { dispatched = true })
    persist(job.resultPath, result)
    return false
  } catch (error) {
    const owned = admission as Admission | null
    const recovered = owned && artifactResult(job.sessionDir, owned.asyncDir, owned.runId, owned.sessionFile)
    persist(job.resultPath, recovered ?? {
      state: dispatched ? "unknown_or_interrupted" : "failed", text: null,
      sessionFile: owned?.sessionFile ?? job.priorSessionFile ?? null,
      runId: owned?.runId ?? null,
      error: error instanceof Error ? error.message : String(error), usage: null,
    })
    return true
  }
}
