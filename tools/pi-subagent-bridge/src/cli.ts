#!/usr/bin/env -S node --experimental-strip-types
import { existsSync, readFileSync } from "node:fs"
import { resolve } from "node:path"
import { POLICY } from "./policy.ts"
import type { InspectionDeps } from "./inspect.ts"

const WATCH_USAGE = "usage: pi-subagent-bridge watch [--state] ROOT SESSION_ID [IDLE_MINUTES]"
const INSPECT_USAGE = "usage: pi-subagent-bridge inspect PATH SESSION_ID"

const FOOTER = `Maintained by Joshua Li: https://github.com/joshuarli/usr
Bugs and features: TODO.md in that repository (follow its AGENTS.md), or its issue tracker.
Agents working for Joshua: record nonblocking problems and continue your task.
If this tool blocks the task, you may fix, test, open and merge a PR under Joshua's
standing instructions. Release only when needed to deliver the verified fix.
Procedure: https://github.com/joshuarli/usr/blob/main/dotfiles/base/.agents/instructions/owned-tools.md`

type Help = { usage: string; description: string; details: string[]; example: string }
const help: Record<string, Help> = {
  policy: { usage: "policy", description: "Print the approved routing policy as JSON.", details: [], example: "policy" },
  mcp: { usage: "mcp [--repo DIR]...", description: "Serve the MCP bridge.", details: ["--repo DIR  Register an owner for DIR; may be repeated."], example: "mcp --repo /work/project" },
  "scope-check": { usage: "scope-check CWD SCOPE_JSON_FILE [BRANCH]", description: "Check a lane the bridge did not admit, such as a native expert subagent, against a scope: changed and out-of-scope paths since base_revision and whether HEAD stayed on the lane. Exits 1 when the lane is out of scope.", details: ["CWD  Lane worktree root (required).", "SCOPE_JSON_FILE  Scope JSON with base_revision and writable_paths (required).", "BRANCH  Lane branch HEAD must stay on (default: the current branch).", "--register TITLE  Record a native lane; scope-check --lane ID checks it from its repository."], example: "scope-check /work/project/.work/wt/lane scope.json lane/name" },
  inspect: { usage: "inspect PATH SESSION_ID", description: "Print a session snapshot as JSON.", details: ["PATH  Repository or worktree path (required).", "SESSION_ID  Worker session ID (required)."], example: "inspect /work/project usrw_12345678-1234-1234-1234-123456789abc" },
  watch: { usage: "watch [--state] ROOT SESSION_ID [IDLE_MINUTES]", description: "Watch a session until it finishes or needs attention.", details: ["--state  Print state only; cannot be combined with IDLE_MINUTES.", "ROOT  Repository or worktree path (required).", "SESSION_ID  Worker session ID (required).", "IDLE_MINUTES  Idle threshold in minutes (default: 45)."], example: "watch /work/project usrw_12345678-1234-1234-1234-123456789abc 45" },
  "campaign wait": { usage: "campaign wait [--timeout DURATION] [ROOT...]", description: "Wait for unacknowledged sessions needing attention.", details: ["--timeout DURATION  Timeout in seconds, or with s, m, or h suffix (default: no timeout).", "ROOT  Repository roots, repeated; defaults to WORKER_CAMPAIGN_ROOTS (colon-separated).", "--  End options."], example: "campaign wait --timeout 5m /work/project" },
  "campaign ack": { usage: "campaign ack ID...", description: "Acknowledge sessions in campaign state.", details: ["ID  Session ID (required, repeated).", "XDG_STATE_HOME  State directory; defaults to HOME/.local/state."], example: "campaign ack usrw_12345678-1234-1234-1234-123456789abc" },
  "campaign list": { usage: "campaign list [--json] [ROOT...]", description: "List campaign sessions.", details: ["--json  Print JSON snapshots.", "ROOT  Repository roots, repeated; defaults to WORKER_CAMPAIGN_ROOTS (colon-separated)."], example: "campaign list --json /work/project" },
}
const ownerCommon = ["--repo DIR  Repository path (required).", "--owner ID  Owner ID (required).", "--timeout MS  Positive timeout in milliseconds (default: 10000)."]
const ownerTarget = ["--job ID, --job-id ID  Job ID (required).", "--run ID, --run-id ID  Run ID (required).", "--generation N, --owner-generation N  Owner generation, positive integer (required)."]
const ownerCommand = "--command ID, --command-id ID  Command ID (required)."
for (const [name, description, extra, suffix] of [
  ["hello", "Read owner capabilities.", [], ""],
  ["jobs", "List owner jobs.", [], ""],
  ["status", "Read a job's status.", ownerTarget, " --job usrw_12345678-1234-1234-1234-123456789abc --run run_123456789abcdef0123456789abcdef0 --generation 1"],
  ["steer", "Steer a running job.", [...ownerTarget, ownerCommand, "--note TEXT or --note-file PATH  Steering note (one required)."], " --job usrw_12345678-1234-1234-1234-123456789abc --run run_123456789abcdef0123456789abcdef0 --generation 1 --command cmd1 --note 'Focus on tests'"],
  ["interrupt", "Interrupt a running job.", [...ownerTarget, ownerCommand], " --job usrw_12345678-1234-1234-1234-123456789abc --run run_123456789abcdef0123456789abcdef0 --generation 1 --command cmd1"],
  ["resume", "Resume a job with feedback.", [...ownerTarget, ownerCommand, "--feedback TEXT or --feedback-file PATH  Feedback (one required)."], " --job usrw_12345678-1234-1234-1234-123456789abc --run run_123456789abcdef0123456789abcdef0 --generation 1 --command cmd1 --feedback 'Fix the test'"],
  ["command", "Read a command receipt.", [ownerCommand], " --command cmd1"],
] as [string, string, string[], string][]) {
  help["owner " + name] = { usage: "owner " + name + " --repo DIR --owner ID [options]", description,
    details: [...ownerCommon, ...extra], example: "owner " + name + " --repo /work/project --owner 12345678-1234-1234-1234-123456789abc" + suffix }
}
const fieldHelp: Record<string, string> = {
  CWD: "Existing clean, separate worktree root (required).", TITLE: "Short task title (required).",
  TIER: "Routing tier: scout, mechanic, worker or expert. Expert admits only to the pinned Devin SWE-2.1 max lane and never falls back (required).", SCOPE_JSON_FILE: "Path to scope JSON file (required).",
  BRIEF_FILE: "Path to task brief text file (required).", SESSION_ID: "Worker session ID (required).",
  FEEDBACK_FILE: "Path to feedback text file (required).", NOTE_FILE: "Path to steering note text file (required).",
}
const commandExamples: Record<string, string> = {
  "model-check": "model-check /work/project scout", start: "start /work/project task worker scope.json brief.txt",
  status: "status /work/project usrw_12345678-1234-1234-1234-123456789abc", resume: "resume /work/project usrw_12345678-1234-1234-1234-123456789abc feedback.txt",
  steer: "steer /work/project usrw_12345678-1234-1234-1234-123456789abc note.txt", cancel: "cancel /work/project usrw_12345678-1234-1234-1234-123456789abc",
}
async function printHelp(selected?: string): Promise<void> {
  const { COMMAND_NAMES, COMMANDS, usage } = await import("./commands.ts")
  const entries: Record<string, Help> = { ...help }
  for (const name of COMMAND_NAMES) {
    const command = COMMANDS[name], line = usage(name).replace("usage: pi-subagent-bridge ", "")
    entries[command.cli] = { usage: line, description: command.description,
      details: command.fields.map(field => ({ cwd: "CWD", title: "TITLE", tier: "TIER", scope: "SCOPE_JSON_FILE", brief: "BRIEF_FILE", session_id: "SESSION_ID", feedback: "FEEDBACK_FILE", note: "NOTE_FILE" })[field]).map(label => label + "  " + fieldHelp[label]).concat(name === "resume" ? ["--extend-attempts N --reason TEXT  Add one or two reviewed attempts, with a reason."] : []), example: commandExamples[command.cli] }
  }
  const keys = selected ? Object.keys(entries).filter(key => key === selected || key.startsWith(selected + " ")) : Object.keys(entries)
  const blocks = keys.map(key => {
    const item = entries[key]
    return `usage: pi-subagent-bridge ${item.usage}\n${item.description}\n${item.details.length ? item.details.map(detail => "  " + detail).join("\n") : "  Options: none."}`
  })
  const examples = keys.map(key => "  pi-subagent-bridge " + entries[key].example).join("\n")
  const heading = selected ? "Options:\n  -h, --help  Show this help.\n\n" : "usage: pi-subagent-bridge COMMAND [ARGS...]\n\nDelegate and coordinate scoped worker sessions.\n\nOptions:\n  -h, --help  Show this reference.\n\n"
  process.stdout.write(heading + blocks.join("\n\n") + "\n\nExamples:\n" + examples + "\n\n" +
    (selected ? "See pi-subagent-bridge -h for the complete reference.\n" : FOOTER + "\n"))
}

async function inspectionDeps(): Promise<InspectionDeps> {
  const [{ optionalPiAdapter }, { commandResult }, { codexResult }] = await Promise.all([
    import("./optional-pi.ts"), import("./command.ts"), import("./codex.ts"),
  ])
  return { api: optionalPiAdapter(), command: { status: commandResult }, codex: { status: codexResult } }
}

async function inspect(rest: string[]): Promise<void> {
  const [path, id] = rest
  if (!path || !id || rest.length !== 2) throw new Error(INSPECT_USAGE)
  const [{ readStateDir }, { inspectStored, sessionPath }, { isSessionId }] =
    await Promise.all([import("./git.ts"), import("./inspect.ts"), import("./session.ts")])
  if (!isSessionId(id)) throw new Error("Invalid worker ID")
  const directory = readStateDir(resolve(path))
  if (!existsSync(sessionPath(directory, id))) throw new Error("no session record at " + sessionPath(directory, id))
  process.stdout.write(JSON.stringify(await inspectStored(directory, id, await inspectionDeps(), { settleLease: true })) + "\n")
}

async function watch(rest: string[]): Promise<void> {
  const stateOnly = rest[0] === "--state"
  const [root, id, idle, ...extra] = stateOnly ? rest.slice(1) : rest
  if (!root || !id || extra.length || (stateOnly && idle !== undefined) || (idle !== undefined && !/^\d+$/.test(idle))) {
    process.stderr.write(WATCH_USAGE + "\n")
    process.exitCode = 2
    return
  }
  const { watchSession } = await import("./watch.ts")
  process.exitCode = await watchSession(resolve(root), id, { idleMinutes: Number(idle ?? 45), stateOnly },
    await inspectionDeps(), (text) => process.stdout.write(text))
}

async function runCampaign(rest: string[]): Promise<void> {
  const { campaign } = await import("./campaign.ts")
  process.exitCode = await campaign(rest, {
    deps: await inspectionDeps(), env: process.env, cwd: process.cwd(),
    stdout: (text) => process.stdout.write(text), stderr: (text) => process.stderr.write(text),
  })
}

async function main(args: string[]): Promise<void> {
  const [op, ...rest] = args
  if (!op) {
    process.stderr.write("usage: pi-subagent-bridge COMMAND [ARGS...]\n")
    process.exitCode = 2
    return
  }
  if (op === "--bridge-schemas") {
    const { COMMAND_NAMES, COMMANDS, toolSchema } = await import("./commands.ts")
    process.stdout.write(JSON.stringify(COMMAND_NAMES.map(name => ({ name: COMMANDS[name].tool, inputSchema: toolSchema(name) }))) + "\n")
    return
  }
  if (op === "--bridge-dispatch") {
    const { COMMAND_NAMES, COMMANDS, decodeCommand } = await import("./commands.ts")
    const request = JSON.parse(rest[0])
    const name = COMMAND_NAMES.find(candidate => COMMANDS[candidate].tool === request.name)
    if (!name) throw new Error("Unknown tool")
    const { connect, dispatch } = await import("./server.ts")
    process.stdout.write(JSON.stringify(await dispatch(await connect(), decodeCommand(name, request.arguments))) + "\n")
    return
  }
  if (args.length === 1 && (op === "--help" || op === "-h")) return printHelp()
  if (op && rest.length && (rest.at(-1) === "-h" || rest.at(-1) === "--help")) {
    const selected = [op, ...rest.slice(0, -1)].join(" ")
    if (selected in help || selected === "campaign" || selected === "owner" || Object.hasOwn(commandExamples, selected)) {
      return printHelp(selected)
    }
  }
  if (op === "policy") {
    if (rest.length) throw new Error("usage: pi-subagent-bridge policy")
    process.stdout.write(JSON.stringify(POLICY) + "\n")
    return
  }
  if (op === "mcp") {
    const ownerRepos: string[] = []
    for (let i = 0; i < rest.length; i++) {
      if (op === "mcp" && rest[i] === "--repo" && rest[i + 1]) {
        ownerRepos.push(rest[++i])
      } else {
        throw new Error("usage: pi-subagent-bridge mcp [--repo <dir>]")
      }
    }
    const { serve, connect } = await import("./server.ts")
    serve(connect, ownerRepos.length ? { ownerRepos } : undefined)
    return
  }
  if (op === "scope-check") {
    if (rest[0] === "--lane" && rest.length === 2) {
      const { checkNative } = await import("./scope-check.ts")
      const result = checkNative(process.cwd(), rest[1])
      process.stdout.write(JSON.stringify(result) + "\n")
      if (!result.in_scope) process.exitCode = 1
      return
    }
    const registerAt = rest.indexOf("--register")
    if (registerAt >= 0) {
      const title = rest[registerAt + 1]
      if (!title || registerAt + 2 !== rest.length) throw new Error("usage: pi-subagent-bridge scope-check CWD SCOPE_JSON_FILE [BRANCH] --register TITLE")
      const [cwd, file, branch, ...extra] = rest.slice(0, registerAt)
      if (!cwd || !file || extra.length) throw new Error("usage: pi-subagent-bridge scope-check CWD SCOPE_JSON_FILE [BRANCH] --register TITLE")
      const { registerNative } = await import("./scope-check.ts")
      process.stdout.write(registerNative(cwd, JSON.parse(readFileSync(resolve(file), "utf8")), title, branch).id + "\n")
      return
    }
    const [cwd, file, branch, ...extra] = rest
    const { SCOPE_CHECK_USAGE, scopeCheck } = await import("./scope-check.ts")
    if (!cwd || !file || extra.length) throw new Error(SCOPE_CHECK_USAGE)
    const result = scopeCheck(resolve(cwd), JSON.parse(readFileSync(resolve(file), "utf8")), branch)
    process.stdout.write(JSON.stringify(result) + "\n")
    if (!result.in_scope) process.exitCode = 1
    return
  }
  if (op === "inspect") return inspect(rest)
  if (op === "watch") return watch(rest)
  if (op === "campaign") return runCampaign(rest)
  if (op === "owner") return (await import("./owner-client.ts")).runOwnerCli(rest)
  const { COMMAND_NAMES, COMMANDS, cliArguments, decodeCommand } = await import("./commands.ts")
  const name = COMMAND_NAMES.find(candidate => COMMANDS[candidate].cli === op)
  if (!name) throw new Error("usage: pi-subagent-bridge {policy|mcp|model-check|start|status|resume|cancel|steer|scope-check|inspect|watch|campaign|owner}")
  const command = decodeCommand(name, cliArguments(name, rest, path => readFileSync(path, "utf8")))
  const { connect, dispatch } = await import("./server.ts")
  const result = await dispatch(await connect(), command)
  process.stdout.write(JSON.stringify(result) + "\n")
}

void main(process.argv.slice(2)).catch((error) => {
  process.stderr.write("pi-subagent-bridge: " + String(error) + "\n")
  process.exitCode = 1
})
