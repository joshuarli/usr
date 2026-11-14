#!/usr/bin/env -S node --experimental-strip-types
import { createInterface } from "node:readline"
import { ROOT_ROUTES } from "./policy.ts"
import { TIERS, isTier } from "./tier-policy.ts"
import { SCOPE_SCHEMA, isRecord, parseScope, requiredText } from "./scope.ts"

const VERSION = "0.3.0"
const PROTOCOL = "2025-06-18"
const MAX_LINE = 100_000

const cwdSchema = { type: "string", description: "Absolute root of an EXISTING clean, separate git worktree under <repo>/.work/wt/<name>. Parent creates and owns it." }
const tierSchema = { type: "string", enum: TIERS }
const routingSummary = TIERS.map(tier => {
  const routes = ROOT_ROUTES[tier]
  return `${tier}: ${routes.map(route => route.executor).join(" then ")}${routes.length === 1 ? ", no fallback" : ""}`
}).join("; ")
const idSchema = { type: "string", description: "usrw_ session ID returned by worker_start; never guess another session." }
const tools = [
  {
    name: "worker_model_check",
    description: "Read-only: inspect this tier's pinned models, provider availability and approved fallbacks.",
    inputSchema: { type: "object", properties: { cwd: cwdSchema, tier: tierSchema }, required: ["cwd", "tier"], additionalProperties: false },
  },
  {
    name: "worker_start",
    description: `Delegate a scoped task using policy routes (${routingSummary}). Never start a duplicate. Admission is not completion: run the returned watch command as a background task to learn when the worker ends.`,
    inputSchema: { type: "object", properties: {
      cwd: cwdSchema,
      title: { type: "string", maxLength: 100, description: "Short scoped task name" },
      tier: tierSchema,
      scope: SCOPE_SCHEMA,
      brief: { type: "string", maxLength: 32000, description: "One bounded outcome and only the context needed" },
    }, required: ["cwd", "title", "tier", "scope", "brief"], additionalProperties: false },
  },
  {
    name: "worker_status",
    description: "Observe actual backend/model, claimed proof, changed/out-of-scope paths, and HEAD. Reports continuations used against the continuation cap and steers used against the steer cap. A run that ends without a final `ACCEPTANCE: met` line reports state incomplete and acceptance_blocked. A Codex or Command Code run whose recorded process is gone without a terminal receipt or whose PID identity changed is interrupted. When fallback_reason is set, fallback_notice identifies the switch. The original provider message is kept in fallback_detail for diagnosis; error is null once the fallback has safely taken over.",
    inputSchema: { type: "object", properties: { cwd: cwdSchema, session_id: idSchema }, required: ["cwd", "session_id"], additionalProperties: false },
  },
  {
    name: "worker_resume",
    description: "Parent ONLY: enqueue targeted feedback in the SAME inactive worker session. Cannot change model, worktree, or ownership boundaries. Never retry unchanged failures.",
    inputSchema: { type: "object", properties: {
      cwd: cwdSchema, session_id: idSchema,
      feedback: { type: "string", maxLength: 32000 },
    }, required: ["cwd", "session_id", "feedback"], additionalProperties: false },
  },
  {
    name: "worker_steer",
    description: "Parent ONLY: redirect a RUNNING worker in the same scope and write boundaries. Pi workers forward the note to the native pi-subagents steer RPC. Codex and Command Code runs are interrupted, termination is proven, and the same session resumes with the note; attempts are unchanged and a separate steer cap applies. A finished session is refused; use worker_resume.",
    inputSchema: { type: "object", properties: {
      cwd: cwdSchema, session_id: idSchema,
      note: { type: "string", minLength: 1, maxLength: 32000 },
    }, required: ["cwd", "session_id", "note"], additionalProperties: false },
  },
  {
    name: "worker_cancel",
    description: "Interrupt this owned usr worker session. Never delete the worktree or branch; parent preserves and reviews its changes.",
    inputSchema: { type: "object", properties: { cwd: cwdSchema, session_id: idSchema }, required: ["cwd", "session_id"], additionalProperties: false },
  },
] as const

export type Bridge = ReturnType<typeof import("./hybrid.ts").makeHybridBridge>
type Message = { jsonrpc: "2.0"; id?: string | number | null; method?: string; params?: unknown }

export async function connect(): Promise<Bridge> {
  for (const path of ["/opt/homebrew/opt/rustup/bin", "/opt/homebrew/bin", "/Users/josh/.local/bin"]) {
    if (!process.env.PATH?.split(":").includes(path)) process.env.PATH = `${path}:${process.env.PATH ?? ""}`
  }
  const [{ piPort }, { makeHybridBridge }] = await Promise.all([import("./pi-port.ts"), import("./hybrid.ts")])
  return makeHybridBridge(piPort())
}

function toolArguments(tool: (typeof tools)[number], value: unknown): Record<string, unknown> {
  if (!isRecord(value)) throw new Error("Tool arguments must be an object")
  for (const name of tool.inputSchema.required) {
    if (!Object.hasOwn(value, name)) throw new Error("Missing tool argument: " + name)
  }
  for (const name of Object.keys(value)) {
    if (!Object.hasOwn(tool.inputSchema.properties, name)) throw new Error("Unknown tool argument: " + name)
  }
  if (typeof value.cwd !== "string" || !value.cwd.trim()) throw new Error("Invalid cwd")
  if ("tier" in tool.inputSchema.properties && !isTier(value.tier)) throw new Error("Unknown Pi tier")
  if (tool.name === "worker_start") {
    if (!isTier(value.tier)) throw new Error("Unknown Pi tier")
    return { ...value, title: requiredText(value.title, "title", 100),
      scope: parseScope(value.scope, value.tier), brief: requiredText(value.brief, "brief", 32000) }
  }
  if ("session_id" in tool.inputSchema.properties) requiredText(value.session_id, "session_id", 64)
  if (tool.name === "worker_resume") requiredText(value.feedback, "feedback", 32000)
  if (tool.name === "worker_steer") requiredText(value.note, "note", 32000)
  return value
}

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
      const params = isRecord(message.params) ? message.params : {}
      const tool = tools.find(tool => tool.name === params.name)
      if (!tool) {
        rpcError(id, -32602, "Unknown tool")
        return
      }
      const args = toolArguments(tool, params.arguments)
      const worker = await bridge()
      let result: unknown
      switch (params.name) {
        case "worker_model_check": result = await worker.modelCheck(args.cwd, args.tier); break
        case "worker_start": result = await worker.start(args.cwd, args.title, args.tier, args.scope, args.brief); break
        case "worker_status": result = await worker.status(args.cwd, args.session_id); break
        case "worker_resume": result = await worker.resume(args.cwd, args.session_id, args.feedback); break
        case "worker_steer": result = await worker.steer(args.cwd, args.session_id, args.note); break
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
      if (!isRecord(data) || data.jsonrpc !== "2.0") return
      void handle(data as Message).catch((error) => console.error("pi-subagent-bridge:", error))
    } catch { console.error("pi-subagent-bridge: invalid MCP JSON") }
  })
}

if (process.argv[1] && /(?:^|\/)server\.ts$/.test(process.argv[1]) && !process.env.USR_OPENCODE_WORKER_TEST) serve()
