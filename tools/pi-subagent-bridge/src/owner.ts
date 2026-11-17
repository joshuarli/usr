import { createHash, randomUUID } from "node:crypto"
import {
  appendFileSync, chmodSync, existsSync, mkdirSync, readdirSync, readFileSync, renameSync, rmSync, writeFileSync,
} from "node:fs"
import { createServer, type Server, type Socket } from "node:net"
import { basename, dirname, join, resolve } from "node:path"
import { git, readStateDir, stateDir } from "./git.ts"
import { OwnerPrecheckError, hybridOwnerOps, type HybridOwnerOps } from "./hybrid.ts"
import { inspectSession, toSnapshot, type Inspection, type InspectionDeps } from "./inspect.ts"
import { isRecord, requiredText } from "./scope.ts"
import { decodeSession, isOwnerId, isSessionId, type Session, type SessionOwner } from "./session.ts"

export const OWNER_PROTOCOL = 1 as const
export const OWNER_CAPABILITIES = ["status", "steer", "interrupt", "resume"] as const

export type OwnerCapability = (typeof OWNER_CAPABILITIES)[number]

export type OwnerTarget = {
  readonly job_id: string
  readonly run_id: string
  readonly owner_generation: number
}

export type OwnerDiscovery = {
  readonly owner_protocol: typeof OWNER_PROTOCOL
  readonly owner_id: string
  readonly owner_generation: number
  readonly pid: number
  readonly socket: string
  readonly capabilities: readonly OwnerCapability[]
}

export type OwnerHello = {
  readonly owner_protocol: typeof OWNER_PROTOCOL
  readonly owner_id: string
  readonly owner_generation: number
  readonly capabilities: readonly OwnerCapability[]
}

export type OwnerJobSummary = {
  readonly job_id: string
  readonly run_id: string
  readonly owner_generation: number
  readonly state: string
}

export type OwnerReceipt =
  | { readonly receipt: "rejected"; readonly reason: string }
  | { readonly receipt: "accepted"; readonly command_id: string }
  | { readonly receipt: "pending"; readonly command_id: string }
  | { readonly receipt: "uncertain"; readonly command_id: string }

export class OwnerAbortedError extends Error {
  constructor(message = "Owner stopped after admitting command") {
    super(message)
  }
}

export type OwnerTestHooks = {
  afterAdmitted?: (context: { command_id: string; method: "steer" | "interrupt" | "resume"; job_id: string }) => Promise<void> | void
}

type JsonRpcId = string | number

class JsonRpcMethodError extends Error {
  readonly code: number
  constructor(code: number, message: string) {
    super(message)
    this.code = code
  }
}

type JournalEntry =
  | {
    readonly type: "admitted"
    readonly command_id: string
    readonly method: "steer" | "interrupt" | "resume"
    readonly request_hash: string
    readonly owner_id: string
    readonly owner_generation: number
    readonly target: OwnerTarget
    readonly recorded_at: string
  }
  | {
    readonly type: "result"
    readonly command_id: string
    readonly method: "steer" | "interrupt" | "resume"
    readonly request_hash: string
    readonly owner_id: string
    readonly owner_generation: number
    readonly receipt: OwnerReceipt
    readonly recorded_at: string
  }

const OWNER_METHODS = new Set(["hello", "jobs", "status", "steer", "interrupt", "resume", "command"])
const REQUEST_KEYS = new Set(["jsonrpc", "id", "method", "params"])
const TARGET_KEYS = new Set(["job_id", "run_id", "owner_generation"])
const PARAMS_KEYS: Record<string, ReadonlySet<string>> = {
  hello: new Set(),
  jobs: new Set(),
  status: new Set(["target"]),
  steer: new Set(["target", "command_id", "note"]),
  interrupt: new Set(["target", "command_id"]),
  resume: new Set(["target", "command_id", "feedback"]),
  command: new Set(["command_id"]),
}

const MAX_UNIX_PATH_BYTES = 100
const SLEEP = (ms: number) => new Promise<void>((resolve) => setTimeout(resolve, ms))

function checkAllowedKeys(obj: Record<string, unknown>, allowed: ReadonlySet<string>, label: string, code = -32602): void {
  for (const key of Object.keys(obj)) {
    if (!allowed.has(key)) throw new JsonRpcMethodError(code, `Unknown field in ${label}: ${key}`)
  }
}

function readPiRunReadOnly(stateDirectory: string, sessionId: string): Record<string, unknown> | null {
  try {
    const raw: unknown = JSON.parse(readFileSync(join(stateDirectory, sessionId + ".pi.json"), "utf8"))
    if (!isRecord(raw) || !isRecord(raw.run)) return null
    return {
      pid: typeof raw.run.pid === "number" ? raw.run.pid : null,
      startedAt: typeof raw.run.startedAt === "string" ? raw.run.startedAt : null,
      runId: typeof raw.run.runId === "string" ? raw.run.runId : null,
      log: typeof raw.run.log === "string" ? raw.run.log : null,
    }
  } catch {
    return null
  }
}

/**
 * Derive a deterministic identifier for the session's current executor run.
 * Changes whenever resume, fallback, or CLI steer starts a new run; stays stable across Pi in-process steer and reads.
 */
export function deriveRunId(session: Session, stateDirectory: string): string {
  let payload: unknown
  if (session.execution.kind === "process") {
    const run = session.execution.run
    payload = {
      kind: "process",
      executor: session.execution.executor,
      selection: session.execution.selection,
      run: {
        pid: run.pid,
        output: run.output,
        errors: run.errors,
        started_at: run.started_at,
        proc_start: run.proc_start ?? null,
      },
      attempts: session.attempts,
      continuations: session.continuations ?? 0,
      steers: session.steers ?? 0,
    }
  } else if (session.execution.kind === "pi") {
    payload = {
      kind: "pi",
      selection: session.execution.selection,
      session_id: session.execution.session_id,
      pi_run: readPiRunReadOnly(stateDirectory, session.execution.session_id),
      attempts: session.attempts,
      continuations: session.continuations ?? 0,
    }
  } else {
    payload = {
      kind: "transition",
      to: session.execution.to,
      previous_run: session.execution.previous_run ?? null,
      pi_id: session.execution.pi_id ?? null,
      attempts: session.attempts,
      continuations: session.continuations ?? 0,
      steers: session.steers ?? 0,
    }
  }
  return "run_" + createHash("sha256").update(JSON.stringify(payload)).digest("hex").slice(0, 32)
}

export function ownerDirectoryFor(stateDirectory: string): string {
  return join(stateDirectory, "owner")
}

function ensurePrivateDir(dir: string): void {
  mkdirSync(dir, { recursive: true, mode: 0o700 })
  chmodSync(dir, 0o700)
}

function writePrivateAtomic(path: string, data: string): void {
  const tmp = path + "." + randomUUID() + ".tmp"
  try {
    writeFileSync(tmp, data, { mode: 0o600 })
    chmodSync(tmp, 0o600)
    renameSync(tmp, path)
  } finally {
    rmSync(tmp, { force: true })
  }
}

async function allocateGeneration(ownerDir: string): Promise<number> {
  ensurePrivateDir(ownerDir)
  const lockDir = join(ownerDir, "generation.lock")
  const deadline = Date.now() + 5000
  for (;;) {
    try {
      mkdirSync(lockDir, { mode: 0o700 })
      break
    } catch (error) {
      if (error instanceof Error && "code" in error && error.code === "EEXIST" && Date.now() < deadline) {
        await SLEEP(10)
        continue
      }
      throw error
    }
  }
  try {
    const counterPath = join(ownerDir, "generation.json")
    let current = 0
    if (existsSync(counterPath)) {
      const parsed: unknown = JSON.parse(readFileSync(counterPath, "utf8"))
      if (!isRecord(parsed) || typeof parsed.generation !== "number" || !Number.isInteger(parsed.generation) || parsed.generation < 0) {
        throw new Error("Invalid persisted owner generation counter")
      }
      current = parsed.generation
    }
    const next = current + 1
    writePrivateAtomic(counterPath, JSON.stringify({ generation: next }) + "\n")
    return next
  } finally {
    rmSync(lockDir, { recursive: true, force: true })
  }
}

function parseCommandId(value: unknown): string {
  if (typeof value !== "string" || !value.trim() || value.length > 128 || /[/\\\0]/.test(value)) {
    throw new JsonRpcMethodError(-32602, "Invalid command_id")
  }
  return value
}

function parseTarget(value: unknown): OwnerTarget {
  if (!isRecord(value)) throw new JsonRpcMethodError(-32602, "Invalid target object")
  checkAllowedKeys(value, TARGET_KEYS, "target")
  if (typeof value.job_id !== "string" || !value.job_id || value.job_id.length > 128 || /[/\\\0]/.test(value.job_id)) {
    throw new JsonRpcMethodError(-32602, "Invalid target.job_id")
  }
  if (typeof value.run_id !== "string" || !value.run_id || value.run_id.length > 128) {
    throw new JsonRpcMethodError(-32602, "Invalid target.run_id")
  }
  if (typeof value.owner_generation !== "number" || !Number.isInteger(value.owner_generation) || value.owner_generation < 1) {
    throw new JsonRpcMethodError(-32602, "Invalid target.owner_generation")
  }
  return {
    job_id: value.job_id,
    run_id: value.run_id,
    owner_generation: value.owner_generation,
  }
}

function parseTextField(value: unknown, field: string): string {
  try {
    return requiredText(value, field, 32000)
  } catch (error) {
    throw new JsonRpcMethodError(-32602, error instanceof Error ? error.message : `Invalid ${field}`)
  }
}

function mapHybridRefusal(error: unknown, method: "steer" | "interrupt" | "resume"): string {
  if (error instanceof OwnerPrecheckError) return error.reason
  const message = error instanceof Error ? error.message : String(error)
  if (method === "interrupt") return "not-running"
  if (message.includes("is not running") || message.includes("not known complete")) {
    return method === "steer" ? "not-running" : "already-running"
  }
  if (message.includes("still running")) return "already-running"
  if (message.includes("Steer limit reached")) return "steer-limit"
  if (message.includes("Turn-limit continuation limit reached")) return "continuation-limit"
  if (message.includes("Task attempt limit reached")) return "attempt-limit"
  if (message.includes("changed HEAD or out-of-scope")) return "scope-violation"
  if (message.includes("transition interrupted")) return "interrupted-transition"
  if (message.includes("session identity is not recorded") || message.includes("No resumable Command Code session") ||
    message.includes("No native subagent run identity")) {
    return "no-session-identity"
  }
  if (message.includes("not owned by this bridge process")) return "not-owned-process"
  if (message.includes("Worktree already has an active worker")) return "worktree-busy"
  if (message.includes("transition in progress")) return "lock-conflict"
  if (message.includes("not known terminal")) return "already-running"
  return "rejected"
}

function hashCommandRequest(method: string, target: OwnerTarget, payload?: string): string {
  return createHash("sha256").update(JSON.stringify({ method, target, payload: payload ?? null })).digest("hex")
}

function readJournalFile(path: string, targetCommandId?: string): Map<string, { admitted?: Extract<JournalEntry, { type: "admitted" }>; result?: Extract<JournalEntry, { type: "result" }> }> {
  const entries = new Map<string, { admitted?: Extract<JournalEntry, { type: "admitted" }>; result?: Extract<JournalEntry, { type: "result" }> }>()
  if (!existsSync(path)) return entries
  const content = readFileSync(path, "utf8")
  for (const line of content.split("\n")) {
    if (!line.trim()) continue
    let parsed: unknown
    try {
      parsed = JSON.parse(line)
    } catch {
      continue
    }
    if (!isRecord(parsed) || typeof parsed.command_id !== "string") continue
    if (targetCommandId !== undefined && parsed.command_id !== targetCommandId) continue
    const record = entries.get(parsed.command_id) ?? {}
    if (parsed.type === "admitted") {
      record.admitted = parsed as Extract<JournalEntry, { type: "admitted" }>
    } else if (parsed.type === "result") {
      record.result = parsed as Extract<JournalEntry, { type: "result" }>
    }
    entries.set(parsed.command_id, record)
  }
  return entries
}

function lookupRecordedCommand(
  ownerDir: string,
  commandId: string,
  currentOwnerId: string,
  inFlight: ReadonlySet<string>,
): { receipt: OwnerReceipt; requestHash?: string; ownerId: string } | null {
  if (!existsSync(ownerDir)) return null
  let names: string[]
  try {
    names = readdirSync(ownerDir).sort()
  } catch {
    return null
  }
  for (const name of names) {
    if (!isOwnerId(name)) continue
    const journalPath = join(ownerDir, name, "commands.jsonl")
    const found = readJournalFile(journalPath, commandId).get(commandId)
    if (!found) continue
    if (found.result) {
      return {
        receipt: found.result.receipt,
        requestHash: found.result.request_hash,
        ownerId: name,
      }
    }
    if (found.admitted) {
      if (name === currentOwnerId && inFlight.has(commandId)) {
        return {
          receipt: { receipt: "pending", command_id: commandId },
          requestHash: found.admitted.request_hash,
          ownerId: name,
        }
      }
      return {
        receipt: { receipt: "uncertain", command_id: commandId },
        requestHash: found.admitted.request_hash,
        ownerId: name,
      }
    }
  }
  return null
}

function readSessionsReadOnly(stateDirectory: string): Session[] {
  if (!existsSync(stateDirectory)) return []
  const sessions: Session[] = []
  let files: string[]
  try {
    files = readdirSync(stateDirectory).sort()
  } catch {
    return []
  }
  for (const file of files) {
    if (!file.endsWith(".json")) continue
    const id = file.slice(0, -5)
    if (!isSessionId(id)) continue
    try {
      const raw: unknown = JSON.parse(readFileSync(join(stateDirectory, file), "utf8"))
      if (!isRecord(raw) || typeof raw.cwd !== "string") continue
      sessions.push(decodeSession(raw, raw.cwd, id))
    } catch {
      continue
    }
  }
  return sessions
}

function readSingleSessionReadOnly(stateDirectory: string, jobId: string): Session | null {
  if (!isSessionId(jobId)) return null
  const file = join(stateDirectory, jobId + ".json")
  if (!existsSync(file)) return null
  try {
    const raw: unknown = JSON.parse(readFileSync(file, "utf8"))
    if (!isRecord(raw) || typeof raw.cwd !== "string") return null
    return decodeSession(raw, raw.cwd, jobId)
  } catch {
    return null
  }
}

function isRunningState(state: string): boolean {
  return state === "running" || state === "queued"
}

function listenUnixSocket(server: Server, socketPath: string): Promise<void> {
  return new Promise<void>((resolve, reject) => {
    const onError = (error: Error) => {
      server.off("listening", onListening)
      reject(error)
    }
    const onListening = () => {
      server.off("error", onError)
      chmodSync(socketPath, 0o600)
      resolve()
    }
    server.once("error", onError)
    server.once("listening", onListening)
    // macOS struct sockaddr_un.sun_path is capped at 104 bytes; bind via cwd relative name when long.
    if (Buffer.byteLength(socketPath) >= MAX_UNIX_PATH_BYTES) {
      const prev = process.cwd()
      process.chdir(dirname(socketPath))
      try {
        server.listen(basename(socketPath))
      } finally {
        process.chdir(prev)
      }
    } else {
      server.listen(socketPath)
    }
  })
}

export function checkedRepoDir(directory: unknown): string {
  const raw = requiredText(directory, "repo", 4096)
  return git(resolve(raw), "rev-parse", "--show-toplevel")
}

export class RepoOwnerEndpoint {
  readonly ownerId: string
  readonly ownerGeneration: number
  readonly stateDirectory: string
  readonly ownerDir: string
  readonly socketPath: string
  readonly metadataPath: string
  readonly journalPath: string

  private readonly bridgeOps: HybridOwnerOps
  private readonly inspection: InspectionDeps
  private readonly testHooks: OwnerTestHooks | undefined
  private readonly inFlight = new Map<string, { promise: Promise<OwnerReceipt>; requestHash: string }>()
  private readonly sockets = new Set<Socket>()
  private readonly socketPending = new Map<Socket, number>()
  private server: Server | null = null
  private closing = false
  private closed = false
  private journalLock: Promise<void> = Promise.resolve()

  private constructor(
    stateDirectory: string,
    ownerId: string,
    ownerGeneration: number,
    bridgeOps: HybridOwnerOps,
    testHooks?: OwnerTestHooks,
  ) {
    this.stateDirectory = stateDirectory
    this.ownerId = ownerId
    this.ownerGeneration = ownerGeneration
    this.ownerDir = ownerDirectoryFor(stateDirectory)
    this.socketPath = join(this.ownerDir, `${ownerId}.sock`)
    this.metadataPath = join(this.ownerDir, `${ownerId}.json`)
    this.journalPath = join(this.ownerDir, ownerId, "commands.jsonl")
    this.bridgeOps = bridgeOps
    this.inspection = bridgeOps.inspection
    this.testHooks = testHooks
  }

  static start(
    repoDir: string,
    bridge: object,
    options?: { ownerId?: string; testHooks?: OwnerTestHooks },
  ): Promise<RepoOwnerEndpoint> {
    const stateDirectory = stateDir(checkedRepoDir(repoDir))
    return RepoOwnerEndpoint.startForStateDir(stateDirectory, bridge, options)
  }

  static async startForStateDir(
    stateDirectory: string,
    bridge: object,
    options?: { ownerId?: string; testHooks?: OwnerTestHooks },
  ): Promise<RepoOwnerEndpoint> {
    const ops = hybridOwnerOps(bridge)
    if (!ops) throw new Error("Bridge instance is not registered for owner control")
    const ownerDir = ownerDirectoryFor(stateDirectory)
    ensurePrivateDir(ownerDir)
    const ownerId = options?.ownerId ?? randomUUID()
    if (!isOwnerId(ownerId)) throw new Error("Invalid owner_id")
    const ownerGeneration = await allocateGeneration(ownerDir)
    const endpoint = new RepoOwnerEndpoint(stateDirectory, ownerId, ownerGeneration, ops, options?.testHooks)
    await endpoint.open()
    return endpoint
  }

  identity(): SessionOwner {
    return { owner_id: this.ownerId, owner_generation: this.ownerGeneration }
  }

  discovery(): OwnerDiscovery {
    return {
      owner_protocol: OWNER_PROTOCOL,
      owner_id: this.ownerId,
      owner_generation: this.ownerGeneration,
      pid: process.pid,
      socket: this.socketPath,
      capabilities: [...OWNER_CAPABILITIES],
    }
  }

  private async open(): Promise<void> {
    ensurePrivateDir(join(this.ownerDir, this.ownerId))
    rmSync(this.socketPath, { force: true })
    const server = createServer((socket) => this.handleConnection(socket))
    this.server = server
    try {
      await listenUnixSocket(server, this.socketPath)
      writePrivateAtomic(this.metadataPath, JSON.stringify(this.discovery()) + "\n")
    } catch (error) {
      rmSync(this.metadataPath, { force: true })
      rmSync(this.socketPath, { force: true })
      server.close()
      this.server = null
      throw error
    }
  }

  async close(): Promise<void> {
    if (this.closed) return
    this.closing = true
    this.closed = true
    rmSync(this.metadataPath, { force: true })
    await Promise.allSettled([...this.inFlight.values()].map((entry) => entry.promise))
    await this.shutdownServer(false)
  }

  /** Stop listening immediately without waiting for in-flight commands; leaves journal intact for crash tests. */
  async abort(): Promise<void> {
    if (this.closed) return
    this.closing = true
    this.closed = true
    rmSync(this.metadataPath, { force: true })
    await this.shutdownServer(true)
  }

  private async shutdownServer(destroyAll: boolean): Promise<void> {
    for (const socket of this.sockets) {
      if (destroyAll || (this.socketPending.get(socket) ?? 0) === 0) socket.destroy()
      else socket.end()
    }
    const server = this.server
    this.server = null
    if (server) {
      await new Promise<void>((resolve) => server.close(() => resolve()))
    }
    rmSync(this.socketPath, { force: true })
  }

  private async appendJournal(entry: JournalEntry): Promise<void> {
    const prev = this.journalLock
    let release!: () => void
    this.journalLock = new Promise<void>((resolve) => { release = resolve })
    await prev
    try {
      ensurePrivateDir(join(this.ownerDir, this.ownerId))
      appendFileSync(this.journalPath, JSON.stringify(entry) + "\n", { mode: 0o600 })
      chmodSync(this.journalPath, 0o600)
    } finally {
      release()
    }
  }

  private handleConnection(socket: Socket): void {
    if (this.closing) {
      socket.destroy()
      return
    }
    this.sockets.add(socket)
    this.socketPending.set(socket, 0)
    socket.setEncoding("utf8")
    let buffer = ""
    let writeChain = Promise.resolve()

    const sendLine = (payload: unknown) => {
      const text = JSON.stringify(payload) + "\n"
      writeChain = writeChain.then(() => {
        if (!socket.destroyed) socket.write(text)
      }).catch(() => {})
      return writeChain
    }

    const processLine = async (line: string) => {
      this.socketPending.set(socket, (this.socketPending.get(socket) ?? 0) + 1)
      try {
        const response = await this.handleRawLine(line)
        await sendLine(response)
      } finally {
        const remaining = Math.max(0, (this.socketPending.get(socket) ?? 1) - 1)
        this.socketPending.set(socket, remaining)
        if (this.closing && remaining === 0) {
          await writeChain
          socket.end()
        }
      }
    }

    socket.on("data", (chunk: string) => {
      buffer += chunk
      let index = buffer.indexOf("\n")
      while (index >= 0) {
        const line = buffer.slice(0, index).trim()
        buffer = buffer.slice(index + 1)
        if (line) void processLine(line)
        index = buffer.indexOf("\n")
      }
    })
    socket.on("end", () => {
      if (buffer.trim()) {
        const tail = buffer.trim()
        buffer = ""
        void processLine(tail)
      }
    })
    socket.on("close", () => {
      this.sockets.delete(socket)
      this.socketPending.delete(socket)
    })
    socket.on("error", () => {
      this.sockets.delete(socket)
      this.socketPending.delete(socket)
    })
  }

  private async handleRawLine(line: string): Promise<unknown> {
    let parsed: unknown
    try {
      parsed = JSON.parse(line)
    } catch {
      return { jsonrpc: "2.0", id: null, error: { code: -32700, message: "Parse error" } }
    }
    if (!isRecord(parsed)) {
      return { jsonrpc: "2.0", id: null, error: { code: -32600, message: "Invalid Request" } }
    }
    const rawId = parsed.id
    const hasValidId = typeof rawId === "string" || (typeof rawId === "number" && Number.isFinite(rawId))
    const replyId: JsonRpcId | null = hasValidId ? rawId : null
    try {
      checkAllowedKeys(parsed, REQUEST_KEYS, "request", -32600)
      if (parsed.jsonrpc !== "2.0") throw new JsonRpcMethodError(-32600, "Invalid Request: jsonrpc must be '2.0'")
      if (!hasValidId) throw new JsonRpcMethodError(-32600, "Invalid Request: id must be a string or finite number")
      if (typeof parsed.method !== "string" || !parsed.method) throw new JsonRpcMethodError(-32600, "Invalid Request: missing method")
      if (!OWNER_METHODS.has(parsed.method)) throw new JsonRpcMethodError(-32601, `Method not found: ${parsed.method}`)
      if (this.closing) throw new JsonRpcMethodError(-32000, "Owner endpoint is shutting down")
      const params = parsed.params === undefined ? {} : parsed.params
      if (!isRecord(params)) throw new JsonRpcMethodError(-32602, "Invalid params: expected object")
      checkAllowedKeys(params, PARAMS_KEYS[parsed.method], `params (${parsed.method})`)
      const result = await this.dispatchMethod(parsed.method, params)
      return { jsonrpc: "2.0", id: replyId, result }
    } catch (error) {
      if (error instanceof JsonRpcMethodError) {
        return { jsonrpc: "2.0", id: replyId, error: { code: error.code, message: error.message } }
      }
      return {
        jsonrpc: "2.0",
        id: replyId,
        error: { code: -32603, message: error instanceof Error ? error.message : String(error) },
      }
    }
  }

  private validateTarget(target: OwnerTarget): { session: Session; currentRunId: string } | { receipt: "rejected"; reason: "stale-target" } {
    if (target.owner_generation !== this.ownerGeneration) {
      return { receipt: "rejected", reason: "stale-target" }
    }
    const session = readSingleSessionReadOnly(this.stateDirectory, target.job_id)
    if (!session || session.owner?.owner_id !== this.ownerId || session.owner?.owner_generation !== this.ownerGeneration) {
      return { receipt: "rejected", reason: "stale-target" }
    }
    const currentRunId = deriveRunId(session, this.stateDirectory)
    if (target.run_id !== currentRunId) {
      return { receipt: "rejected", reason: "stale-target" }
    }
    return { session, currentRunId }
  }

  private async dispatchMethod(method: string, params: Record<string, unknown>): Promise<unknown> {
    switch (method) {
      case "hello":
        return {
          owner_protocol: OWNER_PROTOCOL,
          owner_id: this.ownerId,
          owner_generation: this.ownerGeneration,
          capabilities: [...OWNER_CAPABILITIES],
        } satisfies OwnerHello

      case "jobs": {
        const ownSessions = readSessionsReadOnly(this.stateDirectory).filter(
          (s) => s.owner?.owner_id === this.ownerId && s.owner?.owner_generation === this.ownerGeneration,
        )
        const results: OwnerJobSummary[] = []
        for (const s of ownSessions) {
          const inspected: Inspection = await inspectSession(s, this.stateDirectory, this.inspection)
          results.push({
            job_id: s.id,
            run_id: deriveRunId(s, this.stateDirectory),
            owner_generation: this.ownerGeneration,
            state: inspected.state,
          })
        }
        return results
      }

      case "status": {
        const target = parseTarget(params.target)
        const validated = this.validateTarget(target)
        if ("receipt" in validated) return validated
        const inspected = await inspectSession(validated.session, this.stateDirectory, this.inspection)
        const snap = toSnapshot(inspected)
        return {
          ...snap,
          state: inspected.state,
          job_id: validated.session.id,
          run_id: validated.currentRunId,
          owner_id: this.ownerId,
          owner_generation: this.ownerGeneration,
        }
      }

      case "command": {
        const commandId = parseCommandId(params.command_id)
        const found = lookupRecordedCommand(this.ownerDir, commandId, this.ownerId, new Set(this.inFlight.keys()))
        if (found) return found.receipt
        return { receipt: "rejected", reason: "unknown-command" } satisfies OwnerReceipt
      }

      case "steer": {
        const target = parseTarget(params.target)
        const commandId = parseCommandId(params.command_id)
        const note = parseTextField(params.note, "note")
        return this.executeControlled("steer", target, commandId, note, async (s, admitEffect) => {
          const pre = await inspectSession(s, this.stateDirectory, this.inspection)
          if (!isRunningState(pre.state)) throw new OwnerPrecheckError("not-running", `Worker run is not running (state ${pre.state})`)
          const result = await this.bridgeOps.steerForOwner(s.cwd, s.id, note, admitEffect)
          if (isRecord(result) && (result.status === "steering" || result.status === "pending"))
            return { receipt: "pending", command_id: commandId }
          const outerReceipt = isRecord(result) && isRecord(result.receipt) ? result.receipt : null
          const piReceipt = outerReceipt && isRecord(outerReceipt.receipt) ? outerReceipt.receipt : outerReceipt
          if (piReceipt && piReceipt.accepted === false) {
            return piReceipt.delivery_status === "pending"
              ? { receipt: "pending", command_id: commandId }
              : { receipt: "uncertain", command_id: commandId }
          }
          return { receipt: "accepted", command_id: commandId }
        })
      }

      case "interrupt": {
        const target = parseTarget(params.target)
        const commandId = parseCommandId(params.command_id)
        return this.executeControlled("interrupt", target, commandId, undefined, async (s, admitEffect) => {
          const pre = await inspectSession(s, this.stateDirectory, this.inspection)
          if (!isRunningState(pre.state)) throw new OwnerPrecheckError("not-running", `Worker run is not running (state ${pre.state})`)
          const res = await this.bridgeOps.cancelForOwner(s.cwd, s.id, admitEffect)
          if (res.interrupted) return { receipt: "accepted", command_id: commandId }
          const postSession = readSingleSessionReadOnly(this.stateDirectory, s.id)
          if (postSession) {
            const post = await inspectSession(postSession, this.stateDirectory, this.inspection)
            if (!isRunningState(post.state)) return { receipt: "rejected", reason: "not-running" }
          }
          return { receipt: "uncertain", command_id: commandId }
        })
      }

      case "resume": {
        const target = parseTarget(params.target)
        const commandId = parseCommandId(params.command_id)
        const feedback = parseTextField(params.feedback, "feedback")
        return this.executeControlled("resume", target, commandId, feedback, async (s, admitEffect) => {
          const pre = await inspectSession(s, this.stateDirectory, this.inspection)
          if (isRunningState(pre.state)) {
            throw new Error(`Worker session is still running (state ${pre.state}); steer or interrupt before resuming`)
          }
          await this.bridgeOps.resumeForOwner(s.cwd, s.id, feedback, admitEffect)
          return { receipt: "accepted", command_id: commandId }
        })
      }

      default:
        throw new JsonRpcMethodError(-32601, `Method not found: ${method}`)
    }
  }

  private async executeControlled(
    method: "steer" | "interrupt" | "resume",
    target: OwnerTarget,
    commandId: string,
    payload: string | undefined,
    runner: (session: Session, admitEffect: () => Promise<void>) => Promise<OwnerReceipt>,
  ): Promise<OwnerReceipt> {
    const requestHash = hashCommandRequest(method, target, payload)

    const running = this.inFlight.get(commandId)
    if (running) {
      if (running.requestHash !== requestHash) {
        return { receipt: "rejected", reason: "command-id-conflict" }
      }
      return running.promise
    }

    const existing = lookupRecordedCommand(this.ownerDir, commandId, this.ownerId, new Set(this.inFlight.keys()))
    if (existing) {
      if (existing.requestHash && existing.requestHash !== requestHash) {
        return { receipt: "rejected", reason: "command-id-conflict" }
      }
      return existing.receipt
    }

    const work = (async (): Promise<OwnerReceipt> => {
      const validated = this.validateTarget(target)
      if ("receipt" in validated) {
        const receipt: OwnerReceipt = validated
        await this.appendJournal({
          type: "result",
          command_id: commandId,
          method,
          request_hash: requestHash,
          owner_id: this.ownerId,
          owner_generation: this.ownerGeneration,
          receipt,
          recorded_at: new Date().toISOString(),
        })
        return receipt
      }

      let admitted = false
      const admitEffect = async () => {
        await this.appendJournal({
          type: "admitted",
          command_id: commandId,
          method,
          request_hash: requestHash,
          owner_id: this.ownerId,
          owner_generation: this.ownerGeneration,
          target,
          recorded_at: new Date().toISOString(),
        })
        admitted = true
        await this.testHooks?.afterAdmitted?.({ command_id: commandId, method, job_id: validated.session.id })
      }

      try {
        const receipt = await runner(validated.session, admitEffect)
        await this.appendJournal({
          type: "result",
          command_id: commandId,
          method,
          request_hash: requestHash,
          owner_id: this.ownerId,
          owner_generation: this.ownerGeneration,
          receipt,
          recorded_at: new Date().toISOString(),
        })
        return receipt
      } catch (error) {
        if (error instanceof OwnerAbortedError) {
          throw error
        }
        const receipt: OwnerReceipt = admitted
          ? { receipt: "uncertain", command_id: commandId }
          : { receipt: "rejected", reason: mapHybridRefusal(error, method) }
        await this.appendJournal({
          type: "result",
          command_id: commandId,
          method,
          request_hash: requestHash,
          owner_id: this.ownerId,
          owner_generation: this.ownerGeneration,
          receipt,
          recorded_at: new Date().toISOString(),
        })
        return receipt
      }
    })()

    this.inFlight.set(commandId, { promise: work, requestHash })
    try {
      return await work
    } finally {
      this.inFlight.delete(commandId)
    }
  }
}

export class OwnerManager {
  readonly ownerId: string
  private readonly bridge: object
  private readonly testHooks: OwnerTestHooks | undefined
  private readonly endpoints = new Map<string, Promise<RepoOwnerEndpoint>>()
  private closed = false

  constructor(bridge: object, options?: { ownerId?: string; testHooks?: OwnerTestHooks }) {
    this.ownerId = options?.ownerId ?? randomUUID()
    if (!isOwnerId(this.ownerId)) throw new Error("Invalid owner_id")
    this.bridge = bridge
    this.testHooks = options?.testHooks
    const ops = hybridOwnerOps(bridge)
    if (ops) {
      ops.setOwnerResolver(async (stateDirectory: string) => {
        const endpoint = await this.ensureStateDir(stateDirectory)
        return endpoint.identity()
      })
    }
  }

  ensureRepo(repoDir: string): Promise<RepoOwnerEndpoint> {
    if (this.closed) return Promise.reject(new Error("OwnerManager is closed"))
    const stateDirectory = stateDir(checkedRepoDir(repoDir))
    return this.ensureStateDir(stateDirectory)
  }

  ensureStateDir(stateDirectory: string): Promise<RepoOwnerEndpoint> {
    if (this.closed) return Promise.reject(new Error("OwnerManager is closed"))
    let existing = this.endpoints.get(stateDirectory)
    if (!existing) {
      existing = RepoOwnerEndpoint.startForStateDir(stateDirectory, this.bridge, {
        ownerId: this.ownerId,
        testHooks: this.testHooks,
      }).catch((error) => {
        this.endpoints.delete(stateDirectory)
        throw error
      })
      this.endpoints.set(stateDirectory, existing)
    }
    return existing
  }

  async close(): Promise<void> {
    if (this.closed) return
    this.closed = true
    const ops = hybridOwnerOps(this.bridge)
    ops?.setOwnerResolver(undefined)
    const active = await Promise.allSettled([...this.endpoints.values()])
    await Promise.allSettled(
      active
        .filter((entry): entry is PromiseFulfilledResult<RepoOwnerEndpoint> => entry.status === "fulfilled")
        .map((entry) => entry.value.close()),
    )
  }
}
