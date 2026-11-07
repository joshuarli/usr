import test from "node:test"
import assert from "node:assert/strict"
import { mkdtempSync, mkdirSync, writeFileSync, readFileSync, rmSync, realpathSync } from "node:fs"
import { spawn } from "node:child_process"
import { tmpdir } from "node:os"
import { join } from "node:path"
import { commandResult, startCommand } from "../src/command.ts"

const delay = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms))
test("Command Code headless pins DeepSeek 4.1 Flash and resumes the same session", async () => {
  const root = realpathSync(mkdtempSync(join(tmpdir(), "cmd-worker-")))
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
    assert.match(args, /--max-turns\n160\n/)
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

test("a Command Code run stopped at its turn cap reports turn_limit, not a task failure", async () => {
  const root = realpathSync(mkdtempSync(join(tmpdir(), "cmd-turns-")))
  const output = join(root, "out.ndjson"), errors = join(root, "err.stderr")
  writeFileSync(output, '{"type":"result","subtype":"max_turns","sessionId":"cmd-session","finalText":"partial"}\n')
  writeFileSync(errors, "")
  try {
    const run = { pid: 2 ** 22 + 7, output, errors, started_at: new Date().toISOString() }
    const status = commandResult(run)
    assert.equal(status.state, "turn_limit")
    assert.equal(status.result?.sessionId, "cmd-session")
  } finally {
    rmSync(root, { recursive: true, force: true })
  }
})

test("spawn failure with an invalid cmd shebang is handled without crashing the MCP process", async () => {
  const root = realpathSync(mkdtempSync(join(tmpdir(), "cmd-broken-")))
  const bin = join(root, "bin"), logs = join(root, "logs")
  mkdirSync(bin); mkdirSync(logs)
  const prior = process.env.PATH
  try {
    writeFileSync(join(bin, "cmd"), "#!/nonexistent/interpreter/for-cmd\n", { mode: 0o755 })
    process.env.PATH = bin
    let run: ReturnType<typeof startCommand> | null = null
    try { run = startCommand(root, logs, "test", "low", true) }
    catch (error) { assert.match(String(error), /Cannot start Command Code/) }
    if (run) {
      let state = commandResult(run).state
      for (let i = 0; state === "running" && i < 250; i++) { await delay(20); state = commandResult(run).state }
      assert.notEqual(state, "running")
      assert.notEqual(state, "succeeded")
    } else {
      await delay(30)
    }
  } finally {
    process.env.PATH = prior
    rmSync(root, { recursive: true, force: true })
  }
})

test("a live Command Code process spawned by another bridge process reports running", async () => {
  const root = realpathSync(mkdtempSync(join(tmpdir(), "cmd-foreign-")))
  const output = join(root, "out.ndjson"), errors = join(root, "err.stderr")
  writeFileSync(output, ""); writeFileSync(errors, "")
  const child = spawn("sleep", ["30"], { stdio: "ignore" })
  try {
    const run = { pid: child.pid!, output, errors, started_at: new Date().toISOString() }
    assert.equal(commandResult(run).state, "running")
    child.kill("SIGKILL")
    await new Promise((resolve) => child.on("exit", resolve))
    assert.equal(commandResult(run).state, "unknown_or_interrupted")
  } finally {
    child.kill("SIGKILL")
    rmSync(root, { recursive: true, force: true })
  }
})
