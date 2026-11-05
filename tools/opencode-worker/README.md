# OpenCode workers for `usr/orchestrate`

A small, first-party Claude Code MCP bridge to the OpenCode **V2** TypeScript client. The Claude parent plans, creates Git worktrees, reviews the diff, runs integration checks, and merges; each normal `worker` implementation slice executes in an independent OpenCode session using **DeepSeek V4.1 Flash**.

The bridge uses `@opencode/client` and its managed local service, not repeated `opencode run` subprocesses or CLI output scraping. Session IDs live in OpenCode and survive MCP process restarts. This changes **Claude worker routing only**: `scout`, `mechanic`, `expert`, and `god`, the other harnesses, and Claude's native worker fallback definition are untouched.

## Install (manual on the machine running Claude)

Requires Node.js **26+**, Git, OpenCode **V2**, and Claude Code. The free model is cloud-hosted inside OpenCode; there are no local model weights to download. **Provider access depends on the installed OpenCode account/configuration**. Check `opencode models` and authenticate with OpenCode if necessary; the free offering is temporary and may disappear. `usr` already installs OpenCode and Node via its normal setup; run their existing installers if missing.

```sh
cd ~/usr/tools/opencode-worker
npm install --ignore-scripts --no-package-lock --no-audit --no-fund
npm test
claude mcp add --scope user --transport stdio usr-opencode-worker -- \
  node --experimental-strip-types "$HOME/usr/tools/opencode-worker/src/server.ts"
claude mcp list
```

Restart Claude; `/mcp` should show **usr-opencode-worker** and five worker tools. Registration is a one-time user-local operation, not a tracked secret or an automatic `sh sync` side effect. Do not commit credentials or `node_modules`.

**Model selection:** Default is `opencode/deepseek-v4.1-flash-free`, with a smaller context and output budget and temporary availability. If the free route is unavailable or its limits are insufficient, explicitly configure the existing OpenCode Go paid-allowance route instead (no automatic fallback):

```sh
claude mcp remove --scope user usr-opencode-worker
claude mcp add --scope user --env USR_OPENCODE_WORKER_MODEL=go --transport stdio usr-opencode-worker -- \
  node --experimental-strip-types "$HOME/usr/tools/opencode-worker/src/server.ts"
```

`go` pins `opencode-go/deepseek-v4.1-flash#max`. The only accepted values are `free` and `go`. Different provider or model IDs require a code change and tests; never silently fall back to Sonnet or other models. Costs reported for Go are informational and do not necessarily match subscription allowance accounting.

## Normal implementation lane

1. **Parent** creates a clean linked worktree at `<repo>/.work/wt/<slice>` and its own branch, as already required by `orchestrate`. Do not use the primary checkout, a subdirectory, an untracked dirty tree, or an arbitrary temp directory.
2. **Parent** calls `worker_model_check(cwd)`. If the exact pinned model/variant isn't available, report that blocker or seek authorization to change the configuration; don't silently change models.
3. **Parent** calls `worker_start(cwd, title, brief)` with the base revision, owned and forbidden files, acceptance command, attempt limit, and stopping condition. The bridge pins model and `build` agent, records worktree ownership in session metadata, and disables subagent delegation by instruction. The returned `session_id` means the input was **durably admitted**, *not* that execution finished.
4. **Parent** calls `worker_status(cwd, session_id)` to check `running`, `queued`, or the session outcome, the last assistant text, reported usage/cost, and Git status. The parent checks the diff and actual acceptance evidence; assistant text alone is not proof. Keep the session ID with its exact worktree.
5. After diagnosing an incomplete slice, **parent** may call `worker_resume` with specific feedback only when the session is inactive and has no queued input. For a cancellation, `worker_cancel` requests OpenCode interruption; `interrupted:false` means no active execution was interrupted. Always review preserved work afterward.
6. **Parent** integrates accepted work and handles worktree/branch cleanup under the existing `orchestrate` lifecycle. The worker must never commit, switch branches, merge, push, or remove a worktree.

`agent-tier-gate` guards native Claude `Agent` calls, **not** these MCP tools. The bridge rejects unrelated sessions and worktrees and refuses to change model on resume, but is a **coordination boundary, not an OS sandbox or authenticated proof of a parent caller**. The agent's tools can still access other paths allowed by the host. Only install this MCP server in trusted Claude Code sessions; use `sbx` or a VM if stronger isolation is required.

## Verification and handoff

**Offline / without Claude:**

```sh
cd ~/usr/tools/opencode-worker
npm test
node --experimental-strip-types src/server.ts
```

The second command is the stdio MCP server and will wait for JSON-RPC messages. Tests use temporary Git repositories, a mock OpenCode port, and an actual MCP stdio handshake. They don't spend tokens or need any credentials. They cover worktree boundary enforcement, strict model selection, session ownership, start/status/resume/cancel, pending input, and admission failures. Node 22 may be used for these offline tests, but the tracked runtime target is Node 26+.

**Live Claude + OpenCode smoke test remaining:** After `claude mcp add`, in a disposable test repo create `.work/wt/oc-smoke` and verify `worker_model_check`; assign a bounded one-file slice; record the returned session ID; observe a terminal outcome; check its actual model, resulting diff, and test output. Resume with one targeted correction, test cancellation of a running slice, then restart the MCP process and confirm the same session can still be inspected. Confirm two independent worktrees do not interfere. Only enable unattended multi-lane campaigns when these checks pass.

If OpenCode V2's service cannot start, or the model isn't listed, do not auto-switch providers. Inspect the installed `opencode --version`, the local OpenCode login/status, and `worker_model_check`. `@opencode/client` is pinned to `2.2.5` to keep API expectations explicit. Authentication, real worker execution, and Claude behavior cannot be verified by this repository's offline tests.
