import { randomUUID } from "node:crypto"
import { appendFileSync, existsSync, readdirSync, readFileSync } from "node:fs"
import { join } from "node:path"
import { fileURLToPath } from "node:url"
import { createRequire } from "node:module"
import { REQUEST, REPLY, COMPLETE, record, string, role, persist, steerNative, unwrap, runDetails, terminal, type Job, type Reply, type Result, type Rpc } from "./native-delegation.ts"
import { ensureOpenCodeApiKey } from "./opencode-auth.ts"
import { MUSE_AGENT_NAMES, isMuseTier } from "./tier-policy.ts"
import { MUSE_PROVIDER, museExtensionPath, musePreflight } from "./muse-subscription.ts"
import { registerRequiredChildExtensions } from "pi-subagents/required-child-extensions"
import { assertTierProfiles, tierGuardPath } from "./tier-profile.ts"
import {
  createAgentSession, DefaultResourceLoader, getAgentDir, ModelRuntime,
  SessionManager, SettingsManager, type ExtensionAPI,
} from "@earendil-works/pi-coding-agent"

const require = createRequire(import.meta.url)
const subagentsExtensionPath = require.resolve("pi-subagents")
const POLL_MS = 1500
const TIMEOUT_MS = 4 * 60 * 60 * 1000

function ids(event: Record<string, unknown>): string[] {
  const details = record(event.details)
  return [event.runId, event.id, event.asyncId, details?.runId, details?.id, details?.asyncId]
    .filter((v): v is string => typeof v === "string" && v.length > 0)
}

function artifactResult(sessionDir: string, asyncDir: string | null, runId: string, sessionFile: string): Result | null {
  const roots = [asyncDir, join(sessionDir, "subagent-artifacts")].filter((v): v is string => !!v)
  for (const root of roots) {
    if (!existsSync(root)) continue
    let files: string[]
    try { files = readdirSync(root) } catch { continue }
    const metaName = files.find((f) => f.includes(runId) && f.endsWith("_meta.json"))
      ?? (files.includes("meta.json") && root.includes(runId) ? "meta.json" : undefined)
    if (!metaName) continue
    try {
      const meta = JSON.parse(readFileSync(join(root, metaName), "utf8")) as Record<string, unknown>
      const outputName = files.find((f) => f.includes(runId) && f.endsWith("_output.md"))
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

async function statusResult(rpc: Rpc, runId: string, sessionFile: string): Promise<Result | null> {
  for (const params of [{ id: runId }, { runId }]) {
    try {
      const reply = await rpc("status", params)
      if (!reply.success) continue
      const data = record(reply.data)
      if (!data) continue
      const details = record(data.details) ?? {}
      const results = Array.isArray(details.results) ? details.results : (Array.isArray(data.results) ? data.results : [])
      const child = results.length === 1 ? record(results[0]) : null
      const state = string(details.state) ?? string(data.state) ?? string(child?.state)
      const terminalState = ["succeeded", "failed", "cancelled", "canceled", "stopped", "completed", "error"].includes(state ?? "")
      const text = string(child?.output) ?? string(details.output) ?? string(data.text) ?? (typeof data.text === "string" ? data.text : null)
      const error = string(child?.error) ?? string(details.error) ?? string(data.error)
      if (state === "stopped" || state === "cancelled" || state === "canceled")
        return { state: "cancelled", error: error ?? "Native subagent stopped", text, sessionFile, runId, usage: details.usage ?? null }
      if (state === "failed" || state === "error" || (terminalState && (details.success === false || child?.success === false)))
        return { state: "failed", error: error ?? "Native subagent failed", text, sessionFile, runId, usage: details.usage ?? null }
      if (state === "succeeded" || state === "completed" || details.success === true)
        return text ? { state: "succeeded", error: null, text, sessionFile, runId, usage: details.usage ?? null }
          : { state: "failed", error: "Native subagent completed without a proof record", text, sessionFile, runId, usage: details.usage ?? null }
    } catch { /* try next shape */ }
  }
  return null
}

function drainSteering(controlPath: string, receiptPath: string, offset: number, runId: string, rpc: Rpc): number {
  let buffer: Buffer
  try { buffer = readFileSync(controlPath) } catch { return offset }
  if (buffer.length <= offset) return offset
  const chunk = buffer.subarray(offset)
  const end = chunk.lastIndexOf(0x0a)
  if (end < 0) return offset
  for (const line of chunk.subarray(0, end).toString("utf8").split("\n")) {
    if (!line.trim()) continue
    let request: Record<string, unknown> | null = null
    try { request = record(JSON.parse(line)) } catch { continue }
    if (!request || typeof request.id !== "string" || typeof request.message !== "string") continue
    const requestId = request.id, message = request.message
    void steerNative(rpc, runId, message).then(
      (data) => {
        try { appendFileSync(receiptPath, JSON.stringify({ id: requestId, ok: true, data }) + "\n") }
        catch {}
      },
      (error) => {
        try { appendFileSync(receiptPath, JSON.stringify({ id: requestId, ok: false, error: String(error) }) + "\n") }
        catch {}
      })
  }
  return offset + end + 1
}

async function run(job: Job, started: (id: string) => void, dispatching: () => void): Promise<Result> {
  // Children inherit a no-package-network environment even when the worktree
  // contains an npm/git Pi package declaration.
  process.env.PI_OFFLINE = "1"
  process.env.PI_SKIP_VERSION_CHECK = "1"
  const tier = role(job)
  const muse = job.model.providerID === MUSE_PROVIDER
  if (muse) {
    process.env.PI_MUSE_SDK_CONTRIBUTOR = "on"
    const preflight = musePreflight()
    if (!preflight.available) throw new Error(preflight.issue ?? "Muse Code is unavailable")
  } else ensureOpenCodeApiKey()
  const runtime = await ModelRuntime.create()
  // Extension providers register when the SDK host binds its extensions; it never calls the model itself.
  const model = muse ? undefined : runtime.getModel(job.model.providerID, job.model.id)
  if (!muse && (!model || !runtime.hasConfiguredAuth(job.model.providerID)))
    throw new Error("Pinned Pi provider/model unavailable or credentials not configured")
  const manager = job.priorSessionFile
    ? SessionManager.open(job.priorSessionFile, job.sessionDir, job.cwd)
    : SessionManager.create(job.cwd, job.sessionDir)
  const agentDir = getAgentDir()
  if (!job.priorRunId) assertTierProfiles(agentDir)
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
      if (!event) return
      for (const id of ids(event)) {
        completions.set(id, event)
        const resolve = waiters.get(id)
        if (resolve) { waiters.delete(id); resolve(event) }
      }
    })
  }
  const loader = new DefaultResourceLoader({
    cwd: job.cwd, agentDir, settingsManager: settings,
    noExtensions: true, noSkills: true, noPromptTemplates: true, noThemes: true, noContextFiles: true,
    additionalExtensionPaths: [subagentsExtensionPath, ...(muse ? [museExtensionPath()] : [])],
    extensionFactories: [rpcExtension],
  })
  await loader.reload()
  const errors = loader.getExtensions().errors
  if (errors.length > 0) throw new Error("Pi extension initialization failed: " + errors.map((e) => e.error).join("; "))
  const { session } = await createAgentSession({
    cwd: job.cwd, agentDir, modelRuntime: runtime, ...(model ? { model } : {}), thinkingLevel: job.model.variant === "max" ? "max" :
      job.model.variant === "xhigh" ? "xhigh" : job.model.variant === "medium" ? "medium" : "high",
    sessionManager: manager, settingsManager: settings, resourceLoader: loader, noTools: "builtin",
  })
  try {
    await session.bindExtensions({})
    if (muse) {
      // Muse registers at bindExtensions rather than in the initial ModelRuntime catalog.
      if (!runtime.getModel(job.model.providerID, job.model.id) ||
          !runtime.hasConfiguredAuth(job.model.providerID))
        throw new Error("Pinned Muse subscription provider failed to register in the Pi SDK")
    } else if (session.model?.provider !== job.model.providerID || session.model.id !== job.model.id ||
               session.thinkingLevel !== job.model.variant) {
      throw new Error("Pi SDK changed or clamped the pinned model/effort")
    }
    const required = registerRequiredChildExtensions({
      sessionId: manager.getSessionId(),
      extensions: [
        { id: "usr-nested-tier-guard-v1", path: fileURLToPath(tierGuardPath(tier, job.model)) },
        ...(muse ? [{ id: "usr-muse-subscription-v1", path: museExtensionPath() }] : []),
      ],
      requireForAllRunners: true,
    })
    try {
    const rpc = api.send
    if (!rpc) throw new Error("Pi extension RPC is unavailable")
    const ping = unwrap(await rpc("ping", {}))
    if (ping.version !== 1) throw new Error("Unsupported pi-subagents RPC version")
    const sessionFile = session.sessionFile
    if (!sessionFile) throw new Error("Pi host session is not durable")
    const params: Record<string, unknown> = job.priorRunId
      ? { id: job.priorRunId, message: job.prompt }
      : {
          agent: muse && isMuseTier(tier) ? MUSE_AGENT_NAMES[tier] : tier,
          task: job.prompt, async: true, cwd: job.cwd, worktree: false,
          model: job.model.providerID + "/" + job.model.id + ":" + job.model.variant,
          options: { agentScope: "user" },
        }
    dispatching()
    const reply = await rpc(job.priorRunId ? "resume" : "spawn", params)
    const { runId: id, asyncDir } = runDetails(reply)
    started(id)
    const controlPath = job.controlPath, receiptPath = job.receiptPath
    let steerTimer: NodeJS.Timeout | undefined
    const stopSteering = () => {
      if (steerTimer) clearInterval(steerTimer)
      steerTimer = undefined
    }
    if (controlPath && receiptPath) {
      let steerOffset = 0
      steerTimer = setInterval(() => {
        try { steerOffset = drainSteering(controlPath, receiptPath, steerOffset, id, rpc) }
        catch {}
      }, 300)
      steerTimer.unref?.()
    }
    if (completions.has(id)) {
      stopSteering()
      return terminal(completions.get(id)!, id, sessionFile)
    }
    const event = await new Promise<Record<string, unknown>>((resolve, reject) => {
      let settled = false
      const keepalive = setInterval(() => {}, 60_000)
      const finish = (fn: (v: any) => void, v: unknown) => {
        if (settled) return
        settled = true
        clearInterval(keepalive)
        clearInterval(poll)
        clearTimeout(timer)
        stopSteering()
        waiters.delete(id)
        fn(v)
      }
      waiters.set(id, (e) => finish(resolve, e))
      const poll = setInterval(async () => {
        if (settled) return
        try {
          if (completions.has(id)) return finish(resolve, completions.get(id)!)
          const found = artifactResult(job.sessionDir, asyncDir, id, sessionFile) ?? await statusResult(rpc, id, sessionFile)
          if (found) return finish(resolve, { __bridge_result: found })
        } catch { /* keep waiting */ }
      }, POLL_MS)
      poll.unref?.()
      const timer = setTimeout(() => {
        const found = artifactResult(job.sessionDir, asyncDir, id, sessionFile)
        if (found) return finish(resolve, { __bridge_result: found })
        finish(reject, new Error("Timed out waiting for native subagent completion"))
      }, TIMEOUT_MS)
      timer.unref?.()
      // keepalive is intentionally ref'd: prevents silent drain-exit while a dispatched subagent is in flight.
    })
    const synthesized = event.__bridge_result as Result | undefined
    if (synthesized && typeof synthesized === "object" && "state" in synthesized) return synthesized
    return terminal(event, id, sessionFile)
    } finally { required.dispose() }
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
    if (admitted || dispatchAttempted) {
      try {
        const fallback = artifactResult(job.sessionDir, null, "", job.priorSessionFile ?? "")
        if (fallback) { persist(job.resultPath, fallback); process.exitCode = 1; return }
      } catch { /* fall through */ }
      persist(job.resultPath, {
        state: "failed", text: null, sessionFile: job.priorSessionFile ?? null, runId: job.priorRunId ?? null,
        error: error instanceof Error ? error.message : String(error), usage: null,
      })
      process.exitCode = 1
      return
    }
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
