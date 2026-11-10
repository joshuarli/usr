import { registerSubagentCapabilityCeiling, type SubagentCapabilityCeilingHandle } from "pi-subagents/capability-ceiling"
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent"
import { DELEGATION, isMuseTier, MUSE_DELEGATION, type Tier } from "./tier-policy.ts"

type Block = { block: true; reason: string }
const DENIED_FIELDS = new Set([
  "model", "cwd", "worktree", "tools", "skills", "runner", "machine", "script",
  "workflow", "tasks", "chain", "parallel", "count", "commands",
  "extensions", "subagentOnlyExtensions",
])
const CONTROL_ACTIONS = new Set([
  "list", "get", "status", "children.list", "lane.status", "guide",
  "interrupt", "stop", "steer", "resume",
])
const CONTROL_FIELDS = new Set(["action", "id", "index", "message", "mode", "view", "lines"])
const START_FIELDS = new Set(["agent", "task", "async", "options"])

/** Reject model-controlled attempts to escape the typed tier graph or reconfigure a nested launch. */
export type GuardFamily = "go" | "muse"
export function nestedCallRefusal(parent: Tier, toolName: string, input: unknown, family: GuardFamily = "go"): string | undefined {
  if (toolName === "subagent_launch") return "Nested workflow scripts are not permitted by usr tier policy"
  if (toolName !== "subagent") return undefined
  if (!input || typeof input !== "object" || Array.isArray(input))
    return "Malformed nested subagent request"
  const request = input as Record<string, unknown>
  if (Object.keys(request).some((key) => DENIED_FIELDS.has(key)))
    return "Nested delegation cannot override model, worktree, provider, tools, or workflow execution"
  if (request.action !== undefined) {
    if (typeof request.action !== "string" || !CONTROL_ACTIONS.has(request.action) ||
        Object.keys(request).some((key) => !CONTROL_FIELDS.has(key)))
      return "Nested delegation permits only read/control actions and explicit single-child starts"
    return undefined
  }
  if (Object.keys(request).some((key) => !START_FIELDS.has(key)))
    return "Nested delegation accepts only agent, task, async, and an options.agentScope pin"
  const options = request.options
  if (!options || typeof options !== "object" || Array.isArray(options) ||
      Object.keys(options).length !== 1 ||
      (options as Record<string, unknown>).agentScope !== "user")
    return "Nested delegation requires options.agentScope=user with no other options"
  if (typeof request.task !== "string" || !request.task.trim() || request.task.length > 32_000)
    return "Nested delegation requires a nonempty bounded task"
  const allowed: readonly string[] = family === "muse"
    ? (isMuseTier(parent) ? MUSE_DELEGATION[parent] : [])
    : DELEGATION[parent]
  if (typeof request.agent !== "string" || !allowed.includes(request.agent))
    return `Tier ${parent} cannot delegate to ${String(request.agent)}`
  return undefined
}

/**
 * This module is installed as a *mandatory inherited child extension* by the
 * SDK owner. It runs in the child process, not in the parent prompt. Upstream
 * capability ceilings intersect monotonically and survive nested + async runs.
 */
export function registerTierGuard(parent: Tier, family: GuardFamily = "go"): (pi: ExtensionAPI) => void {
  if (family === "muse" && !isMuseTier(parent)) throw new Error("Muse cannot execute expert")
  const children: readonly string[] = family === "muse"
    ? (isMuseTier(parent) ? MUSE_DELEGATION[parent as keyof typeof MUSE_DELEGATION] as any : [])
    : DELEGATION[parent]
  return (pi: ExtensionAPI) => {
    let ceiling: SubagentCapabilityCeilingHandle | undefined
    pi.on("session_start", (_event, ctx) => {
      ceiling?.dispose()
      ceiling = registerSubagentCapabilityCeiling({
        sessionId: ctx.sessionManager.getSessionId(),
        source: "usr-bridge-" + family + "-" + parent,
        ceiling: { allowedAgents: [...children] },
      })
    })
    pi.on("session_shutdown", () => {
      ceiling?.dispose()
      ceiling = undefined
    })
    pi.on("tool_call", (event) => {
      const reason = nestedCallRefusal(parent, event.toolName, event.input, family)
      return reason ? { block: true, reason } satisfies Block : undefined
    })
  }
}
