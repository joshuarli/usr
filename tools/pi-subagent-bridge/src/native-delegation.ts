import { renameSync, writeFileSync } from "node:fs"
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
}
export type Result = {
  state: "succeeded" | "failed" | "cancelled"
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

