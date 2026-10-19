---
name: lifecycle-concurrency
description: "Apply when code spawns tasks, threads, or child processes, adds queues, channels, locks, or retries, or introduces cleanup, cancellation, or shutdown handling for sockets, transactions, or temp artifacts. Skip ordinary scoped file reads and writes."
---

# Lifecycle and Concurrency

If code acquires or starts something, who ends it must be as explicit as who began it.

- **One owner releases.** Use structured ownership (RAII, scopes). Cleanup must not depend on the happy-path epilogue or on process exit.
- **Partial initialization unwinds.** A failure at step N cleans up steps 1 to N-1, and nothing is visible before it is valid.
- **Cleanup errors never mask the primary error.** Report them, or give the ignore a stated reason.
- **Updates go through a temp artifact and an atomic replace** (details in `os-boundaries`), cleaned up on failure.
- **Every task has an owner** that starts it, holds its handle, stops it, and observes its failure. No spawn-and-forget.
- **Every queue has a capacity and a full-queue policy:** block, reject, drop, or spill. An unbounded queue is a deferred out-of-memory failure. Backpressure should be a decision, not an accident.
- **Cancellation reaches what the owner started:** child processes, temp files, transactions, queued work. Shutdown states whether it drains or aborts, and orders its steps: stop accepting, drain or abort, flush, close, release.
- **Locks stay narrow.** No blocking I/O or callbacks under a lock, and a consistent acquisition order.
- **Retries are bounded:** a maximum or deadline, backoff, jitter where it helps, and explicit retryable categories.

**The test:** if the owner returns early or is cancelled at any line, what keeps running, and what is left on disk or in flight?

Test with signals, channels, and controlled clocks, never sleeps: queue saturation, cancellation, shutdown, worker failure, duplicate submission, and cleanup on each early return.

**Report:** who owns what and how it ends, the cancellation and shutdown policy, and the bounds you set.
