import { changes, currentBranch, laneHead, outside } from "./git.ts"
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
