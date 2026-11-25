import { assertHarnessEnabled } from "./harnesses.ts"
import { readFileSync } from "node:fs"
import { dirname } from "node:path"
import { randomUUID } from "node:crypto"
import { makeFxAdapter, type FxSelection } from "./fx.ts"
import { CHILD_TOOLS, cancelChildRun, childTerminal, readChildLedger, writeChildLedger, type FxChildConfig, type FxChildEntry } from "./fx-children.ts"
import { isRecord } from "./scope.ts"
import { isBridgeTier, type BridgeTier } from "./tier-policy.ts"

// Per-root controller, launched by the root FX worker as a client-supplied ACP MCP server. Children get no
// controller of their own, so delegation is one generation deep. Authority comes only from the admission snapshot.
const [configPath, rootJobPath] = process.argv.slice(2)
const config = JSON.parse(readFileSync(configPath!, "utf8")) as FxChildConfig
const rootJob = JSON.parse(readFileSync(rootJobPath!, "utf8")) as { deadlineAt?: unknown }
const deadlineAt = typeof rootJob.deadlineAt === "number" ? rootJob.deadlineAt : Date.now()
const fxHome = dirname(configPath!)
const fx = makeFxAdapter(config.adapter)
const MAX_TEXT = 4000, MAX_WAIT_S = 300, MAX_RESUMES = 2, STEER_STOP_MS = 15000

type Args = Record<string, unknown>
const SCHEMAS: Record<(typeof CHILD_TOOLS)[number], { description: string; required: string[]; properties: Record<string, object> }> = {
  spawn: { description: "Start one child worker in this worktree. tier must be one this worker may delegate to; intent_id makes retries idempotent.", required: ["tier", "task", "intent_id"], properties: { tier: { type: "string", enum: Object.keys(config.selections) }, task: { type: "string" }, intent_id: { type: "string" } } },
  status: { description: "Report a child's state, final text and error without waiting.", required: ["child_id"], properties: { child_id: { type: "string" } } },
  wait: { description: "Wait up to timeout_s seconds (max 300) for a child to reach a terminal state.", required: ["child_id", "timeout_s"], properties: { child_id: { type: "string" }, timeout_s: { type: "number" } } },
  cancel: { description: "Cancel a running child.", required: ["child_id"], properties: { child_id: { type: "string" } } },
  steer: { description: "Interrupt a running child and continue its session with a same-scope note.", required: ["child_id", "note"], properties: { child_id: { type: "string" }, note: { type: "string" } } },
  resume: { description: "Continue a finished child's session with same-scope feedback.", required: ["child_id", "feedback"], properties: { child_id: { type: "string" }, feedback: { type: "string" } } },
}

function exact(args: unknown, tool: keyof typeof SCHEMAS): Args {
  if (!isRecord(args)) throw new Error("arguments must be an object")
  const allowed = Object.keys(SCHEMAS[tool].properties)
  const extra = Object.keys(args).filter(key => !allowed.includes(key))
  if (extra.length) throw new Error("Child delegation cannot set " + extra.join(", ") + "; model, provider, tools, workspace and nesting come from the root's admission")
  for (const key of SCHEMAS[tool].required) if (args[key] === undefined) throw new Error("missing " + key)
  return args
}
function text(value: unknown, field: string, max = 32000): string {
  if (typeof value !== "string" || !value.trim() || value.length > max) throw new Error(field + " must be a nonempty string of at most " + max + " characters")
  return value
}
function entry(id: unknown): FxChildEntry {
  const found = readChildLedger(fxHome).children.find(child => child.child_id === id)
  if (!found) throw new Error("unknown child_id")
  return found
}
function update(changed: FxChildEntry): void {
  const ledger = readChildLedger(fxHome)
  ledger.children = ledger.children.map(child => child.child_id === changed.child_id ? changed : child)
  writeChildLedger(fxHome, ledger)
}
function observe(child: FxChildEntry) {
  if (child.spawn !== "started" || !child.run) return { child_id: child.child_id, tier: child.tier, state: child.spawn === "uncertain" ? "spawn_uncertain" : "admitting", final_text: null, error: null }
  const status = fx.status(child.run, child.selection)
  const result = status.result
  return { child_id: child.child_id, tier: child.tier, state: status.state, final_text: result?.finalText ? result.finalText.slice(-MAX_TEXT) : null,
    error: result?.error ?? (status.state === "unknown_or_interrupted" ? status.stderr : null), usage: result?.usage ?? null, resumes: child.resumes }
}
function prompt(child: { tier: BridgeTier; task: string }, note?: string): string {
  return [`You are a ${child.tier} child of a bridge-managed worker, sharing its worktree. You cannot spawn further children.`,
    child.tier === "scout" ? "You are read-only: report findings with file and line evidence." : "Edit only what the task requires and report the checks you ran.",
    "TASK: " + child.task, ...(note ? ["SAME-SCOPE FOLLOW-UP: " + note] : [])].join("\n")
}
function launch(child: FxChildEntry, text: string, resume?: string) {
  return fx.start({ directory: config.cwd, logDirectory: config.logDirectory, prompt: text, selection: child.selection,
    access: child.tier === "scout" ? { kind: "read-only" } : { kind: "write" }, deadlineAt, orphan: true, ...(resume ? { resume } : {}) })
}
async function settled(child: FxChildEntry, timeoutMs: number) {
  const until = Date.now() + timeoutMs
  for (;;) {
    const seen = observe(child)
    if (childTerminal(seen.state) || seen.state === "unknown_or_interrupted" || seen.state === "spawn_uncertain" || Date.now() >= until) return seen
    await new Promise(resolve => setTimeout(resolve, 250))
  }
}
function continueChild(child: FxChildEntry, note: string) {
  if (child.resumes >= MAX_RESUMES) throw new Error("child resume limit reached")
  const status = child.run ? fx.status(child.run, child.selection) : null
  if (!status || !childTerminal(status.state) || !status.result?.sessionId) throw new Error("child is not in a resumable terminal state (" + (status?.state ?? "not started") + ")")
  const run = launch(child, prompt(child, note), status.result.sessionId)
  const next = { ...child, run, resumes: child.resumes + 1 }
  update(next)
  return observe(next)
}

async function call(tool: string, raw: unknown): Promise<unknown> {
  if (!(CHILD_TOOLS as readonly string[]).includes(tool)) throw new Error("unknown tool " + tool)
  const name = tool as keyof typeof SCHEMAS, args = exact(raw, name)
  if (name === "spawn" || name === "resume" || name === "steer") assertHarnessEnabled("fx")
  switch (name) {
    case "spawn": {
      const tier = args.tier, task = text(args.task, "task"), intent = text(args.intent_id, "intent_id", 128)
      if (!isBridgeTier(tier)) throw new Error("unknown tier")
      const selection: FxSelection | undefined = config.selections[tier]
      if (!selection) throw new Error("This worker cannot delegate to " + tier)
      const ledger = readChildLedger(fxHome)
      const prior = ledger.children.find(child => child.intent_id === intent)
      if (prior) return { ...observe(prior), replayed: true }
      if (ledger.children.length >= config.limits.maxChildren) throw new Error("child limit reached for this worker")
      const active = ledger.children.filter(child => !childTerminal(observe(child).state))
      if (active.length >= config.limits.maxConcurrent) throw new Error("concurrent child limit reached; wait for a child first")
      if (tier !== "scout" && active.some(child => child.tier !== "scout")) throw new Error("another writing child is active in this worktree; wait for it first")
      const child: FxChildEntry = { child_id: randomUUID(), intent_id: intent, tier, selection, task, spawn: "recorded", resumes: 0 }
      ledger.children.push(child)
      writeChildLedger(fxHome, ledger)
      let run
      try { run = launch(child, prompt(child)) } catch (error) {
        const uncertain = String(error).includes("admission uncertain")
        const current = readChildLedger(fxHome)
        current.children = uncertain ? current.children.map(item => item.child_id === child.child_id ? { ...item, spawn: "uncertain" as const } : item) : current.children.filter(item => item.child_id !== child.child_id)
        writeChildLedger(fxHome, current)
        throw error
      }
      const started = { ...child, run, spawn: "started" as const }
      update(started)
      return observe(started)
    }
    case "status": return observe(entry(args.child_id))
    case "wait": {
      const seconds = typeof args.timeout_s === "number" && args.timeout_s > 0 ? Math.min(args.timeout_s, MAX_WAIT_S) : 0
      return settled(entry(args.child_id), seconds * 1000)
    }
    case "cancel": {
      const child = entry(args.child_id)
      return { child_id: child.child_id, signaled: child.run ? cancelChildRun(child.run) : false }
    }
    case "steer": {
      const child = entry(args.child_id), note = text(args.note, "note")
      if (!child.run || observe(child).state !== "running") throw new Error("child is not running; use resume")
      if (!fx.session(child.run, child.selection)) throw new Error("child native session identity is not bound yet; steering would lose the session, so retry shortly")
      if (!cancelChildRun(child.run)) throw new Error("child process identity changed; refusing to signal")
      const stopped = await settled(child, STEER_STOP_MS)
      if (!childTerminal(stopped.state)) throw new Error("child did not stop within " + STEER_STOP_MS + " ms; inspect it before retrying")
      return { ...continueChild(entry(child.child_id), note), steered: true }
    }
    case "resume": return continueChild(entry(args.child_id), text(args.feedback, "feedback"))
  }
}

let buffer = ""
function send(message: object): void { process.stdout.write(JSON.stringify({ jsonrpc: "2.0", ...message }) + "\n") }
process.stdin.setEncoding("utf8")
process.stdin.on("data", (chunk: string) => {
  buffer += chunk
  let index: number
  while ((index = buffer.indexOf("\n")) >= 0) {
    const line = buffer.slice(0, index); buffer = buffer.slice(index + 1)
    if (line.trim()) void handle(JSON.parse(line) as Record<string, unknown>)
  }
})
process.stdin.on("end", () => process.exit(0))
async function handle(message: Record<string, unknown>): Promise<void> {
  const id = message.id, params = isRecord(message.params) ? message.params : {}
  if (id === undefined) return
  if (message.method === "initialize") return send({ id, result: { protocolVersion: params.protocolVersion ?? "2025-06-18", capabilities: { tools: {} }, serverInfo: { name: "bridge-children", version: "1" } } })
  if (message.method === "tools/list") return send({ id, result: { tools: CHILD_TOOLS.map(name => ({ name, description: SCHEMAS[name].description, inputSchema: { type: "object", additionalProperties: false, required: SCHEMAS[name].required, properties: SCHEMAS[name].properties } })) } })
  if (message.method === "tools/call") {
    try { return send({ id, result: { content: [{ type: "text", text: JSON.stringify(await call(String(params.name), params.arguments)) }] } }) }
    catch (error) { return send({ id, result: { isError: true, content: [{ type: "text", text: error instanceof Error ? error.message : String(error) }] } }) }
  }
  send({ id, error: { code: -32601, message: "Method not found" } })
}
