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

## Install once on the Claude host

Requires Node.js 26+, OpenCode V2, Command Code CLI, and Git. Authenticate Command Code (`cmd status`, then `cmd login` if necessary). OpenCode Go uses its own allowance; Command Code has an independent account/allowance.

~~~sh
cd ~/usr/tools/opencode-worker
npm install --ignore-scripts --no-package-lock --no-audit --no-fund
npm test
claude mcp add --scope user --transport stdio usr-opencode-worker -- \
  node --experimental-strip-types "$HOME/usr/tools/opencode-worker/src/server.ts"
claude mcp list
~~~

Restart Claude and verify `/mcp`. **The tracked orchestration policy is on by default; global MCP registration is a one-time local action.** `sh sync` does not silently modify `~/.claude.json`, install untracked dependencies into the repo, or touch auth. Without the registered bridge, Claude stops and reports setup rather than implementing in Opus or native Claude children.

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
