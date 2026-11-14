#!/usr/bin/env -S node --experimental-strip-types
import { existsSync, readFileSync } from "node:fs"
import { POLICY } from "./policy.ts"
import { isTier } from "./tier-policy.ts"
import { parseScope, requiredText } from "./scope.ts"
import type { InspectionDeps } from "./inspect.ts"
import type { Bridge } from "./server.ts"

const WATCH_USAGE = "usage: pi-subagent-bridge watch [--state] ROOT SESSION_ID [IDLE_MINUTES]"
const INSPECT_USAGE = "usage: pi-subagent-bridge inspect PATH SESSION_ID"

async function inspectionDeps(): Promise<InspectionDeps> {
  const [{ piPort }, { commandResult }, { codexResult }, { antigravityResult }] = await Promise.all([
    import("./pi-port.ts"), import("./command.ts"), import("./codex.ts"), import("./antigravity.ts"),
  ])
  return { api: piPort(), command: { status: commandResult }, codex: { status: codexResult },
    antigravity: { status: antigravityResult } }
}

async function inspect(rest: string[]): Promise<void> {
  const [path, id] = rest
  if (!path || !id || rest.length !== 2) throw new Error(INSPECT_USAGE)
  const [{ readStateDir }, { inspectStored, sessionPath }, { isSessionId }] =
    await Promise.all([import("./git.ts"), import("./inspect.ts"), import("./session.ts")])
  if (!isSessionId(id)) throw new Error("Invalid worker ID")
  const directory = readStateDir(path)
  if (!existsSync(sessionPath(directory, id))) throw new Error("no session record at " + sessionPath(directory, id))
  process.stdout.write(JSON.stringify(await inspectStored(directory, id, await inspectionDeps())) + "\n")
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
  process.exitCode = await watchSession(root, id, { idleMinutes: Number(idle ?? 10), stateOnly },
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
  if (op === "policy") {
    if (rest.length) throw new Error("usage: pi-subagent-bridge policy")
    process.stdout.write(JSON.stringify(POLICY) + "\n")
    return
  }
  if (!op || op === "mcp") {
    if (rest.length) throw new Error("usage: pi-subagent-bridge mcp")
    const { serve } = await import("./server.ts")
    serve()
    return
  }
  if (op === "inspect") return inspect(rest)
  if (op === "watch") return watch(rest)
  if (op === "campaign") return runCampaign(rest)
  let action: (bridge: Bridge) => Promise<unknown>
  switch (op) {
    case "model-check": {
      const [cwd, tier] = rest
      if (!cwd || !tier || rest.length !== 2) throw new Error("usage: pi-subagent-bridge model-check CWD TIER")
      if (!isTier(tier)) throw new Error("Unknown Pi tier")
      action = bridge => bridge.modelCheck(cwd, tier)
      break
    }
    case "start": {
      const [cwd, title, tier, scopeFile, briefFile] = rest
      if (!cwd || !title || !tier || !scopeFile || !briefFile || rest.length !== 5)
        throw new Error("usage: pi-subagent-bridge start CWD TITLE TIER SCOPE_JSON_FILE BRIEF_FILE")
      if (!isTier(tier)) throw new Error("Unknown Pi tier")
      const scope = parseScope(JSON.parse(readFileSync(scopeFile, "utf8")), tier)
      const brief = requiredText(readFileSync(briefFile, "utf8"), "brief", 32000)
      requiredText(title, "title", 100)
      action = bridge => bridge.start(cwd, title, tier, scope, brief)
      break
    }
    case "status": {
      const [cwd, id] = rest
      if (!cwd || !id || rest.length !== 2) throw new Error("usage: pi-subagent-bridge status CWD SESSION_ID")
      action = bridge => bridge.status(cwd, id)
      break
    }
    case "resume": {
      const [cwd, id, feedbackFile] = rest
      if (!cwd || !id || !feedbackFile || rest.length !== 3)
        throw new Error("usage: pi-subagent-bridge resume CWD SESSION_ID FEEDBACK_FILE")
      const feedback = requiredText(readFileSync(feedbackFile, "utf8"), "feedback", 32000)
      action = bridge => bridge.resume(cwd, id, feedback)
      break
    }
    case "cancel": {
      const [cwd, id] = rest
      if (!cwd || !id || rest.length !== 2) throw new Error("usage: pi-subagent-bridge cancel CWD SESSION_ID")
      action = bridge => bridge.cancel(cwd, id)
      break
    }
    case "steer": {
      const [cwd, id, noteFile] = rest
      if (!cwd || !id || !noteFile || rest.length !== 3)
        throw new Error("usage: pi-subagent-bridge steer CWD SESSION_ID NOTE_FILE")
      const note = requiredText(readFileSync(noteFile, "utf8"), "note", 32000)
      action = bridge => bridge.steer(cwd, id, note)
      break
    }
    default:
      throw new Error("usage: pi-subagent-bridge {policy|mcp|model-check|start|status|resume|cancel|steer|inspect|watch|campaign}")
  }
  const { connect } = await import("./server.ts")
  const result = await action(await connect())
  process.stdout.write(JSON.stringify(result) + "\n")
}

void main(process.argv.slice(2)).catch((error) => {
  process.stderr.write("pi-subagent-bridge: " + String(error) + "\n")
  process.exitCode = 1
})
