import test from "node:test"
import assert from "node:assert/strict"
import { spawn, execFileSync, type ChildProcess } from "node:child_process"
import { randomUUID } from "node:crypto"
import {
  chmodSync, existsSync, mkdirSync, mkdtempSync, readdirSync, readFileSync, realpathSync, rmSync, statSync,
  writeFileSync,
} from "node:fs"
import { tmpdir } from "node:os"
import { dirname, join, relative, resolve } from "node:path"
import { fileURLToPath } from "node:url"
import type { OpenCodePort } from "../src/bridge.ts"
import type { CommandRun } from "../src/command.ts"
import { readStateDir, stateDir } from "../src/git.ts"
import { makeHybridBridge } from "../src/hybrid.ts"
import { OwnerAbortedError, OwnerManager, RepoOwnerEndpoint, deriveRunId, ownerDirectoryFor } from "../src/owner.ts"
import {
  listOwnerIds, ownerCommand, ownerHello, ownerInterrupt, ownerJobs, ownerResume, ownerStatus,
  ownerSteer, rawOwnerRpc, readOwnerDiscovery,
} from "../src/owner-client.ts"
import { ROOT_PLANS, type RootPlan } from "../src/policy.ts"
import { decodeSession, encodeSession, type Session } from "../src/session.ts"
import { connect } from "../src/server.ts"
import { worktreeLeasePath } from "../src/worktree-lease.ts"

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), "..")
const CLI_PATH = join(ROOT, "src", "cli.ts")
let repoCounter = 0

function scopeFor(repo: string) {
  return {
    base_revision: execFileSync("git", ["-C", repo, "rev-parse", "HEAD"], { encoding: "utf8" }).trim(),
    writable_paths: ["tracked.txt"],
    acceptance_proof: "node -e 0",
    attempt_limit: 2,
    stop_on: "done",
  }
}

function makeRepo(parent: string): string {
  repoCounter++
  const mainDir = mkdtempSync(join(parent, `main-${repoCounter}-`))
  execFileSync("git", ["init", "-q", "-b", "main", mainDir])
  execFileSync("git", ["-C", mainDir, "config", "user.email", "test@example.com"])
  execFileSync("git", ["-C", mainDir, "config", "user.name", "Test"])
  writeFileSync(join(mainDir, ".gitignore"), ".work/\n")
  writeFileSync(join(mainDir, "tracked.txt"), "base\n")
  execFileSync("git", ["-C", mainDir, "add", ".gitignore", "tracked.txt"])
  execFileSync("git", ["-C", mainDir, "commit", "-q", "-m", "init"])
  const wtDir = join(mainDir, ".work", "wt", `lane-${repoCounter}`)
  mkdirSync(dirname(wtDir), { recursive: true })
  execFileSync("git", ["-C", mainDir, "worktree", "add", "-q", "-b", `wt-${repoCounter}`, wtDir])
  return realpathSync(wtDir)
}

function makeScratch(t: test.TestContext): string {
  const scratch = mkdtempSync(join(realpathSync(tmpdir()), "usr-owner-test-"))
  t.after(() => rmSync(scratch, { recursive: true, force: true }))
  return scratch
}

function snapshotTree(root: string): Map<string, Buffer> {
  const out = new Map<string, Buffer>()
  if (!existsSync(root)) return out
  const walk = (dir: string) => {
    for (const entry of readdirSync(dir, { withFileTypes: true }).sort((a, b) => a.name.localeCompare(b.name))) {
      const full = join(dir, entry.name)
      const rel = relative(root, full)
      if (entry.isDirectory()) {
        walk(full)
      } else if (entry.isFile()) {
        out.set(rel, readFileSync(full))
      }
    }
  }
  walk(root)
  return out
}

function assertTreesByteEqual(before: Map<string, Buffer>, after: Map<string, Buffer>): void {
  assert.deepEqual([...after.keys()], [...before.keys()])
  for (const [key, buf] of before) {
    assert.equal(after.get(key)?.equals(buf), true, `file bytes mutated: ${key}`)
  }
}

type FakeCmdBehavior = {
  state: "running" | "succeeded" | "failed" | "cancelled" | "interrupted" | "turn_limit"
  error?: string
  sessionId?: string
  cancelReturns?: boolean
  onCancel?: () => void
  onStart?: () => void
}

function makeFakeCommand(initial?: Partial<FakeCmdBehavior>) {
  const behavior: FakeCmdBehavior = {
    state: "running",
    sessionId: "cmd_ses_1",
    cancelReturns: true,
    ...initial,
  }
  let starts = 0
  let cancels = 0
  let runSeq = 0
  const runner: NonNullable<Parameters<typeof makeHybridBridge>[1]> = {
    available: () => true,
    start: (input) => {
      starts++
      runSeq++
      behavior.onStart?.()
      mkdirSync(input.logDirectory, { recursive: true })
      const output = join(input.logDirectory, `cmd-out-${runSeq}.jsonl`)
      const errors = join(input.logDirectory, `cmd-err-${runSeq}.log`)
      const sid = behavior.sessionId ?? `cmd_ses_${runSeq}`
      writeFileSync(
        output,
        JSON.stringify({ type: "system", subtype: "init", session_id: sid }) + "\n",
      )
      writeFileSync(errors, `session: ${sid}\n`)
      return {
        pid: 40000 + runSeq,
        output,
        errors,
        started_at: `2026-11-15T00:00:0${runSeq}Z`,
      }
    },
    status: (_run: CommandRun) => {
      if (behavior.state === "running") {
        return { state: "running" as const, result: null, stderr: null }
      }
      if (behavior.state === "succeeded") {
        return {
          state: "succeeded" as const,
          stderr: null,
          result: {
            subtype: "success",
            text: "done\nACCEPTANCE: met",
            sessionId: behavior.sessionId,
            error: undefined,
            usage: null,
          },
        }
      }
      if (behavior.state === "failed") {
        const err = behavior.error ?? "failed"
        return {
          state: "failed" as const,
          stderr: err,
          result: {
            subtype: "error" as const,
            text: "",
            sessionId: behavior.sessionId,
            error: err,
            usage: null,
          },
        }
      }
      if (behavior.state === "turn_limit") {
        return {
          state: "turn_limit" as const,
          stderr: "Turn limit reached",
          result: {
            subtype: "max_turns" as const,
            text: "partial",
            sessionId: behavior.sessionId,
            error: "Turn limit reached",
            usage: null,
          },
        }
      }
      return {
        state: behavior.state,
        stderr: behavior.error ?? null,
        result: behavior.sessionId
          ? { subtype: "error" as const, text: "", sessionId: behavior.sessionId, error: behavior.error, usage: null }
          : null,
      }
    },
    cancel: () => {
      cancels++
      behavior.onCancel?.()
      if (behavior.cancelReturns !== false && behavior.state === "running") {
        behavior.state = "cancelled"
      }
      return behavior.cancelReturns !== false
    },
  }
  return {
    behavior,
    runner,
    counts: () => ({ starts, cancels }),
  }
}

function makeFakePiPort(initialState: "running" | "completed" = "running") {
  let outcome: "running" | "completed" | "cancelled" | "failed" = initialState
  let sessionCounter = 0
  let steerCalls = 0
  let cancelCalls = 0
  let resumeCalls = 0
  let steerReceipt: Record<string, unknown> = { accepted: true, delivery_status: "delivered" }
  const sessions = new Map<string, {
    id: string
    title: string
    model: { id: string; providerID: string; variant?: string }
    location: { directory: string }
    metadata: Record<string, unknown>
  }>()

  const workerPlan = ROOT_PLANS.worker
  if (workerPlan.kind !== "fallback") throw new Error("Expected fallback plan for worker")

  const port: OpenCodePort = {
    async models() {
      return {
        data: workerPlan.pi.map((m) => ({
          id: m.id,
          providerID: m.providerID,
          variants: m.variant ? [{ id: m.variant }] : undefined,
          enabled: true,
        })),
      }
    },
    async create(input) {
      sessionCounter++
      const id = "ses_" + String(sessionCounter).padStart(32, "0")
      sessions.set(id, { id, title: input.title, model: input.model, location: input.location, metadata: input.metadata })
      return { data: { id, title: input.title } }
    },
    async prompt() {
      if (outcome !== "running") resumeCalls++
      outcome = "running"
      return { data: { admitted: true } }
    },
    async get({ sessionID }) {
      const stored = sessions.get(sessionID)
      return {
        data: {
          id: sessionID,
          title: stored?.title ?? "usr-worker: t",
          model: stored?.model ?? workerPlan.pi[0],
          location: stored?.location ?? { directory: "" },
          metadata: stored?.metadata ?? {},
          outcome,
          error: null,
          tokens: null,
        },
      }
    },
    async active() {
      if (outcome !== "running") return { data: {} }
      const map: Record<string, boolean> = {}
      for (const id of sessions.keys()) map[id] = true
      return { data: map }
    },
    async inbox() { return { data: [] } },
    async messages() {
      return {
        data: [{
          info: { role: "assistant", error: null },
          parts: outcome === "completed" ? [{ type: "text", text: "done\nACCEPTANCE: met" }] : [],
        }],
      }
    },
    async interrupt() {
      cancelCalls++
      const wasRunning = outcome === "running"
      if (wasRunning) outcome = "cancelled"
      return { data: { interrupted: wasRunning } }
    },
    async steer() {
      steerCalls++
      return { data: { request_id: "req-" + steerCalls, ...steerReceipt } }
    },
  }

  return {
    port,
    setOutcome(next: "running" | "completed" | "cancelled" | "failed") { outcome = next },
    setSteerReceipt(next: Record<string, unknown>) { steerReceipt = next },
    counts: () => ({ steerCalls, cancelCalls, resumeCalls }),
  }
}

const noCodex: NonNullable<Parameters<typeof makeHybridBridge>[2]> = {
  available: () => false,
  start: () => { throw new Error("codex disabled") },
  status: () => ({ state: "failed", result: null, stderr: "codex disabled" }),
  cancel: () => false,
  session: () => null,
}

const piOnlyPolicy = (): RootPlan => ROOT_PLANS.worker

function writeArbitrarySession(dir: string, overrides: Partial<Session> & { id: string }): Session {
  const sDir = stateDir(dir)
  const workerPlan = ROOT_PLANS.worker
  if (workerPlan.kind !== "fallback") throw new Error("Expected fallback plan")
  const s: Session = {
    cwd: dir,
    title: "foreign",
    tier: "worker",
    scope: {
      writable_paths: ["tracked.txt"],
      acceptance_proof: "node -e 0",
      attempt_limit: 2,
      stop_on: "done",
      base_revision: execFileSync("git", ["-C", dir, "rev-parse", "HEAD"], { encoding: "utf8" }).trim(),
    },
    task: "foreign task",
    plan: workerPlan,
    execution: {
      kind: "process",
      executor: "command-code",
      selection: workerPlan.command,
      run: { pid: 99999, output: "o", errors: "e", started_at: "2026-11-15T00:00:00Z" },
    },
    attempts: 1,
    ...overrides,
  }
  writeFileSync(join(sDir, `${s.id}.json`), JSON.stringify(encodeSession(s)), { mode: 0o600 })
  return s
}

test("a: fresh client lists only this owner's jobs with generation and private socket permissions", async (t) => {
  const scratch = makeScratch(t)
  const repo = makeRepo(scratch)
  const cmd = makeFakeCommand()
  const bridge = makeHybridBridge(makeFakePiPort().port, cmd.runner, noCodex)
  const manager = new OwnerManager(bridge)
  t.after(async () => manager.close())

  const legacyId = "usrw_" + randomUUID()
  const foreignId = "usrw_" + randomUUID()
  writeArbitrarySession(repo, { id: legacyId })
  writeArbitrarySession(repo, { id: foreignId, owner: { owner_id: randomUUID(), owner_generation: 99 } })

  const started = await bridge.start(repo, "job-a", "worker", scopeFor(repo), "task a")
  const oDir = ownerDirectoryFor(readStateDir(repo))
  const discovery = readOwnerDiscovery(repo, manager.ownerId)

  assert.equal(discovery.owner_protocol, 1)
  assert.equal(discovery.owner_id, manager.ownerId)
  assert.equal(discovery.owner_generation, 1)
  assert.equal(discovery.pid, process.pid)
  assert.deepEqual(discovery.capabilities, ["status", "steer", "interrupt", "resume"])
  assert.equal(statSync(oDir).mode & 0o777, 0o700)
  assert.equal(statSync(discovery.socket).mode & 0o777, 0o600)
  assert.equal(statSync(join(oDir, `${manager.ownerId}.json`)).mode & 0o777, 0o600)

  const hello = await ownerHello(repo, manager.ownerId)
  assert.deepEqual(hello, {
    owner_protocol: 1,
    owner_id: manager.ownerId,
    owner_generation: 1,
    capabilities: ["status", "steer", "interrupt", "resume"],
  })

  const jobs = await ownerJobs(repo, manager.ownerId)
  assert.equal(jobs.length, 1)
  assert.equal(jobs[0].job_id, started.session_id)
  assert.equal(jobs[0].owner_generation, 1)
  assert.equal(jobs[0].state, "running")
  assert.match(jobs[0].run_id, /^run_[0-9a-f]{32}$/)
})

test("b: steer twice with one command_id delivers exactly one steer and returns identical receipts", async (t) => {
  const scratch = makeScratch(t)

  // 1) Pi in-process steer: keeps run_id unchanged and delivers once
  const piRepo = makeRepo(scratch)
  const pi = makeFakePiPort("running")
  const noCmd = makeFakeCommand()
  noCmd.runner.available = () => false
  const piBridge = makeHybridBridge(pi.port, noCmd.runner, noCodex, undefined, piOnlyPolicy)
  const piManager = new OwnerManager(piBridge)
  t.after(async () => piManager.close())

  await piBridge.start(piRepo, "pi-job", "worker", scopeFor(piRepo), "pi steer task")
  const [piJobBefore] = await ownerJobs(piRepo, piManager.ownerId)
  const target = {
    job_id: piJobBefore.job_id,
    run_id: piJobBefore.run_id,
    owner_generation: piJobBefore.owner_generation,
  }
  const cmdIdPi = "cmd-steer-pi-1"
  const [r1, r2] = await Promise.all([
    ownerSteer(piRepo, piManager.ownerId, { target, command_id: cmdIdPi, note: "focus here" }),
    ownerSteer(piRepo, piManager.ownerId, { target, command_id: cmdIdPi, note: "focus here" }),
  ])
  const r3 = await ownerSteer(piRepo, piManager.ownerId, { target, command_id: cmdIdPi, note: "focus here" })
  assert.deepEqual(r1, { receipt: "accepted", command_id: cmdIdPi })
  assert.deepEqual(r2, r1)
  assert.deepEqual(r3, r1)
  assert.equal(pi.counts().steerCalls, 1)
  const [piJobAfter] = await ownerJobs(piRepo, piManager.ownerId)
  assert.equal(piJobAfter.run_id, piJobBefore.run_id)
  assert.deepEqual(await ownerCommand(piRepo, piManager.ownerId, cmdIdPi), r1)

  // Same command_id with different note rejects conflict without re-executing
  const conflict = await ownerSteer(piRepo, piManager.ownerId, { target, command_id: cmdIdPi, note: "different note" })
  assert.deepEqual(conflict, { receipt: "rejected", reason: "command-id-conflict" })
  assert.equal(pi.counts().steerCalls, 1)

  // Pi pending delivery receipt is preserved and replayed without extra delivery
  pi.setSteerReceipt({ accepted: false, delivery_status: "pending" })
  const cmdIdPending = "cmd-steer-pi-pending"
  const pPending1 = await ownerSteer(piRepo, piManager.ownerId, { target, command_id: cmdIdPending, note: "second note" })
  const pPending2 = await ownerCommand(piRepo, piManager.ownerId, cmdIdPending)
  assert.deepEqual(pPending1, { receipt: "pending", command_id: cmdIdPending })
  assert.deepEqual(pPending2, pPending1)
  assert.equal(pi.counts().steerCalls, 2)

  // 2) Command Code process steer: restarts run -> new run_id, replay with original target still returns recorded receipt
  const cmdRepo = makeRepo(scratch)
  const cmd = makeFakeCommand({
    onStart: () => {
      cmd.behavior.state = "running"
    },
  })
  const cmdBridge = makeHybridBridge(makeFakePiPort().port, cmd.runner, noCodex)
  const cmdManager = new OwnerManager(cmdBridge)
  t.after(async () => cmdManager.close())

  await cmdBridge.start(cmdRepo, "cmd-job", "worker", scopeFor(cmdRepo), "cmd steer task")
  const [cmdJobBefore] = await ownerJobs(cmdRepo, cmdManager.ownerId)
  const origTarget = {
    job_id: cmdJobBefore.job_id,
    run_id: cmdJobBefore.run_id,
    owner_generation: cmdJobBefore.owner_generation,
  }
  const cmdIdProc = "cmd-steer-proc-1"
  const p1 = await ownerSteer(cmdRepo, cmdManager.ownerId, { target: origTarget, command_id: cmdIdProc, note: "steer proc" })
  const p2 = await ownerSteer(cmdRepo, cmdManager.ownerId, { target: origTarget, command_id: cmdIdProc, note: "steer proc" })
  assert.deepEqual(p1, { receipt: "accepted", command_id: cmdIdProc })
  assert.deepEqual(p2, p1)
  assert.equal(cmd.counts().starts, 2)
  assert.equal(cmd.counts().cancels, 1)
  const [cmdJobAfter] = await ownerJobs(cmdRepo, cmdManager.ownerId)
  assert.notEqual(cmdJobAfter.run_id, cmdJobBefore.run_id)
})

test("c: owner loss mid-command reports uncertain via command and new owner does not replay", async (t) => {
  const scratch = makeScratch(t)
  const repo = makeRepo(scratch)
  const cmd1 = makeFakeCommand()
  const bridge1 = makeHybridBridge(makeFakePiPort().port, cmd1.runner, noCodex)
  const endpoint1 = await RepoOwnerEndpoint.start(repo, bridge1, {
    testHooks: {
      afterAdmitted: async () => {
        await endpoint1.abort()
        throw new OwnerAbortedError("simulated crash after admitted")
      },
    },
  })
  t.after(async () => endpoint1.close())
  const ops1 = bridge1
  // Use OwnerManager-style resolver for bridge1 by wrapping or testing start via OwnerManager:
  const s = await (async () => {
    const { hybridOwnerOps } = await import("../src/hybrid.ts")
    hybridOwnerOps(ops1)?.setOwnerResolver(() => endpoint1.identity())
    return ops1.start(repo, "job-c", "worker", scopeFor(repo), "task c")
  })()

  const [job] = await ownerJobs(repo, endpoint1.ownerId)
  assert.equal(job.job_id, s.session_id)
  const cmdId = "cmd-lost-mid-flight"
  await assert.rejects(
    ownerSteer(repo, endpoint1.ownerId, {
      target: { job_id: job.job_id, run_id: job.run_id, owner_generation: job.owner_generation },
      command_id: cmdId,
      note: "never runs",
    }),
    (err) => err instanceof Error,
  )
  assert.equal(cmd1.counts().cancels, 0)
  assert.equal(cmd1.counts().starts, 1)

  // New owner instance starts at generation 2
  const cmd2 = makeFakeCommand()
  const bridge2 = makeHybridBridge(makeFakePiPort().port, cmd2.runner, noCodex)
  const manager2 = new OwnerManager(bridge2)
  t.after(async () => manager2.close())
  await manager2.ensureRepo(repo)

  const receipt = await ownerCommand(repo, manager2.ownerId, cmdId)
  assert.deepEqual(receipt, { receipt: "uncertain", command_id: cmdId })

  // Retrying same command_id on new owner returns uncertain and never replays
  const replay = await ownerSteer(repo, manager2.ownerId, {
    target: { job_id: job.job_id, run_id: job.run_id, owner_generation: job.owner_generation },
    command_id: cmdId,
    note: "never runs",
  })
  assert.deepEqual(replay, { receipt: "uncertain", command_id: cmdId })
  assert.equal(cmd2.counts().cancels, 0)
  assert.equal(cmd2.counts().starts, 0)
})

test("d: after owner restart old target is stale-target and old commands reconcile without replay", async (t) => {
  const scratch = makeScratch(t)
  const repo = makeRepo(scratch)

  const pi1 = makeFakePiPort("running")
  const noCmd = makeFakeCommand()
  noCmd.runner.available = () => false
  const bridge1 = makeHybridBridge(pi1.port, noCmd.runner, noCodex, undefined, piOnlyPolicy)
  let abortNext = false
  let mgr1Ref: RepoOwnerEndpoint | undefined
  const manager1 = new OwnerManager(bridge1, {
    testHooks: {
      afterAdmitted: async () => {
        if (abortNext) {
          await mgr1Ref?.abort()
          throw new OwnerAbortedError("mid-command shutdown")
        }
      },
    },
  })
  t.after(async () => manager1.close())
  const started = await bridge1.start(repo, "job-d", "worker", scopeFor(repo), "task d")
  mgr1Ref = await manager1.ensureRepo(repo)
  const owner1Id = manager1.ownerId
  const [job1] = await ownerJobs(repo, owner1Id)
  const oldTarget = { job_id: job1.job_id, run_id: job1.run_id, owner_generation: 1 }

  const cmdOk = "cmd-d-ok"
  const okReceipt = await ownerSteer(repo, owner1Id, { target: oldTarget, command_id: cmdOk, note: "first" })
  assert.deepEqual(okReceipt, { receipt: "accepted", command_id: cmdOk })

  const cmdLost = "cmd-d-lost"
  abortNext = true
  await assert.rejects(
    ownerSteer(repo, owner1Id, { target: oldTarget, command_id: cmdLost, note: "lost" }),
    (err) => err instanceof Error,
  )
  await manager1.close()
  assert.equal(existsSync(join(ownerDirectoryFor(readStateDir(repo)), `${owner1Id}.json`)), false)
  assert.equal(existsSync(join(ownerDirectoryFor(readStateDir(repo)), `${owner1Id}.sock`)), false)

  // Restarted owner (generation 2)
  const pi2 = makeFakePiPort("running")
  const bridge2 = makeHybridBridge(pi2.port, noCmd.runner, noCodex, undefined, piOnlyPolicy)
  const manager2 = new OwnerManager(bridge2)
  t.after(async () => manager2.close())
  await manager2.ensureRepo(repo)

  const hello2 = await ownerHello(repo, manager2.ownerId)
  assert.equal(hello2.owner_generation, 2)
  assert.deepEqual(await ownerJobs(repo, manager2.ownerId), [])

  assert.deepEqual(await ownerStatus(repo, manager2.ownerId, oldTarget), { receipt: "rejected", reason: "stale-target" })
  assert.deepEqual(
    await ownerSteer(repo, manager2.ownerId, { target: oldTarget, command_id: "new-steer", note: "retry" }),
    { receipt: "rejected", reason: "stale-target" },
  )
  assert.deepEqual(
    await ownerInterrupt(repo, manager2.ownerId, { target: oldTarget, command_id: "new-int" }),
    { receipt: "rejected", reason: "stale-target" },
  )
  assert.deepEqual(
    await ownerResume(repo, manager2.ownerId, { target: oldTarget, command_id: "new-res", feedback: "fix" }),
    { receipt: "rejected", reason: "stale-target" },
  )
  // Even with generation updated to 2, job1 was not admitted by owner2
  assert.deepEqual(
    await ownerStatus(repo, manager2.ownerId, { ...oldTarget, owner_generation: 2 }),
    { receipt: "rejected", reason: "stale-target" },
  )

  assert.deepEqual(await ownerCommand(repo, manager2.ownerId, cmdOk), { receipt: "accepted", command_id: cmdOk })
  assert.deepEqual(await ownerCommand(repo, manager2.ownerId, cmdLost), { receipt: "uncertain", command_id: cmdLost })
  assert.equal(pi2.counts().steerCalls, 0)
  assert.equal(pi2.counts().cancelCalls, 0)
  assert.equal(pi2.counts().resumeCalls, 0)
  assert.ok(started.session_id)
})

test("e: status, jobs, and hello leave leases, counts, and session records byte-for-byte unchanged", async (t) => {
  const scratch = makeScratch(t)
  const repo = makeRepo(scratch)
  const cmd = makeFakeCommand()
  const bridge = makeHybridBridge(makeFakePiPort().port, cmd.runner, noCodex)
  const manager = new OwnerManager(bridge)
  t.after(async () => manager.close())

  const started = await bridge.start(repo, "job-e", "worker", scopeFor(repo), "task e")
  const [job] = await ownerJobs(repo, manager.ownerId)
  const sDir = readStateDir(repo)
  const before = snapshotTree(sDir)

  await ownerHello(repo, manager.ownerId)
  await ownerJobs(repo, manager.ownerId)
  const status1 = await ownerStatus(repo, manager.ownerId, {
    job_id: job.job_id,
    run_id: job.run_id,
    owner_generation: job.owner_generation,
  })
  assert.equal(status1.state, "running")
  assert.equal(status1.job_id, started.session_id)

  cmd.behavior.state = "succeeded"
  const status2 = await ownerStatus(repo, manager.ownerId, {
    job_id: job.job_id,
    run_id: job.run_id,
    owner_generation: job.owner_generation,
  })
  assert.equal(status2.state, "succeeded")

  const after = snapshotTree(sDir)
  assertTreesByteEqual(before, after)
  assert.equal(existsSync(worktreeLeasePath(sDir, repo)), true)
})

test("f: unknown method, unknown param field, bad protocol use, and unowned job target are rejected", async (t) => {
  const scratch = makeScratch(t)
  const repo = makeRepo(scratch)
  const cmd = makeFakeCommand()
  const bridge = makeHybridBridge(makeFakePiPort().port, cmd.runner, noCodex)
  const manager = new OwnerManager(bridge)
  t.after(async () => manager.close())
  await manager.ensureRepo(repo)

  const legacyId = "usrw_" + randomUUID()
  const legacySession = writeArbitrarySession(repo, { id: legacyId })
  const discovery = readOwnerDiscovery(repo, manager.ownerId)
  const sock = discovery.socket

  const parseErr = await rawOwnerRpc(sock, "{not json") as { error: { code: number } }
  assert.equal(parseErr.error.code, -32700)

  const wrongVersion = await rawOwnerRpc(sock, JSON.stringify({ jsonrpc: "1.0", id: 1, method: "hello" })) as { error: { code: number } }
  assert.equal(wrongVersion.error.code, -32600)

  const extraTop = await rawOwnerRpc(sock, JSON.stringify({ jsonrpc: "2.0", id: 2, method: "hello", extra: 1 })) as { error: { code: number } }
  assert.equal(extraTop.error.code, -32600)

  const unknownMethod = await rawOwnerRpc(sock, JSON.stringify({ jsonrpc: "2.0", id: 3, method: "adopt" })) as { error: { code: number } }
  assert.equal(unknownMethod.error.code, -32601)

  const extraHelloParam = await rawOwnerRpc(sock, JSON.stringify({ jsonrpc: "2.0", id: 4, method: "hello", params: { force: true } })) as { error: { code: number } }
  assert.equal(extraHelloParam.error.code, -32602)

  const extraSteerParam = await rawOwnerRpc(sock, JSON.stringify({
    jsonrpc: "2.0",
    id: 5,
    method: "steer",
    params: { target: { job_id: legacyId, run_id: "r", owner_generation: 1 }, command_id: "c", note: "n", extra: true },
  })) as { error: { code: number } }
  assert.equal(extraSteerParam.error.code, -32602)

  const extraTargetField = await rawOwnerRpc(sock, JSON.stringify({
    jsonrpc: "2.0",
    id: 6,
    method: "status",
    params: { target: { job_id: legacyId, run_id: "r", owner_generation: 1, extra: 1 } },
  })) as { error: { code: number } }
  assert.equal(extraTargetField.error.code, -32602)

  const legacyTarget = {
    job_id: legacyId,
    run_id: deriveRunId(legacySession, readStateDir(repo)),
    owner_generation: 1,
  }
  assert.deepEqual(await ownerStatus(repo, manager.ownerId, legacyTarget), { receipt: "rejected", reason: "stale-target" })
  assert.deepEqual(
    await ownerSteer(repo, manager.ownerId, { target: legacyTarget, command_id: "c-legacy-s", note: "n" }),
    { receipt: "rejected", reason: "stale-target" },
  )
  assert.deepEqual(
    await ownerInterrupt(repo, manager.ownerId, { target: legacyTarget, command_id: "c-legacy-i" }),
    { receipt: "rejected", reason: "stale-target" },
  )
  assert.deepEqual(
    await ownerResume(repo, manager.ownerId, { target: legacyTarget, command_id: "c-legacy-r", feedback: "f" }),
    { receipt: "rejected", reason: "stale-target" },
  )

  // Client discovery rejects wrong owner_protocol
  const metaPath = join(ownerDirectoryFor(readStateDir(repo)), `${manager.ownerId}.json`)
  const badDiscovery = { ...discovery, owner_protocol: 99 }
  writeFileSync(metaPath, JSON.stringify(badDiscovery), { mode: 0o600 })
  assert.throws(() => readOwnerDiscovery(repo, manager.ownerId), /Unsupported owner_protocol/)
  writeFileSync(metaPath, JSON.stringify(discovery), { mode: 0o600 })
})

test("g: steer on finished run -> not-running; resume while running -> rejected; resume on finished -> accepted with new run_id", async (t) => {
  const scratch = makeScratch(t)
  const repo = makeRepo(scratch)
  const cmd = makeFakeCommand()
  const bridge = makeHybridBridge(makeFakePiPort().port, cmd.runner, noCodex)
  const manager = new OwnerManager(bridge)
  t.after(async () => manager.close())

  const started = await bridge.start(repo, "job-g", "worker", scopeFor(repo), "task g")
  const [runningJob] = await ownerJobs(repo, manager.ownerId)
  const runningTarget = {
    job_id: runningJob.job_id,
    run_id: runningJob.run_id,
    owner_generation: runningJob.owner_generation,
  }

  // Resume while running is rejected cleanly
  const whileRunning = await ownerResume(repo, manager.ownerId, {
    target: runningTarget,
    command_id: "res-while-running",
    feedback: "too early",
  })
  assert.deepEqual(whileRunning, { receipt: "rejected", reason: "already-running" })

  // Mark finished
  cmd.behavior.state = "succeeded"
  const statusFinished = await ownerStatus(repo, manager.ownerId, runningTarget)
  assert.equal(statusFinished.state, "succeeded")

  // Steer on finished run -> rejected: not-running
  const steerFinished = await ownerSteer(repo, manager.ownerId, {
    target: runningTarget,
    command_id: "steer-finished",
    note: "late note",
  })
  assert.deepEqual(steerFinished, { receipt: "rejected", reason: "not-running" })

  // Resume on finished latest run -> accepted and new run_id appears in jobs
  cmd.behavior.onStart = () => {
    cmd.behavior.state = "running"
  }
  const resumed = await ownerResume(repo, manager.ownerId, {
    target: runningTarget,
    command_id: "res-finished",
    feedback: "apply fix",
  })
  assert.deepEqual(resumed, { receipt: "accepted", command_id: "res-finished" })

  const [resumedJob] = await ownerJobs(repo, manager.ownerId)
  assert.equal(resumedJob.job_id, started.session_id)
  assert.notEqual(resumedJob.run_id, runningTarget.run_id)
  assert.equal(resumedJob.state, "running")
  assert.deepEqual(await ownerStatus(repo, manager.ownerId, runningTarget), { receipt: "rejected", reason: "stale-target" })

  // Attempt limit exhaustion maps to rejected without mutating further
  cmd.behavior.state = "succeeded"
  const limitTarget = { job_id: resumedJob.job_id, run_id: resumedJob.run_id, owner_generation: resumedJob.owner_generation }
  const limitHit = await ownerResume(repo, manager.ownerId, {
    target: limitTarget,
    command_id: "res-limit",
    feedback: "exceed limit",
  })
  assert.deepEqual(limitHit, { receipt: "rejected", reason: "attempt-limit" })
})

test("h: interrupt on blocked_partial_work returns rejected: not-running and preserves lease file", async (t) => {
  const scratch = makeScratch(t)
  const repo = makeRepo(scratch)
  const cmd = makeFakeCommand()
  const bridge = makeHybridBridge(makeFakePiPort().port, cmd.runner, noCodex)
  const manager = new OwnerManager(bridge)
  t.after(async () => manager.close())

  const started = await bridge.start(repo, "job-h", "worker", scopeFor(repo), "task h")
  const [job] = await ownerJobs(repo, manager.ownerId)
  const target = { job_id: job.job_id, run_id: job.run_id, owner_generation: job.owner_generation }

  // Partial in-scope edit + provider usage limit failure => blocked_partial_work
  writeFileSync(join(repo, "tracked.txt"), "partial edit\n")
  cmd.behavior.state = "failed"
  cmd.behavior.error = "Rate limit exhausted (429)"

  const [listed] = await ownerJobs(repo, manager.ownerId)
  assert.equal(listed.state, "blocked_partial_work")

  const sDir = readStateDir(repo)
  const leaseDir = worktreeLeasePath(sDir, repo)
  const leaseOwnerFile = join(leaseDir, "owner.json")
  const leaseBefore = readFileSync(leaseOwnerFile)
  const sessionBefore = readFileSync(join(sDir, `${started.session_id}.json`))

  const interrupted = await ownerInterrupt(repo, manager.ownerId, { target, command_id: "int-blocked" })
  assert.deepEqual(interrupted, { receipt: "rejected", reason: "not-running" })

  assert.equal(existsSync(leaseOwnerFile), true)
  assert.equal(readFileSync(leaseOwnerFile).equals(leaseBefore), true)
  assert.equal(readFileSync(join(sDir, `${started.session_id}.json`)).equals(sessionBefore), true)
  assert.equal(cmd.counts().cancels, 0)
})

test("CLI start never becomes an owner and MCP server + owner CLI work end-to-end with clean shutdown", async (t) => {
  const scratch = makeScratch(t)
  const fakeBin = join(scratch, "bin")
  mkdirSync(fakeBin, { recursive: true })
  const fakeCmd = join(fakeBin, "cmd")
  writeFileSync(fakeCmd, "#!/bin/sh\nexec /bin/sleep 30\n", { mode: 0o755 })
  chmodSync(fakeCmd, 0o755)
  const env = {
    ...process.env,
    HOME: scratch,
    CODEX_HOME: join(scratch, "no-codex"),
    PATH: `${fakeBin}:/usr/bin:/bin:/opt/homebrew/opt/rustup/bin:/opt/homebrew/bin:/Users/josh/.local/bin`,
  }

  // Verify old v2 session decodes without owner and invalid persisted owner rejects cleanly
  const unownedRepo = makeRepo(scratch)
  const oldSession = writeArbitrarySession(unownedRepo, { id: "usrw_" + randomUUID() })
  const oldRaw = JSON.parse(readFileSync(join(readStateDir(unownedRepo), `${oldSession.id}.json`), "utf8")) as unknown
  assert.equal(decodeSession(oldRaw, unownedRepo, oldSession.id).owner, undefined)
  assert.throws(
    () => decodeSession({ ...(oldRaw as Record<string, unknown>), owner: { owner_id: "not-a-uuid", owner_generation: 1 } }, unownedRepo, oldSession.id),
    /Invalid persisted session owner/,
  )

  // 1) CLI bridge command does not start an owner endpoint or stamp owner onto the session
  const cliRepo = makeRepo(scratch)
  const originalPath = process.env.PATH
  const originalHome = process.env.HOME
  process.env.PATH = env.PATH
  process.env.HOME = scratch
  let cliPid: number | undefined
  try {
    const cliBridge = await connect()
    const cliStarted = await cliBridge.start(cliRepo, "cli-job", "worker", scopeFor(cliRepo), "cli task")
    const cliRaw = JSON.parse(readFileSync(join(readStateDir(cliRepo), `${cliStarted.session_id}.json`), "utf8")) as Record<string, unknown>
    assert.equal(cliRaw.owner, undefined)
    assert.deepEqual(listOwnerIds(cliRepo), [])
    const run = cliRaw.command_run as { pid?: number } | undefined
    cliPid = run?.pid
  } finally {
    process.env.PATH = originalPath
    if (originalHome === undefined) delete process.env.HOME
    else process.env.HOME = originalHome
    if (cliPid) {
      try { process.kill(cliPid, "SIGTERM") } catch {}
    }
  }

  // 2) MCP server process starts owner endpoint, answers CLI owner subcommands, and removes files on shutdown
  const mcpRepo = makeRepo(scratch)
  const serverProc: ChildProcess = spawn(process.execPath, ["--experimental-strip-types", CLI_PATH, "mcp"], {
    cwd: ROOT,
    env,
    stdio: ["pipe", "pipe", "pipe"],
  })
  t.after(() => {
    if (!serverProc.killed && serverProc.exitCode === null) serverProc.kill("SIGTERM")
  })

  const lines: string[] = []
  let stdoutBuf = ""
  const waiters: Array<(line: string) => void> = []
  serverProc.stdout!.setEncoding("utf8")
  serverProc.stdout!.on("data", (chunk: string) => {
    stdoutBuf += chunk
    let idx = stdoutBuf.indexOf("\n")
    while (idx >= 0) {
      const line = stdoutBuf.slice(0, idx)
      stdoutBuf = stdoutBuf.slice(idx + 1)
      const w = waiters.shift()
      if (w) w(line)
      else lines.push(line)
      idx = stdoutBuf.indexOf("\n")
    }
  })

  const nextLine = () => {
    const queued = lines.shift()
    if (queued !== undefined) return Promise.resolve(queued)
    return new Promise<string>((resolveLine) => waiters.push(resolveLine))
  }

  const sendMcp = async (msg: Record<string, unknown>) => {
    serverProc.stdin!.write(JSON.stringify({ jsonrpc: "2.0", ...msg }) + "\n")
    if (!("id" in msg)) return null
    return JSON.parse(await nextLine()) as Record<string, unknown>
  }

  await sendMcp({ id: 1, method: "initialize", params: {} })
  const startResp = await sendMcp({
    id: 2,
    method: "tools/call",
    params: {
      name: "worker_start",
      arguments: {
        cwd: mcpRepo,
        title: "mcp-owner",
        tier: "worker",
        scope: scopeFor(mcpRepo),
        brief: "mcp job",
      },
    },
  }) as { result: { isError?: boolean; content: Array<{ text: string }> } }
  assert.equal(startResp.result.isError, undefined, startResp.result.content[0]?.text)
  const startedPayload = JSON.parse(startResp.result.content[0].text) as { session_id: string }

  const ids = listOwnerIds(mcpRepo)
  assert.equal(ids.length, 1)
  const ownerId = ids[0]

  const runCli = (subArgs: string[]) => JSON.parse(execFileSync(
    process.execPath,
    ["--experimental-strip-types", CLI_PATH, "owner", ...subArgs],
    { cwd: ROOT, env, encoding: "utf8" },
  )) as unknown

  const cliHello = runCli(["hello", "--repo", mcpRepo, "--owner", ownerId]) as { owner_id: string; owner_generation: number }
  assert.equal(cliHello.owner_id, ownerId)
  assert.equal(cliHello.owner_generation, 1)

  const cliJobs = runCli(["jobs", "--repo", mcpRepo, "--owner", ownerId]) as Array<{ job_id: string; run_id: string; owner_generation: number; state: string }>
  assert.equal(cliJobs.length, 1)
  assert.equal(cliJobs[0].job_id, startedPayload.session_id)
  assert.equal(cliJobs[0].state, "running")

  const cliStatus = runCli([
    "status", "--repo", mcpRepo, "--owner", ownerId,
    "--job", cliJobs[0].job_id, "--run", cliJobs[0].run_id, "--generation", String(cliJobs[0].owner_generation),
  ]) as { state: string }
  assert.equal(cliStatus.state, "running")

  const cliInterrupt = runCli([
    "interrupt", "--repo", mcpRepo, "--owner", ownerId,
    "--job", cliJobs[0].job_id, "--run", cliJobs[0].run_id, "--generation", String(cliJobs[0].owner_generation),
    "--command", "cli-int-1",
  ]) as { receipt: string; command_id: string }
  assert.deepEqual(cliInterrupt, { receipt: "accepted", command_id: "cli-int-1" })

  const cliCommand = runCli(["command", "--repo", mcpRepo, "--owner", ownerId, "--command", "cli-int-1"])
  assert.deepEqual(cliCommand, { receipt: "accepted", command_id: "cli-int-1" })

  // Clean MCP shutdown deletes discovery JSON and socket file
  serverProc.stdin!.end()
  const exitCode = await new Promise<number | null>((resolveExit) => serverProc.once("exit", resolveExit))
  assert.equal(exitCode, 0)
  assert.equal(existsSync(join(ownerDirectoryFor(readStateDir(mcpRepo)), `${ownerId}.json`)), false)
  assert.equal(existsSync(join(ownerDirectoryFor(readStateDir(mcpRepo)), `${ownerId}.sock`)), false)
})
