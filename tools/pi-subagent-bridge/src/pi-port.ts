import { execFileSync, spawn, type ChildProcess } from "node:child_process"
import { randomUUID } from "node:crypto"
import {
  appendFileSync, closeSync, mkdirSync, openSync, readFileSync, readdirSync,
  renameSync, rmSync, writeFileSync,
} from "node:fs"
import { isAbsolute, join, relative } from "node:path"
import { fileURLToPath } from "node:url"
import type { ModelRef, OpenCodePort } from "./bridge.ts"
import { readStateDir, stateDir } from "./git.ts"
import { ensureOpenCodeApiKey } from "./opencode-auth.ts"
import { GO_TIER_MODELS, DEVIN_TIER_MODELS, MAX_SUBAGENT_DEPTH } from "./tier-policy.ts"
import { devinPreflight } from "./devin-provider.ts"
import { workerEnvironment } from "./worker-env.ts"
import { processStartTime } from "./command.ts"

type Result = {
  state: "succeeded" | "failed" | "cancelled" | "timed_out" | "unknown_or_interrupted"
  text: string | null; error: string | null; usage: unknown; sessionFile: string | null; runId: string | null
}
type ProcessRecord = { pid: number; proc_start: string; ppid?: number; pgid?: number }
type Run = {
  pid: number; output: string; errors: string; control?: string; receipts?: string
  started_at?: string; proc_start?: string | null; tree?: ProcessRecord[]
}
type Stored = {
  id: string; title: string; model: ModelRef; cwd: string
  metadata: { usr_worker_v1: { directory: string; model: ModelRef } }
  readOnly: boolean; run?: Run; admitting?: boolean
}
const SESSION = /^ses_[a-f0-9]{32}$/
const worker = fileURLToPath(new URL("./sdk-worker.ts", import.meta.url))
// Derive the supported catalog from the same typed pins used at admission.
const VARIANTS = new Map<string, { providerID: "opencode-go"; variants: Set<string> }>()
for (const pin of Object.values(GO_TIER_MODELS)) {
  const group = VARIANTS.get(pin.id)
  if (group) {
    group.variants.add(pin.variant)
  } else {
    VARIANTS.set(pin.id, { providerID: pin.providerID, variants: new Set([pin.variant]) })
  }
}

export type PiProcessRow = { pid: number; ppid: number; pgid: number; stat: string }
export type PiCancelHooks = {
  listProcesses?: () => PiProcessRow[] | null
  startTime?: (pid: number) => string | null
  signal?: (target: number, signal: "SIGTERM" | "SIGKILL") => boolean
  termGraceMs?: number
  killVerifyMs?: number
  pollMs?: number
  beforeSignal?: (tree: ProcessRecord[]) => void
}
export type PiCancelResult = { interrupted: boolean; tree: ProcessRecord[]; unsupported: boolean }

const TERM_GRACE_MS = 500
const KILL_VERIFY_MS = 500
const POLL_MS = 25

function posixProcesses(): PiProcessRow[] | null {
  if (process.platform === "win32") return null
  try {
    const output = execFileSync("ps", ["-axo", "pid=,ppid=,pgid=,stat="], {
      encoding: "utf8", timeout: 1000, maxBuffer: 8 * 1024 * 1024,
    })
    const rows: PiProcessRow[] = []
    for (const line of output.split("\n")) {
      const match = /^\s*(\d+)\s+(\d+)\s+(\d+)\s+(\S+)/.exec(line)
      if (!match) continue
      rows.push({ pid: Number(match[1]), ppid: Number(match[2]), pgid: Number(match[3]), stat: match[4] })
    }
    return rows
  } catch { return null }
}

function defaultSignal(target: number, signal: "SIGTERM" | "SIGKILL"): boolean {
  try { process.kill(target, signal); return true } catch { return false }
}

function live(row: PiProcessRow | undefined): row is PiProcessRow {
  return row !== undefined && !row.stat.startsWith("Z")
}

function indexed(rows: PiProcessRow[]): Map<number, PiProcessRow> {
  return new Map(rows.map((row) => [row.pid, row]))
}

function storedTree(run: Run): ProcessRecord[] {
  if (!Array.isArray(run.tree)) return []
  const records: ProcessRecord[] = []
  for (const value of run.tree) {
    if (!value || typeof value !== "object") continue
    const pid = Number(value.pid), start = value.proc_start
    if (!Number.isSafeInteger(pid) || pid <= 0 || typeof start !== "string" || !start) continue
    const record: ProcessRecord = { pid, proc_start: start }
    if (Number.isSafeInteger(value.ppid) && value.ppid! >= 0) record.ppid = value.ppid
    if (Number.isSafeInteger(value.pgid) && value.pgid! > 0) record.pgid = value.pgid
    records.push(record)
  }
  return records
}

function delay(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

/**
 * Terminate the worker's process group and every verified descendant, including
 * pi-subagents runners that deliberately detached into a process group of their
 * own.  A negative PID is signaled only while that exact PID is still verified
 * as the group leader; a reused or unverified PID is never signaled.
 */
export async function cancelPiProcessTree(run: Run, hooks: PiCancelHooks = {}): Promise<PiCancelResult> {
  const listProcesses = hooks.listProcesses ?? posixProcesses
  const startTime = hooks.startTime ?? processStartTime
  const signal = hooks.signal ?? defaultSignal
  const termGraceMs = hooks.termGraceMs ?? TERM_GRACE_MS
  const killVerifyMs = hooks.killVerifyMs ?? KILL_VERIFY_MS
  const pollMs = hooks.pollMs ?? POLL_MS
  const tracked = new Map<number, ProcessRecord>()
  const unknown = new Set<number>()
  for (const record of storedTree(run)) tracked.set(record.pid, record)
  const treeSnapshot = () => [...tracked.values()]
    .filter((record) => record.pid !== run.pid)
    .map((record) => ({ ...record }))

  if (process.platform === "win32" && !hooks.listProcesses)
    return { interrupted: false, tree: treeSnapshot(), unsupported: true }
  if (!run.proc_start) return { interrupted: false, tree: treeSnapshot(), unsupported: false }

  const currentRootStart = (() => { try { return startTime(run.pid) } catch { return null } })()
  const rootMatches = currentRootStart !== null && currentRootStart === run.proc_start
  if (rootMatches) tracked.set(run.pid, { pid: run.pid, proc_start: run.proc_start })

  const rows0 = listProcesses()
  if (!rows0) return { interrupted: false, tree: treeSnapshot(), unsupported: false }

  function currentStart(pid: number): string | null {
    try { return startTime(pid) } catch { return null }
  }

  function matchRecord(byPid: Map<number, PiProcessRow>, record: ProcessRecord): { state: "same" | "unknown" | "dead"; row: PiProcessRow | null } {
    const row = byPid.get(record.pid)
    if (!live(row)) return { state: "dead", row: null }
    const start = currentStart(record.pid)
    if (start === record.proc_start) return { state: "same", row }
    // A live row whose start cannot be read is not proof of exit.  Treat it as
    // live-but-unverifiable; treating unknown as gone could falsely report a
    // successful cancellation.
    if (start === null) return { state: "unknown", row }
    return { state: "dead", row: null }
  }

  function matchingRow(byPid: Map<number, PiProcessRow>, record: ProcessRecord): PiProcessRow | null {
    const match = matchRecord(byPid, record)
    return match.state === "same" ? match.row : null
  }

  function addDescendants(rows: PiProcessRow[]): void {
    const byParent = new Map<number, PiProcessRow[]>()
    for (const row of rows) {
      const siblings = byParent.get(row.ppid)
      if (siblings) siblings.push(row)
      else byParent.set(row.ppid, [row])
    }
    const byPid = indexed(rows)
    const seeds = [...tracked.values()].filter((record) => matchingRow(byPid, record)).map((record) => record.pid)
    const seen = new Set(seeds)
    const queue = [...seeds]
    for (let index = 0; index < queue.length; index++) {
      for (const child of byParent.get(queue[index]) ?? []) {
        if (seen.has(child.pid)) continue
        seen.add(child.pid)
        queue.push(child.pid)
        if (tracked.has(child.pid)) continue
        const start = currentStart(child.pid)
        if (start) tracked.set(child.pid, { pid: child.pid, proc_start: start, ppid: child.ppid, pgid: child.pgid })
        else unknown.add(child.pid)
      }
    }
  }

  function anyLive(rows: PiProcessRow[]): boolean {
    const byPid = indexed(rows)
    for (const pid of unknown) {
      if (live(byPid.get(pid))) return true
      unknown.delete(pid)
    }
    for (const record of tracked.values()) {
      const match = matchRecord(byPid, record)
      if (match.state === "same" || match.state === "unknown") return true
    }
    return false
  }

  function refresh(): PiProcessRow[] | null {
    const rows = listProcesses()
    if (!rows) return null
    addDescendants(rows)
    return rows
  }

  const ownedGroups = new Set<number>()
  function signalTracked(kind: "SIGTERM" | "SIGKILL"): void {
    const rows = listProcesses()
    if (!rows) return
    const verified = new Map<number, PiProcessRow>()
    const byPid = indexed(rows)
    for (const record of tracked.values()) {
      const row = matchingRow(byPid, record)
      if (!row) continue
      verified.set(record.pid, row)
      // Only a process verified as its own group leader may adopt the negative-
      // PID group form.  Legacy workers were not detached, so their inherited
      // bridge group is never adopted.  Once adopted, the POSIX group lifetime
      // owns that ID even if the leader exits before the last member.
      if (row.pgid === record.pid) ownedGroups.add(record.pid)
    }
    for (const pgid of ownedGroups) signal(-pgid, kind)
    for (const pid of verified.keys()) signal(pid, kind)
  }

  addDescendants(rows0)
  try { hooks.beforeSignal?.(treeSnapshot()) } catch { /* cancellation must remain best-effort */ }
  if (!rootMatches && tracked.size === 0) return { interrupted: false, tree: treeSnapshot(), unsupported: false }
  if (!anyLive(rows0)) return { interrupted: false, tree: treeSnapshot(), unsupported: false }

  signalTracked("SIGTERM")
  let rows = refresh()
  if (!rows) return { interrupted: false, tree: treeSnapshot(), unsupported: false }
  const termDeadline = Date.now() + termGraceMs
  while (anyLive(rows) && Date.now() < termDeadline) {
    await delay(Math.min(pollMs, Math.max(1, termDeadline - Date.now())))
    rows = refresh()
    if (!rows) return { interrupted: false, tree: treeSnapshot(), unsupported: false }
  }
  if (!anyLive(rows)) return { interrupted: true, tree: treeSnapshot(), unsupported: false }

  signalTracked("SIGKILL")
  rows = refresh()
  if (!rows) return { interrupted: false, tree: treeSnapshot(), unsupported: false }
  const killDeadline = Date.now() + killVerifyMs
  while (anyLive(rows) && Date.now() < killDeadline) {
    await delay(Math.min(pollMs, Math.max(1, killDeadline - Date.now())))
    rows = refresh()
    if (!rows) return { interrupted: false, tree: treeSnapshot(), unsupported: false }
  }
  return { interrupted: !anyLive(rows), tree: treeSnapshot(), unsupported: false }
}

function statePath(directory: string, id: string): string {
  if (!SESSION.test(id)) throw new Error("Invalid Pi session ID")
  return join(directory, id + ".pi.json")
}
function load(cwd: string | undefined, id: string): Stored {
  if (!cwd) throw new Error("Pi worker operations require the worktree path")
  const s: Stored = JSON.parse(readFileSync(statePath(readStateDir(cwd), id), "utf8"))
  if (s.id !== id || s.cwd !== cwd || !SESSION.test(s.id))
    throw new Error("Pi worker session/worktree mismatch")
  return s
}
function save(s: Stored): void {
  const path = statePath(stateDir(s.cwd), s.id), temporary = path + "." + randomUUID() + ".tmp"
  try {
    writeFileSync(temporary, JSON.stringify(s), { mode: 0o600, flag: "wx" })
    renameSync(temporary, path)
  } finally {
    rmSync(temporary, { force: true })
  }
}
function alive(run: Run, children: Map<number, ChildProcess>): boolean {
  if (children.has(run.pid)) return true
  const rootMatches = run.proc_start ? processStartTime(run.pid) === run.proc_start : true
  if (rootMatches) {
    try { process.kill(run.pid, 0); return true }
    catch (error) {
      if ((error as NodeJS.ErrnoException).code === "EPERM") return true
    }
  }
  // A Pi runner is detached by pi-subagents.  Once cancellation has recorded
  // its identity, continue to report that owned survivor as part of the run
  // instead of declaring the run interrupted while it can still edit.
  for (const record of storedTree(run)) {
    if (processStartTime(record.pid) !== record.proc_start) continue
    try { process.kill(record.pid, 0); return true }
    catch (error) { if ((error as NodeJS.ErrnoException).code === "EPERM") return true }
  }
  return false
}
function observe(s: Stored, children: Map<number, ChildProcess>): { state: string; result: Result | null } {
  if (s.admitting) return { state: "blocked_transition", result: null }
  if (!s.run) return { state: "blocked_admission", result: null }
  if (alive(s.run, children)) return { state: "running", result: null }
  try {
    const result: Result = JSON.parse(readFileSync(s.run.output, "utf8"))
    if (!["succeeded", "failed", "cancelled", "timed_out"].includes(result.state))
      throw new Error("Invalid Pi result state")
    if (result.state === "succeeded" && (!result.runId?.trim() || !result.sessionFile?.trim()))
      throw new Error("Pi success has no owned native identity")
    return { state: result.state, result }
  } catch {
    return { state: "unknown_or_interrupted", result: null }
  }
}
function run(s: Stored, prompt: string, children: Map<number, ChildProcess>, workerPath: string, priorSessionFile?: string, priorRunId?: string): Run {
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
    const child = spawn(process.execPath, ["--experimental-strip-types", workerPath, jobPath], {
      cwd: s.cwd, stdio: ["ignore", "ignore", fd], detached: process.platform !== "win32",
      env: { ...workerEnvironment(), PI_OFFLINE: "1", PI_SKIP_VERSION_CHECK: "1", PI_SUBAGENT_MAX_DEPTH: String(MAX_SUBAGENT_DEPTH) },
    })
    const pid = child.pid
    child.on("error", (error) => {
      if (pid !== undefined) children.delete(pid)
      try { appendFileSync(errors, "spawn error: " + error.message + "\n") } catch { /* preserve admission error */ }
    })
    child.on("close", () => { if (pid !== undefined) children.delete(pid) })
    if (pid === undefined) throw new Error("Cannot launch Pi SDK worker")
    const procStart = processStartTime(pid)
    if (!procStart) {
      try { process.kill(process.platform === "win32" ? pid : -pid, "SIGKILL") } catch { /* best-effort admission rollback */ }
      throw new Error("Cannot record Pi SDK worker process identity")
    }
    children.set(pid, child)
    child.unref()
    return { pid, output, errors, control, receipts, started_at: new Date().toISOString(), proc_start: procStart }
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

/** The Devin model as the bridge's model check sees it: every pinned tier variant, each once. */
export function devinModelEntry() {
  const variants = [...new Set(Object.values(DEVIN_TIER_MODELS).map(pin => pin.variant))]
  return { id: DEVIN_TIER_MODELS.worker.id, providerID: "devin", enabled: true, status: "active",
    variants: variants.map(id => ({ id })) }
}

export type PiPortTestHooks = { workerPath?: string; cancel?: PiCancelHooks }

export function piPort(testHooks: PiPortTestHooks = {}): OpenCodePort {
  const children = new Map<number, ChildProcess>()
  const workerPath = testHooks.workerPath ?? worker
  return {
    async models() {
      // An authenticated Devin account must not require unrelated OpenCode credentials.
      let goAuthenticated = false
      try { ensureOpenCodeApiKey(); goAuthenticated = true } catch { /* independent providers */ }
      const { ModelRuntime } = await import("@earendil-works/pi-coding-agent")
      const runtime = await ModelRuntime.create()
      const available: Array<{
        id: string; providerID: string; enabled: boolean; status: string; variants: { id: string }[]
      }> = [...VARIANTS]
        .filter(([id, config]) => goAuthenticated && runtime.getModel(config.providerID, id) && runtime.hasConfiguredAuth(config.providerID))
        .map(([id, config]) => ({
          id, providerID: config.providerID, enabled: true, status: "active",
          variants: [...config.variants].map((variant) => ({ id: variant })),
        }))
      if (devinPreflight().available) available.push(devinModelEntry())
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
        const previous = observe(s, children)
        if (!previous.result || !["succeeded", "failed", "cancelled", "timed_out"].includes(previous.state))
          throw new Error("Pi session is not known terminal; no overlapping run")
        prior = verifiedSessionPath(s, previous.result.sessionFile)
        if (!previous.result.runId) throw new Error("No native subagent run identity for same-session correction")
        priorRunId = previous.result.runId
      }
      s.admitting = true
      save(s)
      const launched = run(s, input.text, children, workerPath, prior, priorRunId)
      s.run = launched
      s.admitting = false
      save(s)
      return { data: { admitted: true } }
    },
    async get(input) {
      const s = load(input.cwd, input.sessionID), status = observe(s, children)
      return { data: {
        id: s.id, title: s.title, model: s.model,
        location: { directory: s.cwd }, metadata: s.metadata,
        outcome: status.state, error: status.result?.error ?? null,
        tokens: status.result?.usage ?? null,
      } }
    },
    async active(input) {
      if (!input?.cwd) return { data: {} }
      const dir = readStateDir(input.cwd), sessions: Record<string, boolean> = {}
      for (const filename of readdirSync(dir)) {
        if (!/^ses_[a-f0-9]{32}\.pi\.json$/.test(filename)) continue
        const id = filename.slice(0, -8)
        const entry = JSON.parse(readFileSync(join(dir, filename), "utf8")) as Stored
        if (entry.cwd !== input.cwd || entry.id !== id) continue
        if (observe(entry, children).state === "running") sessions[id] = true
      }
      return { data: sessions }
    },
    async inbox() { return { data: [] } },
    async messages(input) {
      const status = observe(load(input.cwd, input.sessionID), children)
      return { data: [{
        info: { role: "assistant", error: status.result?.error ?? null },
        parts: status.result?.text ? [{ type: "text", text: status.result.text }] : [],
      }] }
    },
    async interrupt(input) {
      const s = load(input.cwd, input.sessionID)
      if (!s.run) return { data: { interrupted: false } }
      const result = await cancelPiProcessTree(s.run, {
        ...testHooks.cancel,
        beforeSignal: (tree) => {
          testHooks.cancel?.beforeSignal?.(tree)
          if (!s.run) return
          if (tree.length > 0) s.run.tree = tree
          try { save(s) } catch { /* cancellation must remain best-effort */ }
        },
      })
      if (result.interrupted && s.run.tree) {
        delete s.run.tree
        try { save(s) } catch { /* the verified cancellation is already complete */ }
      } else if (!result.interrupted && result.tree.length > 0) {
        s.run.tree = result.tree
        try { save(s) } catch { /* the caller still receives the truthful negative result */ }
      }
      return { data: { interrupted: result.interrupted, ...(result.unsupported ? { error: "process groups are unsupported on this platform" } : {}) } }
    },
    async steer(input) {
      const s = load(input.cwd, input.sessionID)
      if (!s.run?.control || !s.run.receipts) throw new Error("Pi worker has no steering channel")
      if (observe(s, children).state !== "running") throw new Error("Pi worker is not running; use worker_resume for a finished session")
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

export async function diagnoseGoModel(model: ModelRef): Promise<string | null> {
  try {
    ensureOpenCodeApiKey()
    const { ModelRuntime } = await import("@earendil-works/pi-coding-agent")
    const runtime = await ModelRuntime.create()
    if (!runtime.getModel(model.providerID, model.id))
      return `Pinned OpenCode Go model ${model.providerID}/${model.id} is not in the Pi SDK catalog`
    if (!runtime.hasConfiguredAuth(model.providerID))
      return `No configured auth for ${model.providerID} in Pi SDK; sign in with opencode or set OPENCODE_API_KEY`
  } catch { return null }
  return null
}
