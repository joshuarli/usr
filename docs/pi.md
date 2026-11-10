# Pi

Pi SDK and [`pi-subagents`](https://github.com/nicobailon/pi-subagents) are the canonical delegated runtime. Every coding harness calls the shared `pi-subagent-bridge` MCP tools or CLI shim. The bridge loads pi-subagents into an embedded SDK host and invokes its versioned delegation RPC directly, never through `pi -p` or an LLM-driven subagent decision. The outer bridge retains cross-harness worktree leases and verified fallback; pi-subagents owns the native child execution, completion events, and retained-session continuation.

## Pinned models

| Role | Pi SDK primary | Thinking | Command Code fallback |
| --- | --- | --- | --- |
| scout | `opencode/muse-ember-1.0` | medium | `meta/muse-ember`, medium |
| mechanic | `opencode/muse-ember-1.0` | xhigh | `meta/muse-ember`, xhigh |
| worker | `opencode-go/deepseek-v4.1-flash` | high | `deepseek/deepseek-v4.1-flash`, high |
| expert | `opencode-go/deepseek-v4.1-flash` | max | `deepseek/deepseek-v4.1-flash`, max |

Pi's default parent model is `opencode-go/deepseek-v4.1-flash` at high. Its global `subagents.modelScope` allows exactly the pinned Ember model on OpenCode Zen and DeepSeek on OpenCode Go. No Pi `god` role exists. Claude Code and Codex alone may invoke their existing native `god` models. The SDK bridge independently enforces the role pins and the effective model, effort, and tool allowlists, so Pi settings or a project override cannot silently select another model for bridge workers.

## Install

Run `sh sync plan`, `sh sync`, and `sh sync doctor` from the `usr` checkout. The default tool set includes Pi, Node.js and Command Code. The bridge's pinned Pi SDK and pi-subagents dependencies are installed within `tools/pi-subagent-bridge`, and its MCP entry is registered for Claude, Pi and OpenCode; Codex uses its tracked MCP entry. Sync migrates recognized legacy `usr-opencode-worker` registrations without disturbing unrelated MCP connections.

Pi authenticates to OpenCode Zen and Go using the existing OpenCode login. In the **untracked and private** `~/.pi/agent/auth.json`:

```json
{
  "opencode": {
    "type": "api_key",
    "key": "!opencode2 auth export opencode | jaq -r '.[] | select(.active) | .value.access'"
  },
  "opencode-go": {
    "type": "api_key",
    "key": "!opencode2 auth export opencode | jaq -r '.[] | select(.active) | .value.access'"
  }
}
```

Pi resolves the command at runtime; OpenCode's OAuth session may need refreshing with `opencode2`. The bridge also checks the active OpenCode login without printing its credential. Ember is an OpenCode **Zen** (metered) model, not a Go model. `~/.pi/agent/models.json` explicitly declares its OpenAI Responses metadata until the bundled Pi catalog catches up; this prevents a newly released model from being absent solely because the SDK is pinned. The fallback uses a separate interactive `cmd login`. No credentials are committed.

`sh sync` now reconciles interactive Pi packages automatically: it repairs missing or mismatched exact pins with `pi install`, then runs `pi update --extensions --no-approve`. The updater alone skips exact-pinned packages, which is why both steps are needed. `sh sync plan` and `sh sync doctor` inspect installed versions without modifying anything. The bridge has its own pinned SDK dependency and does not require a second manual Pi package installation. The four user agent profiles in `~/.pi/agent/agents/` enforce the same role contract for interactive Pi.

## Worker runtime

Each assignment gets a clean linked worktree under `.work/wt/` and an explicit scope (base HEAD, writable paths, acceptance proof, bounded attempts, stop conditions). The bridge launches a dedicated SDK host with only the pinned pi-subagents extension and calls `subagents:rpc:v1:request` (`spawn`, async) with the exact tier/model/task. The package owns the child lifecycle, artifacts, and completion events. Corrections reopen the same durable SDK host session and use the native `resume` RPC with the previous run ID. Because the external parent already owns the worktree, native pi-subagents worktree allocation is disabled. Ambiguous admissions and missing completion receipts are blocked, not replayed.

Only an unavailable exact model/provider or a recognized provider usage limit can fall back to the tier-pinned Command Code runner, and **only when the worktree is untouched and admission is unambiguous**. The fallback is reported as expected, not as an error: `fallback_reason` summarizes what happened, `fallback_notice` states that the switch was automatic, needs no parent action, and must not be retried or duplicated, `fallback_detail` keeps the original provider message for diagnosis, and `error` is cleared once the fallback has taken over. If the worktree already has edits, no switch happens and the session blocks with a manual-decision notice. A task/test failure or an interrupted process does not warrant a retry with another provider. A runner report is not verification: the parent independently checks proof, changed paths, HEAD and the diff.

This is a Git write-scope check, not an OS sandbox. Ignored paths and host-side effects require additional containment such as `sbx` or a VM.

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
