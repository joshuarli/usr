+++
name = "cli-interrupt"
summary = "CLIs, long-running scripts, background jobs, and interactive terminal tools stop cooperatively on Ctrl-C or SIGTERM, discard partial work, and die by the signal so the shell sees 130."

[[trigger]]
paths = ["bin/", "cli/", "cli.py", "__main__.py", "**/src/main.rs", "**/src/bin/"]

[[trigger]]
paths = ["*", "!*.md", "!*.txt", "!*.rst", "!*.json", "!*.jsonl", "!*.log", "!*.csv", "!*.tsv", "!*.svg", "!*.snap", "!*.lock"]
content = [
  '\bSIG(INT|TERM)\b',
  '\bKeyboardInterrupt\b',
  '\bAbort(Controller|Signal)\b',
  '\bprocess\.argv\b',
  '\bargparse\b',
  '\blexopt\b',
  '\bclap::',
  '\btrap\b.*\b(INT|TERM|EXIT)\b',
]

[examples]
match = [
  "dotfiles/base/.local/bin/standards",
  "crates/tool/src/main.rs",
  "src/bin/extra.rs",
  { path = "tools/report.py", text = "import argparse\n" },
]
skip = [{ path = "fixtures/data.json", text = "import argparse\n" }, "README.md",
  "src/lib.rs",
  { path = "docs/signals.md", text = "Handle SIGINT.\n" },
  { path = "tools/util.py", text = "def f():\n    return 1\n" },
]
+++

# Cooperative CLI interruption

Ctrl-C is a user request to stop, not a reason to abort mid-write. A tool that exits immediately on the first signal can leave partial files, unreleased resources, or a checkpoint that never landed. Treat interruption as a first-class control flow path from the start. This applies to any CLI, subcommand, long-running script, background job, or interactive terminal tool. It does not apply to instantaneous commands with no I/O or locks.

## Code

### Standard

- **One signal owner.** Install one SIGINT handler that cancels a single cancellation token, and route that token through every phase of the run: an `AbortController` in Node, a cancelled task or `threading.Event` in Python (or the `KeyboardInterrupt` that `asyncio.run` delivers), a `CancellationToken` or shared `AtomicBool` in Rust, a cancelled `context.Context` in Go. Do not exit from the handler on the first signal (`process.exit`, `sys.exit`, `std::process::exit`). A second signal may force exit as an escape hatch.
- **Cancellation reaches every wait.** Pass the token into network calls, timers, sleep/backoff loops, child processes, page automation, and credential capture. Combine it with per-operation timeouts rather than replacing it, so a timeout and an interrupt both stop promptly. No phase may ignore cancellation for longer than one bounded operation.
- **Stop at boundaries, not mid-artifact.** Finish the current unit of work or discard it cleanly; never start the next unit, target, or batch item after an abort. Persist checkpoints and pending state, then export or flush from what was saved.
- **Partials never become products.** Downloads and generated files land in a temp location and are moved into place atomically only after they validate. On interrupt, close handles, remove temp files, and leave no `.part` or truncated output behind. Cleanup runs through `finally`, not only the happy path.
- **Die by the signal.** Print a short interruption notice to stderr, finish cleanup, then restore the default disposition and re-raise the signal, as `lifecycle-concurrency` requires, so the parent sees signal death and a shell reports 130 for SIGINT. Do not `exit(130)`: a parent loop or `make` only stops on a child that died by the signal. Keep it distinct from a runtime failure (1) and a usage error (2); do not report an interrupt as a failed run. Tell the user that saved data is kept and that re-running resumes.
- **Re-run is safe.** Checkpoints, cursors, and merge-by-id stores make the next invocation idempotent. An interrupted run must never require manual cleanup before it can be retried.
- **Limits are documented.** Say in `--help` that Ctrl-C stops after the current unit, that a second Ctrl-C forces exit, and what the exit code is.

### Tests

- A mid-flight abort test: start a slow or staged operation, abort it, then assert no final or partial artifact, no further work started, and the saved state is still readable.
- A pre-aborted signal test: no work is scheduled at all.
- A real signal smoke test for long-running tools: send SIGINT to a child process and assert it died by SIGINT (130 in a shell, a negative signal status from a subprocess API) with the interruption notice, not a failure trace.
- Use controlled signals and clocks, not sleeps, to make the abort deterministic.

Mechanics for signal handlers, terminal restoration, temp artifacts, and structured cleanup belong to `lifecycle-concurrency` and `os-boundaries`; CLI spelling and exit-code conventions belong to `design-cli`.

**The test:** interrupt at any line of the run. What is still running, what is on disk, what did the user see, and does the next invocation pick up exactly where this one stopped?
