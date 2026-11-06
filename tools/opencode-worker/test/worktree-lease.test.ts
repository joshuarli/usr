import test from "node:test"
import assert from "node:assert/strict"
import { randomUUID } from "node:crypto"
import { mkdtempSync, mkdirSync, rmSync, symlinkSync, writeFileSync } from "node:fs"
import { tmpdir } from "node:os"
import { join } from "node:path"
import { activeWorktreeOwner, claimWorktree, ensureWorktree, releaseWorktree, worktreeLeasePath } from "../src/worktree-lease.ts"

const id = () => "usrw_" + randomUUID()
function fixture() {
  const root = mkdtempSync(join(tmpdir(), "usr-lease-"))
  const cwd = join(root, "wt-a")
  const state = join(root, "state")
  mkdirSync(cwd); mkdirSync(state)
  return { root, cwd, state, close: () => rmSync(root, { recursive: true, force: true }) }
}

test("same-worktree lease is exclusive, persistent, and owner-scoped", () => {
  const f = fixture()
  try {
    const a = id(), b = id()
    assert.equal(activeWorktreeOwner(f.state, f.cwd), null)
    claimWorktree(f.state, f.cwd, a)
    assert.equal(activeWorktreeOwner(f.state, f.cwd), a)
    assert.throws(() => claimWorktree(f.state, f.cwd, b), /already has active worker/)
    assert.throws(() => ensureWorktree(f.state, f.cwd, b), /active for worker/)
    ensureWorktree(f.state, f.cwd, a)
    assert.throws(() => releaseWorktree(f.state, f.cwd, b), /another worker/)
    assert.equal(releaseWorktree(f.state, f.cwd, a), true)
    assert.equal(releaseWorktree(f.state, f.cwd, a), false)
    claimWorktree(f.state, f.cwd, b)
    assert.equal(activeWorktreeOwner(f.state, f.cwd), b)
  } finally { f.close() }
})

test("leases are keyed by worktree, not by repository", () => {
  const f = fixture()
  try {
    const other = join(f.root, "wt-b"), a = id(), b = id()
    mkdirSync(other)
    claimWorktree(f.state, f.cwd, a)
    claimWorktree(f.state, other, b)
    assert.equal(activeWorktreeOwner(f.state, f.cwd), a)
    assert.equal(activeWorktreeOwner(f.state, other), b)
  } finally { f.close() }
})

test("incomplete and symlinked lease directories fail closed", () => {
  const f = fixture()
  try {
    const lease = worktreeLeasePath(f.state, f.cwd)
    mkdirSync(lease)
    assert.throws(() => claimWorktree(f.state, f.cwd, id()), /Incomplete worktree admission lease/)
    writeFileSync(join(lease, "owner.json"), "not-json")
    assert.throws(() => activeWorktreeOwner(f.state, f.cwd), /Incomplete worktree admission lease/)
    assert.throws(() => releaseWorktree(f.state, f.cwd, id()), /Incomplete worktree admission lease/)
    rmSync(lease, { recursive: true })
    const foreign = join(f.root, "foreign")
    mkdirSync(foreign)
    symlinkSync(foreign, lease, "dir")
    assert.throws(() => activeWorktreeOwner(f.state, f.cwd), /Unrecognized worktree lease path/)
  } finally { f.close() }
})
