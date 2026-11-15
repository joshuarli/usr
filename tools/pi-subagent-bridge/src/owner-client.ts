import { randomUUID } from "node:crypto"
import { existsSync, readdirSync, readFileSync } from "node:fs"
import { createConnection, type Socket } from "node:net"
import { basename, dirname, join } from "node:path"
import { readStateDir } from "./git.ts"
import {
  OWNER_PROTOCOL, checkedRepoDir, ownerDirectoryFor, type OwnerDiscovery, type OwnerHello, type OwnerJobSummary,
  type OwnerReceipt, type OwnerTarget,
} from "./owner.ts"
import { isRecord } from "./scope.ts"
import { isOwnerId } from "./session.ts"

const DEFAULT_TIMEOUT_MS = 10_000
const MAX_UNIX_PATH_BYTES = 100

export class OwnerRpcError extends Error {
  readonly code: number
  constructor(code: number, message: string) {
    super(message)
    this.code = code
  }
}

function connectUnix(socketPath: string): Socket {
  // macOS struct sockaddr_un.sun_path is capped at 104 bytes; connect via cwd relative name when long.
  if (Buffer.byteLength(socketPath) >= MAX_UNIX_PATH_BYTES) {
    const prev = process.cwd()
    process.chdir(dirname(socketPath))
    try {
      return createConnection(basename(socketPath))
    } finally {
      process.chdir(prev)
    }
  }
  return createConnection(socketPath)
}

export function readOwnerDiscovery(repoDir: string, ownerId: string): OwnerDiscovery {
  if (!isOwnerId(ownerId)) throw new Error("Invalid owner_id")
  const dir = checkedRepoDir(repoDir)
  const ownerDir = ownerDirectoryFor(readStateDir(dir))
  const metaPath = join(ownerDir, `${ownerId}.json`)
  const parsed: unknown = JSON.parse(readFileSync(metaPath, "utf8"))
  if (!isRecord(parsed)) throw new Error("Invalid owner metadata file")
  if (parsed.owner_protocol !== OWNER_PROTOCOL) {
    throw new Error(`Unsupported owner_protocol: ${String(parsed.owner_protocol)}`)
  }
  if (parsed.owner_id !== ownerId) throw new Error("Owner metadata id mismatch")
  if (typeof parsed.owner_generation !== "number" || !Number.isInteger(parsed.owner_generation) || parsed.owner_generation < 1) {
    throw new Error("Invalid owner metadata generation")
  }
  if (typeof parsed.pid !== "number" || !Number.isInteger(parsed.pid) || parsed.pid < 1) {
    throw new Error("Invalid owner metadata pid")
  }
  if (typeof parsed.socket !== "string" || !parsed.socket) {
    throw new Error("Invalid owner metadata socket path")
  }
  if (!Array.isArray(parsed.capabilities)) {
    throw new Error("Invalid owner metadata capabilities")
  }
  return parsed as OwnerDiscovery
}

export function listOwnerIds(repoDir: string): string[] {
  const dir = checkedRepoDir(repoDir)
  const ownerDir = ownerDirectoryFor(readStateDir(dir))
  if (!existsSync(ownerDir)) return []
  const ids: string[] = []
  for (const name of readdirSync(ownerDir).sort()) {
    if (!name.endsWith(".json") || name === "generation.json") continue
    const id = name.slice(0, -5)
    if (isOwnerId(id)) ids.push(id)
  }
  return ids
}

export function rawOwnerRpc(socketPath: string, line: string, timeoutMs = DEFAULT_TIMEOUT_MS): Promise<unknown> {
  return new Promise<unknown>((resolve, reject) => {
    let settled = false
    let buffer = ""
    const socket = connectUnix(socketPath)
    socket.setEncoding("utf8")

    const finish = (err: unknown, value?: unknown) => {
      if (settled) return
      settled = true
      clearTimeout(timer)
      socket.destroy()
      if (err) reject(err)
      else resolve(value)
    }

    const timer = setTimeout(() => {
      finish(new Error(`Owner RPC timed out after ${timeoutMs}ms`))
    }, timeoutMs)

    socket.once("error", (err) => finish(err))
    socket.once("connect", () => {
      socket.write(line.endsWith("\n") ? line : line + "\n")
    })
    socket.on("data", (chunk: string) => {
      buffer += chunk
      const newline = buffer.indexOf("\n")
      if (newline === -1) return
      const rawLine = buffer.slice(0, newline)
      try {
        finish(null, JSON.parse(rawLine))
      } catch (err) {
        finish(err)
      }
    })
    socket.once("end", () => {
      if (settled) return
      if (buffer.trim()) {
        try {
          finish(null, JSON.parse(buffer.trim()))
          return
        } catch (err) {
          finish(err)
          return
        }
      }
      finish(new Error("Owner socket closed before replying"))
    })
    socket.once("close", () => {
      if (settled) return
      finish(new Error("Owner socket closed before replying"))
    })
  })
}

export async function callOwnerSocket<T = unknown>(
  socketPath: string,
  method: string,
  params?: Record<string, unknown>,
  timeoutMs = DEFAULT_TIMEOUT_MS,
): Promise<T> {
  const id = randomUUID()
  const request = params === undefined
    ? { jsonrpc: "2.0", id, method }
    : { jsonrpc: "2.0", id, method, params }
  const raw = await rawOwnerRpc(socketPath, JSON.stringify(request), timeoutMs)
  if (!isRecord(raw) || raw.jsonrpc !== "2.0" || raw.id !== id) {
    throw new Error("Invalid JSON-RPC response from owner endpoint")
  }
  if ("error" in raw && raw.error !== undefined) {
    if (isRecord(raw.error) && typeof raw.error.code === "number" && typeof raw.error.message === "string") {
      throw new OwnerRpcError(raw.error.code, raw.error.message)
    }
    throw new OwnerRpcError(-32603, "Malformed JSON-RPC error from owner endpoint")
  }
  return raw.result as T
}

export async function callOwner<T = unknown>(
  repoDir: string,
  ownerId: string,
  method: string,
  params?: Record<string, unknown>,
  timeoutMs = DEFAULT_TIMEOUT_MS,
): Promise<T> {
  const discovery = readOwnerDiscovery(repoDir, ownerId)
  return callOwnerSocket<T>(discovery.socket, method, params, timeoutMs)
}

export function ownerHello(repoDir: string, ownerId: string, timeoutMs?: number): Promise<OwnerHello> {
  return callOwner<OwnerHello>(repoDir, ownerId, "hello", undefined, timeoutMs)
}

export function ownerJobs(repoDir: string, ownerId: string, timeoutMs?: number): Promise<OwnerJobSummary[]> {
  return callOwner<OwnerJobSummary[]>(repoDir, ownerId, "jobs", undefined, timeoutMs)
}

export function ownerStatus(
  repoDir: string,
  ownerId: string,
  target: OwnerTarget,
  timeoutMs?: number,
): Promise<Record<string, unknown>> {
  return callOwner<Record<string, unknown>>(repoDir, ownerId, "status", { target }, timeoutMs)
}

export function ownerSteer(
  repoDir: string,
  ownerId: string,
  params: { target: OwnerTarget; command_id: string; note: string },
  timeoutMs?: number,
): Promise<OwnerReceipt> {
  return callOwner<OwnerReceipt>(repoDir, ownerId, "steer", params, timeoutMs)
}

export function ownerInterrupt(
  repoDir: string,
  ownerId: string,
  params: { target: OwnerTarget; command_id: string },
  timeoutMs?: number,
): Promise<OwnerReceipt> {
  return callOwner<OwnerReceipt>(repoDir, ownerId, "interrupt", params, timeoutMs)
}

export function ownerResume(
  repoDir: string,
  ownerId: string,
  params: { target: OwnerTarget; command_id: string; feedback: string },
  timeoutMs?: number,
): Promise<OwnerReceipt> {
  return callOwner<OwnerReceipt>(repoDir, ownerId, "resume", params, timeoutMs)
}

export function ownerCommand(
  repoDir: string,
  ownerId: string,
  commandId: string,
  timeoutMs?: number,
): Promise<OwnerReceipt> {
  return callOwner<OwnerReceipt>(repoDir, ownerId, "command", { command_id: commandId }, timeoutMs)
}

const OWNER_CLI_USAGE =
  "usage: pi-subagent-bridge owner <hello|jobs|status|steer|interrupt|resume|command> --repo <dir> --owner <owner_id> [options]"

function parseOwnerFlags(args: string[]): Map<string, string> {
  const flags = new Map<string, string>()
  for (let i = 0; i < args.length; i++) {
    const flag = args[i]
    if (!flag.startsWith("--")) throw new Error(`Unexpected argument: ${flag}`)
    const value = args[++i]
    if (value === undefined) throw new Error(`Missing value for ${flag}`)
    if (flags.has(flag)) throw new Error(`Duplicate flag: ${flag}`)
    flags.set(flag, value)
  }
  return flags
}

function takeFlag(flags: Map<string, string>, ...names: string[]): string | undefined {
  let value: string | undefined
  for (const name of names) {
    const found = flags.get(name)
    if (found !== undefined) {
      if (value !== undefined) throw new Error(`Conflicting flags: ${names.join(", ")}`)
      value = found
      flags.delete(name)
    }
  }
  return value
}

function requiredFlag(flags: Map<string, string>, label: string, ...names: string[]): string {
  const value = takeFlag(flags, ...names)
  if (!value) throw new Error(`Missing required ${label} flag (${names[0]})`)
  return value
}

function parseGenerationFlag(flags: Map<string, string>): number {
  const raw = requiredFlag(flags, "generation", "--generation", "--owner-generation")
  if (!/^[1-9][0-9]*$/.test(raw)) throw new Error("Invalid --generation: expected positive integer")
  return Number(raw)
}

function parseTimeoutFlag(flags: Map<string, string>): number | undefined {
  const raw = takeFlag(flags, "--timeout")
  if (raw === undefined) return undefined
  if (!/^[1-9][0-9]*$/.test(raw)) throw new Error("Invalid --timeout: expected positive integer ms")
  return Number(raw)
}

function requiredTargetFlags(flags: Map<string, string>): OwnerTarget {
  return {
    job_id: requiredFlag(flags, "job_id", "--job", "--job-id"),
    run_id: requiredFlag(flags, "run_id", "--run", "--run-id"),
    owner_generation: parseGenerationFlag(flags),
  }
}

function textOrFileFlag(flags: Map<string, string>, name: string): string {
  const inline = takeFlag(flags, `--${name}`)
  const file = takeFlag(flags, `--${name}-file`)
  if (inline !== undefined && file !== undefined) {
    throw new Error(`Pass either --${name} or --${name}-file, not both`)
  }
  if (inline !== undefined) return inline
  if (file !== undefined) return readFileSync(file, "utf8")
  throw new Error(`Missing required --${name} or --${name}-file`)
}

export async function runOwnerCli(args: string[]): Promise<void> {
  const [sub, ...rest] = args
  if (!sub || sub === "--help" || sub === "-h") {
    process.stdout.write(OWNER_CLI_USAGE + "\n")
    return
  }
  const flags = parseOwnerFlags(rest)
  const repoDir = requiredFlag(flags, "repo", "--repo")
  const ownerId = requiredFlag(flags, "owner", "--owner")
  const timeoutMs = parseTimeoutFlag(flags)

  let output: unknown
  switch (sub) {
    case "hello":
      if (flags.size) throw new Error(`Unknown flag: ${[...flags.keys()][0]}`)
      output = await ownerHello(repoDir, ownerId, timeoutMs)
      break
    case "jobs":
      if (flags.size) throw new Error(`Unknown flag: ${[...flags.keys()][0]}`)
      output = await ownerJobs(repoDir, ownerId, timeoutMs)
      break
    case "status": {
      const target = requiredTargetFlags(flags)
      if (flags.size) throw new Error(`Unknown flag: ${[...flags.keys()][0]}`)
      output = await ownerStatus(repoDir, ownerId, target, timeoutMs)
      break
    }
    case "steer": {
      const target = requiredTargetFlags(flags)
      const commandId = requiredFlag(flags, "command_id", "--command", "--command-id")
      const note = textOrFileFlag(flags, "note")
      if (flags.size) throw new Error(`Unknown flag: ${[...flags.keys()][0]}`)
      output = await ownerSteer(repoDir, ownerId, { target, command_id: commandId, note }, timeoutMs)
      break
    }
    case "interrupt": {
      const target = requiredTargetFlags(flags)
      const commandId = requiredFlag(flags, "command_id", "--command", "--command-id")
      if (flags.size) throw new Error(`Unknown flag: ${[...flags.keys()][0]}`)
      output = await ownerInterrupt(repoDir, ownerId, { target, command_id: commandId }, timeoutMs)
      break
    }
    case "resume": {
      const target = requiredTargetFlags(flags)
      const commandId = requiredFlag(flags, "command_id", "--command", "--command-id")
      const feedback = textOrFileFlag(flags, "feedback")
      if (flags.size) throw new Error(`Unknown flag: ${[...flags.keys()][0]}`)
      output = await ownerResume(repoDir, ownerId, { target, command_id: commandId, feedback }, timeoutMs)
      break
    }
    case "command": {
      const commandId = requiredFlag(flags, "command_id", "--command", "--command-id")
      if (flags.size) throw new Error(`Unknown flag: ${[...flags.keys()][0]}`)
      output = await ownerCommand(repoDir, ownerId, commandId, timeoutMs)
      break
    }
    default:
      throw new Error(OWNER_CLI_USAGE)
  }
  process.stdout.write(JSON.stringify(output, null, 2) + "\n")
}
