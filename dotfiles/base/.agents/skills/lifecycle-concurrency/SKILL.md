---
name: lifecycle-concurrency
description: Use when code acquires resources or starts concurrent work, such as spawning tasks, threads, or child processes, queues and channels, worker pools, locks, retries, cancellation, shutdown, temp files, or transactions.
---

# Lifecycle and Concurrency

Make the end of every acquisition and every unit of concurrent work as explicit as its start. Apply this to the code being changed or the scope the user names. Do not widen into a repository-wide audit unless asked; if nothing here applies, say so and change nothing.

Read repository and scoped `AGENTS.md` first. Inventory the affected resources, tasks, queues, and locks with their creation and cleanup paths, including error and cancellation paths, and run the narrowest baseline check before editing.

## Rules

- Every resource has one owner responsible for release, preferably through structured ownership (RAII, scopes). Cleanup must not depend on reaching the happy-path epilogue or on process exit.
- Partial initialization: a failure at step N cleans up steps 1 to N-1, and nothing is visible before it is valid.
- Cleanup failures are handled deliberately: do not swallow them and do not let them replace the primary error.
- File generation and updates use a temp artifact, write, flush, atomic replace, and cleanup on failure.
- Every task or thread has an owner that starts it, holds its handle, stops it, and observes its failure. No spawn-and-forget.
- Every queue has a capacity and a stated full-queue policy (block, reject, drop, spill). Unbounded queues are deferred memory failures.
- Cancellation reaches owned work, including child processes, temp files, transactions, and queued items. Shutdown states whether it drains, aborts, times out, or flushes, and orders its steps (stop accepting, drain, flush, close, release).
- Keep lock scope narrow: no blocking I/O or callbacks under a lock, and a consistent acquisition order.
- Retries have a maximum or deadline, backoff, jitter where appropriate, and explicit retryable categories.

## Verify

Test with deterministic coordination (signals, channels, controlled clocks), never sleeps: queue saturation, cancellation, shutdown, worker failure, duplicate submission, and cleanup on each early return. Distinguish pre-existing failures from regressions.

Load `reference.md` for the full inspection checklist, anti-patterns, and acceptance criteria when the change is a broad audit or the design is non-trivial. Where it says "this codebase" or "repository-wide", read it as the requested scope.

## Handoff

Report who owns what and how it ends, the cancellation and shutdown policy, bounds you set, checks actually run, and decisions the user must make.
