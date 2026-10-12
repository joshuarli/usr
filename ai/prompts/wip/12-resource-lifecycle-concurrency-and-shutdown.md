# Resource Lifecycle, Concurrency, and Shutdown

You are improving this codebase so every resource and every unit of concurrent work has clear acquisition, ownership, boundedness, cleanup, cancellation, and shutdown semantics.

The goal is to prevent leaked processes, descriptors, temporary files, locks, sockets, transactions, tasks, and partially initialized resources, and to make concurrency predictable under load and failure.

Scope: files, sockets, transactions, locks, temp artifacts, child processes, threads/tasks, queues/channels, worker pools, retries, watchers, terminal modes, mappings, and leases.

Applicability: Apply this prompt only when the subsystem acquires resources or performs concurrent or background work whose partial initialization, ownership, boundedness, backpressure, cancellation, cleanup, or shutdown semantics matter. If the condition is materially absent, report that evidence and make no speculative changes.

Preserve: Existing valid behavior, public contracts, persisted data and formats, output, side effects, permissions, state transitions, and supported-platform semantics unless this request explicitly changes them.

Intentional changes: Only changes explicitly authorized by the invoking request; otherwise none.

If inspection shows that the relevant contract already holds, do not manufacture
changes. Verify it, correct only concrete gaps, and report the evidence.

## First inspect the repository

Before editing:

Inventory resources such as:

- files and file descriptors
- sockets
- database connections and transactions
- locks
- temporary files/directories
- child processes
- threads/tasks
- subscriptions/watchers
- terminal modes
- memory mappings
- external leases
- mounted resources
- executors/runtimes, channels/queues, semaphores, atomics, worker pools, timers, background loops, and detached tasks
- unbounded buffering and retry loops

For each, identify creation and cleanup paths, including errors and cancellation.
Identify producer/consumer relationships and shutdown paths.

- Record failures that predate the work.

## Non-negotiable design

Each numbered requirement defines an invariant or observable behavior, its
authoritative owner or boundary, the shortcut or ambiguous state it prohibits,
and the evidence that proves it. Do not prescribe incidental implementation
structure unless that structure is itself part of the contract.

### 1. Pair acquisition with ownership through partial initialization and early failure

#### Pair acquisition with ownership


A resource should have an obvious owner responsible for release.

Prefer structured ownership and RAII where the language supports it.

#### Handle partial initialization


If initialization has multiple steps, ensure failure at step N cleans up steps 1..N-1.

Avoid objects that are externally visible before they are valid.

#### Define cleanup on early return


Audit every error path between acquisition and normal completion.

Cleanup must not depend on reaching the happy-path epilogue.

### 2. Define cancellation and shutdown as lifecycle contracts

#### Define cancellation semantics


For long-running work, decide what cancellation does to:

- child processes
- temp files
- transactions
- locks
- queued work
- externally visible state

Cancellation should not leave ambiguous ownership.

#### Define shutdown order


If components depend on one another, make shutdown ordering deliberate.

Examples:

```text
stop accepting work
drain/abort workers
flush state
close persistence
release external resources
```

### 3. Handle cleanup failure and temporary mutation deliberately

#### Treat cleanup failures deliberately


Do not silently discard cleanup errors.

Also do not overwrite the primary failure casually.

Define precedence and logging/reporting semantics.

#### Make temporary artifacts atomic where needed


For file generation/update workflows, consider:

```text
create temp
write
flush
fsync if durability requires it
rename/replace atomically
cleanup temp on failure
```

### 4. Prevent detached work and oversized lock lifetimes

#### Avoid detached work without ownership


Background tasks and child processes should not outlive the component that conceptually owns them unless explicitly designed to.

#### Keep lock lifetime narrow


Do not hold locks across blocking I/O, callbacks, or unrelated work unless required and justified.

### 5. Own concurrent work and bound producer/consumer fan-out

#### Make task ownership explicit

For every task/thread, answer: who starts it, who owns its handle, who stops it,
who observes its failure, and what happens if the owner disappears.

#### Bound queues and define backpressure

Unbounded queues are deferred memory failures. For each queue define capacity,
producer behavior when full, consumer behavior when slow, and the
drop/retry/block policy. Backpressure should propagate intentionally rather than
emerge through OOM, latency explosions, or timeouts.

#### Propagate cancellation and define shutdown

Cancellation should flow through owned work so abandoned requests do not keep
running state-mutating operations. Specify whether shutdown drains, aborts,
times out, flushes, or preserves queued work, and make that policy testable.

#### Audit lock scope and ordering

Look for nested locks, inconsistent acquisition order, blocking I/O or callbacks
under a lock, and oversized critical sections.

#### Keep retries bounded

Retries need a maximum attempt count or deadline, backoff, a jitter policy, and
explicit retryable categories. Avoid retry storms.

#### Test concurrency semantically

Prefer deterministic coordination over sleeps. Cover queue saturation,
cancellation, shutdown, worker failure, duplicate submission, and lock-sensitive
paths.

### Migration and compatibility policy

Do not create parallel legacy and canonical implementations as part of this work.
If a rename, move, replacement, or contract change becomes necessary, inventory all
references first, keep one canonical path, and retain compatibility only when the
invoking request or an existing external contract requires it.

## Explicit anti-patterns

Do not:

- spawn and forget without ownership
- use unbounded queues by default
- retry forever
- rely on sleeps in concurrency tests
- assume scheduler fairness
- rely on process exit for cleanup
- duplicate manual cleanup in many branches when structured ownership can encode it
- ignore child-process lifecycle
- detach tasks casually
- leak temp files on error
- overwrite primary errors with cleanup errors
- hold broad locks for convenience


## Verification

After editing:

- Run the nearest hard judge for files, sockets, transactions, locks, temp artifacts, child processes, tasks, watchers, terminal modes, mappings, and leases: the compiler, type checker, schema/build check, or focused tests that can reject an invalid change.
- Test the observable success behavior, failure behavior, edge cases, and invariants established by the numbered requirements.
- Audit acquisition/release pairs, partial init, early returns, cancellation, shutdown order, cleanup errors, detached work, and lock lifetime; classify every remaining exception rather than assuming it is harmless.
- Broaden checks only when the changed boundary warrants it, and distinguish pre-existing failures from regressions introduced by this work.

## Acceptance criteria

The work is complete only when:

- each resource has a clear owner
- partial initialization cleans up correctly
- early returns and cancellation release owned resources
- shutdown ordering is explicit
- cleanup failures have deliberate semantics
- background work cannot silently leak
- lock lifetimes are justified and narrow
- temporary mutation is atomic where required
- all long-lived tasks have owners, and queues and worker pools are bounded intentionally
- backpressure, cancellation propagation, and shutdown behavior are defined and tested
- retry behavior is bounded
- lifecycle tests cover meaningful failure paths

The architectural principle is: **if code acquires something or starts something, ownership of its end-of-life must be just as explicit; concurrency is a resource-management problem before it is a performance feature.**
