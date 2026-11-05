#!/usr/bin/env -S node --experimental-strip-types
import { createInterface } from "node:readline"
import { makeWorkerBridge, type OpenCodePort } from "./bridge.ts"

const VERSION = "0.1.0"
const PROTOCOL = "2025-06-18"
const MAX_LINE = 100_000

const cwdSchema = { type: "string", description: "Absolute root of an EXISTING clean, separate git worktree under <repo>/.work/wt/<name>. Parent creates and owns it." }
const idSchema = { type: "string", description: "OpenCode session_id returned by worker_start; never guess or substitute another session." }
const tools = [
  {
    name: "worker_model_check",
    description: "Read-only: verify usr's pinned DeepSeek worker model is available in the configured OpenCode v2 location. Never fall back to another model.",
    inputSchema: { type: "object", properties: { cwd: cwdSchema }, required: ["cwd"], additionalProperties: false },
  },
  {
    name: "worker_start",
    description: "Parent orchestrator ONLY: start ONE normal implementation worker in an existing, clean dedicated git worktree. Claude retains review/integration. Not for expert/god, not from a child. Prompt is durably admitted, not necessarily completed.",
    inputSchema: { type: "object", properties: {
      cwd: cwdSchema,
      title: { type: "string", maxLength: 100, description: "Short human-readable slice name" },
      brief: { type: "string", maxLength: 32000, description: "Self-contained worker brief: exact write boundaries, deliverable, acceptance commands, attempt and stopping limits" },
    }, required: ["cwd", "title", "brief"], additionalProperties: false },
  },
  {
    name: "worker_status",
    description: "Observe worker outcome, pending inputs, reported cost, last assistant result, and Git status. This does NOT prove correctness; parent reviews diff and checks.",
    inputSchema: { type: "object", properties: { cwd: cwdSchema, session_id: idSchema }, required: ["cwd", "session_id"], additionalProperties: false },
  },
  {
    name: "worker_resume",
    description: "Parent ONLY: enqueue targeted feedback in the SAME inactive, unqueued usr worker session. Cannot change model, worktree, or ownership boundaries. Never retry unchanged failures.",
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

type Bridge = ReturnType<typeof makeWorkerBridge>
type Message = { jsonrpc: "2.0"; id?: string | number | null; method?: string; params?: unknown }
function isObject(value: unknown): value is Record<string, unknown> {
  return !!value && typeof value === "object" && !Array.isArray(value)
}

/** Connect lazily: tools/list and unit tests need neither OpenCode nor credentials. */
export async function connect(): Promise<Bridge> {
  const [{ OpenCode }, { Service }] = await Promise.all([
    import("@opencode/client"), import("@opencode/client/service"),
  ])
  const endpoint = await Service.ensure({ version: (version: string) => version.startsWith("2.") })
  const client = OpenCode.make({ baseUrl: endpoint.url, headers: Service.headers(endpoint) })
  const api: OpenCodePort = {
    create: (input) => client.session.create(input),
    prompt: (input) => client.session.prompt(input),
    get: (input) => client.session.get(input),
    active: () => client.session.active(),
    inbox: (input) => client.session.inbox.list(input),
    messages: (input) => client.session.message.list(input),
    interrupt: (input) => client.session.interrupt(input),
    models: (input) => client.model.list(input),
  }
  return makeWorkerBridge(api)
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
        serverInfo: { name: "usr-opencode-worker", version: VERSION },
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
        case "worker_model_check": result = await worker.modelCheck(args.cwd); break
        case "worker_start": result = await worker.start(args.cwd, args.title, args.brief); break
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
    if (Buffer.byteLength(line) > MAX_LINE) { console.error("usr-opencode-worker: oversized MCP request"); return }
    try {
      const data: unknown = JSON.parse(line)
      if (!isObject(data) || data.jsonrpc !== "2.0") return
      void handle(data as Message).catch((error) => console.error("usr-opencode-worker:", error))
    } catch { console.error("usr-opencode-worker: invalid MCP JSON") }
  })
}

if (process.argv[1] && /(?:^|\/)server\.ts$/.test(process.argv[1]) && !process.env.USR_OPENCODE_WORKER_TEST) serve()
