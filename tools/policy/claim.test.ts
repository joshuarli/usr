import test from "node:test"
import assert from "node:assert/strict"
import { execFileSync, spawn, spawnSync } from "node:child_process"
import { mkdirSync, mkdtempSync, readFileSync, realpathSync, rmSync, writeFileSync } from "node:fs"
import { hostname, tmpdir } from "node:os"
import { dirname, join, resolve } from "node:path"
import { fileURLToPath } from "node:url"
import { renderOutputs } from "./generate.ts"
import { STALE_BOUND_MS, evaluate, gateGenerate, ownerIdentity, parseRecord, pidAlive, sessionPid, type ClaimRecord } from "./claim.ts"

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), "../..")
const SOURCES = [
  "tools/policy/generate.ts",
  "tools/policy/claim.ts",
  "tools/policy/package.json",
  "tools/pi-subagent-bridge/src/policy.ts",
  "tools/pi-subagent-bridge/src/tier-policy.ts",
  "tools/pi-subagent-bridge/package.json",
]

function gitEnv(tmp: string): NodeJS.ProcessEnv {
  return {
    PATH: process.env.PATH ?? "",
    HOME: tmp,
    GIT_CONFIG_NOSYSTEM: "1",
    GIT_AUTHOR_NAME: "t", GIT_AUTHOR_EMAIL: "t@t",
    GIT_COMMITTER_NAME: "t", GIT_COMMITTER_EMAIL: "t@t",
  }
}

function git(cwd: string, env: NodeJS.ProcessEnv, ...args: string[]): string {
  return execFileSync("git", ["-C", cwd, ...args], { encoding: "utf8", env, stdio: ["ignore", "pipe", "pipe"] }).trim()
}

/** Two scratch worktrees of one scratch repository sharing one Git common dir. */
function scratch() {
  mkdirSync(join(ROOT, ".work/tmp"), { recursive: true })
  const tmp = mkdtempSync(join(ROOT, ".work/tmp", "policy-claim-"))
  const env = gitEnv(tmp)
  const primary = join(tmp, "repo")
  execFileSync("git", ["init", "-q", "-b", "main", primary], { env, stdio: ["ignore", "pipe", "pipe"] })
  for (const output of renderOutputs(ROOT)) {
    mkdirSync(dirname(join(primary, output.path)), { recursive: true })
    writeFileSync(join(primary, output.path), output.content)
  }
  for (const source of SOURCES) {
    mkdirSync(dirname(join(primary, source)), { recursive: true })
    writeFileSync(join(primary, source), readFileSync(join(ROOT, source), "utf8"))
  }
  git(primary, env, "add", "-A")
  git(primary, env, "commit", "-q", "-m", "fixture")
  const secondary = join(tmp, "repo-b")
  git(primary, env, "worktree", "add", "-q", "-b", "lane-b", secondary)
  const stateDir = join(primary, ".work", "policy-claim")
  return {
    tmp, env, primary, secondary, stateDir,
    claimPath: join(stateDir, "claim.json"),
    close: () => rmSync(tmp, { recursive: true, force: true }),
  }
}

function node(env: NodeJS.ProcessEnv, cwd: string, args: string[], extraEnv: NodeJS.ProcessEnv = {}) {
  return spawnSync(process.execPath, [...args], {
    cwd, encoding: "utf8", env: { ...env, ...extraEnv }, timeout: 120_000,
  })
}

function generate(env: NodeJS.ProcessEnv, worktree: string, args: string[] = [], extraEnv: NodeJS.ProcessEnv = {}) {
  return node(env, worktree, [join(worktree, "tools/policy/generate.ts"), ...args], extraEnv)
}

function claim(env: NodeJS.ProcessEnv, worktree: string, action: string, extraEnv: NodeJS.ProcessEnv = {}) {
  return node(env, worktree, [join(worktree, "tools/policy/claim.ts"), action], extraEnv)
}

function deadPid(): number {
  const child = spawnSync("sh", ["-c", "true"])
  assert.ok(child.pid && child.pid > 0)
  assert.equal(pidAlive(child.pid!), false)
  return child.pid!
}

function record(overrides: Partial<ClaimRecord>): ClaimRecord {
  const now = Date.now()
  return {
    schema_version: 1, area: "policy", owner: "session:other", branch: "main",
    worktree: "/nonexistent", pid: deadPid(), host: hostname(),
    started: new Date(now).toISOString(), started_epoch_ms: now, ...overrides,
  }
}

test("a live claim in worktree A makes generation in worktree B fail, naming branch, owner, start time and the commands to see or break it", () => {
  const f = scratch()
  try {
    const owner = { USR_SESSION_ID: "session-alpha" }
    const claimed = claim(f.env, f.primary, "claim", owner)
    assert.equal(claimed.status, 0, claimed.stderr)
    const held = parseRecord(readFileSync(f.claimPath, "utf8"))
    assert.equal(held.branch, "main")
    assert.equal(held.owner, "session:session-alpha")

    const blocked = generate(f.env, f.secondary, [], { USR_SESSION_ID: "session-beta" })
    assert.equal(blocked.status, 1, `stdout: ${blocked.stdout}\nstderr: ${blocked.stderr}`)
    assert.match(blocked.stderr, /policy claim held by another live session/)
    assert.match(blocked.stderr, /owner:\s+session:session-alpha/)
    assert.match(blocked.stderr, /branch:\s+main/)
    assert.ok(blocked.stderr.includes(held.started), "stderr must name the claim start time")
    assert.match(blocked.stderr, /make policy-claims/)
    assert.match(blocked.stderr, /claim\.ts break/)
    assert.ok(!blocked.stdout.includes("policy.generated.json"), "no projection may be written")

    const own = generate(f.env, f.primary, [], owner)
    assert.equal(own.status, 0, `stdout: ${own.stdout}\nstderr: ${own.stderr}`)
  } finally { f.close() }
})

test("generation in the claiming worktree succeeds while the claim is held", () => {
  const f = scratch()
  try {
    assert.equal(claim(f.env, f.primary, "claim").status, 0)
    const run = generate(f.env, f.primary)
    assert.equal(run.status, 0, `stdout: ${run.stdout}\nstderr: ${run.stderr}`)
  } finally { f.close() }
})

test("a claim whose process is gone and whose age exceeds the stale bound is reported stale and taken over", () => {
  const f = scratch()
  try {
    const startedEpoch = Date.now() - STALE_BOUND_MS - 60 * 60 * 1000
    const stale = record({
      owner: "claude-code:abandoned", branch: "main", worktree: realpathSync(f.primary),
      started: new Date(startedEpoch).toISOString(), started_epoch_ms: startedEpoch,
    })
    mkdirSync(f.stateDir, { recursive: true })
    writeFileSync(f.claimPath, JSON.stringify(stale, null, 2) + "\n")

    const run = generate(f.env, f.secondary, [], { USR_SESSION_ID: "session-beta" })
    assert.equal(run.status, 0, `stdout: ${run.stdout}\nstderr: ${run.stderr}`)
    assert.match(run.stderr, /stale claim taken over/)
    assert.match(run.stderr, /never silently/)
    assert.match(run.stderr, /pid \d+ is gone/)
    assert.match(run.stderr, /exceeds the .* stale bound/)
    const taken = parseRecord(readFileSync(f.claimPath, "utf8"))
    assert.equal(taken.worktree, realpathSync(f.secondary))
    assert.equal(taken.owner, "session:session-beta")
    assert.equal(taken.branch, "lane-b")
  } finally { f.close() }
})

test("a dead process alone is not stale while the claim is younger than the bound", () => {
  const f = scratch()
  try {
    mkdirSync(f.stateDir, { recursive: true })
    writeFileSync(f.claimPath, JSON.stringify(record({ worktree: realpathSync(f.primary) }), null, 2) + "\n")
    const run = generate(f.env, f.secondary)
    assert.equal(run.status, 1, `stdout: ${run.stdout}\nstderr: ${run.stderr}`)
    assert.match(run.stderr, /within the .* stale bound/)
  } finally { f.close() }
})

test("a live process alone keeps the claim live even beyond the age bound", () => {
  const startedEpoch = Date.now() - STALE_BOUND_MS - 60 * 60 * 1000
  const verdict = evaluate(record({ pid: process.pid, started_epoch_ms: startedEpoch }))
  assert.equal(verdict.stale, false)
  assert.equal(verdict.alive, true)
  const dead = evaluate(record({ started_epoch_ms: startedEpoch }))
  assert.equal(dead.stale, true)
  const young = evaluate(record({}))
  assert.equal(young.stale, false)
})

test("releasing the claim lets the other worktree proceed", () => {
  const f = scratch()
  try {
    assert.equal(claim(f.env, f.primary, "claim").status, 0)
    assert.equal(generate(f.env, f.secondary).status, 1)
    const released = claim(f.env, f.primary, "release")
    assert.equal(released.status, 0, released.stderr)
    assert.match(released.stdout, /released/)
    const run = generate(f.env, f.secondary)
    assert.equal(run.status, 0, `stdout: ${run.stdout}\nstderr: ${run.stderr}`)
  } finally { f.close() }
})

test("release refuses another session's live claim but break removes it with a loud report", () => {
  const f = scratch()
  try {
    assert.equal(claim(f.env, f.primary, "claim", { USR_SESSION_ID: "session-alpha" }).status, 0)
    const refused = claim(f.env, f.secondary, "release")
    assert.equal(refused.status, 1)
    assert.match(refused.stderr, /another live session/)
    const broken = claim(f.env, f.secondary, "break")
    assert.equal(broken.status, 0, broken.stderr)
    assert.match(broken.stdout, /broken/)
    assert.match(broken.stdout, /session:session-alpha/)
    assert.equal(generate(f.env, f.secondary).status, 0)
  } finally { f.close() }
})

test("check mode stays read-only and is never blocked by a conflicting live claim", () => {
  const f = scratch()
  try {
    assert.equal(claim(f.env, f.primary, "claim").status, 0)
    const before = readFileSync(f.claimPath, "utf8")
    const checked = generate(f.env, f.secondary, ["--check"])
    assert.equal(checked.status, 0, `stdout: ${checked.stdout}\nstderr: ${checked.stderr}`)
    assert.ok(!checked.stderr.includes("claim"), "check mode must not even consult the claim")
    assert.equal(readFileSync(f.claimPath, "utf8"), before)
    const json = generate(f.env, f.secondary, ["--json"])
    assert.equal(json.status, 0)
    assert.ok(!json.stderr.includes("claim"))
    assert.equal(readFileSync(f.claimPath, "utf8"), before)
  } finally { f.close() }
})

test("a recent corrupt claim blocks with instructions and break clears it", () => {
  const f = scratch()
  try {
    mkdirSync(f.stateDir, { recursive: true })
    writeFileSync(f.claimPath, "{ not json")
    const blocked = generate(f.env, f.secondary)
    assert.equal(blocked.status, 1)
    assert.match(blocked.stderr, /corrupt/)
    assert.match(blocked.stderr, /break/)
    const broken = claim(f.env, f.secondary, "break")
    assert.equal(broken.status, 0, broken.stderr)
    assert.equal(generate(f.env, f.secondary).status, 0)
  } finally { f.close() }
})

test("status reports a live claim, a stale claim and the empty state without mutating anything", () => {
  const f = scratch()
  try {
    const empty = claim(f.env, f.primary, "status")
    assert.equal(empty.status, 0)
    assert.match(empty.stdout, /none/)
    assert.equal(claim(f.env, f.primary, "claim").status, 0)
    const before = readFileSync(f.claimPath, "utf8")
    const held = claim(f.env, f.secondary, "status")
    assert.equal(held.status, 0)
    assert.match(held.stdout, /held — live/)
    assert.match(held.stdout, /branch:\s+main/)
    assert.equal(readFileSync(f.claimPath, "utf8"), before)
    const staleEpoch = Date.now() - STALE_BOUND_MS - 60 * 60 * 1000
    writeFileSync(f.claimPath, JSON.stringify(record({
      worktree: realpathSync(f.primary),
      started: new Date(staleEpoch).toISOString(), started_epoch_ms: staleEpoch,
    }), null, 2) + "\n")
    const stale = claim(f.env, f.secondary, "status")
    assert.match(stale.stdout, /held — stale/)
    assert.match(stale.stdout, /pid \d+ is gone/)
  } finally { f.close() }
})

test("repeated claims by the same worktree are idempotent and keep the original start time", () => {
  const f = scratch()
  try {
    assert.equal(claim(f.env, f.primary, "claim").status, 0)
    const first = parseRecord(readFileSync(f.claimPath, "utf8"))
    const again = claim(f.env, f.primary, "claim")
    assert.equal(again.status, 0, again.stderr)
    assert.match(again.stdout, /already held/)
    assert.deepEqual(parseRecord(readFileSync(f.claimPath, "utf8")), first)
  } finally { f.close() }
})

test("truly parallel claimants in two worktrees are serialized: exactly one wins, never two holders", async () => {
  const f = scratch()
  try {
    const racing = [f.primary, f.secondary].map((worktree, index) => new Promise<{
      worktree: string; status: number | null; stdout: string; stderr: string
    }>((resolvePromise, reject) => {
      const child = spawn(process.execPath, [join(worktree, "tools/policy/claim.ts"), "claim"], {
        cwd: worktree, env: { ...f.env, USR_SESSION_ID: `parallel-${index}` },
      })
      let stdout = ""
      let stderr = ""
      child.stdout.on("data", chunk => { stdout += chunk })
      child.stderr.on("data", chunk => { stderr += chunk })
      child.on("error", reject)
      child.on("close", status => resolvePromise({ worktree, status, stdout, stderr }))
      child.unref()
    }))
    const results = await Promise.all(racing)
    const winners = results.filter(result => result.status === 0)
    const losers = results.filter(result => result.status === 1)
    assert.equal(winners.length, 1, results.map(result => `${result.worktree}: ${result.status}: ${result.stderr}`).join("\n"))
    assert.equal(losers.length, 1)
    assert.match(losers[0]!.stderr, /policy claim held by another live session/)
    assert.match(losers[0]!.stderr, new RegExp(`parallel-${results.indexOf(winners[0])}`))
    const held = parseRecord(readFileSync(f.claimPath, "utf8"))
    assert.equal(held.worktree, realpathSync(winners[0]!.worktree))
    assert.equal(generate(f.env, losers[0]!.worktree).status, 1)
    assert.equal(generate(f.env, winners[0]!.worktree).status, 0)
  } finally { f.close() }
})

test("the generator gate degrades with a warning outside a Git worktree instead of blocking", () => {
  // The scratch directory must be outside this checkout, or Git discovery finds the outer repository.
  const tmp = mkdtempSync(join(tmpdir(), "policy-claim-nogit-"))
  try {
    const gate = gateGenerate(tmp)
    assert.equal(gate.proceed, true)
    if (gate.proceed) assert.match(gate.notices.join("\n"), /policy claim check skipped/)
  } finally { rmSync(tmp, { recursive: true, force: true }) }
})

test("owner identity prefers agent session environment identifiers and falls back to user@host", () => {
  assert.equal(ownerIdentity({ USR_SESSION_ID: "abc 123" }), "session:abc 123")
  assert.equal(ownerIdentity({ CLAUDE_CODE_SESSION_ID: "xyz" }), "claude-code:xyz")
  assert.equal(ownerIdentity({ PI_SESSION_ID: "p" }), "pi:p")
  assert.match(ownerIdentity({}), /^.+@.+/)
})

test("session pid detection skips transient command shells and make", () => {
  const shell = (pid: number, ppid: number, args: string) => `  ${pid} ${ppid} ${args}\n`
  // A harness-spawned chain: node(500) <- sh -c(400) <- make(300) <- sh -c(200) <- harness(100).
  const harnessed =
    shell(1, 0, "/sbin/launchd") +
    shell(50, 1, "/usr/sbin/sshd") +
    shell(100, 50, "node /opt/pi/bin/pi.mjs") +
    shell(200, 100, "sh -c make policy-claim") +
    shell(300, 200, "make policy-claim") +
    shell(400, 300, "sh -c node tools/policy/claim.ts claim") +
    shell(500, 400, "node tools/policy/claim.ts claim")
  assert.equal(sessionPid(harnessed, 400), 100)
  // An interactive human chain: node(500) <- sh -c(400) <- make(300) <- zsh(100).
  const interactive =
    shell(1, 0, "/sbin/launchd") +
    shell(100, 1, "-zsh") +
    shell(300, 100, "make policy-claim") +
    shell(400, 300, "sh -c node tools/policy/claim.ts claim") +
    shell(500, 400, "node tools/policy/claim.ts claim")
  assert.equal(sessionPid(interactive, 400), 100)
  // Direct invocation from an interactive shell stops at the shell immediately.
  const direct = shell(1, 0, "/sbin/launchd") + shell(100, 1, "zsh") + shell(500, 100, "node tools/policy/claim.ts claim")
  assert.equal(sessionPid(direct, 100), 100)
  assert.equal(typeof sessionPid(), "number")
  assert.ok(sessionPid() > 0)
  assert.ok(pidAlive(process.pid))
})

test("claim record validation rejects malformed records", () => {
  const valid = record({})
  parseRecord(JSON.stringify(valid))
  for (const bad of [
    { ...valid, schema_version: 2 }, { ...valid, area: "other" }, { ...valid, owner: "" },
    { ...valid, pid: -1 }, { ...valid, pid: "x" }, { ...valid, started_epoch_ms: 0 },
    { ...valid, branch: 3 }, { ...valid, worktree: "" },
  ]) assert.throws(() => parseRecord(JSON.stringify(bad)), /claim/)
  assert.throws(() => parseRecord("{"), // corrupt JSON is reported by the caller
    /JSON|Expected/)
})
