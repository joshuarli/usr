# Pi

Command Code is the preferred executor for delegated work; the exact-pinned Muse SDK subscription is the default middle option for scout/mechanic/worker, and Pi SDK + [`pi-subagents`](https://github.com/nicobailon/pi-subagents) provide the last-resort OpenCode Go fallback. Every coding harness calls the shared `pi-subagent-bridge` MCP tools or CLI shim. When a Pi fallback is required, the bridge loads pi-subagents into an embedded SDK host and invokes its versioned delegation RPC directly, never through `pi -p` or an LLM-driven subagent decision. The outer bridge retains cross-harness worktree leases and verified fallback; pi-subagents owns the native child execution, completion events, and retained-session continuation.

## Vendored, npm-free Pi runtime

Pi 1.5.0, its SDK, `pi-subagents`, the Muse provider and `agent-intercom-pi` are packaged with their transitive dependencies under [`vendor/pi/runtime/`](../vendor/pi/README.md). `sh sync tools pi` checks the platform-specific archive against a committed SHA-256 and extracts the local closure. The shared `pi-subagent-bridge` links to the **same** local SDK packages. Supported platforms: macOS ARM64, Linux x64 and Linux ARM64. Pi setup and bridge registration do not invoke npm, npx, or `pi install/update`; `/pi-update` is the explicit maintainer-only update workflow.

The [source manifest](../vendor/pi/upstreams.json) records full upstream Git commit and file blob SHAs, while [artifacts.json](../vendor/pi/runtime/artifacts.json) authenticates the built runtime archives. Pi's launcher loads `pi-subagents` and `agent-intercom-pi` from the installed local directory. Intercom's broker uses the bundled TypeScript loader, with automatic model wakeups disabled by default (`inboundTrigger: "never"`). Interactive Pi can communicate with compatible peers; Claude/Codex/OpenCode companion adapters are not installed by this Pi-only runtime. Scoped SDK children intentionally do not inherit intercom capabilities.

**Scope:** unrelated `usr` tools may still install or update themselves with npm. This guarantee is about the Pi executable, SDK, bridge dependencies, and Pi extension setup, not every tool in full `sh sync`.

## Pinned models

| Role | Command Code primary | Effort | Muse SDK middle | OpenCode Go fallback via Pi SDK |
| --- | --- | --- | --- | --- |
| scout | `meta/muse-ember` | medium | `muse-sdk/muse-ember-1.0` (medium) | `opencode-go/muse-spark-1.3-contributor` (medium) |
| mechanic | `meta/muse-ember` | xhigh | `muse-sdk/muse-ember-1.0` (xhigh) | `opencode-go/muse-spark-1.3-contributor` (high) |
| worker | `deepseek/deepseek-v4.1-flash` | high | `muse-sdk/muse-spark-1.3` (xhigh) | `opencode-go/deepseek-v4.1-flash` (high) |
| expert | `deepseek/deepseek-v4.1-flash` | max | — | `opencode-go/deepseek-v4.1-flash` (max) |

Pi's default parent model is `opencode-go/deepseek-v4.1-flash` at high. Its global `subagents.modelScope` allows only the pinned OpenCode Go Spark/DeepSeek models and the pinned Muse SDK models. **Only models supported by OpenCode Go may be used through OpenCode/Pi:** standard `opencode/*` Zen models, metered endpoints, and custom providers are forbidden even when advertised by a model catalog. No Pi `god` role exists. Claude Code and Codex alone may invoke their existing native `god` models. The SDK bridge independently enforces the role pins and the effective model, effort, and tool allowlists, so Pi settings or a project override cannot silently select another model for bridge workers.

## Install

Run `sh sync plan`, `sh sync`, and `sh sync doctor` from the `usr` checkout. The default tool set includes Pi, Node.js and Command Code. The bridge's pinned Pi SDK and pi-subagents dependencies are symlinked from the SHA-256-verified local Pi runtime into `tools/pi-subagent-bridge`, and its MCP entry is registered for Claude, Pi and OpenCode; Codex uses its tracked MCP entry. Sync migrates recognized legacy `usr-opencode-worker` registrations without disturbing unrelated MCP connections.

Pi authenticates only to OpenCode Go using the existing OpenCode login. In the **untracked and private** `~/.pi/agent/auth.json`:

```json
{
  "opencode-go": {
    "type": "api_key",
    "key": "!opencode2 auth export opencode | jaq -r '.[] | select(.active) | .value.access'"
  }
}
```

Pi resolves the credential command at runtime; OpenCode's OAuth session may need refreshing with `opencode2`. Muse Ember is available in Command Code and through the Muse SDK, **not** in the allowed OpenCode Go set. The tracked custom Zen model catalog has been removed. Command Code uses a separate interactive `cmd login` and runs first. No credentials are committed.

`sh sync` does **not** run `pi install`, `pi update`, or npm for Pi. The tracked package list is empty and a nonempty Pi package list is treated as a sync conflict; the CLI explicitly loads its locally vendored extensions. `sh sync plan` and `sh sync doctor` inspect local postconditions without writing. The bridge uses the single installed Pi runtime, and the tracked user profiles in `~/.pi/agent/agents/` enforce the same tier contract for interactive Pi.

## Worker runtime

Each assignment gets a clean linked worktree under `.work/wt/` and an explicit scope (base HEAD, writable paths, acceptance proof, bounded attempts, stop conditions). The bridge starts Command Code first with its exact tier model and effort. Only when safely required, the bridge launches a dedicated SDK host with only the pinned pi-subagents extension (plus the pinned Muse provider on a Muse route) and calls `subagents:rpc:v1:request` (`spawn`, async) with the exact tier/model/task. The package owns the child lifecycle, artifacts, and completion events. Corrections reopen the same durable SDK host session and use the native `resume` RPC with the previous run ID. Because the external parent already owns the worktree, native pi-subagents worktree allocation is disabled. Ambiguous admissions and missing completion receipts are blocked, not replayed.

Only a missing Command Code executable, an unavailable exact Command Code model/provider, or a recognized provider usage limit can fall back, and **only when the worktree is untouched and admission is unambiguous**: scout/mechanic/worker try the pinned Muse SDK model first, then the OpenCode Go runner; expert goes straight to OpenCode Go. The fallback is reported as expected, not as an error: `fallback_reason` summarizes what happened, `fallback_notice` states that the switch was automatic, needs no parent action, and must not be retried or duplicated, `fallback_detail` keeps the original provider message for diagnosis, and `error` is cleared once the fallback has taken over. If the worktree already has edits, no switch happens and the session blocks with a manual-decision notice. A task/test failure or an interrupted process does not warrant a retry with another provider. A runner report is not verification: the parent independently checks proof, changed paths, HEAD and the diff.

This is a Git write-scope check, not an OS sandbox. Ignored paths and host-side effects require additional containment such as `sbx` or a VM.

## Coordinating a campaign

Sessions are recorded per repository under `.work/worker-bridge/`, so a parent does not need a hand-maintained lane table. `worker-watch` follows one session and exits on its terminal evidence. `worker-campaign` discovers every `usrw_*.json` under one or more repository roots and blocks until any unacknowledged session becomes terminal:

```
worker-campaign wait [--timeout DURATION] [ROOT...]
worker-campaign ack ID...
worker-campaign list [ROOT...]
```

`wait` exits 0 and prints one `<id> <state> <cwd> <title>` line per newly terminal session (`succeeded`, `failed`, `turn_limit`, `interrupted`), or exits 2 with a one-line `tick: N running` summary after `--timeout` (for example `30m`). Roots may instead be given colon-separated in `$WORKER_CAMPAIGN_ROOTS`, which lets one background wait cover worktrees in several repositories. `ack` records the IDs under `${XDG_STATE_HOME:-$HOME/.local/state}/worker-campaign/acked` so a session is never reported twice; it is idempotent. `list` prints state, age, worktree and the recorded continuation/steer budgets. Terminal state is the same evidence `worker-watch` uses, obtained with `worker-watch --state ROOT ID`: the Command Code `result` record, a gone process without one, or a Pi SDK child record.

## One-level native Pi nesting

The embedded Pi fallback is not inherently limited to leaf agents. The tracked native Pi agent profiles (scout, mechanic, worker, expert, and the Muse-only `muse-scout`, `muse-mechanic`, `muse-worker`) explicitly expose `subagent` and declare exact, ordered descendant allowlists. A required child extension registers an independently enforced capability ceiling from the typed `src/tier-policy.ts` graph in **each first-level child and its descendants**. The SDK checks parsed YAML profile parity and the exact modelScope before a new root launch. The native runtime inherits the ceiling through nested/async children and applies a strict `maxSubagentDepth = 2`; second-level agents cannot delegate again. A permitted nested launch uses the model-facing shape `subagent({ agent: "mechanic", task: "...", options: { agentScope: "user" } })`; all other nested options are rejected.

Scout → scout; mechanic → scout/mechanic; worker → scout/mechanic/worker; expert → scout/mechanic/worker/expert. No God. A nested call cannot select a model, override tools/provider, create a new worktree, change cwd or use workflow-script launch modes: a code-installed tool-call guard rejects those paths, alongside the upstream `allowedAgents` and depth admission checks. Nested children remain in the assigned worktree; the outer parent must check the combined diff and acceptance proof. This is *not* an OS sandbox against arbitrary shell commands.

**Command Code is still the primary backend and currently remains a leaf.** This change enables nesting in the Pi fallback (Muse or OpenCode Go) only, not Command Code's standalone CLI process; do not claim universal bridge nesting without implementing a separate typed, authenticated child-delegation interface.

## CLI entrypoint

The `pi-subagent-bridge` executable in `~/.local/bin` invokes the same SDK bridge when a harness cannot speak MCP:

```
pi-subagent-bridge model-check /absolute/repo/.work/wt/task worker
pi-subagent-bridge start /absolute/repo/.work/wt/task "Fix one bug" worker /path/scope.json /path/brief.txt
pi-subagent-bridge status /absolute/repo/.work/wt/task usrw_SESSION_ID
pi-subagent-bridge resume /absolute/repo/.work/wt/task usrw_SESSION_ID /path/feedback.txt
pi-subagent-bridge cancel /absolute/repo/.work/wt/task usrw_SESSION_ID
```

It also exposes `pi-subagent-bridge mcp` for JSON-RPC. See `tools/pi-subagent-bridge/README.md` for schema and live acceptance checks.

## Verification

Offline: `python3 -I tools/pi/vendor.py check`, `python3 -I tools/pi/test_offline.py`, `cd tools/pi-subagent-bridge && npm test` (developer test invocation only), `python3 -I dotfiles/pi-test.py`, `python3 -I dotfiles/orchestrate-test.py`, the `tools/sync/*worker-test.py` cases, `sh dotfiles/worker-watch-test.sh` and `sh dotfiles/worker-campaign-test.sh`. These tests cannot prove live SDK-provider compatibility, auth refresh, quota balance, model catalog freshness or successful tool execution. Complete the disposable-worktree live gate before relying on unattended operation.

Pi SDK: https://pi.dev/docs/latest/sdk · pi-subagents RPC: https://github.com/nicobailon/pi-subagents/blob/main/docs/extension-api.md

## Muse subscription integration

After `sh sync` and `muse` → `/login`, the bridge uses the pinned Muse SDK models as
the default middle option when Command Code is unavailable or fails before edits:
`muse-sdk/muse-ember-1.0` for scout (medium) and mechanic (xhigh), and
`muse-sdk/muse-spark-1.3` for worker (xhigh). Expert has no Muse route. No environment
flag is required and `USR_PI_MUSE_SUBSCRIPTION` is ignored. Muse-only nested child
profiles preserve type-checked tier limits and the two-level depth cap. The bridge sets
`PI_MUSE_SDK_CONTRIBUTOR=on` for its Muse workers, so Meta may use prompts, code and
outputs for training.
For a disposable real-account verification and Contributor-mode privacy details,
read [the bridge documentation](../tools/pi-subagent-bridge/README.md).
