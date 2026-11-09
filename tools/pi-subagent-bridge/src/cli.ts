#!/usr/bin/env -S node --experimental-strip-types
import { readFileSync } from "node:fs"
import { connect, serve } from "./server.ts"

async function main(args: string[]): Promise<void> {
  const [op, ...rest] = args
  if (!op || op === "mcp") { serve(); return }
  const bridge = await connect()
  let result: unknown
  switch (op) {
    case "model-check": {
      const [cwd, tier] = rest
      if (!cwd || !tier || rest.length !== 2) throw new Error("usage: pi-subagent-bridge model-check CWD TIER")
      result = await bridge.modelCheck(cwd, tier)
      break
    }
    case "start": {
      const [cwd, title, tier, scopeFile, briefFile] = rest
      if (!cwd || !title || !tier || !scopeFile || !briefFile || rest.length !== 5)
        throw new Error("usage: pi-subagent-bridge start CWD TITLE TIER SCOPE_JSON_FILE BRIEF_FILE")
      const scope: unknown = JSON.parse(readFileSync(scopeFile, "utf8"))
      const brief = readFileSync(briefFile, "utf8")
      result = await bridge.start(cwd, title, tier, scope, brief)
      break
    }
    case "status": {
      const [cwd, id] = rest
      if (!cwd || !id || rest.length !== 2) throw new Error("usage: pi-subagent-bridge status CWD SESSION_ID")
      result = await bridge.status(cwd, id)
      break
    }
    case "resume": {
      const [cwd, id, feedbackFile] = rest
      if (!cwd || !id || !feedbackFile || rest.length !== 3)
        throw new Error("usage: pi-subagent-bridge resume CWD SESSION_ID FEEDBACK_FILE")
      result = await bridge.resume(cwd, id, readFileSync(feedbackFile, "utf8"))
      break
    }
    case "cancel": {
      const [cwd, id] = rest
      if (!cwd || !id || rest.length !== 2) throw new Error("usage: pi-subagent-bridge cancel CWD SESSION_ID")
      result = await bridge.cancel(cwd, id)
      break
    }
    default:
      throw new Error("usage: pi-subagent-bridge {mcp|model-check|start|status|resume|cancel}")
  }
  process.stdout.write(JSON.stringify(result) + "\n")
}

void main(process.argv.slice(2)).catch((error) => {
  process.stderr.write("pi-subagent-bridge: " + String(error) + "\n")
  process.exitCode = 1
})
