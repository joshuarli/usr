#!/usr/bin/env -S node --experimental-strip-types
import { readFileSync } from "node:fs"
import { POLICY } from "./policy.ts"
import { isTier } from "./tier-policy.ts"
import { parseScope, requiredText } from "./scope.ts"
import type { Bridge } from "./server.ts"

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
      throw new Error("usage: pi-subagent-bridge {policy|mcp|model-check|start|status|resume|cancel|steer}")
  }
  const { connect } = await import("./server.ts")
  const result = await action(await connect())
  process.stdout.write(JSON.stringify(result) + "\n")
}

void main(process.argv.slice(2)).catch((error) => {
  process.stderr.write("pi-subagent-bridge: " + String(error) + "\n")
  process.exitCode = 1
})
