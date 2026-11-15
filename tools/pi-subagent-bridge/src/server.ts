#!/usr/bin/env -S node --experimental-strip-types
import { createInterface } from "node:readline"
import { COMMANDS, COMMAND_NAMES, decodeCommand, toolSchema, type Command } from "./commands.ts"
import { isRecord } from "./scope.ts"

const VERSION = "0.3.0"
const PROTOCOL = "2025-06-18"
const MAX_LINE = 100_000

const tools = COMMAND_NAMES.map(name => ({ name: COMMANDS[name].tool, description: COMMANDS[name].description, inputSchema: toolSchema(name) }))

export type Bridge = ReturnType<typeof import("./hybrid.ts").makeHybridBridge>
type Message = { jsonrpc: "2.0"; id?: string | number | null; method?: string; params?: unknown }

export async function connect(): Promise<Bridge> {
  const [{ optionalPiPort }, { makeHybridBridge }] = await Promise.all([import("./optional-pi.ts"), import("./hybrid.ts")])
  return makeHybridBridge(optionalPiPort())
}

export function dispatch(worker: Bridge, command: Command): Promise<unknown> {
  switch (command.name) {
    case "model_check": return worker.modelCheck(command.cwd, command.tier)
    case "start": return worker.start(command.cwd, command.title, command.tier, command.scope, command.brief)
    case "status": return worker.status(command.cwd, command.session_id)
    case "resume": return worker.resume(command.cwd, command.session_id, command.feedback)
    case "steer": return worker.steer(command.cwd, command.session_id, command.note)
    case "cancel": return worker.cancel(command.cwd, command.session_id)
  }
}

export type ServeOptions = {
  ownerRepos?: string[]
  ownerId?: string
}

export function serve(load: () => Promise<Bridge> = connect, options?: ServeOptions): void {
  const manageOwner = load === connect || (options?.ownerRepos !== undefined && options.ownerRepos.length > 0)
  let ownerManagerPromise: Promise<{ ensureRepo(dir: string): Promise<unknown>; close(): Promise<void> }> | undefined
  let cached: Promise<Bridge> | undefined
  let closing = false
  const pending = new Set<Promise<void>>()
  const bridge = () => cached ??= (async () => {
    const loaded = await load()
    if (manageOwner && !closing) {
      ownerManagerPromise ??= import("./owner.ts").then(({ OwnerManager }) =>
        new OwnerManager(loaded, options?.ownerId ? { ownerId: options.ownerId } : undefined),
      )
      await ownerManagerPromise
    }
    return loaded
  })().catch((error: unknown) => {
    cached = undefined
    throw error
  })
  const eagerOwner = options?.ownerRepos?.length
    ? (async () => {
      await bridge()
      const manager = ownerManagerPromise ? await ownerManagerPromise : undefined
      if (manager) {
        for (const repo of options.ownerRepos!) {
          await manager.ensureRepo(repo)
        }
      }
    })().catch((error: unknown) => console.error("pi-subagent-bridge:", error))
    : undefined
  const write = (message: unknown) => process.stdout.write(JSON.stringify(message) + "\n")
  const rpcError = (id: string | number | null, code: number, message: string) =>
    write({ jsonrpc: "2.0", id, error: { code, message } })

  async function handle(message: Message): Promise<void> {
    const { id, method } = message
    if (method === "notifications/initialized" || method === "notifications/cancelled") return
    if (id === undefined) return
    if (method === "initialize") {
      write({ jsonrpc: "2.0", id, result: {
        protocolVersion: PROTOCOL, capabilities: { tools: { listChanged: false } },
        serverInfo: { name: "pi-subagent-bridge", version: VERSION },
      } })
      return
    }
    if (method === "ping") { write({ jsonrpc: "2.0", id, result: {} }); return }
    if (method === "tools/list") { write({ jsonrpc: "2.0", id, result: { tools } }); return }
    if (method !== "tools/call") { rpcError(id, -32601, `Method not found: ${method}`); return }
    try {
      const params = isRecord(message.params) ? message.params : {}
      const name = COMMAND_NAMES.find(name => COMMANDS[name].tool === params.name)
      if (!name) {
        rpcError(id, -32602, "Unknown tool")
        return
      }
      if (eagerOwner) await eagerOwner
      const command = decodeCommand(name, params.arguments)
      const activeBridge = await bridge()
      if (ownerManagerPromise) {
        const manager = await ownerManagerPromise
        if (typeof command.cwd === "string" && command.cwd.trim()) {
          await manager.ensureRepo(command.cwd).catch(() => undefined)
        }
      }
      const result = await dispatch(activeBridge, command)
      write({ jsonrpc: "2.0", id, result: { content: [{ type: "text", text: JSON.stringify(result) }] } })
    } catch (error) {
      // Tool failures are returned to the orchestrator as recoverable tool results, not stdout logs.
      write({ jsonrpc: "2.0", id, result: { content: [{ type: "text", text: String(error) }], isError: true } })
    }
  }

  const lines = createInterface({ input: process.stdin, crlfDelay: Infinity })
  let shutdownStarted = false
  let signalStop = false
  const shutdown = async () => {
    if (shutdownStarted) return
    shutdownStarted = true
    closing = true
    process.off("SIGINT", onSignal)
    process.off("SIGTERM", onSignal)
    if (eagerOwner) await eagerOwner
    await Promise.allSettled([...pending])
    if (ownerManagerPromise) {
      const manager = await ownerManagerPromise.catch(() => undefined)
      await manager?.close()
    }
    if (signalStop) process.exit(0)
  }
  const onSignal = () => {
    signalStop = true
    lines.close()
    void shutdown()
  }
  process.on("SIGINT", onSignal)
  process.on("SIGTERM", onSignal)
  lines.on("close", () => { void shutdown() })
  lines.on("line", (line) => {
    if (Buffer.byteLength(line) > MAX_LINE) { console.error("pi-subagent-bridge: oversized MCP request"); return }
    try {
      const data: unknown = JSON.parse(line)
      if (!isRecord(data) || data.jsonrpc !== "2.0") return
      const task = handle(data as Message)
        .catch((error) => console.error("pi-subagent-bridge:", error))
        .finally(() => pending.delete(task))
      pending.add(task)
    } catch { console.error("pi-subagent-bridge: invalid MCP JSON") }
  })
}

if (process.argv[1] && /(?:^|\/)server\.ts$/.test(process.argv[1]) && !process.env.USR_OPENCODE_WORKER_TEST) serve()
