/** Cross-process, crash-conservative ownership of an active writer worktree. */
import { createHash } from "node:crypto"
import { closeSync, lstatSync, mkdirSync, openSync, readFileSync, rmdirSync, unlinkSync, writeSync, fsyncSync } from "node:fs"
import { join } from "node:path"

type Owner = { version: 1; cwd: string; session_id: string }

export function worktreeLeasePath(stateDir: string, cwd: string): string {
  return join(stateDir, ".active-worktree-" + createHash("sha256").update(cwd).digest("hex"))
}

function readOwner(stateDir: string, cwd: string): Owner | null {
  const lease = worktreeLeasePath(stateDir, cwd)
  try {
    const info = lstatSync(lease)
    if (!info.isDirectory() || info.isSymbolicLink()) throw new Error("Unrecognized worktree lease path; inspect before retrying")
  } catch (error) {
    if (error instanceof Error && "code" in error && error.code === "ENOENT") return null
    throw error
  }
  let value: unknown
  try {
    value = JSON.parse(readFileSync(join(lease, "owner.json"), "utf8"))
  } catch {
    throw new Error("Incomplete worktree admission lease; inspect before retrying")
  }
  if (!value || typeof value !== "object" || Array.isArray(value))
    throw new Error("Invalid worktree admission lease")
  const owner = value as Record<string, unknown>
  if (owner.version !== 1 || owner.cwd !== cwd || typeof owner.session_id !== "string" ||
      !/^usrw_[0-9a-f-]{36}$/.test(owner.session_id))
    throw new Error("Invalid worktree admission lease")
  return owner as Owner
}

export function activeWorktreeOwner(stateDir: string, cwd: string): string | null {
  return readOwner(stateDir, cwd)?.session_id ?? null
}

export function claimWorktree(stateDir: string, cwd: string, sessionID: string): void {
  if (!/^usrw_[0-9a-f-]{36}$/.test(sessionID)) throw new Error("Invalid worker session ID")
  const lease = worktreeLeasePath(stateDir, cwd)
  try {
    mkdirSync(lease, { mode: 0o700 })
  } catch (error) {
    if (error instanceof Error && "code" in error && error.code === "EEXIST") {
      const holder = activeWorktreeOwner(stateDir, cwd)
      throw new Error("Worktree already has active worker " + (holder ?? "(unidentified)") + "; inspect it before starting another")
    }
    throw error
  }
  const file = join(lease, "owner.json")
  try {
    const fd = openSync(file, "wx", 0o600)
    try {
      writeSync(fd, JSON.stringify({ version: 1, cwd, session_id: sessionID }) + "\n")
      fsyncSync(fd)
    } finally { closeSync(fd) }
  } catch (error) {
    // This process created the lease. If admission metadata cannot be written,
    // remove only its own empty/incomplete directory, not someone else's lease.
    try { unlinkSync(file) } catch { /* no owner yet */ }
    rmdirSync(lease)
    throw error
  }
}

export function ensureWorktree(stateDir: string, cwd: string, sessionID: string): void {
  const holder = activeWorktreeOwner(stateDir, cwd)
  if (holder === sessionID) return
  if (holder !== null) throw new Error("Worktree is active for worker " + holder)
  claimWorktree(stateDir, cwd, sessionID)
}

export function releaseWorktree(stateDir: string, cwd: string, sessionID: string): boolean {
  const holder = activeWorktreeOwner(stateDir, cwd)
  if (holder === null) return false
  if (holder !== sessionID) throw new Error("Refusing to release another worker's active lease: " + holder)
  const lease = worktreeLeasePath(stateDir, cwd)
  unlinkSync(join(lease, "owner.json"))
  rmdirSync(lease)
  return true
}
