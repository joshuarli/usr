import { startCommand } from "./harness-fixtures.ts"
import test from "node:test"
import assert from "node:assert/strict"
import { mkdtempSync, mkdirSync, writeFileSync, readFileSync, rmSync, realpathSync } from "node:fs"
import { spawn } from "node:child_process"
import { tmpdir } from "node:os"
import { join } from "node:path"
import { COMMAND_EMBER_MODEL, COMMAND_MODEL, cancelCommand, commandResult, commandSession, processStartTime } from "../src/command.ts"
import { codexResult } from "../src/codex.ts"
import type { LaunchRequest } from "../src/launch.ts"

const delay = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms))
function request(root: string, logs: string, overrides: Partial<LaunchRequest> = {}): LaunchRequest {
  return { directory: root, logDirectory: logs, prompt: "test", selection: { model: COMMAND_MODEL, effort: "high" }, access: { kind: "write" }, ...overrides }
}
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
    const first = startCommand(request(root, logs, { prompt: "change README" }))
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
    const second = startCommand(request(root, logs, { prompt: "cite lines", selection: { model: COMMAND_EMBER_MODEL, effort: "xhigh" },
      access: { kind: "read-only" }, resume: output.result?.sessionId }))
    let next = commandResult(second)
    for (let i = 0; i < 100 && !next.result; i++) { await delay(10); next = commandResult(second) }
    assert.equal(next.state, "succeeded")
    assert.match(readFileSync(argsFile, "utf8"), /--plan/)
    assert.ok(readFileSync(argsFile, "utf8").includes("--model\nmeta/muse-ember\n"))
    assert.ok(readFileSync(argsFile, "utf8").includes("--effort\nxhigh\n"))
    assert.match(readFileSync(argsFile, "utf8"), /--resume\ncmd-session/)
    assert.equal(commandSession(first), "cmd-session")
    assert.equal(commandSession(second), "cmd-session")
    const admittedPin = { model: "fixture/historical-command", effort: "low" } as const
    const retained = startCommand(request(root, logs, { prompt: "retain pin", selection: admittedPin, access: { kind: "read-only" }, resume: "cmd-session" }))
    let retainedResult = commandResult(retained)
    for (let i = 0; i < 100 && !retainedResult.result; i++) { await delay(10); retainedResult = commandResult(retained) }
    assert.equal(retainedResult.state, "succeeded")
    assert.match(readFileSync(argsFile, "utf8"), /--model\nfixture\/historical-command\n--effort\nlow/)
  } finally {
    process.env.PATH = oldPath
    rmSync(root, { recursive: true, force: true })
  }
})

test("a planned Command Code launch writes its identity before executor output", async () => {
  const root = realpathSync(mkdtempSync(join(tmpdir(), "cmd-planned-")))
  const bin = join(root, "bin"), logs = join(root, "logs"), previous = process.env.PATH
  mkdirSync(bin); mkdirSync(logs)
  try {
    writeFileSync(join(bin, "cmd"), '#!/bin/sh\nprintf \'{"type":"event"}\\n\'\n', { mode: 0o755 })
    process.env.PATH = bin + ":" + previous
    const planned = { output: join(logs, "planned.ndjson"), errors: join(logs, "planned.stderr"), started_at: "2026-01-01T00:00:00Z" }
    const run = startCommand(request(root, logs, { planned_run: planned }))
    for (let i = 0; i < 100; i++) {
      try { if (readFileSync(planned.output, "utf8")) break } catch {}
      await delay(10)
    }
    assert.equal(Number(readFileSync(planned.output + ".pid", "utf8")), run.pid)
    assert.match(readFileSync(planned.output, "utf8"), /"type":"event"/)
    assert.equal(run.started_at, planned.started_at)
  } finally { process.env.PATH = previous; rmSync(root, { recursive: true, force: true }) }
})

test("Command Code refuses a forbidden family", () => {
  for (const model of ["gemini-4-argon-high", "google/gemini-4-carbon-high", "openai/gpt-6.2-astra-xhigh"]) {
    assert.throws(() => startCommand(request("/absent", "/absent", { selection: { model, effort: "high" } })), /Prohibited Command Code model/)
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
    try { run = startCommand(request(root, logs, { selection: { model: COMMAND_MODEL, effort: "low" }, access: { kind: "read-only" } })) }
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

test("cancellation terminates the entire Command Code process group", async () => {
  const root = realpathSync(mkdtempSync(join(tmpdir(), "cmd-cancel-")))
  const bin = join(root, "bin"), logs = join(root, "logs")
  mkdirSync(bin); mkdirSync(logs)
  const oldPath = process.env.PATH
  let pid = 0
  try {
    writeFileSync(join(bin, "cmd"), "#!/bin/sh\nsleep 30 &\nsleep 30\n", { mode: 0o755 })
    process.env.PATH = bin + ":" + oldPath
    const run = startCommand(request(root, logs)); pid = run.pid
    await delay(100)
    assert.equal(cancelCommand(run), true)
    let alive = true
    for (let i = 0; i < 150 && alive; i++) {
      await delay(20)
      try { process.kill(-pid, 0) } catch (error) { if ((error as NodeJS.ErrnoException).code === "ESRCH") alive = false; else throw error }
    }
    assert.equal(alive, false, "process group remains alive after cancellation")
    assert.notEqual(commandResult(run).state, "running")
  } finally {
    if (pid) { try { process.kill(-pid, "SIGKILL") } catch {} }
    process.env.PATH = oldPath
    rmSync(root, { recursive: true, force: true })
  }
})

test("cancel signals a verified worker that this process never spawned (USR-79)", async () => {
  const root = realpathSync(mkdtempSync(join(tmpdir(), "cmd-cli-cancel-")))
  const bin = join(root, "bin")
  mkdirSync(bin)
  const oldPath = process.env.PATH
  let pid = 0
  try {
    writeFileSync(join(bin, "cmd"), "#!/bin/sh\nsleep 30 &\nsleep 30\n", { mode: 0o755 })
    process.env.PATH = bin + ":" + oldPath
    // A CLI-started worker: spawned outside this bridge's child registry, like `pi-subagent-bridge start`.
    const child = spawn("cmd", ["-p", "do work", "--model", "deepseek/deepseek-v4.1-flash"], { cwd: root, detached: true, stdio: "ignore" })
    pid = child.pid!
    await delay(150)
    const run = { pid, output: join(root, "out"), errors: join(root, "err"),
      started_at: new Date().toISOString(), proc_start: processStartTime(pid) }
    assert.equal(cancelCommand(run, root), true)
    let alive = true
    for (let i = 0; i < 150 && alive; i++) {
      await delay(20)
      try { process.kill(-pid, 0) } catch (error) {
        if ((error as NodeJS.ErrnoException).code === "ESRCH") alive = false; else throw error
      }
    }
    assert.equal(alive, false, "CLI-started process group survives cancellation")
  } finally {
    if (pid) { try { process.kill(-pid, "SIGKILL") } catch {} }
    process.env.PATH = oldPath
    rmSync(root, { recursive: true, force: true })
  }
})

test("cancel refuses an unverified PID without touching its group (USR-79)", async () => {
  const root = realpathSync(mkdtempSync(join(tmpdir(), "cmd-cli-refuse-")))
  const bin = join(root, "bin")
  mkdirSync(bin)
  const oldPath = process.env.PATH
  let pid = 0
  try {
    writeFileSync(join(bin, "cmd"), "#!/bin/sh\nsleep 30 &\nsleep 30\n", { mode: 0o755 })
    process.env.PATH = bin + ":" + oldPath
    const child = spawn("cmd", ["-p", "do work"], { cwd: root, detached: true, stdio: "ignore" })
    pid = child.pid!
    await delay(150)
    const run = { pid, output: join(root, "out"), errors: join(root, "err"), started_at: "now", proc_start: "0" }
    assert.equal(cancelCommand(run, root), false)
    process.kill(-pid, 0)
  } finally {
    if (pid) { try { process.kill(-pid, "SIGKILL") } catch {} }
    process.env.PATH = oldPath
    rmSync(root, { recursive: true, force: true })
  }
})

test("all observers reject a different identity even when its detached group is alive", async () => {
  const root = realpathSync(mkdtempSync(join(tmpdir(), "cmd-reused-group-")))
  const child = spawn("sh", ["-c", "sleep 30 & wait"], { detached: true, stdio: "ignore" })
  try {
    await delay(100)
    const run = { pid: child.pid!, output: join(root, "out"), errors: join(root, "err"), started_at: "now", proc_start: "0" }
    assert.ok(processStartTime(run.pid))
    assert.deepEqual([commandResult(run).state, codexResult(run).state],
      ["interrupted", "interrupted"])
  } finally {
    try { process.kill(-child.pid!, "SIGKILL") } catch {}
    await new Promise<void>(resolve => child.exitCode !== null || child.signalCode !== null ? resolve() : child.once("exit", () => resolve()))
    rmSync(root, { recursive: true, force: true })
  }
})
