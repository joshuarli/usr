import { ROOT_PLANS, routesOf } from "./policy.ts"
import { TIERS, isTier, type Tier } from "./tier-policy.ts"
import { SCOPE_SCHEMA, isRecord, parseScope, requiredText, type Scope } from "./scope.ts"

export type Command =
  | { readonly name: "model_check"; readonly cwd: string; readonly tier: Tier }
  | { readonly name: "start"; readonly cwd: string; readonly title: string; readonly tier: Tier; readonly scope: Scope; readonly brief: string }
  | { readonly name: "status"; readonly cwd: string; readonly session_id: string }
  | { readonly name: "resume"; readonly cwd: string; readonly session_id: string; readonly feedback: string }
  | { readonly name: "steer"; readonly cwd: string; readonly session_id: string; readonly note: string }
  | { readonly name: "cancel"; readonly cwd: string; readonly session_id: string }
export type CommandName = Command["name"]
export const COMMAND_NAMES = ["model_check", "start", "status", "resume", "steer", "cancel"] as const satisfies readonly CommandName[]

type Field = "cwd" | "title" | "tier" | "scope" | "brief" | "session_id" | "feedback" | "note"
const FIELDS: Record<Field, { readonly schema: object; readonly label: string; readonly file?: "text" | "json" }> = {
  cwd: { label: "CWD", schema: { type: "string", description: "Absolute root of an EXISTING clean, separate git worktree under <repo>/.work/wt/<name>. Parent creates and owns it." } },
  title: { label: "TITLE", schema: { type: "string", maxLength: 100, description: "Short scoped task name" } },
  tier: { label: "TIER", schema: { type: "string", enum: TIERS } },
  scope: { label: "SCOPE_JSON_FILE", file: "json", schema: SCOPE_SCHEMA },
  brief: { label: "BRIEF_FILE", file: "text", schema: { type: "string", maxLength: 32000, description: "One bounded outcome and only the context needed" } },
  session_id: { label: "SESSION_ID", schema: { type: "string", description: "usrw_ session ID returned by worker_start; never guess another session." } },
  feedback: { label: "FEEDBACK_FILE", file: "text", schema: { type: "string", maxLength: 32000 } },
  note: { label: "NOTE_FILE", file: "text", schema: { type: "string", minLength: 1, maxLength: 32000 } },
}

const routingSummary = TIERS.map(name => {
  const routes = routesOf(ROOT_PLANS[name])
  return `${name}: ${routes.map(route => route.executor).join(" then ")}${routes.length === 1 ? ", no fallback" : ""}`
}).join("; ")

export const COMMANDS: Record<CommandName, {
  readonly tool: string; readonly cli: string; readonly fields: readonly Field[]; readonly description: string
}> = {
  model_check: {
    tool: "worker_model_check", cli: "model-check", fields: ["cwd", "tier"],
    description: "Read-only: inspect this tier's pinned models, provider availability and approved fallbacks.",
  },
  start: {
    tool: "worker_start", cli: "start", fields: ["cwd", "title", "tier", "scope", "brief"],
    description: `Delegate a scoped task using policy routes (${routingSummary}). Never start a duplicate. Admission is not completion: run the returned watch command as a background task to learn when the worker ends.`,
  },
  status: {
    tool: "worker_status", cli: "status", fields: ["cwd", "session_id"],
    description: "Observe actual backend/model, claimed proof, changed/out-of-scope paths, and HEAD. Reports continuations used against the continuation cap and steers used against the steer cap. A run that ends without a final `ACCEPTANCE: met` line reports state incomplete and acceptance_blocked. A Codex or Command Code run whose recorded process is gone without a terminal receipt or whose PID identity changed is interrupted. When fallback_reason is set, fallback_notice identifies the switch. The original provider message is kept in fallback_detail for diagnosis; error is null once the fallback has safely taken over.",
  },
  resume: {
    tool: "worker_resume", cli: "resume", fields: ["cwd", "session_id", "feedback"],
    description: "Parent ONLY: enqueue targeted feedback in the SAME inactive worker session. Cannot change model, worktree, or ownership boundaries. Never retry unchanged failures.",
  },
  steer: {
    tool: "worker_steer", cli: "steer", fields: ["cwd", "session_id", "note"],
    description: "Parent ONLY: redirect a RUNNING worker in the same scope and write boundaries. Pi workers forward the note to the native pi-subagents steer RPC. Codex and Command Code runs are interrupted, termination is proven, and the same session resumes with the note; attempts are unchanged and a separate steer cap applies. A finished session is refused; use worker_resume.",
  },
  cancel: {
    tool: "worker_cancel", cli: "cancel", fields: ["cwd", "session_id"],
    description: "Interrupt this owned usr worker session. Never delete the worktree or branch; parent preserves and reviews its changes.",
  },
}

export function toolSchema(name: CommandName) {
  const fields = COMMANDS[name].fields
  return { type: "object", properties: Object.fromEntries(fields.map(field => [field, FIELDS[field].schema])),
    required: fields, additionalProperties: false }
}
export function usage(name: CommandName): string {
  const { cli, fields } = COMMANDS[name]
  return "usage: pi-subagent-bridge " + [cli, ...fields.map(field => FIELDS[field].label)].join(" ")
}

function parseJson(text: string): unknown {
  return JSON.parse(text)
}
function cwd(value: unknown): string {
  if (typeof value !== "string" || !value.trim()) throw new Error("Invalid cwd")
  return value
}
function tier(value: unknown): Tier {
  if (!isTier(value)) throw new Error("Unknown Pi tier")
  return value
}

export function decodeCommand(name: CommandName, args: unknown): Command {
  if (!isRecord(args)) throw new Error("Tool arguments must be an object")
  const fields = COMMANDS[name].fields
  for (const field of fields) {
    if (!Object.hasOwn(args, field)) throw new Error("Missing tool argument: " + field)
  }
  for (const key of Object.keys(args)) {
    if (!fields.some(field => field === key)) throw new Error("Unknown tool argument: " + key)
  }
  const dir = cwd(args.cwd)
  switch (name) {
    case "model_check": return { name, cwd: dir, tier: tier(args.tier) }
    case "start": {
      const requested = tier(args.tier)
      return { name, cwd: dir, title: requiredText(args.title, "title", 100), tier: requested,
        scope: parseScope(args.scope, requested), brief: requiredText(args.brief, "brief", 32000) }
    }
    case "status": return { name, cwd: dir, session_id: requiredText(args.session_id, "session_id", 64) }
    case "resume":
      return { name, cwd: dir, session_id: requiredText(args.session_id, "session_id", 64), feedback: requiredText(args.feedback, "feedback", 32000) }
    case "steer":
      return { name, cwd: dir, session_id: requiredText(args.session_id, "session_id", 64), note: requiredText(args.note, "note", 32000) }
    case "cancel": return { name, cwd: dir, session_id: requiredText(args.session_id, "session_id", 64) }
  }
}

export function cliArguments(name: CommandName, rest: readonly string[], read: (path: string) => string): Record<string, unknown> {
  const fields = COMMANDS[name].fields
  if (rest.length !== fields.length || rest.some(value => !value)) throw new Error(usage(name))
  return Object.fromEntries(fields.map((field, index) => {
    const value = rest[index]
    const file = FIELDS[field].file
    return [field, file === undefined ? value : file === "json" ? parseJson(read(value)) : read(value)]
  }))
}
