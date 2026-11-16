import { randomUUID } from "node:crypto"
import { readFileSync, writeFileSync } from "node:fs"
import { join, resolve } from "node:path"
import { changes, currentBranch, laneHead, outside, stateDir, readStateDir } from "./git.ts"
import { isRecord } from "./scope.ts"

export const SCOPE_CHECK_USAGE = "usage: pi-subagent-bridge scope-check CWD SCOPE_JSON_FILE [BRANCH]"

export type ScopeCheck = {
  readonly head: string
  readonly branch: string | null
  readonly commits_since_base: number
  readonly head_on_lane: boolean
  readonly drift: string | null
  readonly changed_paths: readonly string[]
  readonly out_of_scope_paths: readonly string[]
  readonly in_scope: boolean
}
export type NativeLane = { id: string; kind: "native"; cwd: string; branch: string | null; scope: unknown; title: string; registered_at: string; last_scope_check: ScopeCheck | null }
const NATIVE_ID = /^usrn_[a-f0-9-]{36}$/
export function isNativeId(id: string): boolean { return NATIVE_ID.test(id) }
export function registerNative(cwd: string, scope: unknown, title: string, branch?: string): NativeLane {
  const absolute = resolve(cwd)
  scopeFields(scope)
  if (!title.trim() || title.length > 100) throw new Error("Invalid native lane title")
  const lane: NativeLane = { id: "usrn_" + randomUUID(), kind: "native", cwd: absolute,
    branch: branch ?? currentBranch(absolute), scope, title, registered_at: new Date().toISOString(), last_scope_check: null }
  writeFileSync(join(stateDir(absolute), lane.id + ".json"), JSON.stringify(lane), { mode: 0o600, flag: "wx" })
  return lane
}
export function checkNative(root: string, id: string): ScopeCheck {
  if (!isNativeId(id)) throw new Error("Invalid native lane ID")
  const path = join(readStateDir(resolve(root)), id + ".json")
  const lane = JSON.parse(readFileSync(path, "utf8")) as NativeLane
  if (lane.id !== id || lane.kind !== "native") throw new Error("Invalid native lane record")
  const result = scopeCheck(lane.cwd, lane.scope, lane.branch ?? undefined)
  lane.last_scope_check = result
  writeFileSync(path, JSON.stringify(lane), { mode: 0o600 })
  return result
}

function scopeFields(value: unknown): { base: string; writable: string[] } {
  if (!isRecord(value)) throw new Error("scope must be a JSON object")
  const base = value.base_revision, writable = value.writable_paths
  if (typeof base !== "string" || !/^[0-9a-f]{40}$/.test(base)) throw new Error("scope base_revision must be a full commit hash")
  if (!Array.isArray(writable) || !writable.every(path => typeof path === "string" && path.length > 0))
    throw new Error("scope writable_paths must be an array of non-empty paths")
  return { base, writable }
}

/** The bridge's Git scope check for a lane the bridge did not admit, such as a harness-native subagent. */
export function scopeCheck(cwd: string, scope: unknown, branch?: string): ScopeCheck {
  const { base, writable } = scopeFields(scope)
  const lane = laneHead({ cwd, tier: "worker", lane_branch: branch ?? currentBranch(cwd), scope: { base_revision: base } })
  const changed_paths = changes(cwd, base)
  const out_of_scope_paths = outside(changed_paths, writable)
  return {
    head: lane.head, branch: currentBranch(cwd), commits_since_base: lane.commits_since_base,
    head_on_lane: lane.head_on_lane, drift: lane.drift, changed_paths, out_of_scope_paths,
    in_scope: lane.head_on_lane && out_of_scope_paths.length === 0,
  }
}
