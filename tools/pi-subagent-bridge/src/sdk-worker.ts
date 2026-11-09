import { randomUUID } from "node:crypto"
import { readFileSync, renameSync, writeFileSync } from "node:fs"
import {
  createAgentSession, DefaultResourceLoader, getAgentDir, ModelRuntime,
  SessionManager, SettingsManager, type ExtensionAPI,
} from "@earendil-works/pi-coding-agent"
import registerSubagents from "pi-subagents"

type Job = {
  cwd: string
  model: { providerID: string; id: string; variant?: string }
  readOnly: boolean
  prompt: string
  sessionDir: string
  priorSessionFile?: string
  priorRunId?: string
  resultPath: string
}
type Result = {
  state: "succeeded" | "failed" | "cancelled"
  error: string | null
  text: string | null
  sessionFile: string | null
  runId: string | null
  usage: unknown
}
type Reply = { success: boolean; data?: unknown; error?: { message?: string } }
type Rpc = (method: string, params: Record<string, unknown>) => Promise<Reply>

const REQUEST = "subagents:rpc:v1:request"
const REPLY = "subagents:rpc:v1:reply:"
const COMPLETE = "subagent:async-complete"

function record(value: unknown): Record<string, unknown> | null {
  return value && typeof value === "object" && !Array.isArray(value) ? value as Record<string, unknown> : null
}
function string(value: unknown): string | null {
  return typeof value === "string" && value.length > 0 ? value : null
}
function role(job: Job): string {
  const identity = job.model.providerID + "/" + job.model.id + ":" + job.model.variant
  const tiers: Record<string, string> = {
    "opencode-go/muse-spark-1.3-contributor:medium": "scout",
    "opencode-go/muse-spark-1.3-contributor:high": "mechanic",
    "opencode-go/deepseek-v4.1-flash:high": "worker",
    "opencode-go/deepseek-v4.1-flash:max": "expert",
  }
  const tier = tiers[identity]
  if (!tier || (job.readOnly !== (tier === "scout"))) throw new Error("Unapproved Pi tier or tool scope")
  return tier
}
function persist(path: string, result: Result): void {
  const temporary = path + "." + process.pid + ".tmp"
  writeFileSync(temporary, JSON.stringify(result), { mode: 0o600, flag: "wx" })
  renameSync(temporary, path)
}
function unwrap(reply: Reply): Record<string, unknown> {
  if (!reply.success) throw new Error("pi-subagents RPC rejected request: " + (reply.error?.message ?? "unknown error"))
  const data = record(reply.data)
  if (!data) throw new Error("pi-subagents RPC returned no data")
  return data
}
function runId(reply: Reply): string {
  const data = unwrap(reply), details = record(data.details)
  const id = string(details?.asyncId) ?? string(details?.runId)
  if (!id || id.length > 128 || !/^[a-zA-Z0-9._-]+$/.test(id))
    throw new Error("pi-subagents RPC returned no trustworthy async run identity")
  return id
}
function terminal(event: Record<string, unknown>, id: string, sessionFile: string): Result {
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

async function run(job: Job, started: (id: string) => void, dispatching: () => void): Promise<Result> {
  const tier = role(job)
  const runtime = await ModelRuntime.create()
  const model = runtime.getModel(job.model.providerID, job.model.id)
  if (!model || !runtime.hasConfiguredAuth(job.model.providerID))
    throw new Error("Pinned Pi provider/model unavailable or credentials not configured")
  const manager = job.priorSessionFile
    ? SessionManager.open(job.priorSessionFile, job.sessionDir, job.cwd)
    : SessionManager.create(job.cwd, job.sessionDir)
  const agentDir = getAgentDir()
  const settings = SettingsManager.inMemory({ retry: { enabled: false }, compaction: { enabled: false } })
  const completions = new Map<string, Record<string, unknown>>()
  const waiters = new Map<string, (event: Record<string, unknown>) => void>()
  const api: { send?: Rpc } = {}
  const rpcExtension = (pi: ExtensionAPI): void => {
    api.send = (method, params) => new Promise<Reply>((resolve) => {
      const requestId = randomUUID()
      const unsubscribe = pi.events.on(REPLY + requestId, (value: unknown) => {
        unsubscribe()
        const data = record(value)
        if (data && typeof data.success === "boolean")
          resolve({ success: data.success, data: data.data, error: record(data.error) ? { message: string(record(data.error)?.message) ?? undefined } : undefined })
        else resolve({ success: false, error: { message: "Malformed pi-subagents RPC response" } })
      })
      pi.events.emit(REQUEST, { version: 1, requestId, method, params })
    })
    pi.events.on(COMPLETE, (value: unknown) => {
      const event = record(value)
      const id = string(event?.runId) ?? string(event?.id)
      if (!id || !event) return
      completions.set(id, event)
      const resolve = waiters.get(id)
      if (resolve) { waiters.delete(id); resolve(event) }
    })
  }
  const loader = new DefaultResourceLoader({
    cwd: job.cwd, agentDir, settingsManager: settings,
    noExtensions: true, noSkills: true, noPromptTemplates: true, noThemes: true, noContextFiles: true,
    extensionFactories: [registerSubagents, rpcExtension],
  })
  await loader.reload()
  const errors = loader.getExtensions().errors
  if (errors.length > 0) throw new Error("Pi extension initialization failed: " + errors.map((e) => e.error).join("; "))
  const { session } = await createAgentSession({
    cwd: job.cwd, agentDir, modelRuntime: runtime, model, thinkingLevel: job.model.variant === "max" ? "max" :
      job.model.variant === "medium" ? "medium" : "high",
    sessionManager: manager, settingsManager: settings, resourceLoader: loader, noTools: "builtin",
  })
  try {
    await session.bindExtensions({})
    const rpc = api.send
    if (!rpc) throw new Error("Pi extension RPC is unavailable")
    const ping = unwrap(await rpc("ping", {}))
    if (ping.version !== 1) throw new Error("Unsupported pi-subagents RPC version")
    const sessionFile = session.sessionFile
    if (!sessionFile) throw new Error("Pi host session is not durable")
    const params: Record<string, unknown> = job.priorRunId
      ? { id: job.priorRunId, message: job.prompt }
      : {
          agent: tier, task: job.prompt, async: true, cwd: job.cwd, worktree: false,
          model: job.model.providerID + "/" + job.model.id + ":" + job.model.variant,
          options: { agentScope: "user" },
        }
    dispatching()
    const reply = await rpc(job.priorRunId ? "resume" : "spawn", params)
    const id = runId(reply)
    started(id)
    const event = completions.get(id) ?? await new Promise<Record<string, unknown>>((resolve) => {
      waiters.set(id, resolve)
    })
    return terminal(event, id, sessionFile)
  } finally {
    session.dispose()
  }
}

async function main(): Promise<void> {
  if (process.argv.length !== 3) throw new Error("usage: sdk-worker.ts JOB_JSON")
  const job = JSON.parse(readFileSync(process.argv[2], "utf8")) as Job
  if (!job || typeof job.cwd !== "string" || typeof job.prompt !== "string" ||
      typeof job.resultPath !== "string" || typeof job.sessionDir !== "string")
    throw new Error("Malformed Pi delegation job")
  let admitted = false
  let dispatchAttempted = false
  try {
    const result = await run(job, () => { admitted = true }, () => { dispatchAttempted = true })
    persist(job.resultPath, result)
  } catch (error) {
    if (admitted || dispatchAttempted) throw error
    persist(job.resultPath, {
      state: "failed", text: null, sessionFile: job.priorSessionFile ?? null, runId: null,
      error: error instanceof Error ? error.message : String(error), usage: null,
    })
    process.exitCode = 1
  }
}

void main().then(() => { process.exit(process.exitCode ?? 0) }, (error) => {
  process.stderr.write("pi-subagent-bridge: " + String(error) + "\n")
  process.exit(1)
})
