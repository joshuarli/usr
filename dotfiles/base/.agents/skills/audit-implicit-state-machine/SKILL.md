---
name: audit-implicit-state-machine
description: "Use for /audit-implicit-state-machine: against a stated domain model, find the few lifecycles whose loose representation (flags, nullable fields, loose strings, parallel collections) lets the type checker accept states the domain forbids, and file each with a witness program the proposed type would reject. Skip fixing them (use make-invalid-states-unrepresentable, lifecycle-concurrency, or durable-state) and single-type reviews."
disable-model-invocation: true
metadata:
  opencode/autoinvoke: "false"
---

# Audit Implicit State Machines

Look at enough code without a domain model and everything starts to look like a state machine. "This would read more like a state machine" is a matter of taste, so it is not a finding. A finding is a value or transition that the domain forbids, that the type checker accepts today, and that a stronger type would reject. Audit the requested scope. Make no code change other than filing tickets.

## Name the domain model first

Before you look for candidates, write down the domain model at the level of abstraction you are auditing: the entities, their states, and the events that move between them. Take it from evidence that exists independently of the code's shape. Good sources are a spec, an RFC, a persisted or wire format, documented behavior, tests that state the rules, or the user-visible behavior. Cite each source.

If no such model exists for a lifecycle, do not invent one from the fields you happen to find. Report the gap in one line and move on. Keep independent dimensions independent: if every combination of `dirty` and `pinned` is meaningful, they are not one state machine.

## Find candidates

Start where the checker is weakest and the stakes are highest. Do not start where the code looks untidy.

- **Unchecked boundaries:** persisted records, wire payloads, and CLI or tool arguments that are decoded with casts, `any`, or partial checks, and then drive decisions.
- **Dependent fields:** a field whose presence depends on another field's value (`status`, `result?`, `error?`), followed by a runtime "missing X" check or an unwrap.
- **Exclusive flags:** booleans or nullables the domain says can never be set together.
- **Split async state:** one lifecycle spread across a pending map, a timer, an in-flight task, a generation counter, or an abort handle.
- **Loose closed sets:** strings or integers that stand for a finite set and are compared by value in several places.

Follow the lifecycle verbs (start, finish, cancel, retry, commit, dispose) and the guards that repeat. Do not assume a repository has a given subsystem.

## Keep a finding only with checker evidence

For each candidate, read the writers and readers of every field involved. Keep it only if you can write both of these:

1. **Witness:** a short program, in the project's language, that constructs the forbidden value or performs the forbidden transition and that the type checker accepts today. Cite the declaration that permits it as `path:line`. If you cannot write the witness, drop the candidate.
2. **Rejection:** the smallest type change under which the checker rejects that witness, together with the runtime checks, casts, and assertions that change would let the code delete (`path:line` each).

Then classify it:

- **Reachable defect:** real code paths produce the witness state. Show the event sequence and what the caller then sees. A failing test or a reproduction beats a reading.
- **Guard tax:** no path produces it today, but callers prevent it with repeated checks. Count and cite the checks. If one caller gets the check wrong, it is a reachable defect.
- **Representation only:** one owner keeps the invariant and nothing else would be deleted. Drop it, or list it in one line.

A finding that says "can", "risking", or "if ... leaked" and gives no witness is not evidence. A count of unconstrained combinations is not a finding unless the bad ones can actually be built. If an explicit state type already exists and code copies it into flags, the fix is to use that type.

## Don't be greedy

Report at most three findings per audit, ranked by severity: reachable defects at trust boundaries first, then reachable defects elsewhere, then guard tax. Each finding must be fixable in one small change that leaves the code compiling. Do not propose a redesign that has to land all at once. List the remaining candidates in one line each, so the next pass can pick them up.

Before you file, check `TODO.md`, the RFCs, and the tests. If a finding overlaps an existing ticket, extend that ticket.

## Report

Group findings by root cause, not by file. Give each finding:

- its domain model source;
- the witness program and the declaration that admits it;
- the evidence class, with the trigger sequence or the guard sites;
- the proposed type, the checks it lets the code delete, and the skill that applies it: `make-invalid-states-unrepresentable` for types, `lifecycle-concurrency` for tasks, timers, and cancellation, `durable-state` for persisted state.

The witness becomes the fix's regression test: an expected-error check that fails if the type is ever loosened again. Rank with the priority definitions in `todo`. A guard tax alone is P3 at most. File a ticket for every finding that survives, following `todo`, without waiting to be asked.

**Report:** the scope, the domain models used and their sources, the findings ranked with their witnesses, the deferred candidates, the lifecycles skipped for lack of a model, what you did not read or run, and any tickets filed.
