import { readStateDir } from "./git.ts"
import { inspectStored, type InspectionDeps, type Snapshot } from "./inspect.ts"
import { isSessionId } from "./session.ts"

export const WATCH_POLL_MS = 15_000
const TEXT_LIMIT = 2000
const FINISHED = ["succeeded", "failed", "turn_limit", "cancelled"]
const GONE = ["interrupted", "unknown_or_interrupted"]

export const EXIT_STALLED = 2
export const EXIT_GONE = 3
export const EXIT_UNINSPECTABLE = 4

export type Clock = {
  now: () => number
  sleep: (milliseconds: number) => Promise<void>
}
export const systemClock: Clock = {
  now: () => Date.now(),
  sleep: (milliseconds) => new Promise((resolve) => setTimeout(resolve, milliseconds)),
}
export type WatchOptions = { idleMinutes: number; stateOnly: boolean; pollMs?: number; clock?: Clock }

export function text(value: unknown): string {
  if (value === null || value === undefined) return ""
  return typeof value === "string" ? value : JSON.stringify(value)
}

function activityMs(snapshot: Snapshot): number | null {
  return snapshot.last_activity === "unknown" ? null : Date.parse(snapshot.last_activity)
}

export async function watchSession(
  path: string, id: string, options: WatchOptions, deps: InspectionDeps, stdout: (text: string) => void,
): Promise<number> {
  const clock = options.clock ?? systemClock, pollMs = options.pollMs ?? WATCH_POLL_MS
  const refuse = (reason: string) => {
    if (options.stateOnly) { stdout("unknown\n"); return 0 }
    stdout(id + ": " + reason + "; inspect worker_status\n")
    return EXIT_UNINSPECTABLE
  }
  if (!isSessionId(id)) return refuse("not a worker session ID")
  let directory: string
  try { directory = readStateDir(path) } catch { return refuse("not a Git repository: " + path) }
  for (;;) {
    const snapshot = await inspectStored(directory, id, deps)
    const state = snapshot.execution_state
    if (options.stateOnly) { stdout(state + "\n"); return 0 }
    if (state === "unknown" || state.startsWith("blocked"))
      return refuse(snapshot.reason ?? (text(snapshot.error) || state))
    if (FINISHED.includes(state)) {
      const evidence = snapshot.last_assistant_text === "unknown" ? null : snapshot.last_assistant_text
      stdout("finished: " + state + "\n" + (text(evidence) || text(snapshot.error)).slice(0, TEXT_LIMIT) + "\n")
      return 0
    }
    if (GONE.includes(state)) {
      stdout("exited without terminal result (pid " + snapshot.pid + "); last event: " + snapshot.last_event + "\n")
      return EXIT_GONE
    }
    const activity = activityMs(snapshot)
    if (activity !== null) {
      const quietSeconds = Math.max(0, Math.floor((clock.now() - activity) / 1000))
      if (quietSeconds >= options.idleMinutes * 60) {
        stdout("stalled: no executor output for " + Math.floor(quietSeconds / 60) + " min; last event: " + snapshot.last_event + "\n")
        return EXIT_STALLED
      }
    }
    await clock.sleep(pollMs)
  }
}
