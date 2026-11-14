import test from "node:test"
import assert from "node:assert/strict"
import type { Command } from "../src/commands.ts"
import type { CommandRun } from "../src/command.ts"
import type { LaunchRequest, WriteAccess } from "../src/launch.ts"
import type { CliPin, PiSelection, RootPlan } from "../src/policy.ts"
import type { Execution, PiFallbackPlan, Target } from "../src/session.ts"

declare const RUN: CommandRun
declare const PIN: CliPin
declare const PI: PiSelection
declare const SCOPE: Extract<Command, { name: "start" }>["scope"]

export function witnesses(): void {
  const validProcess = { kind: "process", executor: "codex", selection: PIN, run: RUN } satisfies Execution
  // @ts-expect-error an active process execution needs its selection
  const noSelection = { kind: "process", executor: "codex", run: RUN } satisfies Execution

  // @ts-expect-error a process executes on a CLI executor, never on Pi
  const piProcess = { kind: "process", executor: "pi", selection: PIN, run: RUN } satisfies Execution

  const validPi = { kind: "pi", selection: PI, session_id: "ses" } satisfies Execution
  // @ts-expect-error a Pi execution needs its effort
  const noVariant = { kind: "pi", selection: { providerID: "p", id: "m" }, session_id: "ses" } satisfies Execution

  // @ts-expect-error a Pi execution holds a Pi selection, not a CLI pin
  const cliPinOnPi = { kind: "pi", selection: PIN, session_id: "ses" } satisfies Execution

  const validTransition = { kind: "transition", to: { executor: "command-code", selection: PIN } } satisfies Execution
  // @ts-expect-error a transition names its destination selection
  const noDestination = { kind: "transition", to: { executor: "command-code" } } satisfies Execution

  // @ts-expect-error a Pi destination needs a Pi selection
  const wrongDestination = { executor: "pi", selection: PIN } satisfies Target

  const validPlan = { kind: "fallback", codex: PIN, command: PIN, pi: [PI] } satisfies RootPlan
  // @ts-expect-error a fallback plan needs at least one Pi destination
  const emptyPi = { kind: "fallback", codex: PIN, command: PIN, pi: [] } satisfies RootPlan

  // @ts-expect-error a Pi selection cannot occupy the codex slot
  const piInCodexSlot = { kind: "fallback", codex: PI, command: PIN, pi: [PI] } satisfies RootPlan

  const resolvedPiFallback = { kind: "fallback", codex: PIN, command: PIN, pi: [PI] } satisfies PiFallbackPlan
  // @ts-expect-error a plan whose Pi destinations are unresolved cannot be passed to the Pi fallback
  const unresolvedPiFallback = { kind: "fallback-unresolved-pi", codex: PIN, command: PIN } satisfies PiFallbackPlan

  // @ts-expect-error an extra executor kind is not an arrangement
  const extraExecutor = { kind: "fallback", codex: PIN, command: PIN, pi: [PI], antigravity: PIN } satisfies RootPlan

  // @ts-expect-error a plan is named slots, not an ordered list of routes
  const routeList = { kind: "fallback", routes: [PIN] } satisfies RootPlan

  const validRequest = { directory: "/w", logDirectory: "/l", prompt: "p", selection: PIN, access: { kind: "read-only" } } satisfies LaunchRequest
  // @ts-expect-error a launch request needs its selection
  const noRequestSelection = { directory: "/w", logDirectory: "/l", prompt: "p", access: { kind: "read-only" } } satisfies LaunchRequest

  // @ts-expect-error Antigravity launches are never read-only
  const readOnlyAntigravity = { ...validRequest, access: { kind: "read-only" } } satisfies LaunchRequest<WriteAccess>

  const validStart = { name: "start", cwd: "/w", title: "t", tier: "scout", scope: SCOPE, brief: "b" } satisfies Command
  // @ts-expect-error a start command needs its scope
  const noScope = { name: "start", cwd: "/w", title: "t", tier: "scout", brief: "b" } satisfies Command

  void [validProcess, noSelection, piProcess, validPi, noVariant, cliPinOnPi, validTransition, noDestination,
    wrongDestination, validPlan, emptyPi, resolvedPiFallback, unresolvedPiFallback, piInCodexSlot, extraExecutor, routeList, validRequest, noRequestSelection,
    readOnlyAntigravity, validStart, noScope]
}

test("type witnesses are checked by the compiler, not at runtime", () => {
  assert.equal(typeof witnesses, "function")
})
