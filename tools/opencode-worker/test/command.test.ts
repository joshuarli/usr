import test from "node:test"
import assert from "node:assert/strict"
import { mkdtempSync, mkdirSync, writeFileSync, readFileSync, rmSync } from "node:fs"
import { tmpdir } from "node:os"
import { join } from "node:path"
import { commandResult, startCommand } from "../src/command.ts"

const delay = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms))
test("Command Code headless pins DeepSeek 4.1 Flash and resumes the same session", async () => {
  const root = mkdtempSync(join(tmpdir(), "cmd-worker-"))
  const bin = join(root, "bin"), logs = join(root, "logs")
  mkdirSync(bin); mkdirSync(logs)
  const oldPath = process.env.PATH
  try {
    const argsFile = join(root, "args")
    writeFileSync(join(bin, "cmd"), '#!/bin/sh\nprintf "%s\\n" "$@" >> ' + JSON.stringify(argsFile) +
      '\nprintf \'{"type":"event","event":{"type":"tool_running"}}\\n\'\nprintf \'{"type":"result","subtype":"success","sessionId":"cmd-session","finalText":"proof","usage":{"input":3}}\\n\'\n',
      { mode: 0o755 })
    process.env.PATH = bin + ":" + oldPath
    const first = startCommand(root, logs, "change README", "high", false)
    let output = commandResult(first)
    for (let i = 0; i < 100 && !output.result; i++) { await delay(10); output = commandResult(first) }
    assert.equal(output.state, "succeeded")
    assert.equal(output.result?.sessionId, "cmd-session")
    const args = readFileSync(argsFile, "utf8")
    assert.match(args, /deepseek\/deepseek-v4\.1-flash/)
    assert.match(args, /--effort\nhigh/)
    assert.match(args, /--yolo/)
    const second = startCommand(root, logs, "cite lines", "low", true, output.result?.sessionId)
    let next = commandResult(second)
    for (let i = 0; i < 100 && !next.result; i++) { await delay(10); next = commandResult(second) }
    assert.equal(next.state, "succeeded")
    assert.match(readFileSync(argsFile, "utf8"), /--plan/)
    assert.match(readFileSync(argsFile, "utf8"), /--resume\ncmd-session/)
  } finally {
    process.env.PATH = oldPath
    rmSync(root, { recursive: true, force: true })
  }
})
