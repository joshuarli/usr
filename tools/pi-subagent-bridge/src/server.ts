#!/usr/bin/env -S node --experimental-strip-types
for (const p of ["/opt/homebrew/opt/rustup/bin", "/opt/homebrew/bin", "/Users/josh/.local/bin"]) {
  if (!process.env.PATH?.split(":").includes(p)) {
    process.env.PATH = `${p}:${process.env.PATH ?? ""}`
  }
}
import { createInterface } from "node:readline"
import { piPort } from "./pi-port.ts"
import { makeHybridBridge } from "./hybrid.ts"

const VERSION = "0.3.0"
const PROTOCOL = "2025-06-18"
const MAX_LINE = 100_000

const cwdSchema = { type: "string", description: "Absolute root of an EXISTING clean, separate git worktree under <repo>/.work/wt/<name>. Parent creates and owns it." }
const tierSchema = { type: "string", enum: ["scout", "mechanic", "worker", "expert"] }
const scopeSchema = {
  type: "object",
  properties: {
    base_revision: { type: "string", pattern: "^[a-f0-9]{40}$" },
    writable_paths: { type: "array", maxItems: 20, items: { type: "string" }, description: "Exact files or directory prefixes ending in /; empty only for scout" },
    acceptance_proof: { type: "string", minLength: 1, maxLength: 2000 },
    attempt_limit: { type: "integer", minimum: 1, maximum: 2 },
    stop_on: { type: "string", minLength: 1, maxLength: 2000 },
  },
  required: ["base_revision", "writable_paths", "acceptance_proof", "attempt_limit", "stop_on"],
  additionalProperties: false,
}
const idSchema = { type: "string", description: "usrw_ session ID returned by worker_start; never guess another session." }
const tools = [
  {
    name: "worker_model_check",
    description: "Read-only: inspect the pinned Pi SDK model for this tier and Command Code fallback availability.",
    inputSchema: { type: "object", properties: { cwd: cwdSchema, tier: tierSchema }, required: ["cwd", "tier"], additionalProperties: false },
  },
  {
    name: "worker_start",
    description: "Any parent harness: delegate a scoped task to a Pi SDK worker; fall back to Command Code DeepSeek 4.1 Flash only before edits on model/quota failure. Admission is NOT completion.",
    inputSchema: { type: "object", properties: {
      cwd: cwdSchema,
      title: { type: "string", maxLength: 100, description: "Short scoped task name" },
      tier: tierSchema,
      scope: scopeSchema,
      brief: { type: "string", maxLength: 32000, description: "One bounded outcome and only the context needed" },
    }, required: ["cwd", "title", "tier", "scope", "brief"], additionalProperties: false },
  },
  {
    name: "worker_status",
    description: "Observe actual backend/model, claimed proof, changed/out-of-scope paths, and HEAD. Can trigger quota fallback only when the original worktree is untouched.",
    inputSchema: { type: "object", properties: { cwd: cwdSchema, session_id: idSchema }, required: ["cwd", "session_id"], additionalProperties: false },
  },
  {
    name: "worker_resume",
    description: "Parent ONLY: enqueue targeted feedback in the SAME inactive, unqueued Pi worker session. Cannot change model, worktree, or ownership boundaries. Never retry unchanged failures.",
    inputSchema: { type: "object", properties: {
      cwd: cwdSchema, session_id: idSchema,
      feedback: { type: "string", maxLength: 32000 },
    }, required: ["cwd", "session_id", "feedback"], additionalProperties: false },
  },
  {
    name: "worker_cancel",
    description: "Interrupt this owned usr worker session. Never delete the worktree or branch; parent preserves and reviews its changes.",
    inputSchema: { type: "object", properties: { cwd: cwdSchema, session_id: idSchema }, required: ["cwd", "session_id"], additionalProperties: false },
  },
] as const

type Bridge = ReturnType<typeof makeHybridBridge>
type Message = { jsonrpc: "2.0"; id?: string | number | null; method?: string; params?: unknown }
function isObject(value: unknown): value is Record<string, unknown> {
  return !!value && typeof value === "object" && !Array.isArray(value)
}

export async function connect(): Promise<Bridge> { return makeHybridBridge(piPort()) }

export function serve(load: () => Promise<Bridge> = connect): void {
  let cached: Promise<Bridge> | undefined
  const bridge = () => cached ??= load().catch((error: unknown) => {
    cached = undefined
    throw error
  })
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
      const params = isObject(message.params) ? message.params : {}
      const args = isObject(params.arguments) ? params.arguments : {}
      if (typeof params.name !== "string" || !tools.some((tool) => tool.name === params.name)) {
        rpcError(id, -32602, "Unknown tool")
        return
      }
      const worker = await bridge()
      let result: unknown
      switch (params.name) {
        case "worker_model_check": result = await worker.modelCheck(args.cwd, args.tier); break
        case "worker_start": result = await worker.start(args.cwd, args.title, args.tier, args.scope, args.brief); break
        case "worker_status": result = await worker.status(args.cwd, args.session_id); break
        case "worker_resume": result = await worker.resume(args.cwd, args.session_id, args.feedback); break
        case "worker_cancel": result = await worker.cancel(args.cwd, args.session_id); break
        default: rpcError(id, -32602, "Unknown tool"); return
      }
      write({ jsonrpc: "2.0", id, result: { content: [{ type: "text", text: JSON.stringify(result) }] } })
    } catch (error) {
      // Tool failures are returned to the orchestrator as recoverable tool results, not stdout logs.
      write({ jsonrpc: "2.0", id, result: { content: [{ type: "text", text: String(error) }], isError: true } })
    }
  }

  const lines = createInterface({ input: process.stdin, crlfDelay: Infinity })
  lines.on("line", (line) => {
    if (Buffer.byteLength(line) > MAX_LINE) { console.error("pi-subagent-bridge: oversized MCP request"); return }
    try {
      const data: unknown = JSON.parse(line)
      if (!isObject(data) || data.jsonrpc !== "2.0") return
      void handle(data as Message).catch((error) => console.error("pi-subagent-bridge:", error))
    } catch { console.error("pi-subagent-bridge: invalid MCP JSON") }
  })
}

if (process.argv[1] && /(?:^|\/)server\.ts$/.test(process.argv[1]) && !process.env.USR_OPENCODE_WORKER_TEST) serve()
