# Claude orchestration: OpenCode Go → Command Code (DeepSeek V4.1 Flash)

**Default Claude `orchestrate` execution path.** Opus scopes tasks, checks evidence, does one bounded diff review, and integrates. All substantive research, implementation, and testing goes to DeepSeek V4.1 Flash executors through this MCP bridge. Native Claude workers are **not** a fallback.

The bridge favors OpenCode Go. If the pinned OpenCode tier is unavailable or returns a recognized quota/usage error, it falls back to Command Code's exact model, `deepseek/deepseek-v4.1-flash`, without changing the task scope or worktree. No other model or provider is permitted.

| Tier | OpenCode Go model | Command Code effort | Use |
| --- | --- | --- | --- |
| scout | `opencode-go/deepseek-v4.1-flash#low` | `low` | Read-only research |
| mechanic | `opencode-go/deepseek-v4.1-flash#low` | `low` | Precisely specified edits |
| worker | `opencode-go/deepseek-v4.1-flash#high` | `high` | Ordinary implementation/tests |
| expert | `opencode-go/deepseek-v4.1-flash#max` | `max` | Demonstrably difficult work |
| god | `opencode-go/deepseek-v4.1-flash#max` | `max` | Fresh context after a failed expert |

All Command Code tiers use `deepseek/deepseek-v4.1-flash` with the corresponding effort. OpenCode uses the pinned V2 client; Command Code uses documented headless `cmd -p --output-format json` NDJSON, explicit `--model`/`--effort`, `--resume`, and `--plan` for scouts or `--yolo` for writers. Neither model text nor successful exit proves correctness.

## Installation and lifecycle

Run `sh sync` from the usr checkout. It installs Node.js, OpenCode, and Command Code, installs the bridge's pinned `@opencode/client` dependency, and idempotently registers `usr-opencode-worker` in Claude's user MCP configuration. This needs no manual `npm install` or `claude mcp add`.

Use `sh sync bridge` to repair just the bridge, `sh sync plan` to preview its setup, `sh sync doctor` to inspect it, and `sh sync uninstall` to unregister the owned MCP entry. Other MCP servers, Claude credentials and sessions remain untouched. Credentials are reused; if needed, run `cmd login` yourself. The dependency installation requires Node.js 26+, and the code remains in the tracked checkout.

When the checkout path changes, re-run `sh sync` to update the MCP command. Headless Alpine server profiles skip the Claude integration.

## Task protocol

Opus prepares a clean separate linked worktree at `<repo>/.work/wt/<slice>` and calls `worker_model_check(cwd, tier)`. It creates one bounded assignment with `worker_start(cwd, title, tier, scope, brief)`:

- `scope.base_revision`: exact 40-character worktree HEAD.
- `scope.writable_paths`: up to 20 explicit relative files or directory prefixes ending in `/`; **empty** for scout.
- `scope.acceptance_proof`: exact verification command and expected result, or source `file:line` evidence for read-only investigation.
- `scope.attempt_limit`: 1 normally; 2 for one targeted correction.
- `scope.stop_on`: design ambiguity, dependencies, contract changes, blocked proof, or expanded scope.

`worker_start` returns a stable `usrw_…` bridge ID and **admitted**, not completed. `worker_status(cwd, session_id)` reports actual backend, model/effort, result, errors, changed/out-of-scope paths, and unchanged HEAD. Opus checks claimed commands/output independently.

The **one Opus review** uses `git diff --check` and `git diff <base_revision>` plus untracked files. Check the intended change, ownership, obvious breakage, and unrelated churn. One same-scope `worker_resume` correction may follow if the attempt limit permits; otherwise reject or park. Workers never commit, merge, push, or remove worktrees.

Fallback requires an untouched tree. If OpenCode wrote anything before exhausting quota, the bridge returns `blocked_partial_work` instead of running Command Code over partial changes. Command Code failures do not fall back to a third provider. Bridge state and Command Code NDJSON logs persist under the ignored `<repo>/.work/worker-bridge/`, allowing completed sessions to be inspected after MCP restarts. Old child PIDs are never blindly signaled.

**Isolation limitation:** this is a Git scope check, not an OS sandbox; ignored-file changes or host writes elsewhere might not be detected. Use `sbx` or a VM for stronger containment.

## Verification

~~~sh
cd ~/usr/tools/opencode-worker
npm test
~~~

Offline tests cover worktree/scope boundaries, tier pinning, quota fallback, partial edits, resume, and the MCP handshake using mocks, without inference credits. They do not prove live account access.

**Live gate before unattended work:** register MCP, use a disposable one-file worktree task, inspect the result diff and acceptance command, verify an OpenCode quota failure transitions to Command Code with the same scope, test one resume, then restart MCP and inspect the session again.
