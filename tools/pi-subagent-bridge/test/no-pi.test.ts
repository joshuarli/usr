import test from "node:test"
import assert from "node:assert/strict"
import { cpSync, mkdtempSync, mkdirSync, writeFileSync, rmSync, realpathSync, readFileSync, symlinkSync, readdirSync, renameSync } from "node:fs"
import { execFileSync, spawn } from "node:child_process"
import { tmpdir } from "node:os"
import { join } from "node:path"

test("public Codex lifecycle works with a physically Pi-free bridge", async () => {
  const root = realpathSync(mkdtempSync(join(tmpdir(), "no-pi-")))
  const git = (...args: string[]) => execFileSync("git", ["-C", root, ...args], { encoding: "utf8" }).trim()
  try {
    const source = join(root, "tools", "pi-subagent-bridge", "src"), bin = join(root, "bin"), home = join(root, "home")
    cpSync(new URL("../src", import.meta.url), source, { recursive: true })
    mkdirSync(bin); mkdirSync(home)
    symlinkSync(process.execPath, join(bin, "node"))
    cpSync(new URL("../../sync", import.meta.url), join(root, "tools/sync"), { recursive: true })
    cpSync(new URL("../package.json", import.meta.url), join(root, "tools/pi-subagent-bridge/package.json"))
    writeFileSync(join(home, ".claude.json"), JSON.stringify({ mcpServers: { foreign: { command: "preserve" } } }))
    const installerEnv = { PATH: bin + ":/usr/bin:/bin", HOME: home, TMPDIR: root }
    for (const action of ["install", "install", "check"]) {
      execFileSync("python3", ["-I", join(root, "tools/sync/claude-worker.py"), action, "--core"], { env: installerEnv })
    }
    assert.equal(JSON.parse(readFileSync(join(home, ".claude.json"), "utf8")).mcpServers.foreign.command, "preserve")
    const hook = join(root, "trap.mjs")
    writeFileSync(hook, `
import { registerHooks, syncBuiltinESMExports } from 'node:module';
import fs from 'node:fs';
import cp from 'node:child_process';
registerHooks({ resolve(specifier, context, next) {
  if (/pi-port|pi-coding-agent|pi-subagents|pi-muse|yaml/.test(specifier)) throw new Error('TRAPPED Pi access: '+specifier);
  return next(specifier, context);
} });
for (const name of ['readFileSync', 'openSync', 'readdirSync']) {
  const original = fs[name];
  fs[name] = (path, ...args) => {
    if (typeof path !== 'number' && /[\\/]\\.pi[\\/]|credentials|auth\\.json/.test(String(path))) throw new Error('TRAPPED credential access: '+path);
    return original(path, ...args);
  };
}
for (const name of ['spawn', 'spawnSync', 'execFile', 'execFileSync']) {
  const original = cp[name];
  cp[name] = (command, ...args) => {
    if (/(^|\\/)(pi|npm|npx)$/.test(String(command))) throw new Error('TRAPPED runtime spawn: '+command);
    return original(command, ...args);
  };
}
syncBuiltinESMExports();
`)

    writeFileSync(join(bin, "codex"), `#!/bin/sh
if [ "$1" = login ]; then echo 'Logged in using ChatGPT'; exit 0; fi
printf '%s\\n' "$@" >> '${root}/args'
printf '%s\\n' '{"type":"thread.started","thread_id":"fixture-thread"}'
if [ -e '${root}/hold' ]; then sleep 30; fi
printf '%s\\n' '{"type":"item.completed","item":{"type":"agent_message","text":"fixture proof\\nACCEPTANCE: met"}}' '{"type":"turn.completed"}'
`, { mode: 0o755 })
    git("init", "-q"); git("config", "user.name", "Fixture"); git("config", "user.email", "fixture@example.com")
    writeFileSync(join(root, "README"), "fixture\n"); git("add", "README"); git("commit", "-qm", "fixture")
    writeFileSync(join(root, ".git/info/exclude"), "/.work/\n/tools/\n/bin/\n/home/\n/trap.mjs\n/args\n/scope.json\n/brief\n")
    const cwd = join(root, ".work/wt/lane")
    mkdirSync(join(root, ".work/wt"), { recursive: true }); git("worktree", "add", "-qb", "lane", cwd)
    const scope = join(root, "scope.json"), brief = join(root, "brief")
    writeFileSync(scope, JSON.stringify({ base_revision: git("rev-parse", "HEAD"), writable_paths: ["README"], acceptance_proof: "fixture proof", attempt_limit: 2, stop_on: "scope expansion" }))
    writeFileSync(brief, "Perform fixture task")
    const cli = (...args: string[]) => JSON.parse(execFileSync(process.execPath, ["--import", hook, join(source, "cli.ts"), ...args], {
      encoding: "utf8", timeout: 15000, env: { PATH: bin + ":/usr/bin:/bin", HOME: home, TMPDIR: root },
    }))
    assert.ok(cli("policy").tiers)
    const started = cli("start", cwd, "fixture", "worker", scope, brief)
    assert.equal(started.backend, "codex")
    const wait = async (id = started.session_id) => {
      for (let i = 0; i < 60; i++) {
        const status = cli("status", cwd, id)
        if (status.state !== "running") return status
        await new Promise(resolve => setTimeout(resolve, 50))
      }
      throw new Error("fixture worker did not terminate")
    }
    assert.equal((await wait()).state, "succeeded")
    assert.equal(cli("inspect", root, started.session_id).execution_state, "succeeded")
    cli("resume", cwd, started.session_id, brief)
    assert.equal((await wait()).state, "succeeded")
    assert.match(readFileSync(join(root, "args"), "utf8"), /resume\nfixture-thread/)
    assert.throws(() => cli("steer", cwd, started.session_id, brief), /finished|inactive|running/)
    cli("cancel", cwd, started.session_id)
    const child = spawn(process.execPath, ["--import", hook, join(source, "cli.ts"), "mcp", "--repo", root], {
      env: { PATH: bin + ":/usr/bin:/bin", HOME: home, TMPDIR: root }, stdio: ["pipe", "pipe", "pipe"],
    })
    let output = "", errors = ""
    child.stdout.on("data", chunk => { output += chunk })
    child.stderr.on("data", chunk => { errors += chunk })
    try {
      child.stdin.write(JSON.stringify({ jsonrpc: "2.0", id: 1, method: "tools/call", params: { name: "worker_model_check", arguments: { cwd, tier: "worker" } } }) + "\n")
      for (let i = 0; i < 100 && !output.includes("\n"); i++) await new Promise(resolve => setTimeout(resolve, 50))
      assert.ok(output.includes("\n"), errors)
      const response = JSON.parse(output.trim().split("\n")[0])
      assert.equal(response.result.isError, undefined)
      assert.doesNotMatch(output + errors, /TRAPPED/)
      writeFileSync(join(root, "hold"), "hold")
      child.stdin.write(JSON.stringify({ jsonrpc: "2.0", id: 2, method: "tools/call", params: { name: "worker_start", arguments: { cwd, title: "owned fixture", tier: "worker", scope: JSON.parse(readFileSync(scope, "utf8")), brief: "Perform fixture task" } } }) + "\n")
      for (let i = 0; i < 100 && output.trim().split("\n").length < 2; i++) await new Promise(resolve => setTimeout(resolve, 50))
      const admitted = JSON.parse(output.trim().split("\n")[1])
      assert.equal(admitted.result.isError, undefined)
      const job = JSON.parse(admitted.result.content[0].text)
      const ownerDir = join(root, ".work/worker-bridge/owner")
      const ownerFile = readdirSync(ownerDir).find(name => name.endsWith(".json") && name !== "generation.json")!
      const owner = JSON.parse(readFileSync(join(ownerDir, ownerFile), "utf8"))
      const ownerArgs = ["--repo", root, "--owner", owner.owner_id]
      assert.equal(cli("owner", "hello", ...ownerArgs).owner_protocol, 1)
      const jobs = cli("owner", "jobs", ...ownerArgs)
      assert.equal(jobs.length, 1)
      assert.equal(jobs[0].job_id, job.session_id)
      const target = ["--job", jobs[0].job_id, "--run", jobs[0].run_id, "--generation", String(jobs[0].owner_generation)]
      assert.equal(cli("owner", "status", ...ownerArgs, ...target).job_id, job.session_id)
      await new Promise(resolve => setTimeout(resolve, 100))
      rmSync(join(root, "hold"))
      const steerArgs = ["owner", "steer", ...ownerArgs, ...target, "--command", "fixture-steer", "--note", "same scope correction"]
      assert.equal(cli(...steerArgs).receipt, "accepted")
      const argsAfterSteer = readFileSync(join(root, "args"), "utf8")
      assert.equal(cli(...steerArgs).receipt, "accepted")
      assert.equal(readFileSync(join(root, "args"), "utf8"), argsAfterSteer)
      assert.equal((await wait(job.session_id)).state, "succeeded")

      mkdirSync(join(home, ".local/bin"), { recursive: true })
      renameSync(join(bin, "codex"), join(home, ".local/bin/codex"))
      const fallbackPath = cli("start", cwd, "home executable", "worker", scope, brief)
      assert.equal(fallbackPath.backend, "codex")
      assert.equal((await wait(fallbackPath.session_id)).state, "succeeded")

    } finally {
      child.stdin.end()
      await new Promise<void>((resolve, reject) => {
        const timer = setTimeout(() => { child.kill(); reject(new Error("MCP shutdown timeout")) }, 5000)
        child.once("close", () => { clearTimeout(timer); resolve() })
      })
    }
  } finally { rmSync(root, { recursive: true, force: true }) }
})
