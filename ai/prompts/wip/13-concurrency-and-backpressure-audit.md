# Concurrency, Cancellation, and Backpressure Audit

You are improving this codebase so task ownership, boundedness, synchronization, cancellation, and shutdown behavior are explicit.

The goal is predictable concurrency under load and failure.

Scope: threads/tasks, queues, channels, worker pools, locks, retries, cancellation, shutdown, and shared state.

Applicability: Apply this prompt only when the subsystem performs concurrent or background work whose ownership, boundedness, backpressure, or shutdown behavior matters. If the condition is materially absent, report that evidence and make no speculative changes.

Preserve: Existing valid behavior, public contracts, persisted data and formats, output, side effects, permissions, state transitions, and supported-platform semantics unless this request explicitly changes them.

Intentional changes: Only changes explicitly authorized by the invoking request; otherwise none.

If inspection shows that the relevant contract already holds, do not manufacture
changes. Verify it, correct only concrete gaps, and report the evidence.

## First inspect the repository

Before editing:

Inventory:

- threads/tasks
- executors/runtimes
- channels/queues
- locks
- semaphores
- atomics
- shared state
- worker pools
- retries
- timers
- background loops
- detached tasks
- unbounded buffering

Identify producer/consumer relationships and shutdown paths.

- Record failures that predate the work.

## Non-negotiable design

Each numbered requirement defines an invariant or observable behavior, its
authoritative owner or boundary, the shortcut or ambiguous state it prohibits,
and the evidence that proves it. Do not prescribe incidental implementation
structure unless that structure is itself part of the contract.

### 1. Own concurrent work and bound producer/consumer fan-out

#### Make concurrency ownership explicit


For every task/thread:

- who starts it?
- who owns its handle?
- who stops it?
- who observes failure?
- what happens if the owner disappears?

#### Bound queues and fan-out


Unbounded queues are deferred memory failures.

For each queue, define:

- capacity
- producer behavior when full
- consumer behavior when slow
- drop/retry/block policy

#### Define backpressure


Backpressure should propagate intentionally rather than emerge through OOM, latency explosions, or timeouts.

### 2. Propagate cancellation and define shutdown

#### Define cancellation propagation


Cancellation should flow through owned work.

Avoid orphaned tasks continuing expensive or state-mutating operations after the caller has abandoned the request.

#### Define shutdown


Specify whether shutdown:

- drains
- aborts
- times out
- flushes
- preserves queued work

Make the policy testable.

### 3. Make synchronization and duplicate-work semantics explicit

#### Audit lock scope and ordering


Look for:

- nested locks
- inconsistent acquisition order
- blocking I/O under lock
- callbacks under lock
- oversized critical sections

#### Avoid duplicate work races


For idempotent or deduplicated jobs, define:

- at-most-once
- at-least-once
- exactly-once illusion boundaries
- lease/claim semantics
- retry behavior

### 4. Bound retries and test concurrency through semantic synchronization

#### Keep retry policy bounded


Retries must have explicit:

- max attempts or deadline
- backoff
- jitter policy
- retryable categories

Avoid retry storms.

#### Test concurrency semantically


Prefer deterministic coordination over sleeps.

Test:

- queue saturation
- cancellation
- shutdown
- worker failure
- duplicate submission
- lock-sensitive paths

### Migration and compatibility policy

Do not create parallel legacy and canonical implementations as part of this work.
If a rename, move, replacement, or contract change becomes necessary, inventory all
references first, keep one canonical path, and retain compatibility only when the
invoking request or an existing external contract requires it.

## Explicit anti-patterns

Do not:

- spawn and forget without ownership
- use unbounded queues by default
- hold locks across arbitrary I/O
- retry forever
- rely on sleeps in concurrency tests
- assume scheduler fairness
- conflate concurrency with throughput


## Verification

After editing:

- Run the nearest hard judge for threads/tasks, queues, channels, worker pools, locks, retries, cancellation, shutdown, and shared state: the compiler, type checker, schema/build check, or focused tests that can reject an invalid change.
- Test the observable success behavior, failure behavior, edge cases, and invariants established by the numbered requirements.
- Audit task ownership, queue capacity, backpressure, cancellation, lock scope/order, retries, duplicate work, and shutdown; classify every remaining exception rather than assuming it is harmless.
- Broaden checks only when the changed boundary warrants it, and distinguish pre-existing failures from regressions introduced by this work.

## Acceptance criteria

The work is complete only when:

- all long-lived tasks have owners
- queues and worker pools are bounded intentionally
- backpressure behavior is explicit
- cancellation propagates coherently
- shutdown behavior is defined and tested
- lock ordering/scope is understandable
- retry behavior is bounded
- duplicate-work semantics are explicit
- no detached background work leaks unintentionally

The architectural principle is: **concurrency is a resource-management problem before it is a performance feature.**
