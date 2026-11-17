import { execFileSync } from "node:child_process"
import { accessSync, constants, mkdirSync } from "node:fs"
import { dirname, join } from "node:path"
import { deadlineTimeout } from "./steer-deadline.ts"

function readOnlyEnv(): NodeJS.ProcessEnv {
  return { ...process.env, GIT_OPTIONAL_LOCKS: "0" }
}

/** Git reads must not refresh the index, so inspection never writes to the repository. */
export function git(cwd: string, ...args: string[]): string {
  return execFileSync("git", ["-C", cwd, ...args], { encoding: "utf8", timeout: deadlineTimeout(10000), env: readOnlyEnv(), stdio: "pipe" }).trim()
}
export function changes(cwd: string, base: string): string[] {
  const options = { encoding: "utf8", env: readOnlyEnv(), stdio: "pipe" } as const
  const diff = execFileSync("git", ["-C", cwd, "diff", "--no-renames", "--name-only", "-z", base, "--"], { ...options, timeout: deadlineTimeout(5000) })
  const newFiles = execFileSync("git", ["-C", cwd, "ls-files", "--others", "--exclude-standard", "-z"], { ...options, timeout: deadlineTimeout(5000) })
  return [...new Set((diff + newFiles).split("\0").filter(Boolean))].sort()
}
function available(program: string): boolean {
  return (process.env.PATH ?? "").split(":").some(path => {
    try { accessSync(join(path || ".", program), constants.X_OK); return true } catch { return false }
  })
}
function inspectionCommand(args: string[]): string {
  const nice = available("nice"), ionice = nice && process.platform === "linux" && available("ionice")
  const program = nice ? "nice" : "git"
  const prefix = nice ? ["-n", "19", ...(ionice ? ["ionice", "-c3"] : []), "git"] : []
  return execFileSync(program, [...prefix, ...args], { encoding: "utf8", timeout: deadlineTimeout(10000), env: readOnlyEnv(), stdio: "pipe" })
}
export function inspectionGit(cwd: string, ...args: string[]): string {
  return inspectionCommand(["-C", cwd, ...args]).trim()
}
export function inspectionChanges(cwd: string, base: string): string[] {
  const diff = inspectionCommand(["-C", cwd, "diff", "--no-renames", "--name-only", "-z", base, "--"])
  const newFiles = inspectionCommand(["-C", cwd, "ls-files", "--others", "--exclude-standard", "-z"])
  return [...new Set((diff + newFiles).split("\0").filter(Boolean))].sort()
}
/** A writable path owns itself and, as a directory, everything beneath it, with or without a trailing slash. */
export function outside(paths: string[], owned: string[]): string[] {
  return paths.filter((p) => !owned.some((w) => p === w || p.startsWith(w.endsWith("/") ? w : `${w}/`)))
}

export function readStateDir(cwd: string): string {
  const root = dirname(inspectionGit(cwd, "rev-parse", "--path-format=absolute", "--git-common-dir"))
  return join(root, ".work", "worker-bridge")
}
export function stateDir(cwd: string): string {
  const dir = readStateDir(cwd)
  execFileSync("git", ["-C", dirname(dirname(dir)), "check-ignore", "-q", ".work/worker-bridge/state"],
    { stdio: "ignore", timeout: deadlineTimeout(10000) })
  mkdirSync(dir, { recursive: true, mode: 0o700 })
  return dir
}

/** The admitted branch is absent for detached worktrees and legacy sessions. */
export function currentBranch(cwd: string, probe = git): string | null {
  try { return probe(cwd, "symbolic-ref", "--quiet", "--short", "HEAD") }
  catch (error) {
    if ((error as { status?: number }).status === 1) return null
    throw error
  }
}

export function laneHead(s: { cwd: string; tier: string; lane_branch?: string | null; scope: { base_revision: string } }, probe = git) {
  const base = s.scope.base_revision, head = probe(s.cwd, "rev-parse", "HEAD")
  const commits_since_base = Number(probe(s.cwd, "rev-list", "--count", base + ".." + head))
  if (head === base) return { head, commits_since_base, head_on_lane: true, drift: null }
  let drift: string | null = null
  if (s.tier === "scout") drift = "scout HEAD changed from base"
  else if (!s.lane_branch) drift = "no admitted branch; HEAD must equal base"
  else if (currentBranch(s.cwd, probe) !== s.lane_branch) drift = "current branch differs from admitted branch " + s.lane_branch
  else {
    try { probe(s.cwd, "merge-base", "--is-ancestor", base, head) }
    catch (error) {
      if ((error as { status?: number }).status !== 1) throw error
      drift = "base revision is not an ancestor of HEAD"
    }
    if (!drift && probe(s.cwd, "rev-list", "--merges", base + ".." + head)) drift = "merge commit since base"
  }
  return { head, commits_since_base, head_on_lane: drift === null, drift }
}
