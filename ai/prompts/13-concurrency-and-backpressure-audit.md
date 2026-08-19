# Concurrency, Cancellation, and Backpressure Audit

You are improving an existing concurrent codebase so task ownership, boundedness, synchronization, cancellation, and shutdown behavior are explicit.

The goal is not to maximize parallelism. The goal is predictable concurrency under load and failure.

Preserve behavior unless correcting a concurrency defect.

## First inspect the repository

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

## 1. Make concurrency ownership explicit

For every task/thread:

- who starts it?
- who owns its handle?
- who stops it?
- who observes failure?
- what happens if the owner disappears?

## 2. Bound queues and fan-out

Unbounded queues are deferred memory failures.

For each queue, define:

- capacity
- producer behavior when full
- consumer behavior when slow
- drop/retry/block policy

## 3. Define backpressure

Backpressure should propagate intentionally rather than emerge through OOM, latency explosions, or timeouts.

## 4. Define cancellation propagation

Cancellation should flow through owned work.

Avoid orphaned tasks continuing expensive or state-mutating operations after the caller has abandoned the request.

## 5. Define shutdown

Specify whether shutdown:

- drains
- aborts
- times out
- flushes
- preserves queued work

Make the policy testable.

## 6. Audit lock scope and ordering

Look for:

- nested locks
- inconsistent acquisition order
- blocking I/O under lock
- callbacks under lock
- oversized critical sections

## 7. Avoid duplicate work races

For idempotent or deduplicated jobs, define:

- at-most-once
- at-least-once
- exactly-once illusion boundaries
- lease/claim semantics
- retry behavior

## 8. Keep retry policy bounded

Retries must have explicit:

- max attempts or deadline
- backoff
- jitter policy
- retryable categories

Avoid retry storms.

## 9. Test concurrency semantically

Prefer deterministic coordination over sleeps.

Test:

- queue saturation
- cancellation
- shutdown
- worker failure
- duplicate submission
- lock-sensitive paths

## Explicit anti-patterns

Do not:

- spawn and forget without ownership
- use unbounded queues by default
- hold locks across arbitrary I/O
- retry forever
- rely on sleeps in concurrency tests
- assume scheduler fairness
- conflate concurrency with throughput

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
