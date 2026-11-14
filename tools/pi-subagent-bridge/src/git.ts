import { execFileSync } from "node:child_process"
import { mkdirSync } from "node:fs"
import { dirname, join } from "node:path"

function readOnlyEnv(): NodeJS.ProcessEnv {
  return { ...process.env, GIT_OPTIONAL_LOCKS: "0" }
}

/** Git reads must not refresh the index, so inspection never writes to the repository. */
export function git(cwd: string, ...args: string[]): string {
  return execFileSync("git", ["-C", cwd, ...args], { encoding: "utf8", timeout: 10000, env: readOnlyEnv(), stdio: "pipe" }).trim()
}
export function changes(cwd: string, base: string): string[] {
  const options = { encoding: "utf8", env: readOnlyEnv(), stdio: "pipe" } as const
  const diff = execFileSync("git", ["-C", cwd, "diff", "--no-renames", "--name-only", "-z", base, "--"], options)
  const newFiles = execFileSync("git", ["-C", cwd, "ls-files", "--others", "--exclude-standard", "-z"], options)
  return [...new Set((diff + newFiles).split("\0").filter(Boolean))].sort()
}
export function outside(paths: string[], owned: string[]): string[] {
  return paths.filter((p) => !owned.some((w) => w.endsWith("/") ? p.startsWith(w) : p === w))
}

export function readStateDir(cwd: string): string {
  const root = dirname(git(cwd, "rev-parse", "--path-format=absolute", "--git-common-dir"))
  return join(root, ".work", "worker-bridge")
}
export function stateDir(cwd: string): string {
  const dir = readStateDir(cwd)
  execFileSync("git", ["-C", dirname(dirname(dir)), "check-ignore", "-q", ".work/worker-bridge/state"],
    { stdio: "ignore", timeout: 10000 })
  mkdirSync(dir, { recursive: true, mode: 0o700 })
  return dir
}
