import { execFileSync, spawn, type ChildProcess } from "node:child_process"
import { randomUUID } from "node:crypto"
import {
  appendFileSync, closeSync, mkdirSync, openSync, readFileSync, readdirSync,
  renameSync, rmSync, writeFileSync,
} from "node:fs"
import { dirname, isAbsolute, join, relative } from "node:path"
import { fileURLToPath } from "node:url"
import type { ModelRef, OpenCodePort } from "./bridge.ts"
import { ensureOpenCodeApiKey } from "./opencode-auth.ts"
import { GO_TIER_MODELS, MUSE_TIER_MODELS, MAX_SUBAGENT_DEPTH, TIERS } from "./tier-policy.ts"
import { musePreflight } from "./muse-subscription.ts"

type Result = {
  state: "succeeded" | "failed" | "cancelled" | "unknown_or_interrupted"
  text: string | null; error: string | null; usage: unknown; sessionFile: string | null; runId: string | null
}
type Run = { pid: number; output: string; errors: string; control?: string; receipts?: string }
type Stored = {
  id: string; title: string; model: ModelRef; cwd: string
  metadata: { usr_worker_v1: { directory: string; model: ModelRef } }
  readOnly: boolean; run?: Run; admitting?: boolean
}
const SESSION = /^ses_[a-f0-9]{32}$/
const children = new Map<number, ChildProcess>()
const worker = fileURLToPath(new URL("./sdk-worker.ts", import.meta.url))
// Derive the supported catalog from the same typed pins used at admission.
const VARIANTS = new Map<string, { providerID: "opencode-go"; variants: Set<string> }>()
for (const tier of TIERS) {
  const { providerID, id, variant } = GO_TIER_MODELS[tier]
  const group = VARIANTS.get(id)
  if (group) {
    group.variants.add(variant)
  } else {
    VARIANTS.set(id, { providerID, variants: new Set([variant]) })
  }
}

function stateDir(cwd: string): string {
  const common = execFileSync("git", ["-C", cwd, "rev-parse", "--path-format=absolute", "--git-common-dir"],
    { encoding: "utf8", timeout: 10000 }).trim()
  const root = dirname(common)
  execFileSync("git", ["-C", root, "check-ignore", "-q", ".work/worker-bridge/state"],
    { stdio: "ignore", timeout: 10000 })
  const dir = join(root, ".work", "worker-bridge")
  mkdirSync(dir, { recursive: true, mode: 0o700 })
  return dir
}
function statePath(cwd: string, id: string): string {
  if (!SESSION.test(id)) throw new Error("Invalid Pi session ID")
  return join(stateDir(cwd), id + ".pi.json")
}
function load(cwd: string | undefined, id: string): Stored {
  if (!cwd) throw new Error("Pi worker operations require the worktree path")
  const s: Stored = JSON.parse(readFileSync(statePath(cwd, id), "utf8"))
  if (s.id !== id || s.cwd !== cwd || !SESSION.test(s.id))
    throw new Error("Pi worker session/worktree mismatch")
  return s
}
function save(s: Stored): void {
  const path = statePath(s.cwd, s.id), temporary = path + "." + randomUUID() + ".tmp"
  try {
    writeFileSync(temporary, JSON.stringify(s), { mode: 0o600, flag: "wx" })
    renameSync(temporary, path)
  } finally {
    rmSync(temporary, { force: true })
  }
}
function alive(pid: number): boolean {
  if (children.has(pid)) return true
  try { process.kill(pid, 0); return true }
  catch (error) { return (error as NodeJS.ErrnoException).code === "EPERM" }
}
function observe(s: Stored): { state: string; result: Result | null } {
  if (s.admitting) return { state: "blocked_transition", result: null }
  if (!s.run) return { state: "blocked_admission", result: null }
  try {
    const result: Result = JSON.parse(readFileSync(s.run.output, "utf8"))
    if (!["succeeded", "failed", "cancelled"].includes(result.state))
      throw new Error("Invalid Pi result state")
    if (result.state === "succeeded" && (!result.runId?.trim() || !result.sessionFile?.trim()))
      throw new Error("Pi success has no owned native identity")
    return { state: result.state, result }
  } catch (error) {
    if (!(error instanceof Error && "code" in error && error.code === "ENOENT"))
      return { state: "unknown_or_interrupted", result: null }
  }
  return { state: alive(s.run.pid) ? "running" : "unknown_or_interrupted", result: null }
}
function run(s: Stored, prompt: string, priorSessionFile?: string, priorRunId?: string): Run {
  const dir = stateDir(s.cwd), id = randomUUID()
  const output = join(dir, id + ".result.json"), errors = join(dir, id + ".stderr")
  const jobPath = join(dir, id + ".job.json")
  const control = join(dir, id + ".steer.ndjson"), receipts = join(dir, id + ".steer-receipts.ndjson")
  const sessionDir = join(dir, "pi-sessions")
  mkdirSync(sessionDir, { recursive: true, mode: 0o700 })
  writeFileSync(control, "", { mode: 0o600, flag: "wx" })
  writeFileSync(receipts, "", { mode: 0o600, flag: "wx" })
  const job = {
    cwd: s.cwd, model: s.model, readOnly: s.readOnly, prompt,
    sessionDir, priorSessionFile, priorRunId, resultPath: output, controlPath: control, receiptPath: receipts,
  }
  writeFileSync(jobPath, JSON.stringify(job), { mode: 0o600, flag: "wx" })
  const fd = openSync(errors, "wx", 0o600)
  try {
    const child = spawn(process.execPath, ["--experimental-strip-types", worker, jobPath], {
      cwd: s.cwd, stdio: ["ignore", "ignore", fd],
      env: { ...process.env, PI_OFFLINE: "1", PI_SKIP_VERSION_CHECK: "1", PI_SUBAGENT_MAX_DEPTH: String(MAX_SUBAGENT_DEPTH) },
    })
    const pid = child.pid
    child.on("error", (error) => {
      if (pid !== undefined) children.delete(pid)
      try { appendFileSync(errors, "spawn error: " + error.message + "\n") } catch { /* preserve admission error */ }
    })
    child.on("close", () => { if (pid !== undefined) children.delete(pid) })
    if (pid === undefined) throw new Error("Cannot launch Pi SDK worker")
    children.set(pid, child)
    child.unref()
    return { pid, output, errors, control, receipts }
  } finally { closeSync(fd) }
}
function verifiedSessionPath(s: Stored, value: string | null): string {
  if (!value || !isAbsolute(value)) throw new Error("No durable Pi session to resume")
  const dir = join(stateDir(s.cwd), "pi-sessions")
  const name = relative(dir, value)
  if (!name || name === ".." || name.startsWith("../") || isAbsolute(name) || !name.endsWith(".jsonl"))
    throw new Error("Pi session file is outside the owned state directory")
  return value
}

export function piPort(): OpenCodePort {
  return {
    async models() {
      ensureOpenCodeApiKey()
      const { ModelRuntime } = await import("@earendil-works/pi-coding-agent")
      const runtime = await ModelRuntime.create()
      const available: Array<{
        id: string; providerID: string; enabled: boolean; status: string; variants: { id: string }[]
      }> = [...VARIANTS]
        .filter(([id, config]) => runtime.getModel(config.providerID, id) && runtime.hasConfiguredAuth(config.providerID))
        .map(([id, config]) => ({
          id, providerID: config.providerID, enabled: true, status: "active",
          variants: [...config.variants].map((variant) => ({ id: variant })),
        }))
      if (musePreflight().available) {
        const variants = new Set<string>()
        for (const t of ["scout", "mechanic", "worker"] as const) {
          const m = (MUSE_TIER_MODELS as any)[t]
          if (m) variants.add(m.variant)
        }
        available.push({
          id: MUSE_TIER_MODELS.scout.id === MUSE_TIER_MODELS.mechanic.id ? MUSE_TIER_MODELS.scout.id : (MUSE_TIER_MODELS as any).worker?.id ?? MUSE_TIER_MODELS.scout.id,
          providerID: "muse-sdk", enabled: true, status: "active",
          variants: Array.from(variants).map((variant) => ({ id: variant })),
        })
        // Also add worker model explicitly if different
        if ((MUSE_TIER_MODELS as any).worker && (MUSE_TIER_MODELS as any).worker.id !== MUSE_TIER_MODELS.scout.id) {
          available.push({
            id: (MUSE_TIER_MODELS as any).worker.id, providerID: "muse-sdk", enabled: true, status: "active",
            variants: [{ id: (MUSE_TIER_MODELS as any).worker.variant }],
          })
        }
      }
      return { data: available }
    },
    async create(input) {
      const id = "ses_" + randomUUID().replaceAll("-", "")
      const s: Stored = {
        id, cwd: input.location.directory, title: input.title,
        model: input.model, metadata: input.metadata, readOnly: input.agent === "plan",
      }
      save(s)
      return { data: { id } }
    },
    async prompt(input) {
      const s = load(input.cwd, input.sessionID)
      let prior: string | undefined
      let priorRunId: string | undefined
      if (s.run) {
        const previous = observe(s)
        if (!previous.result || !["succeeded", "failed", "cancelled"].includes(previous.state))
          throw new Error("Pi session is not known terminal; no overlapping run")
        prior = verifiedSessionPath(s, previous.result.sessionFile)
        if (!previous.result.runId) throw new Error("No native subagent run identity for same-session correction")
        priorRunId = previous.result.runId
      }
      s.admitting = true
      save(s)
      const launched = run(s, input.text, prior, priorRunId)
      s.run = launched
      s.admitting = false
      save(s)
      return { data: { admitted: true } }
    },
    async get(input) {
      const s = load(input.cwd, input.sessionID), status = observe(s)
      return { data: {
        id: s.id, title: s.title, model: s.model,
        location: { directory: s.cwd }, metadata: s.metadata,
        outcome: status.state, error: status.result?.error ?? null,
        tokens: status.result?.usage ?? null,
      } }
    },
    async active(input) {
      if (!input?.cwd) return { data: {} }
      const dir = stateDir(input.cwd), sessions: Record<string, boolean> = {}
      for (const filename of readdirSync(dir)) {
        if (!/^ses_[a-f0-9]{32}\.pi\.json$/.test(filename)) continue
        const id = filename.slice(0, -8)
        const entry = JSON.parse(readFileSync(join(dir, filename), "utf8")) as Stored
        if (entry.cwd !== input.cwd || entry.id !== id) continue
        if (observe(entry).state === "running") sessions[id] = true
      }
      return { data: sessions }
    },
    async inbox() { return { data: [] } },
    async messages(input) {
      const status = observe(load(input.cwd, input.sessionID))
      return { data: [{
        info: { role: "assistant", error: status.result?.error ?? null },
        parts: status.result?.text ? [{ type: "text", text: status.result.text }] : [],
      }] }
    },
    async interrupt(input) {
      const s = load(input.cwd, input.sessionID)
      const child = s.run && children.get(s.run.pid)
      return { data: { interrupted: child ? child.kill("SIGTERM") : false } }
    },
    async steer(input) {
      const s = load(input.cwd, input.sessionID)
      if (!s.run?.control || !s.run.receipts) throw new Error("Pi worker has no steering channel")
      if (observe(s).state !== "running") throw new Error("Pi worker is not running; use worker_resume for a finished session")
      const requestId = randomUUID()
      appendFileSync(s.run.control, JSON.stringify({ id: requestId, message: input.text }) + "\n", { mode: 0o600 })
      const deadline = Date.now() + 5000
      while (Date.now() < deadline) {
        let text = ""
        try { text = readFileSync(s.run.receipts, "utf8") } catch {}
        for (const line of text.split("\n")) {
          if (!line.trim()) continue
          let receipt: Record<string, unknown> | null = null
          try {
            const value: unknown = JSON.parse(line)
            receipt = value && typeof value === "object" && !Array.isArray(value) ? value as Record<string, unknown> : null
          } catch { continue }
          if (!receipt || receipt.id !== requestId) continue
          if (receipt.ok !== true)
            throw new Error("pi-subagents RPC rejected steer: " + String(receipt.error ?? "unknown error"))
          const data = receipt.data && typeof receipt.data === "object" && !Array.isArray(receipt.data)
            ? receipt.data as Record<string, unknown> : {}
          return { data: { ...data, request_id: requestId, accepted: true } }
        }
        await new Promise((resolve) => setTimeout(resolve, 100))
      }
      return { data: { request_id: requestId, accepted: false, delivery_status: "pending" } }
    },
  }
}
