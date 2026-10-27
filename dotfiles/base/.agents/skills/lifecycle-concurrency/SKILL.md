---
name: lifecycle-concurrency
description: "Apply when code spawns tasks, threads, or child processes, adds queues, channels, locks, or retries, installs signal handlers, or introduces cleanup, cancellation, or shutdown handling for sockets, transactions, terminal modes, or temp artifacts. Skip ordinary scoped file reads and writes."
---

# Lifecycle and Concurrency

If code acquires or starts something, who ends it must be as explicit as who began it.

- **One owner releases.** Use structured ownership (RAII, scopes). Cleanup must not depend on the happy-path epilogue or on process exit.
- **Partial initialization unwinds.** A failure at step N cleans up steps 1 to N-1, and nothing is visible before it is valid.
- **Cleanup errors never mask the primary error.** Report them.
- **Updates go through a temp artifact and an atomic replace** (details in `os-boundaries`), cleaned up on failure.
- **Every task has an owner** that starts it, holds its handle, stops it, and observes its failure. No spawn-and-forget.
- **Every queue has a capacity and a full-queue policy:** block, reject, drop, or spill. An unbounded queue is a deferred out-of-memory failure. Backpressure should be a decision, not an accident.
- **Cancellation reaches what the owner started:** child processes, temp files, transactions, queued work. Shutdown states whether it drains or aborts, and orders its steps: stop accepting, drain or abort, flush, close, release.
- **Terminal state has an owner that restores it on every exit.** Raw mode, alternate screen, mouse reporting, bracketed paste, and cursor visibility are acquired resources: pair every enable with a disable that runs on normal exit, error return, panic, and fatal signals.
- **Signals: this skill owns the policy.** Shut down gracefully on TERM, HUP, INT, and QUIT, and install a one-shot async-signal-safe fatal handler (abort, illegal instruction, trap, segfault, bus error, floating-point exception) for crashes. After cleanup, restore the default disposition and re-raise, so the parent sees signal death and fatal signals still dump core. `panic = "abort"` still runs hooks; immediate-abort does not, so the fatal handler is the backstop. Handler mechanics are in `os-boundaries`.
- **Inherited dispositions are explicit.** Ignored or blocked signals survive `exec`: install a handler for every signal the program must observe, and reset in children before `exec` what they must not inherit.
- **Locks stay narrow.** No blocking I/O or callbacks under a lock, and a consistent acquisition order.
- **Retries are bounded:** a maximum or deadline, backoff, jitter where it helps, and explicit retryable categories (`error-model`).

**The test:** if the owner returns early or is cancelled at any line, what keeps running, and what is left on disk or in flight?

Test with signals, channels, and controlled clocks, never sleeps: queue saturation, cancellation, shutdown, worker failure, duplicate submission, cleanup on each early return, and signal death mid-operation with the terminal (or other shared state) verified usable afterward.

**Report:** who owns what and how it ends, the cancellation and shutdown policy, and the bounds you set.
