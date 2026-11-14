import test, { after, before } from "node:test"
import assert from "node:assert/strict"
import { readFileSync, utimesSync, writeFileSync } from "node:fs"
import { join } from "node:path"
import { campaign } from "../src/campaign.ts"
import { piPort } from "../src/pi-port.ts"
import {
  Scratch, collect, commandLane, commandResultLine, piSession, piSuccess, realDeps, runFor,
  toolQueued, writeLog, writePiChild, writeSession, type Repo,
} from "./worker-fixtures.ts"

const working = (description: string) => toolQueued(description)
const succeeded = (text: string) => commandResultLine("success", { finalText: text })

const scratch = new Scratch()
let alive: number, gone: number, repoA: Repo, repoB: Repo
let alpha: string, beta: string, gamma: string, delta: string, epsilon: string, zeta: string
let env: NodeJS.ProcessEnv
before(async () => {
  alive = scratch.alive()
  gone = await scratch.gone()
  repoA = scratch.repo("repo-a")
  repoB = scratch.repo("repo-b")
  env = { XDG_STATE_HOME: join(scratch.path, "home", "state"), HOME: join(scratch.path, "home") }
  alpha = commandLane(repoA, 1, gone, [succeeded("first done")], { title: "Alpha lane" })
  beta = commandLane(repoA, 2, gone, [commandResultLine("error", { error: "compile failed", finalText: "compile failed" })], { title: "Beta lane" })
  gamma = commandLane(repoA, 3, gone, [commandResultLine("max_turns", { finalText: "ran out of turns" })], { title: "Gamma lane" })
  delta = commandLane(repoA, 4, gone, [working("Download kernel")], { title: "Delta lane" })
  epsilon = commandLane(repoA, 5, alive, [working("Still working")], { title: "Epsilon running" })
  zeta = commandLane(repoB, 6, gone, [succeeded("second repo done")], { title: "Zeta other repo" })
})
after(() => scratch.close())

type Options = { cwd?: string; env?: NodeJS.ProcessEnv; pollMs?: number; clock?: { now: () => number; sleep: (ms: number) => Promise<void> }; api?: ReturnType<typeof piPort> }
async function run(args: string[], options: Options = {}) {
  const out = collect(), err = collect()
  const status = await campaign(args, {
    deps: realDeps(options.api), env: options.env ?? env, cwd: options.cwd ?? scratch.path,
    stdout: out.write, stderr: err.write, pollMs: options.pollMs ?? (options.clock ? 3_600_000 : 10), ...(options.clock ? { clock: options.clock } : {}),
  })
  return { status, out: out.text(), err: err.text() }
}

test("wait discovers sessions under both roots", async () => {
  const { status, out } = await run(["wait", repoA.root, repoB.root])
  assert.equal(status, 0)
  assert.ok(out.includes(`${alpha} succeeded ${repoA.cwd} Alpha lane\n`), out)
  assert.ok(out.includes(`${beta} failed ${repoA.cwd} Beta lane\n`), "wait reports the failed lane: " + out)
  assert.ok(out.includes(`${gamma} turn_limit ${repoA.cwd} Gamma lane\n`), "wait reports the turn_limit lane: " + out)
  assert.ok(out.includes(`${delta} interrupted ${repoA.cwd} Delta lane\n`), "wait reports a gone Command Code process as interrupted: " + out)
  assert.ok(out.includes(`${zeta} succeeded ${repoB.cwd} Zeta other repo\n`), "wait discovers the other repo root: " + out)
  assert.ok(!out.includes(epsilon), "wait leaves a running session out: " + out)
})

test("a relative root resolves to the absolute worktree", async () => {
  const { status, out } = await run(["wait", "repo-a"])
  assert.equal(status, 0)
  assert.ok(out.includes(`${alpha} succeeded ${repoA.cwd} Alpha lane`), out)
})

test("a missing root is refused", async () => {
  const { status, err } = await run(["wait", "no-such-repo"])
  assert.equal(status, 1)
  assert.equal(err, "no such root: no-such-repo\n")
})

test("list shows state, age and worktree", async () => {
  const { status, out } = await run(["list", repoA.root])
  assert.equal(status, 0)
  assert.match(out, new RegExp(`^${alpha} succeeded \\d+s ${repoA.cwd}\\n`, "m"))
})

test("list includes the continuation and steer budgets", async () => {
  const budgeted = commandLane(repoA, 7, gone, [succeeded("budgeted done")], { title: "Budgeted lane", continuations: 1, steers: 2 })
  const { out } = await run(["list", repoA.root])
  assert.ok(out.includes(` ${repoA.cwd} continuations=1 steers=2\n`), out)
  assert.match(out, new RegExp(`^${budgeted} succeeded `, "m"))
})

test("list reports the age of the session record", async () => {
  const old = commandLane(repoA, 13, gone, [succeeded("old")], { title: "Old lane" })
  const path = join(repoA.directory, old + ".json")
  const hourAgo = new Date(Date.now() - 3 * 3600 * 1000 - 5 * 60 * 1000)
  utimesSync(path, hourAgo, hourAgo)
  const { out } = await run(["list", repoA.root])
  assert.match(out, new RegExp(`^${old} succeeded 3h5m ${repoA.cwd}\\n`, "m"))
})

test("ack accepts ids", async () => {
  const { status, out, err } = await run(["ack", alpha, beta])
  assert.equal(status, 0)
  assert.equal(out + err, "")
})

test("ack is idempotent", async () => {
  const { status } = await run(["ack", alpha, beta])
  assert.equal(status, 0)
})

test("ack persisted one id per line under XDG_STATE_HOME", () => {
  const file = join(env.XDG_STATE_HOME!, "worker-campaign", "acked")
  assert.equal(readFileSync(file, "utf8"), [alpha, beta].sort().join("\n") + "\n")
})

test("ack needs at least one id", async () => {
  const { status, err } = await run(["ack"])
  assert.equal(status, 1)
  assert.match(err, /^usage: pi-subagent-bridge campaign wait/)
})

test("an acknowledged session is never reported again", async () => {
  const { status, out } = await run(["wait", repoA.root])
  assert.equal(status, 0)
  assert.ok(out.includes(`${gamma} turn_limit`), out)
  assert.ok(!out.includes(`${beta} failed`), "an acknowledged failed session stays silent: " + out)
  assert.ok(!out.includes(`${alpha} `), out)
})

test("a timeout exits 2 with a tick", async () => {
  const lonely = scratch.repo("repo-timeout")
  commandLane(lonely, 9, alive, [working("Waiting")], { title: "Still running" })
  let now = 1_000_000
  const clock = { now: () => now, sleep: async (ms: number) => { now += ms } }
  const { status, out } = await run(["wait", "--timeout", "1s", lonely.root], { clock })
  assert.equal(status, 2)
  assert.equal(out, "tick: 1 running\n", "the timeout prints a single tick line")
})

test("a timeout accepts minutes, hours and the equals form", async () => {
  const lonely = scratch.repo("repo-duration")
  let now = 0
  const clock = { now: () => now, sleep: async (ms: number) => { now += ms } }
  for (const duration of ["30m", "2h", "45"]) {
    const { status } = await run(["wait", `--timeout=${duration}`, lonely.root], { clock })
    assert.equal(status, 2)
  }
  const bad = await run(["wait", "--timeout", "soon", lonely.root], { clock })
  assert.equal(bad.status, 1)
  assert.equal(bad.err, "invalid duration: soon\n")
})

test("a Pi SDK terminal result is reported", async () => {
  const pi = scratch.repo("repo-pi")
  writePiChild(pi, gone, piSuccess("SDK proof\nACCEPTANCE: met"))
  const id = piSession(pi, 10, { title: "Pi lane" })
  const { status, out } = await run(["wait", pi.root], { api: piPort() })
  assert.equal(status, 0, out)
  assert.equal(out, `${id} succeeded ${pi.cwd} Pi lane\n`)
})

test("an Antigravity terminal result is reported", async () => {
  const agy = scratch.repo("agy")
  const output = runFor(agy, "agy", gone)
  writeLog(output.output, [{ event: "init", init: { model: "fixture-model" } }, { event: "result", result: { status: "SUCCESS", response: "Expert proof" } }])
  const id = writeSession(agy, 12, { title: "Expert lane", tier: "expert", backend: "antigravity", command_model: undefined,
    command_effort: undefined, antigravity_pin: { model: "fixture-model", effort: "xhigh" }, command_run: output })
  const { status, out } = await run(["wait", "--timeout", "1s", agy.root])
  assert.equal(status, 0)
  assert.equal(out, `${id} succeeded ${agy.cwd} Expert lane\n`)
})

test("wait keeps blocking while the session runs", async () => {
  const live = scratch.repo("repo-live")
  const worker = scratch.alive()
  const id = commandLane(live, 11, worker, [working("Working")], { title: "Live lane" })
  let settled = false
  const waiter = run(["wait", live.root], { pollMs: 20 }).then((result) => { settled = true; return result })
  await new Promise((resolve) => setTimeout(resolve, 200))
  assert.equal(settled, false)
  await scratch.stop(worker)
  const result = await waiter
  assert.equal(result.status, 0, "the unblocked wait exited 0")
  assert.equal(result.out, `${id} interrupted ${live.cwd} Live lane\n`)
})

test("wait returns once the session terminates", async () => {
  const live = scratch.repo("repo-finish")
  const id = commandLane(live, 14, alive, [working("Working")], { title: "Finishing lane" })
  let settled = false
  const waiter = run(["wait", live.root], { pollMs: 20 }).then((result) => { settled = true; return result })
  await new Promise((resolve) => setTimeout(resolve, 100))
  assert.equal(settled, false)
  writeLog(join(live.directory, "lane-14.ndjson"), [succeeded("finished")])
  writeSession(live, 14, { title: "Finishing lane", command_run: runFor(live, "lane-14", gone) })
  const result = await waiter
  assert.equal(result.status, 0)
  assert.equal(result.out, `${id} succeeded ${live.cwd} Finishing lane\n`)
})

test("WORKER_CAMPAIGN_ROOTS supplies the roots", async () => {
  const roots = { ...env, WORKER_CAMPAIGN_ROOTS: `${repoB.root}:${repoA.root}` }
  const { status, out } = await run(["wait"], { env: roots })
  assert.equal(status, 0)
  assert.ok(out.startsWith(`${zeta} succeeded ${repoB.cwd}`), out)
})

test("no root and no WORKER_CAMPAIGN_ROOTS is refused", async () => {
  const { status, err } = await run(["list"])
  assert.equal(status, 1)
  assert.equal(err, "no ROOT given and WORKER_CAMPAIGN_ROOTS is empty\n")
})

test("an empty campaign still honours the timeout", async () => {
  const empty = scratch.repo("repo-empty")
  let now = 0
  const clock = { now: () => now, sleep: async (ms: number) => { now += ms } }
  const { status, out } = await run(["wait", "--timeout", "1s", empty.root], { clock })
  assert.equal(status, 2)
  assert.equal(out, "tick: 0 running\n")
})

test("an unknown subcommand prints usage", async () => {
  const { status, err } = await run(["frobnicate"])
  assert.equal(status, 1)
  assert.match(err, /^usage: pi-subagent-bridge campaign wait/)
})

test("list --json is a snapshot array in which missing evidence is the string unknown", async () => {
  const snapshotRepo = scratch.repo("repo-snapshot")
  const finished = commandLane(snapshotRepo, 20, gone, [succeeded("proof\nACCEPTANCE: met")], { title: "Snapshot lane", steers: 1 })
  const future = writeSession(snapshotRepo, 21, { schema_version: 2, title: "Future lane" })
  const bare = scratch.repo("repo-snapshot-missing")
  const { status, out } = await run(["list", "--json", snapshotRepo.root, bare.root])
  assert.equal(status, 0)
  const snapshots = JSON.parse(out) as Array<Record<string, unknown>>
  assert.deepEqual(snapshots.map((entry) => entry.id), [finished, future])
  const [known, unreadable] = snapshots as [Record<string, unknown>, Record<string, unknown>]
  assert.equal(known.execution_state, "succeeded")
  assert.equal(known.acceptance_claim, "met")
  assert.equal(known.title, "Snapshot lane")
  assert.equal(known.worktree, snapshotRepo.cwd)
  assert.equal(known.base_revision, snapshotRepo.base)
  assert.equal(known.head, snapshotRepo.base)
  assert.equal(known.backend, "command-code")
  assert.equal(known.model, "deepseek/deepseek-v4.1-flash")
  assert.equal(known.effort, "high")
  assert.deepEqual(known.changed_paths, [])
  assert.deepEqual(known.out_of_scope_paths, [])
  assert.equal(known.steers, 1)
  assert.equal(known.continuations, 0)
  assert.equal(typeof known.observed_at, "string")
  assert.equal(known.reason, null)
  assert.equal(unreadable.execution_state, "unknown")
  assert.equal(unreadable.title, "Future lane")
  assert.match(String(unreadable.reason), /Unsupported worker session version/)
  const keys = Object.keys(known).sort()
  assert.deepEqual(Object.keys(unreadable).sort(), keys)
  for (const key of ["head", "model", "effort", "changed_paths", "out_of_scope_paths", "head_unchanged", "acceptance_claim", "continuations", "steers", "base_revision", "tier"])
    assert.equal(unreadable[key], "unknown", key)
})

test("snapshot scope facts are reported separately from execution state and the acceptance claim", async () => {
  const scoped = scratch.repo("repo-scope")
  const id = commandLane(scoped, 22, gone, [succeeded("proof\nACCEPTANCE: met")], { title: "Scoped lane" })
  writeFileSync(join(scoped.cwd, "README"), "changed\n")
  writeFileSync(join(scoped.cwd, "stray.txt"), "outside\n")
  const { out } = await run(["list", "--json", scoped.root])
  const [snapshot] = JSON.parse(out) as Array<Record<string, unknown>>
  assert.equal(snapshot!.id, id)
  assert.equal(snapshot!.execution_state, "succeeded")
  assert.equal(snapshot!.acceptance_claim, "met")
  assert.deepEqual(snapshot!.changed_paths, ["README", "stray.txt"])
  assert.deepEqual(snapshot!.out_of_scope_paths, ["stray.txt"])
  assert.equal(snapshot!.head_unchanged, true)
})

