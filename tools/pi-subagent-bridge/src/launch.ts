import type { CliPin } from "./policy.ts"

export type ReadOnlyAccess = { readonly kind: "read-only" }
export type WriteAccess = { readonly kind: "write"; readonly network: boolean }
export type Access = ReadOnlyAccess | WriteAccess

export type LaunchRequest<A extends Access = Access> = {
  readonly directory: string
  readonly logDirectory: string
  readonly prompt: string
  readonly selection: CliPin
  readonly access: A
  readonly resume?: string
}
