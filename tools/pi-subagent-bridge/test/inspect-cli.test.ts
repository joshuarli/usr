import test, { after, before } from "node:test"
import assert from "node:assert/strict"
import { spawnSync } from "node:child_process"
import { join } from "node:path"
import { fileURLToPath } from "node:url"
import { Scratch, commandLane, commandResultLine, toolQueued, type Repo } from "./worker-fixtures.ts"

const cli = fileURLToPath(new URL("../src/cli.ts", import.meta.url))
const scratch = new Scratch()
let repo: Repo, finished: string, crashed: string, running: string
before(async () => {
  repo = scratch.repo()
  const gone = await scratch.gone(), alive = scratch.alive()
  finished = commandLane(repo, 1, gone, [commandResultLine("success", { finalText: "report written" })], { title: "Done lane" })
  crashed = commandLane(repo, 2, gone, [toolQueued("Download kernel")], { title: "Crashed lane" })
  running = commandLane(repo, 3, alive, [toolQueued("Waiting")], { title: "Running lane" })
})
after(() => scratch.close())

function run(...args: string[]) {
  return spawnSync(process.execPath, ["--experimental-strip-types", cli, ...args], {
    encoding: "utf8", timeout: 30000, cwd: scratch.path,
    env: { ...process.env, XDG_STATE_HOME: join(scratch.path, "state"), WORKER_CAMPAIGN_ROOTS: "" },
  })
}

test("inspect prints one JSON snapshot for a repository root or a worktree", () => {
  for (const path of [repo.root, repo.cwd]) {
    const result = run("inspect", path, finished)
    assert.equal(result.status, 0, result.stderr)
    const snapshot = JSON.parse(result.stdout)
    assert.equal(snapshot.id, finished)
    assert.equal(snapshot.execution_state, "succeeded")
    assert.equal(snapshot.last_assistant_text, "report written")
  }
})

test("inspect refuses a session that has no record", () => {
  const result = run("inspect", repo.root, "usrw_01234567-89ab-cdef-0123-4567890000ff")
  assert.equal(result.status, 1)
  assert.match(result.stderr, /no session record at/)
})

test("watch keeps its exit-code contract", () => {
  const done = run("watch", repo.root, finished)
  assert.equal(done.status, 0)
  assert.equal(done.stdout, "finished: succeeded\nreport written\n")
  const gone = run("watch", repo.root, crashed)
  assert.equal(gone.status, 3)
  assert.match(gone.stdout, /^exited without terminal result \(pid \d+\); last event: shell_command: Download kernel\n$/)
  const stalled = run("watch", repo.root, running, "0")
  assert.equal(stalled.status, 2)
  assert.match(stalled.stdout, /^stalled: no executor output for 0 min; last event: shell_command: Waiting\n$/)
  const unknown = run("watch", repo.root, "usrw_01234567-89ab-cdef-0123-4567890000ff")
  assert.equal(unknown.status, 4)
  assert.match(unknown.stdout, /no session record at/)
})

test("watch --state prints one state word", () => {
  assert.equal(run("watch", "--state", repo.root, running).stdout, "running\n")
  assert.equal(run("watch", "--state", repo.root, crashed).stdout, "interrupted\n")
})

test("watch rejects malformed arguments", () => {
  const result = run("watch", repo.root, finished, "soon")
  assert.equal(result.status, 2)
  assert.match(result.stderr, /^usage: pi-subagent-bridge watch/)
})

test("campaign lists, reports, acknowledges and times out", () => {
  const listed = run("campaign", "list", repo.root)
  assert.equal(listed.status, 0, listed.stderr)
  assert.match(listed.stdout, new RegExp(`^${finished} succeeded \\d+s ${repo.cwd}$`, "m"))
  const waited = run("campaign", "wait", repo.root)
  assert.equal(waited.status, 0)
  assert.ok(waited.stdout.includes(`${finished} succeeded ${repo.cwd} Done lane\n`), waited.stdout)
  assert.equal(run("campaign", "ack", finished, crashed).status, 0)
  const ticked = run("campaign", "wait", "--timeout", "1s", repo.root)
  assert.equal(ticked.status, 2)
  assert.equal(ticked.stdout, "tick: 1 running\n")
  const json = JSON.parse(run("campaign", "list", "--json", repo.root).stdout)
  assert.deepEqual(json.map((entry: { id: string }) => entry.id), [finished, crashed, running])
})
