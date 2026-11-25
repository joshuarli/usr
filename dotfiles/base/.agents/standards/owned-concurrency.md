+++
name = "owned-concurrency"
summary = "Long-lived threads, listeners and retry loops are owned, stoppable and joinable; production and tests share one primitive so a stalled or cancelled run cannot leak threads or grow memory without bound."

[[trigger]]
paths = ["*.rs"]
content = ['\bthread::spawn\b', '\bJoinHandle\b']

[[trigger]]
paths = ["*.rs"]
content = ['\b(reconnect|retry|backoff|retry_loop)\b']

[[trigger]]
paths = ["*.rs"]
content = ['\b(accept|listener|serve)\s*\(', '\bloop\s*\{']

[examples]
match = [{ path = "src/daemon/mod.rs", text = "std::thread::spawn(move || listener.serve(daemon));\n" }, { path = "src/daemon/server.rs", text = "loop { let (stream, _) = listener.accept()?; }\n" }]
skip = [{ path = "src/math.rs", text = "fn add(a: u32, b: u32) -> u32 { a + b }\n" }, { path = "README.md", text = "thread::spawn\n" }]
+++

# Owned Concurrency

A thread outliving its owner is a resource leak, not a style issue. If a run
can end, every task it started must end with it.

## Code

- **No fire-and-forget threads.** A long-lived thread is created through one
  owning primitive that records its `JoinHandle` before the spawning function
  returns. A bare `std::thread::spawn` for a listener, worker, drainer, or
  retry loop is a must-fix finding.
- **One owner, one shutdown path.** The owner holds the stop flag and the
  handles. Dropping it signals stop, unblocks any I/O the threads are parked on
  (close the listener or socket, wake the poll), then joins every handle. This
  runs on normal return, error, and test failure — never only on the happy path.
- **Every long-lived loop observes stop.** `accept`, `read`, and `poll` loops
  check a stop signal on every iteration. Do not write `loop { accept() }`
  without one. Backoff waits are interruptible and bounded in latency.
- **Per-request threads are capped and tracked.** A connection or request may
  not spawn an untracked thread; the cap and the release path belong to the
  same owner that accepts the request.
- **Retries are bounded or explicitly rate-limited.** A retry loop has a
  terminal condition and either a maximum count/deadline or a named slow
  interval with a stop check. It must not spawn a fresh listener, server, or
  worker for each attempt; retry the action, not the owner.
- **Tests use the production primitive.** A test helper may not create a
  detached listener or server thread. It returns an owning guard whose `Drop`
  stops and joins. Tests of retry and timeout behavior use injected timing and
  a stub action with a fixed iteration count; no test relies on process exit
  to clean up threads.
- **Handles are a bounded collection.** If an owner stores handles, the
  collection has a cap and a drain policy (join on completion, close on
  overflow). An ever-growing `Vec<JoinHandle>` is a deferred OOM.

**The test:** at any early return, cancellation, or test failure, ask what is
still running and whether its stack and socket were released.

Verify with a controlled stop: shut the owner down twice, saturate it, and
assert the thread count and RSS return to baseline. A test that leaks threads
is a must-fix even when it passes.

**Report:** name the owner, the stop signal, how blocked I/O is unblocked, the
join deadline, and the bound on spawned work.
