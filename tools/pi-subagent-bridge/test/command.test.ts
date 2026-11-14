import test from "node:test"
import assert from "node:assert/strict"
import { mkdtempSync, mkdirSync, writeFileSync, readFileSync, rmSync, realpathSync } from "node:fs"
import { spawn } from "node:child_process"
import { tmpdir } from "node:os"
import { join } from "node:path"
import { COMMAND_EMBER_MODEL, commandResult, commandSession, processStartTime, startCommand } from "../src/command.ts"

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
    assert.match(args, /--verbose/)
    assert.match(args, /--max-turns\n100000\n/)
    const second = startCommand(root, logs, "cite lines", "xhigh", true, output.result?.sessionId, COMMAND_EMBER_MODEL)
    let next = commandResult(second)
    for (let i = 0; i < 100 && !next.result; i++) { await delay(10); next = commandResult(second) }
    assert.equal(next.state, "succeeded")
    assert.match(readFileSync(argsFile, "utf8"), /--plan/)
    assert.ok(readFileSync(argsFile, "utf8").includes("--model\nmeta/muse-ember\n"))
    assert.ok(readFileSync(argsFile, "utf8").includes("--effort\nxhigh\n"))
    assert.throws(() => startCommand(root, logs, "bad", "medium", true, undefined, "unapproved"), /Unapproved/)
    assert.match(readFileSync(argsFile, "utf8"), /--resume\ncmd-session/)
    assert.equal(commandSession(first), "cmd-session")
    assert.equal(commandSession(second), "cmd-session")
    const admittedPin = { model: "fixture/historical-command", effort: "low" } as const
    assert.throws(() => startCommand(root, logs, "resume", "low", true, "cmd-session", admittedPin.model), /Unapproved/)
    const retained = startCommand(root, logs, "retain pin", "low", true, "cmd-session", admittedPin.model, admittedPin)
    let retainedResult = commandResult(retained)
    for (let i = 0; i < 100 && !retainedResult.result; i++) { await delay(10); retainedResult = commandResult(retained) }
    assert.equal(retainedResult.state, "succeeded")
    assert.match(readFileSync(argsFile, "utf8"), /--model\nfixture\/historical-command\n--effort\nlow/)
  } finally {
    process.env.PATH = oldPath
    rmSync(root, { recursive: true, force: true })
  }
})

test("Command Code cannot change an admitted pair or restore a forbidden family", () => {
  const pin = { model: "fixture/historical-command", effort: "low" } as const
  assert.throws(() => startCommand("/absent", "/absent", "test", "high", false, "session", pin.model, pin), /preserve the admitted pin/)
  assert.throws(() => startCommand("/absent", "/absent", "test", "low", false, "session", COMMAND_EMBER_MODEL, pin), /preserve the admitted pin/)
  for (const model of ["gemini-4-argon-high", "google/gemini-4-carbon-high"]) {
    assert.throws(() => startCommand("/absent", "/absent", "test", "high", false, "session", model, { model, effort: "high" }), /Unapproved/)
  }
})

test("the verbose session line identifies a run before its result line exists", async () => {
  const root = realpathSync(mkdtempSync(join(tmpdir(), "cmd-session-")))
  const output = join(root, "out.ndjson"), errors = join(root, "err.stderr")
  writeFileSync(output, "")
  writeFileSync(errors, "session: early-session\nsome progress\n")
  try {
    const run = { pid: 2 ** 22 + 9, output, errors, started_at: new Date().toISOString(), proc_start: "1" }
    assert.equal(commandResult(run).state, "interrupted")
    assert.equal(commandSession(run), "early-session")
  } finally {
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

test("a recorded process start time keeps a live foreign run running and makes a reused PID interrupted", async () => {
  const root = realpathSync(mkdtempSync(join(tmpdir(), "cmd-foreign-")))
  const output = join(root, "out.ndjson"), errors = join(root, "err.stderr")
  writeFileSync(output, ""); writeFileSync(errors, "")
  const child = spawn("sleep", ["30"], { stdio: "ignore" })
  try {
    const recorded = processStartTime(child.pid!)
    assert.ok(recorded)
    const run = { pid: child.pid!, output, errors, started_at: new Date().toISOString(), proc_start: recorded }
    assert.equal(commandResult(run).state, "running")
    assert.equal(commandResult({ ...run, proc_start: "0" }).state, "interrupted")
    child.kill("SIGKILL")
    await new Promise((resolve) => child.on("exit", resolve))
    assert.equal(commandResult(run).state, "interrupted")
  } finally {
    child.kill("SIGKILL")
    rmSync(root, { recursive: true, force: true })
  }
})

test("a terminal receipt from a still-live Command Code process is not terminal until the process ends", async () => {
  const root = realpathSync(mkdtempSync(join(tmpdir(), "cmd-live-receipt-")))
  const output = join(root, "out.ndjson"), errors = join(root, "err.stderr")
  writeFileSync(output, '{"type":"result","subtype":"error","sessionId":"cmd-session","error":"quota"}\n')
  writeFileSync(errors, "")
  const child = spawn("sleep", ["30"], { stdio: "ignore" })
  try {
    const recorded = processStartTime(child.pid!)
    assert.ok(recorded)
    const run = { pid: child.pid!, output, errors, started_at: new Date().toISOString(), proc_start: recorded }
    assert.deepEqual(commandResult(run), { state: "running", result: null, stderr: null })
    child.kill("SIGKILL")
    await new Promise((resolve) => child.on("exit", resolve))
    assert.equal(commandResult(run).state, "failed")
    assert.equal(commandResult({ ...run, proc_start: "0" }).state, "failed")
  } finally {
    child.kill("SIGKILL")
    rmSync(root, { recursive: true, force: true })
  }
})
