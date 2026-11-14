import { chmodSync, mkdirSync, readdirSync, readFileSync, realpathSync, renameSync, statSync, writeFileSync } from "node:fs"
import { homedir } from "node:os"
import { dirname, join, resolve } from "node:path"
import { readStateDir } from "./git.ts"
import { inspectStored, sessionPath, type InspectionDeps, type Snapshot } from "./inspect.ts"
import { isSessionId } from "./session.ts"
import { systemClock, type Clock } from "./watch.ts"

export const CAMPAIGN_POLL_MS = 10_000
export const EXIT_TICK = 2
const USAGE = [
  "usage: pi-subagent-bridge campaign wait [--timeout DURATION] [ROOT...]",
  "       pi-subagent-bridge campaign ack ID...",
  "       pi-subagent-bridge campaign list [--json] [ROOT...]",
].join("\n") + "\n"

export type CampaignContext = {
  deps: InspectionDeps
  env: NodeJS.ProcessEnv
  cwd: string
  stdout: (text: string) => void
  stderr: (text: string) => void
  pollMs?: number
  clock?: Clock
}

class CampaignError extends Error {
  readonly status: number
  constructor(message: string, status = 1) {
    super(message)
    this.status = status
  }
}

function parseDuration(value: string): number {
  const match = /^(\d+)([smh]?)$/.exec(value)
  if (!match) throw new CampaignError("invalid duration: " + value)
  return Number(match[1]) * ({ "": 1, s: 1, m: 60, h: 3600 }[match[2] as "" | "s" | "m" | "h"])
}

function humanAge(seconds: number): string {
  if (seconds < 60) return seconds + "s"
  if (seconds < 3600) return Math.floor(seconds / 60) + "m"
  if (seconds < 86400) return Math.floor(seconds / 3600) + "h" + Math.floor(seconds % 3600 / 60) + "m"
  return Math.floor(seconds / 86400) + "d" + Math.floor(seconds % 86400 / 3600) + "h"
}

function ackedFile(env: NodeJS.ProcessEnv): string {
  return join(env.XDG_STATE_HOME || join(env.HOME || homedir(), ".local", "state"), "worker-campaign", "acked")
}
function readAcked(env: NodeJS.ProcessEnv): Set<string> {
  try { return new Set(readFileSync(ackedFile(env), "utf8").split("\n").filter(Boolean)) }
  catch { return new Set() }
}

function stateDirectories(arguments_: string[], context: CampaignContext): string[] {
  const requested = arguments_.length ? arguments_ : (context.env.WORKER_CAMPAIGN_ROOTS ?? "").split(":")
  const directories = new Set<string>()
  for (const root of requested.filter(Boolean)) {
    let absolute: string
    try { absolute = realpathSync(resolve(context.cwd, root)) } catch { throw new CampaignError("no such root: " + root) }
    try { directories.add(readStateDir(absolute)) } catch { throw new CampaignError("not a Git repository: " + root) }
  }
  if (!directories.size) throw new CampaignError("no ROOT given and WORKER_CAMPAIGN_ROOTS is empty")
  return [...directories]
}

type Entry = { snapshot: Snapshot; record: string }
async function discover(directories: string[], deps: InspectionDeps): Promise<Entry[]> {
  const seen = new Set<string>(), entries: Entry[] = []
  for (const directory of directories) {
    let names: string[]
    try { names = readdirSync(directory).sort() } catch { continue }
    for (const name of names) {
      const id = name.slice(0, -".json".length)
      if (!name.endsWith(".json") || !isSessionId(id) || seen.has(id)) continue
      seen.add(id)
      entries.push({ snapshot: await inspectStored(directory, id, deps), record: sessionPath(directory, id) })
    }
  }
  return entries
}

function cell(value: string): string {
  return value.replace(/[\t\r\n]+/g, " ")
}

async function wait(arguments_: string[], context: CampaignContext): Promise<number> {
  const clock = context.clock ?? systemClock, pollMs = context.pollMs ?? CAMPAIGN_POLL_MS
  let timeout: number | undefined
  const rest = [...arguments_]
  while (rest.length && rest[0]!.startsWith("-")) {
    const flag = rest.shift()!
    if (flag === "--") break
    if (flag === "--timeout") {
      const value = rest.shift()
      if (value === undefined) throw new CampaignError(USAGE.trimEnd())
      timeout = parseDuration(value)
    } else if (flag.startsWith("--timeout=")) {
      timeout = parseDuration(flag.slice("--timeout=".length))
    } else {
      throw new CampaignError(USAGE.trimEnd())
    }
  }
  const directories = stateDirectories(rest, context)
  const deadline = timeout === undefined ? undefined : clock.now() + timeout * 1000
  for (;;) {
    const acked = readAcked(context.env)
    const pending = (await discover(directories, context.deps)).filter(({ snapshot }) => !acked.has(snapshot.id))
    const finished = pending.filter(({ snapshot }) => snapshot.attention !== "active")
    if (finished.length) {
      for (const { snapshot } of finished)
        context.stdout([snapshot.id, snapshot.execution_state, snapshot.worktree, cell(snapshot.title)].join(" ") + "\n")
      return 0
    }
    let nap = pollMs
    if (deadline !== undefined) {
      const remaining = deadline - clock.now()
      if (remaining <= 0) {
        context.stdout("tick: " + pending.filter(({ snapshot }) => snapshot.attention === "active").length + " running\n")
        return EXIT_TICK
      }
      nap = Math.min(pollMs, remaining)
    }
    await clock.sleep(nap)
  }
}

async function list(arguments_: string[], context: CampaignContext): Promise<number> {
  const json = arguments_.includes("--json")
  const entries = await discover(stateDirectories(arguments_.filter((argument) => argument !== "--json"), context), context.deps)
  if (json) {
    context.stdout(JSON.stringify(entries.map(({ snapshot }) => snapshot)) + "\n")
    return 0
  }
  const now = (context.clock ?? systemClock).now()
  for (const { snapshot, record } of entries) {
    let age = 0
    try { age = Math.max(0, Math.floor((now - statSync(record).mtimeMs) / 1000)) } catch { age = 0 }
    const budgets = [
      typeof snapshot.continuations === "number" && snapshot.continuations > 0 ? " continuations=" + snapshot.continuations : "",
      typeof snapshot.steers === "number" && snapshot.steers > 0 ? " steers=" + snapshot.steers : "",
    ].join("")
    context.stdout(snapshot.id + " " + snapshot.execution_state + " " + humanAge(age) + " " + snapshot.worktree + budgets + "\n")
  }
  return 0
}

function ack(ids: string[], context: CampaignContext): number {
  if (!ids.length) throw new CampaignError(USAGE.trimEnd())
  const file = ackedFile(context.env), directory = dirname(file)
  mkdirSync(directory, { recursive: true, mode: 0o700 })
  chmodSync(directory, 0o700)
  const merged = [...new Set([...readAcked(context.env), ...ids.filter(Boolean)])].sort()
  const temporary = file + "." + process.pid
  writeFileSync(temporary, merged.map((id) => id + "\n").join(""), { mode: 0o600 })
  renameSync(temporary, file)
  return 0
}

export async function campaign(arguments_: string[], context: CampaignContext): Promise<number> {
  const [command, ...rest] = arguments_
  try {
    switch (command) {
      case "wait": return await wait(rest, context)
      case "ack": return ack(rest, context)
      case "list": return await list(rest, context)
      default: throw new CampaignError(USAGE.trimEnd())
    }
  } catch (error) {
    if (!(error instanceof CampaignError)) throw error
    context.stderr(error.message + "\n")
    return error.status
  }
}
