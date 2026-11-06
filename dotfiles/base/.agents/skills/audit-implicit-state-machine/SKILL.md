---
name: audit-implicit-state-machine
description: "Use for /audit-implicit-state-machine: inventory lifecycles a codebase or path manages through flags, nullable fields, loose strings, or parallel collections, and report only those whose invalid states are reachable or force guards on every caller. Skip fixing them (use make-invalid-states-unrepresentable, lifecycle-concurrency, or durable-state) and single-type reviews."
disable-model-invocation: true
---

# Audit Implicit State Machines

An implicit state machine is a lifecycle that the code tracks through flags, nullable fields, loose strings, closure variables, or parallel collections instead of one explicit enum or union. This audit is useful only when it reports defects. A list of representations that could be tidier is not useful. Audit the requested scope, and make no code change.

## Find candidates

Look for these shapes:

- **Exclusive flags:** booleans or nullables that should never be set at the same time (`loading` and `error`, two open overlays).
- **Dependent fields:** a field whose presence depends on another field's value (`status`, `result?`, `error?`, `finished_at?`).
- **Loose persisted state:** a lifecycle stored as free text or as several columns in a database, file, or wire payload, with no constraint that rejects bad combinations.
- **Split async state:** one lifecycle spread across a pending map, a timer map, an in-flight promise or task, a generation counter, or an abort handle.
- **Closure state:** a multi-step interaction tracked in local variables that event handlers mutate.

To find them, follow lifecycle verbs (open, close, start, finish, cancel, retry, commit, dispose) and guards that repeat in several places. Do not assume a repository has a given subsystem.

## Keep a finding only with evidence

For each candidate, read the writers and the readers of every field involved. Then put the candidate in one of three classes:

1. **Reachable defect:** show the sequence of events that reaches the invalid state and what the user or caller then sees. Cite each step as `path:line`. A test or a run that reproduces it is better evidence than a reading of the code.
2. **Guard tax:** no invalid state is reachable, but the invariant is enforced only by checks that callers repeat. Cite the checks and count them. If one caller got a check wrong, the finding is a reachable defect.
3. **Representation only:** the type is looser than the domain, but one owner keeps the invariant. Drop this class from the report, or list it as one line at the end.

A finding is not evidence if it says "can", "risking", or "if ... leaked" and gives no trigger. Do not report a state-space count (such as "512 combinations") unless the bad combinations can actually be produced. Check whether an explicit state type already exists and the problem is only that code copies it into flags. If so, the fix is to use that type, not to create another one. Keep independent dimensions as independent fields. `dirty` and `pinned` do not form one state machine.

Before you file a finding, check `TODO.md`, the RFCs, and the tests. If the finding overlaps an existing ticket, extend that ticket.

## Report

Group findings by root cause, not by file. Give each finding:

- where the fields are and where the transitions happen;
- the real states and the events that move between them;
- the evidence class, with the trigger sequence or the guard sites;
- the smallest fix, and the skill that applies it: `make-invalid-states-unrepresentable` for types, `lifecycle-concurrency` for tasks, timers, and cancellation, `durable-state` for persisted state.

Rank findings with the priority definitions in `todo`. A guard tax alone is P3 at most. Representation-only items get no ticket. File tickets only when asked, and then follow `todo`.

**Report:** the scope, the findings ranked with their evidence class, the representation-only items you dropped (one line each), what you did not read or run, and any tickets filed.
