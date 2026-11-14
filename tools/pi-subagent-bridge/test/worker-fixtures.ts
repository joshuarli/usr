import { execFileSync, spawn, type ChildProcess } from "node:child_process"
import { once } from "node:events"
import { appendFileSync, mkdirSync, mkdtempSync, readdirSync, readFileSync, realpathSync, rmSync, statSync, writeFileSync } from "node:fs"
import { tmpdir } from "node:os"
import { join } from "node:path"
import type { OpenCodePort } from "../src/bridge.ts"
import { antigravityResult } from "../src/antigravity.ts"
import { codexResult } from "../src/codex.ts"
import { commandResult } from "../src/command.ts"
import type { InspectionDeps } from "../src/inspect.ts"
import { decodeSession, encodeSession } from "../src/session.ts"

export const PI_MODEL = { providerID: "opencode-go", id: "deepseek-v4.1-flash", variant: "high" }
export const PI_ID = "ses_0123456789abcdef0123456789abcdef"

export function git(cwd: string, ...args: string[]): string {
  return execFileSync("git", ["-C", cwd, ...args], { encoding: "utf8" }).trim()
}

export type Repo = { root: string; cwd: string; directory: string; base: string }

export class Scratch {
  readonly path = realpathSync(mkdtempSync(join(tmpdir(), "usr-inspect-")))
  private children: ChildProcess[] = []
  private repos = 0

  repo(name = "repo-" + ++this.repos): Repo {
    const root = join(this.path, name)
    mkdirSync(root)
    git(root, "init", "-q")
    git(root, "config", "user.email", "test@example.com")
    git(root, "config", "user.name", "Test")
    writeFileSync(join(root, "README"), "original\n")
    git(root, "add", "README")
    git(root, "commit", "-qm", "init")
    appendFileSync(join(root, ".git", "info", "exclude"), "\n/.work/\n")
    mkdirSync(join(root, ".work", "wt"), { recursive: true })
    const cwd = join(root, ".work", "wt", "a")
    git(root, "worktree", "add", "-qb", "lane-" + name, cwd)
    const directory = join(root, ".work", "worker-bridge")
    mkdirSync(directory, { recursive: true })
    return { root, cwd, directory, base: git(cwd, "rev-parse", "HEAD") }
  }

  alive(): number {
    const child = spawn("sleep", ["600"], { stdio: "ignore" })
    this.children.push(child)
    return child.pid!
  }

  async gone(): Promise<number> {
    const child = spawn("sh", ["-c", "exit 0"], { stdio: "ignore" })
    await once(child, "exit")
    return child.pid!
  }

  async stop(pid: number): Promise<void> {
    const child = this.children.find((candidate) => candidate.pid === pid)!
    child.kill()
    await once(child, "exit")
  }

  close(): void {
    for (const child of this.children) child.kill()
    rmSync(this.path, { recursive: true, force: true })
  }
}

export function sessionId(n: number): string {
  return "usrw_01234567-89ab-cdef-0123-4567890000" + String(n).padStart(2, "0")
}

export function runFor(repo: Repo, name: string, pid: number, extra: Record<string, unknown> = {}) {
  return {
    pid, output: join(repo.directory, name + ".ndjson"), errors: join(repo.directory, name + ".stderr"),
    started_at: "2026-11-09T00:00:00.000Z", ...extra,
  }
}

export function writeSession(repo: Repo, n: number, fields: Record<string, unknown> = {}): string {
  const id = sessionId(n)
  const record = {
    schema_version: 1, id, cwd: repo.cwd, title: "Lane " + n, task: "Do the task", tier: "worker",
    scope: { base_revision: repo.base, writable_paths: ["README"], acceptance_proof: "Run the check", attempt_limit: 2, stop_on: "Scope change" },
    attempts: 1, backend: "command-code", command_model: "deepseek/deepseek-v4.1-flash", command_effort: "high",
    codex_model: "gpt-6.1-terra", codex_effort: "medium", execution_order: "codex-first", pi_candidates: [PI_MODEL],
    ...fields,
  }
  writeFileSync(join(repo.directory, id + ".json"), JSON.stringify(record))
  return id
}

/** Rewrite a stored v1 record in the current format, exactly as the bridge would save it. */
export function migrate(repo: Repo, id: string): string {
  const path = join(repo.directory, id + ".json")
  const session = decodeSession(JSON.parse(readFileSync(path, "utf8")), repo.cwd, id)
  writeFileSync(path, JSON.stringify(encodeSession(session)))
  return id
}

export function writeLog(path: string, lines: Array<string | Record<string, unknown>>): void {
  writeFileSync(path, lines.map((line) => (typeof line === "string" ? line : JSON.stringify(line)) + "\n").join(""))
}

export function commandLane(repo: Repo, n: number, pid: number, lines: Array<string | Record<string, unknown>>,
  fields: Record<string, unknown> = {}): string {
  const run = runFor(repo, "lane-" + n, pid)
  writeLog(run.output, lines)
  return writeSession(repo, n, { command_run: run, ...fields })
}

export const toolQueued = (description: string) =>
  ({ type: "event", event: { type: "tool_queued", toolName: "shell_command", input: { description } } })
export const commandResultLine = (subtype: string, extra: Record<string, unknown> = {}) =>
  ({ type: "result", subtype, ...extra })

export function writePiChild(repo: Repo, pid: number, result?: Record<string, unknown>): { output: string; errors: string } {
  const output = join(repo.directory, "pi.result.json"), errors = join(repo.directory, "pi.stderr")
  const child = {
    id: PI_ID, title: "usr-worker: Pi lane", cwd: repo.cwd, model: PI_MODEL,
    metadata: { usr_worker_v1: { directory: repo.cwd, model: PI_MODEL } }, readOnly: false,
    run: { pid, output, errors },
  }
  writeFileSync(join(repo.directory, PI_ID + ".pi.json"), JSON.stringify(child))
  writeFileSync(errors, "pi host log\n")
  if (result) writeFileSync(output, JSON.stringify(result))
  else rmSync(output, { force: true })
  return { output, errors }
}

export function piSession(repo: Repo, n: number, fields: Record<string, unknown> = {}): string {
  return writeSession(repo, n, {
    backend: "pi", pi_id: PI_ID, primary_model: PI_MODEL, pi_candidates: [], ...fields,
  })
}

export const piSuccess = (text = "SDK proof\nACCEPTANCE: met") =>
  ({ state: "succeeded", text, error: null, usage: null, sessionFile: "/tmp/pi-session.jsonl", runId: "run-1" })

export function unusedApi(): OpenCodePort {
  return new Proxy({}, { get() { throw new Error("the Pi API is not used here") } }) as OpenCodePort
}

export function realDeps(api: OpenCodePort = unusedApi()): InspectionDeps {
  return { api, command: { status: commandResult }, codex: { status: codexResult }, antigravity: { status: antigravityResult } }
}

export function collect() {
  const chunks: string[] = []
  return { write: (text: string) => { chunks.push(text) }, text: () => chunks.join("") }
}

export type TreeEntry = { path: string; kind: "file" | "directory"; mtimeMs: number; content?: string }
export function treeOf(directory: string, prefix = ""): TreeEntry[] {
  const entries: TreeEntry[] = []
  for (const name of readdirSync(directory).sort()) {
    const path = join(directory, name), info = statSync(path)
    if (info.isDirectory()) {
      entries.push({ path: prefix + name, kind: "directory", mtimeMs: info.mtimeMs })
      entries.push(...treeOf(path, prefix + name + "/"))
    } else {
      entries.push({ path: prefix + name, kind: "file", mtimeMs: info.mtimeMs, content: readFileSync(path, "utf8") })
    }
  }
  return entries
}
