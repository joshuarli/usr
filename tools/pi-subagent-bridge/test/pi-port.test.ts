import test from "node:test"
import assert from "node:assert/strict"
import { execFileSync } from "node:child_process"
import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs"
import { join } from "node:path"
import { piPort, type PiCancelHooks } from "../src/pi-port.ts"
import { processStartTime } from "../src/command.ts"
import { PI_MODEL, Scratch, type Repo } from "./worker-fixtures.ts"

const delay = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms))

function fixtures(root: string): { worker: string } {
  const directory = join(root, "pi-fixtures")
  mkdirSync(directory, { recursive: true })
  writeFileSync(join(directory, "grandchild.mjs"), `process.on("SIGTERM", () => {})
setInterval(() => {}, 1000)
`)
  writeFileSync(join(directory, "sdk-worker-fixture.mjs"), `import { spawn } from "node:child_process"
import { readFileSync, writeFileSync } from "node:fs"
import { fileURLToPath } from "node:url"
const job = JSON.parse(readFileSync(process.argv[2], "utf8"))
const grandchildPath = fileURLToPath(new URL("./grandchild.mjs", import.meta.url))
const grandchild = spawn(process.execPath, [grandchildPath], { detached: true, stdio: "ignore" })
writeFileSync(job.resultPath + ".fixture", JSON.stringify({ parent: process.pid, grandchild: grandchild.pid }))
setInterval(() => {}, 1000)
`)
  return { worker: join(directory, "sdk-worker-fixture.mjs") }
}

function data<T>(value: unknown): T {
  return (value as { data: T }).data
}

async function admit(repo: Repo, worker: string, cancel?: PiCancelHooks) {
  const port = piPort({ workerPath: worker, cancel })
  const created = data<{ id: string }>(await port.create({
    title: "Pi cancellation fixture", agent: "build", model: PI_MODEL,
    location: { directory: repo.cwd },
    metadata: { usr_worker_v1: { directory: repo.cwd, model: PI_MODEL } },
  }))
  await port.prompt({ sessionID: created.id, cwd: repo.cwd, text: "run the process-tree fixture" })
  return { port, id: created.id }
}

function stored(repo: Repo, id: string): any {
  return JSON.parse(readFileSync(join(repo.directory, id + ".pi.json"), "utf8"))
}

function writeStored(repo: Repo, id: string, value: unknown): void {
  writeFileSync(join(repo.directory, id + ".pi.json"), JSON.stringify(value))
}

async function fixturePids(repo: Repo, id: string): Promise<{ parent: number; grandchild: number }> {
  const marker = stored(repo, id).run.output + ".fixture"
  for (let i = 0; i < 150; i++) {
    if (existsSync(marker)) {
      const value = JSON.parse(readFileSync(marker, "utf8")) as { parent: number; grandchild: number }
      if (value.parent > 0 && value.grandchild > 0) return value
    }
    await delay(20)
  }
  throw new Error("Pi process fixture did not start")
}

function alive(pid: number): boolean {
  try {
    if (process.platform === "linux") {
      const stat = readFileSync("/proc/" + pid + "/stat", "utf8")
      if (stat.slice(stat.lastIndexOf(")") + 1).trim().split(/\s+/)[0] === "Z") return false
    } else if (execFileSync("ps", ["-o", "stat=", "-p", String(pid)], { encoding: "utf8" }).trim().startsWith("Z")) return false
  } catch { /* the process may already be gone; kill(0) below is authoritative */ }
  try { process.kill(pid, 0); return true }
  catch (error) { return (error as NodeJS.ErrnoException).code === "EPERM" }
}

async function waitGone(pid: number): Promise<void> {
  for (let i = 0; i < 150; i++) {
    if (!alive(pid)) return
    await delay(20)
  }
  throw new Error("process still alive: " + pid)
}

function killTree(parent: number, grandchild?: number): void {
  for (const target of [grandchild, parent]) {
    if (!target) continue
    for (const id of [-target, target]) {
      try { process.kill(id, "SIGKILL") } catch {}
    }
  }
}

function pgid(pid: number): number {
  if (process.platform === "linux") {
    const stat = readFileSync("/proc/" + pid + "/stat", "utf8")
    return Number(stat.slice(stat.lastIndexOf(")") + 1).trim().split(/\s+/)[2])
  }
  return Number(execFileSync("ps", ["-o", "pgid=", "-p", String(pid)], { encoding: "utf8" }).trim())
}

test("interrupting a Pi run terminates a detached grandchild that survives its parent", async () => {
  const scratch = new Scratch()
  let pids: { parent: number; grandchild: number } | null = null
  try {
    const repo = scratch.repo("pi-cancel-tree")
    const { worker } = fixtures(scratch.path)
    const { port, id } = await admit(repo, worker)
    pids = await fixturePids(repo, id)
    assert.equal(pids.parent, stored(repo, id).run.pid)
    assert.equal(pgid(pids.parent), pids.parent, "the SDK worker must be its own process-group leader")
    assert.equal(pgid(pids.grandchild), pids.grandchild, "the fixture runner is deliberately detached")
    assert.ok(stored(repo, id).run.proc_start, "the run records process start identity")

    const reply = data<{ interrupted: boolean }>(await port.interrupt({ sessionID: id, cwd: repo.cwd }))
    assert.equal(reply.interrupted, true)
    await waitGone(pids.parent)
    await waitGone(pids.grandchild)
  } finally {
    if (pids) killTree(pids.parent, pids.grandchild)
    scratch.close()
  }
})

test("a fresh port uses recorded start identity and refuses a mismatched PID identity", async () => {
  const scratch = new Scratch()
  let first: { parent: number; grandchild: number } | null = null
  let second: { parent: number; grandchild: number } | null = null
  try {
    const repo = scratch.repo("pi-cancel-fresh")
    const { worker } = fixtures(scratch.path)

    const original = await admit(repo, worker)
    first = await fixturePids(repo, original.id)
    // This instance has an empty per-instance child map: admission used `original.port`.
    const fresh = piPort({ workerPath: worker })
    const reply = data<{ interrupted: boolean }>(await fresh.interrupt({ sessionID: original.id, cwd: repo.cwd }))
    assert.equal(reply.interrupted, true)
    await waitGone(first.grandchild)

    const mismatched = await admit(repo, worker)
    second = await fixturePids(repo, mismatched.id)
    const record = stored(repo, mismatched.id)
    assert.ok(record.run.proc_start)
    assert.notEqual(processStartTime(second.parent), "0")
    record.run.proc_start = "0"
    writeStored(repo, mismatched.id, record)
    const refused = data<{ interrupted: boolean }>(await piPort({ workerPath: worker }).interrupt({ sessionID: mismatched.id, cwd: repo.cwd }))
    assert.equal(refused.interrupted, false)
    await delay(100)
    assert.equal(alive(second.parent), true, "a mismatched/reused PID identity was signaled")
    assert.equal(alive(second.grandchild), true, "a mismatched/reused descendant identity was signaled")
  } finally {
    if (first) killTree(first.parent, first.grandchild)
    if (second) killTree(second.parent, second.grandchild)
    scratch.close()
  }
})

test("interrupt reports false and keeps status running when the tree survives the grace period", async () => {
  const scratch = new Scratch()
  let pids: { parent: number; grandchild: number } | null = null
  try {
    const repo = scratch.repo("pi-cancel-survives")
    const { worker } = fixtures(scratch.path)
    const port = piPort({
      workerPath: worker,
      cancel: {
        termGraceMs: 100, killVerifyMs: 100, pollMs: 10,
        signal(target, kind) {
          // Simulate a kernel/permission failure of the fatal escalation.  The
          // first SIGTERM is real, so only the SIGTERM-proof fixture survives.
          if (kind === "SIGKILL") return false
          try { process.kill(target, kind); return true } catch { return false }
        },
      },
    })
    const created = data<{ id: string }>(await port.create({
      title: "Pi cancellation survivor fixture", agent: "build", model: PI_MODEL,
      location: { directory: repo.cwd },
      metadata: { usr_worker_v1: { directory: repo.cwd, model: PI_MODEL } },
    }))
    await port.prompt({ sessionID: created.id, cwd: repo.cwd, text: "run the process-tree fixture" })
    pids = await fixturePids(repo, created.id)

    const reply = data<{ interrupted: boolean }>(await port.interrupt({ sessionID: created.id, cwd: repo.cwd }))
    assert.equal(reply.interrupted, false)
    assert.equal(alive(pids.grandchild), true)
    const persisted = stored(repo, created.id)
    assert.ok(persisted.run.tree.some((entry: { pid: number }) => entry.pid === pids!.grandchild))
    const status = data<{ outcome: string }>(await piPort({ workerPath: worker }).get({ sessionID: created.id, cwd: repo.cwd }))
    assert.equal(status.outcome, "running")
  } finally {
    if (pids) killTree(pids.parent, pids.grandchild)
    scratch.close()
  }
})
