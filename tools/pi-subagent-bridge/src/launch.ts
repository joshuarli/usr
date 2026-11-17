import type { CliPin } from "./policy.ts"

export type ReadOnlyAccess = { readonly kind: "read-only" }
export type WriteAccess = { readonly kind: "write" }
export type Access = ReadOnlyAccess | WriteAccess
export type PlannedRun = { output: string; errors: string; started_at: string }

export type LaunchRequest<A extends Access = Access> = {
  readonly directory: string
  readonly logDirectory: string
  readonly prompt: string
  readonly selection: CliPin
  readonly access: A
  readonly resume?: string
  readonly planned_run?: PlannedRun
}

export function plannedCommand(executable: string, args: string[], planned?: PlannedRun): { executable: string; args: string[] } {
  return planned ? { executable: "/bin/sh", args: ["-c", 'printf "%s\\n" "$$" > "$1" || exit 1; shift; exec "$@"', "bridge-launch", planned.output + ".pid", executable, ...args] } : { executable, args }
}
