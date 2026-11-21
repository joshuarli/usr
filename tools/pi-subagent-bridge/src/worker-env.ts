import { execFileSync } from "node:child_process"
import { existsSync } from "node:fs"
import { basename, dirname, join } from "node:path"
import { ADMITTING_PARENT_ENV } from "./session.ts"

/** Coordinator enrollment and transport settings never enter scoped worker processes. */
export function workerEnvironment(source: NodeJS.ProcessEnv = process.env): NodeJS.ProcessEnv {
  const env: NodeJS.ProcessEnv = { ...source, USR_SCOPED_WORKER: "1" }
  delete env[ADMITTING_PARENT_ENV]
  stripIntercomEnvironment(env)
  return env
}

/** Also protect direct SDK worker launches and everything they subsequently spawn. */
export function stripIntercomEnvironment(env: NodeJS.ProcessEnv): void {
  for (const key of Object.keys(env)) {
    if (key.startsWith("AGENT_INTERCOM_") || key.startsWith("PI_INTERCOM_")) delete env[key]
  }
}

/** Contributor models may permit training on code and prompts. A repo marker or
 * explicit deny environment blocks all known contributor-backed Pi/FX lanes.
 * The marker is at the primary repository root, not the worker worktree.
 */
export function contributorAllowed(workerDirectory: string, env: NodeJS.ProcessEnv = process.env): boolean {
  if (env.USR_CONTRIBUTOR_MODE === "deny") return false
  try {
    // Git's common dir points to the primary repository even from linked worktrees.
    const common = execFileSync("git", ["-C", workerDirectory, "rev-parse",
      "--path-format=absolute", "--git-common-dir"], {
      encoding: "utf8", timeout: 2000, stdio: ["ignore", "pipe", "ignore"],
    }).trim()
    if (basename(common) !== ".git") return false
    return !existsSync(join(dirname(common), ".agents/no-contributor"))
  } catch {
    // Unknown repository provenance cannot authorize uploading private code.
    return false
  }
}

export function contributorModel(provider: string, model: string): boolean {
  return model.toLowerCase().includes("contributor")
}
