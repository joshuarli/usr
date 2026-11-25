/**
 * Shared model-policy edit claim. One lightweight advisory claim per checkout,
 * visible from every worktree through the Git common dir, so a second session
 * learns at the start of policy work that another live session holds the area.
 * Pure POSIX and Node standard library; no dependencies.
 */
import { execFileSync } from "node:child_process"
import { mkdirSync, readFileSync, realpathSync, renameSync, rmdirSync, statSync, unlinkSync, writeFileSync } from "node:fs"
import { hostname, userInfo } from "node:os"
import { basename, dirname, join } from "node:path"
import { fileURLToPath, pathToFileURL } from "node:url"
import { resolve } from "node:path"

/** A claim goes stale only when its recorded process is gone AND it is older than this bound. */
export const STALE_BOUND_MS = 12 * 60 * 60 * 1000
/** The mutation lock is held for milliseconds; a lock older than this is abandoned. */
const LOCK_STALE_MS = 30_000
const LOCK_WAIT_MS = 5_000
const SCHEMA = 1
const CLAIM_FILE = "claim.json"
const LOCK_DIR = "lock"

export type ClaimRecord = {
  readonly schema_version: number
  readonly area: "policy"
  readonly owner: string
  readonly branch: string | null
  readonly worktree: string
  readonly pid: number
  readonly host: string
  readonly started: string
  readonly started_epoch_ms: number
}

export type ClaimRead =
  | { readonly kind: "none" }
  | { readonly kind: "valid"; readonly record: ClaimRecord }
  | { readonly kind: "corrupt"; readonly error: string; readonly mtimeMs: number }

export type Layout = {
  readonly worktree: string
  readonly commonRoot: string
  readonly stateDir: string
  readonly claimPath: string
  readonly lockPath: string
}

function git(cwd: string, ...args: string[]): string {
  return execFileSync("git", ["-C", cwd, ...args], {
    encoding: "utf8", timeout: 10_000,
    env: { ...process.env, GIT_OPTIONAL_LOCKS: "0" }, stdio: ["ignore", "pipe", "pipe"],
  }).trim()
}

function realpath(path: string): string {
  try { return realpathSync(path) } catch { return path }
}

/** Every worktree of one checkout resolves to the same state directory under the common root. */
export function repoLayout(cwd: string): Layout {
  const common = git(cwd, "rev-parse", "--path-format=absolute", "--git-common-dir")
  const worktree = git(cwd, "rev-parse", "--path-format=absolute", "--show-toplevel")
  const commonRoot = dirname(realpath(common))
  const stateDir = join(commonRoot, ".work", "policy-claim")
  return {
    worktree: realpath(worktree), commonRoot, stateDir,
    claimPath: join(stateDir, CLAIM_FILE), lockPath: join(stateDir, LOCK_DIR),
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value)
}

export function parseRecord(text: string): ClaimRecord {
  const value: unknown = JSON.parse(text)
  if (!isRecord(value)) throw new Error("claim is not an object")
  if (value.schema_version !== SCHEMA) throw new Error(`unsupported claim schema version: ${String(value.schema_version)}`)
  if (value.area !== "policy") throw new Error(`unsupported claim area: ${String(value.area)}`)
  for (const field of ["owner", "worktree", "host", "started"] as const)
    if (typeof value[field] !== "string" || !value[field]) throw new Error(`claim field ${field} is missing`)
  if (value.branch !== null && typeof value.branch !== "string") throw new Error("claim field branch is invalid")
  if (!Number.isSafeInteger(value.pid) || (value.pid as number) <= 0) throw new Error("claim field pid is invalid")
  if (!Number.isSafeInteger(value.started_epoch_ms) || (value.started_epoch_ms as number) <= 0)
    throw new Error("claim field started_epoch_ms is invalid")
  return value as unknown as ClaimRecord
}

/** Read-only claim inspection. A corrupt file is reported, never silently discarded. */
export function readClaim(claimPath: string): ClaimRead {
  let text: string
  try { text = readFileSync(claimPath, "utf8") } catch (error) {
    if (error instanceof Error && "code" in error && error.code === "ENOENT") return { kind: "none" }
    throw error
  }
  try { return { kind: "valid", record: parseRecord(text) } } catch (error) {
    let mtimeMs = 0
    try { mtimeMs = statSync(claimPath).mtimeMs } catch { /* unreadable stat keeps mtime 0 */ }
    return { kind: "corrupt", error: error instanceof Error ? error.message : String(error), mtimeMs }
  }
}

/** Process liveness by POSIX signal zero; EPERM still means the process exists. */
export function pidAlive(pid: number): boolean {
  try { process.kill(pid, 0); return true } catch (error) {
    if (error instanceof Error && "code" in error && error.code === "EPERM") return true
    return false
  }
}

export type Verdict = {
  readonly stale: boolean
  readonly alive: boolean
  readonly ageMs: number
  readonly hostMatches: boolean
  readonly reasons: readonly string[]
}

export function formatAge(ms: number): string {
  const minutes = Math.floor(ms / 60_000)
  if (minutes < 1) return "under a minute"
  if (minutes < 60) return `${minutes}m`
  const hours = Math.floor(minutes / 60)
  if (hours < 48) return `${hours}h${minutes % 60 ? `${minutes % 60}m` : ""}`
  return `${Math.floor(hours / 24)}d${hours % 24 ? `${hours % 24}h` : ""}`
}

/** Staleness needs both a dead (or unverifiable) process and an age beyond the bound; never one alone. */
export function evaluate(record: ClaimRecord, now = Date.now(), staleBoundMs = STALE_BOUND_MS): Verdict {
  const hostMatches = record.host === hostname()
  const alive = hostMatches ? pidAlive(record.pid) : false
  const ageMs = Math.max(0, now - record.started_epoch_ms)
  const reasons: string[] = []
  if (!hostMatches) reasons.push(`recorded host ${record.host} is not this host, so process liveness cannot be verified`)
  reasons.push(alive ? `pid ${record.pid} is alive` : `pid ${record.pid} is gone${hostMatches ? "" : " or unverifiable"}`)
  reasons.push(ageMs > staleBoundMs ?
    `age ${formatAge(ageMs)} exceeds the ${formatAge(staleBoundMs)} stale bound` :
    `age ${formatAge(ageMs)} is within the ${formatAge(staleBoundMs)} stale bound`)
  return { stale: !alive && ageMs > staleBoundMs, alive, ageMs, hostMatches, reasons }
}

function sanitize(value: string): string {
  return value.replace(/[\s\p{Cc}]+/gu, " ").trim().slice(0, 80)
}

/** An agent/session identifier from the environment when present, else user@host. */
export function ownerIdentity(env: NodeJS.ProcessEnv = process.env): string {
  const known: readonly [string, string][] = [
    ["USR_SESSION_ID", "session"],
    ["CLAUDE_CODE_SESSION_ID", "claude-code"],
    ["PI_SESSION_ID", "pi"],
    ["CODEX_SESSION_ID", "codex"],
    ["OPENCODE_SESSION_ID", "opencode"],
    ["DEVIN_SESSION_ID", "devin"],
    ["AGENT_SESSION_ID", "agent"],
  ]
  for (const [name, label] of known) {
    const value = env[name]
    if (value && value.trim()) return `${label}:${sanitize(value)}`
  }
  let user = "unknown"
  try { user = userInfo().username } catch { /* user database may be absent */ }
  return `${user}@${hostname()}`
}

/**
 * Best-effort pid of the invoking session: walk the ancestor chain past the
 * transient command shells (`sh -c ...`) and `make` that sit between this
 * process and the long-lived harness or interactive shell. Falls back to the
 * direct parent. The age bound is the final guard when this guess outlives
 * the real session, so a wrong answer can only delay staleness, never cause it.
 */
export function sessionPid(psOutput?: string, startPid = process.ppid): number {
  try {
    const out = psOutput ?? execFileSync("ps", ["-eo", "pid=,ppid=,args="], { encoding: "utf8", timeout: 10_000 })
    const rows = new Map<number, { ppid: number; args: string }>()
    for (const line of out.split("\n")) {
      const match = line.match(/^\s*(\d+)\s+(\d+)\s+(.*\S)\s*$/)
      if (match) rows.set(Number(match[1]), { ppid: Number(match[2]), args: match[3] })
    }
    let current = startPid
    for (let depth = 0; depth < 10; depth++) {
      const row = rows.get(current)
      if (!row || row.ppid === current || row.ppid <= 0) break
      const command = basename(row.args.split(/\s+/)[0] ?? "").replace(/^-/, "")
      const shell = ["sh", "dash", "bash", "zsh"].includes(command)
      const transientShell = shell && /(?:^|\s)-c(?:\s|$)/.test(row.args)
      const build = command === "make" || command === "gmake"
      if (!transientShell && !build) return current
      current = row.ppid
    }
  } catch { /* ps may be absent or unreadable; the parent pid is the fallback */ }
  return startPid
}

export function buildRecord(layout: Layout, env: NodeJS.ProcessEnv = process.env, now = Date.now()): ClaimRecord {
  let branch: string | null = null
  try { branch = git(layout.worktree, "symbolic-ref", "--quiet", "--short", "HEAD") || null } catch { branch = null }
  return {
    schema_version: SCHEMA, area: "policy", owner: ownerIdentity(env), branch,
    worktree: layout.worktree, pid: sessionPid(), host: hostname(),
    started: new Date(now).toISOString(), started_epoch_ms: now,
  }
}

function sleep(ms: number): void {
  Atomics.wait(new Int32Array(new SharedArrayBuffer(4)), 0, 0, ms)
}

function writeClaimAtomic(stateDir: string, claimPath: string, record: ClaimRecord): void {
  const tmp = join(stateDir, `claim.json.tmp.${process.pid}`)
  writeFileSync(tmp, JSON.stringify(record, null, 2) + "\n", { mode: 0o600 })
  renameSync(tmp, claimPath)
}

/** Serialize every mutation. The critical section is milliseconds; a lock older than LOCK_STALE_MS is abandoned. */
function withLock<T>(layout: Layout, notes: string[], fn: () => T): T {
  mkdirSync(layout.stateDir, { recursive: true, mode: 0o700 })
  const deadline = Date.now() + LOCK_WAIT_MS
  for (;;) {
    try { mkdirSync(layout.lockPath); break } catch (error) {
      if (!(error instanceof Error && "code" in error && error.code === "EEXIST")) throw error
      let ageMs = 0
      try { ageMs = Date.now() - statSync(layout.lockPath).mtimeMs } catch { ageMs = LOCK_STALE_MS + 1 }
      if (ageMs > LOCK_STALE_MS) {
        notes.push(`policy claim lock was older than ${formatAge(LOCK_STALE_MS)}; its holder crashed, breaking the abandoned lock`)
        try { rmdirSync(layout.lockPath) } catch { /* another process broke it first */ }
        continue
      }
      if (Date.now() > deadline) throw new Error("policy claim lock stayed busy; retry the command")
      sleep(40)
    }
  }
  try { return fn() } finally {
    try { rmdirSync(layout.lockPath) } catch { /* a crash breaking the lock is reported by the next mutator */ }
  }
}

function isSelf(record: ClaimRecord, layout: Layout): boolean {
  return realpath(record.worktree) === layout.worktree
}

export function describe(record: ClaimRecord, verdict?: Verdict, now = Date.now()): string {
  const age = formatAge(Math.max(0, now - record.started_epoch_ms))
  const lines = [
    `  owner:    ${record.owner}`,
    `  branch:   ${record.branch ?? "(detached HEAD)"}`,
    `  worktree: ${record.worktree}`,
    `  pid:      ${record.pid}${verdict ? (verdict.alive ? " (alive)" : " (gone)") : ""}`,
    `  started:  ${record.started} (${age} ago)`,
  ]
  return lines.join("\n")
}

export const SEE_OR_BREAK =
  "Run `make policy-claims` to inspect the claim, or `node tools/policy/claim.ts break` to break it after coordinating with the owner."

export function conflictMessage(record: ClaimRecord, verdict: Verdict): string {
  return [
    "policy claim held by another live session:",
    describe(record, verdict),
    ...verdict.reasons.map(reason => `  ${reason}`),
    SEE_OR_BREAK,
  ].join("\n")
}

export type AcquireOutcome =
  | { readonly outcome: "acquired" | "already-held"; readonly record: ClaimRecord; readonly notes: readonly string[] }
  | { readonly outcome: "took-over"; readonly record: ClaimRecord; readonly prior: string; readonly notes: readonly string[] }
  | { readonly outcome: "conflict"; readonly record: ClaimRecord; readonly verdict: Verdict; readonly notes: readonly string[] }

function corruptClaimError(layout: Layout, state: { error: string }): string {
  return `policy claim file ${layout.claimPath} is corrupt (${state.error}) and too recent to override; inspect it and run \`node tools/policy/claim.ts break\` if it should be removed`
}

/** Claim the policy area for this worktree, taking over claims that are provably stale and reporting every takeover. */
export function acquire(cwd: string, env: NodeJS.ProcessEnv = process.env, now = Date.now()): AcquireOutcome {
  const layout = repoLayout(cwd)
  const notes: string[] = []
  const record = buildRecord(layout, env, now)
  return withLock(layout, notes, () => {
    const state = readClaim(layout.claimPath)
    if (state.kind === "valid") {
      if (isSelf(state.record, layout)) return { outcome: "already-held" as const, record: state.record, notes }
      const verdict = evaluate(state.record, now)
      if (!verdict.stale) return { outcome: "conflict" as const, record: state.record, verdict, notes }
      writeClaimAtomic(layout.stateDir, layout.claimPath, record)
      const prior = `stale claim taken over (never silently):\n${describe(state.record, verdict, now)}\n` +
        verdict.reasons.map(reason => `  ${reason}`).join("\n")
      return { outcome: "took-over" as const, record, prior, notes }
    }
    if (state.kind === "corrupt") {
      const ageMs = Math.max(0, now - state.mtimeMs)
      if (state.mtimeMs > 0 && ageMs <= STALE_BOUND_MS) throw new Error(corruptClaimError(layout, state))
      writeClaimAtomic(layout.stateDir, layout.claimPath, record)
      const prior = `corrupt claim file older than the ${formatAge(STALE_BOUND_MS)} bound replaced (${state.error})`
      return { outcome: "took-over" as const, record, prior, notes }
    }
    writeClaimAtomic(layout.stateDir, layout.claimPath, record)
    return { outcome: "acquired" as const, record, notes }
  })
}

export type ReleaseOutcome =
  | { readonly outcome: "none" | "released" | "removed-stale" | "removed-broken"; readonly prior?: ClaimRecord; readonly notes: readonly string[] }
  | { readonly outcome: "conflict"; readonly record: ClaimRecord; readonly verdict: Verdict; readonly notes: readonly string[] }

/** Release this worktree's own claim. Another session's live claim is refused; a stale one is removed and reported. */
export function release(cwd: string, now = Date.now(), force = false): ReleaseOutcome {
  const layout = repoLayout(cwd)
  const notes: string[] = []
  return withLock(layout, notes, () => {
    const state = readClaim(layout.claimPath)
    if (state.kind === "none") return { outcome: "none" as const, notes }
    if (state.kind === "corrupt") {
      const ageMs = Math.max(0, now - state.mtimeMs)
      if (!force && state.mtimeMs > 0 && ageMs <= STALE_BOUND_MS) throw new Error(corruptClaimError(layout, state))
      unlinkSync(layout.claimPath)
      return { outcome: "removed-broken" as const, notes: [...notes, `removed corrupt claim file (${state.error})`] }
    }
    if (!force && !isSelf(state.record, layout)) {
      const verdict = evaluate(state.record, now)
      if (!verdict.stale) return { outcome: "conflict" as const, record: state.record, verdict, notes }
      unlinkSync(layout.claimPath)
      return {
        outcome: "removed-stale" as const, prior: state.record,
        notes: [...notes, `removed another session's stale claim:\n${describe(state.record, verdict, now)}`],
      }
    }
    const prior = state.record
    unlinkSync(layout.claimPath)
    return { outcome: force && !isSelf(prior, layout) ? "removed-broken" as const : "released" as const, prior, notes }
  })
}

export type Gate =
  | { readonly proceed: true; readonly notices: readonly string[] }
  | { readonly proceed: false; readonly message: string }

/**
 * Write-mode generator gate. Read-only paths never call this. Without any
 * claim the generator proceeds; a conflicting live claim blocks generation;
 * a stale claim is reported and taken over for the calling worktree.
 */
export function gateGenerate(root: string, env: NodeJS.ProcessEnv = process.env, now = Date.now()): Gate {
  let layout: Layout
  try { layout = repoLayout(root) } catch (error) {
    return { proceed: true, notices: [`policy claim check skipped: ${root} is not in a Git worktree (${error instanceof Error ? error.message.split("\n")[0] : String(error)})`] }
  }
  try {
    const state = readClaim(layout.claimPath)
    if (state.kind === "none") return { proceed: true, notices: [] }
    if (state.kind === "valid" && isSelf(state.record, layout)) return { proceed: true, notices: [] }
  } catch (error) {
    return { proceed: false, message: `policy claim could not be read: ${error instanceof Error ? error.message : String(error)}` }
  }
  try {
    const result = acquire(root, env, now)
    if (result.outcome === "conflict") return { proceed: false, message: conflictMessage(result.record, result.verdict) }
    const notices = [...result.notes]
    if (result.outcome === "took-over") notices.push(result.prior)
    return { proceed: true, notices }
  } catch (error) {
    return { proceed: false, message: `${error instanceof Error ? error.message : String(error)}` }
  }
}

function printOutcome(outcome: AcquireOutcome | ReleaseOutcome): number {
  for (const note of outcome.notes) process.stderr.write(`policy claim: ${note}\n`)
  if (outcome.outcome === "conflict") {
    process.stderr.write(conflictMessage(outcome.record, outcome.verdict) + "\n")
    return 1
  }
  return 0
}

export function statusText(cwd: string, now = Date.now()): string {
  const layout = repoLayout(cwd)
  const state = readClaim(layout.claimPath)
  if (state.kind === "none")
    return `policy claim: none — the model-policy area is unclaimed in this checkout\n  state: ${layout.claimPath}\n  claim it with \`make policy-claim\` before editing model policy`
  if (state.kind === "corrupt") {
    const age = state.mtimeMs ? formatAge(Math.max(0, now - state.mtimeMs)) : "unknown"
    return `policy claim: CORRUPT — ${layout.claimPath} cannot be parsed (${state.error}); file age ${age}\n` +
      "  it blocks until it ages past the stale bound; inspect it and run `node tools/policy/claim.ts break` if it should be removed"
  }
  const verdict = evaluate(state.record, now)
  const self = isSelf(state.record, layout)
  const head = verdict.stale ? "stale" : verdict.hostMatches ? "live" : "live unless aged out (pid unverifiable across hosts)"
  return [
    `policy claim: held — ${head}${self ? " — held by this worktree" : ""}`,
    describe(state.record, verdict, now),
    ...verdict.reasons.map(reason => `  ${reason}`),
    `  state: ${layout.claimPath}`,
  ].join("\n")
}

export function main(args: readonly string[], cwd = process.cwd()): number {
  const [command] = args
  if (args.length !== 1 || !["claim", "release", "status", "break"].includes(command ?? "")) {
    process.stderr.write("usage: node tools/policy/claim.ts <claim|release|status|break>\n")
    return 2
  }
  try {
    if (command === "status") {
      process.stdout.write(statusText(cwd) + "\n")
      return 0
    }
    if (command === "claim") {
      const outcome = acquire(cwd)
      const code = printOutcome(outcome)
      if (outcome.outcome === "acquired" || outcome.outcome === "took-over" || outcome.outcome === "already-held") {
        if (outcome.outcome === "took-over") process.stderr.write(`policy claim: ${outcome.prior}\n`)
        process.stdout.write(outcome.outcome === "already-held" ?
          `policy claim already held by this worktree since ${outcome.record.started}\n` :
          `policy claim held by this worktree (${outcome.record.owner}) since ${outcome.record.started}; release it with \`make policy-release\` when policy work is done\n`)
      }
      return code
    }
    if (command === "release") {
      const outcome = release(cwd)
      const code = printOutcome(outcome)
      if (outcome.outcome === "none") process.stdout.write("policy claim: none held; nothing to release\n")
      if (outcome.outcome === "released") process.stdout.write(`policy claim released (was held since ${outcome.prior?.started ?? "unknown"})\n`)
      if (outcome.outcome === "removed-stale") process.stdout.write("policy claim: removed another session's stale claim\n")
      if (outcome.outcome === "removed-broken") process.stdout.write("policy claim: removed\n")
      return code
    }
    const outcome = release(cwd, Date.now(), true)
    const code = printOutcome(outcome)
    if (outcome.outcome === "none") process.stdout.write("policy claim: none held; nothing to break\n")
    else if (outcome.outcome !== "conflict" && outcome.prior)
      process.stdout.write(`policy claim broken; removed claim held by ${outcome.prior.owner} since ${outcome.prior.started}\n`)
    else if (outcome.outcome !== "conflict") process.stdout.write("policy claim broken; corrupt claim removed\n")
    return code
  } catch (error) {
    process.stderr.write(`policy claim: ${error instanceof Error ? error.message : String(error)}\n`)
    return 1
  }
}

if (process.argv[1] && import.meta.url === pathToFileURL(resolve(process.argv[1])).href)
  process.exitCode = main(process.argv.slice(2))
