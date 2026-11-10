# Pi

Command Code is the preferred executor for delegated work; Pi SDK and [`pi-subagents`](https://github.com/nicobailon/pi-subagents) provide the OpenCode Go-only fallback. Every coding harness calls the shared `pi-subagent-bridge` MCP tools or CLI shim. When OpenCode Go fallback is required, the bridge loads pi-subagents into an embedded SDK host and invokes its versioned delegation RPC directly, never through `pi -p` or an LLM-driven subagent decision. The outer bridge retains cross-harness worktree leases and verified fallback; pi-subagents owns the native child execution, completion events, and retained-session continuation.

## Pinned models

| Role | Command Code primary | Effort | OpenCode Go fallback via Pi SDK | Thinking |
| --- | --- | --- | --- | --- |
| scout | `meta/muse-ember` | medium | `opencode-go/muse-spark-1.3-contributor` | medium |
| mechanic | `meta/muse-ember` | xhigh | `opencode-go/muse-spark-1.3-contributor` | high |
| worker | `deepseek/deepseek-v4.1-flash` | high | `opencode-go/deepseek-v4.1-flash` | high |
| expert | `deepseek/deepseek-v4.1-flash` | max | `opencode-go/deepseek-v4.1-flash` | max |

Pi's default parent model is `opencode-go/deepseek-v4.1-flash` at high. Its global `subagents.modelScope` allows only the pinned OpenCode Go Spark and DeepSeek models. **Only models supported by OpenCode Go may be used through OpenCode/Pi:** standard `opencode/*` Zen models, metered endpoints, and custom providers are forbidden even when advertised by a model catalog. No Pi `god` role exists. Claude Code and Codex alone may invoke their existing native `god` models. The SDK bridge independently enforces the role pins and the effective model, effort, and tool allowlists, so Pi settings or a project override cannot silently select another model for bridge workers.

## Install

Run `sh sync plan`, `sh sync`, and `sh sync doctor` from the `usr` checkout. The default tool set includes Pi, Node.js and Command Code. The bridge's pinned Pi SDK and pi-subagents dependencies are installed within `tools/pi-subagent-bridge`, and its MCP entry is registered for Claude, Pi and OpenCode; Codex uses its tracked MCP entry. Sync migrates recognized legacy `usr-opencode-worker` registrations without disturbing unrelated MCP connections.

Pi authenticates only to OpenCode Go using the existing OpenCode login. In the **untracked and private** `~/.pi/agent/auth.json`:

```json
{
  "opencode-go": {
    "type": "api_key",
    "key": "!opencode2 auth export opencode | jaq -r '.[] | select(.active) | .value.access'"
  }
}
```

Pi resolves the credential command at runtime; OpenCode's OAuth session may need refreshing with `opencode2`. Muse Ember is available in Command Code, **not** in the allowed OpenCode Go set. The tracked custom Zen model catalog has been removed. Command Code uses a separate interactive `cmd login` and runs first. No credentials are committed.

`sh sync` now reconciles interactive Pi packages automatically: it repairs missing or mismatched exact pins with `pi install`, then runs `pi update --extensions --no-approve`. The updater alone skips exact-pinned packages, which is why both steps are needed. `sh sync plan` and `sh sync doctor` inspect installed versions without modifying anything. The bridge has its own pinned SDK dependency and does not require a second manual Pi package installation. The four user agent profiles in `~/.pi/agent/agents/` enforce the same role contract for interactive Pi.

## Worker runtime

Each assignment gets a clean linked worktree under `.work/wt/` and an explicit scope (base HEAD, writable paths, acceptance proof, bounded attempts, stop conditions). The bridge starts Command Code first with its exact tier model and effort. Only when safely required, the bridge launches a dedicated SDK host with only the pinned pi-subagents extension and calls `subagents:rpc:v1:request` (`spawn`, async) with the exact Go-only tier/model/task. The package owns the child lifecycle, artifacts, and completion events. Corrections reopen the same durable SDK host session and use the native `resume` RPC with the previous run ID. Because the external parent already owns the worktree, native pi-subagents worktree allocation is disabled. Ambiguous admissions and missing completion receipts are blocked, not replayed.

Only a missing Command Code executable, an unavailable exact Command Code model/provider, or a recognized provider usage limit can fall back to the OpenCode Go runner, and **only when the worktree is untouched and admission is unambiguous**. The fallback is reported as expected, not as an error: `fallback_reason` summarizes what happened, `fallback_notice` states that the switch was automatic, needs no parent action, and must not be retried or duplicated, `fallback_detail` keeps the original provider message for diagnosis, and `error` is cleared once the fallback has taken over. If the worktree already has edits, no switch happens and the session blocks with a manual-decision notice. A task/test failure or an interrupted process does not warrant a retry with another provider. A runner report is not verification: the parent independently checks proof, changed paths, HEAD and the diff.

This is a Git write-scope check, not an OS sandbox. Ignored paths and host-side effects require additional containment such as `sbx` or a VM.

## One-level native Pi nesting

The embedded Pi fallback is not inherently limited to leaf agents. The four tracked native Pi agent profiles explicitly expose `subagent` and declare exact, ordered descendant allowlists. A required child extension registers an independently enforced capability ceiling from the typed `src/tier-policy.ts` graph in **each first-level child and its descendants**. The SDK checks parsed YAML profile parity and Go-only modelScope before a new root launch. The native runtime inherits the ceiling through nested/async children and applies a strict `maxSubagentDepth = 2`; second-level agents cannot delegate again. A permitted nested launch uses the model-facing shape `subagent({ agent: "mechanic", task: "...", options: { agentScope: "user" } })`; all other nested options are rejected.

Scout → scout; mechanic → scout/mechanic; worker → scout/mechanic/worker; expert → scout/mechanic/worker/expert. No God. A nested call cannot select a model, override tools/provider, create a new worktree, change cwd or use workflow-script launch modes: a code-installed tool-call guard rejects those paths, alongside the upstream `allowedAgents` and depth admission checks. Nested children remain in the assigned worktree; the outer parent must check the combined diff and acceptance proof. This is *not* an OS sandbox against arbitrary shell commands.

**Command Code is still the primary backend and currently remains a leaf.** This change enables nesting in the Pi/OpenCode Go fallback only, not Command Code's standalone CLI process; do not claim universal bridge nesting without implementing a separate typed, authenticated child-delegation interface.

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

Offline: `cd tools/pi-subagent-bridge && npm test`, `python3 -I dotfiles/pi-test.py`, `python3 -I dotfiles/orchestrate-test.py`, the `tools/sync/*worker-test.py` cases, and `sh dotfiles/worker-watch-test.sh`. These tests cannot prove live SDK-provider compatibility, auth refresh, quota balance, model catalog freshness or successful tool execution. Complete the disposable-worktree live gate before relying on unattended operation.

Pi SDK: https://pi.dev/docs/latest/sdk · pi-subagents RPC: https://github.com/nicobailon/pi-subagents/blob/main/docs/extension-api.md

## Experimental Muse subscription integration

After `sh sync` and `muse` → `/login`, export
`USR_PI_MUSE_SUBSCRIPTION=1` before launching the coding harness/MCP bridge.
This selects the pinned `muse-sdk/muse-spark-1.3` subscription-backed provider
for scout and mechanic as Pi-first; worker and expert retain their current routes.
Muse-only nested child profiles preserve type-checked tier limits and the two-level
depth cap. Remove the flag to preserve the standard Command Code/OpenCode Go policy.
For a disposable real-account verification and Contributor-mode privacy details,
read [the bridge documentation](../tools/pi-subagent-bridge/README.md).
