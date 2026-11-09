# Pi

Pi is the canonical worker runtime for subagents launched from any coding harness. Use the shared `pi-subagent-bridge` MCP server or its CLI shim; do not invoke native Pi `pi-subagents`. The bridge uses `@earendil-works/pi-coding-agent` directly, rather than shelling out to `pi -p`. Independent SDK subprocesses preserve worktree and process isolation.

## Pinned models

| Role | OpenCode Go via Pi SDK | Thinking | Command Code fallback |
| --- | --- | --- | --- |
| scout | `muse-spark-1.3-contributor` | medium | DeepSeek V4.1 Flash low |
| mechanic | `muse-spark-1.3-contributor` | high | DeepSeek V4.1 Flash high |
| worker | `deepseek-v4.1-flash` | high | DeepSeek V4.1 Flash high |
| expert | `deepseek-v4.1-flash` | max | DeepSeek V4.1 Flash max |

Pi's default parent model is `opencode-go/deepseek-v4.1-flash` at high. Its global `subagents.modelScope` allows exactly those two OpenCode Go models. No Pi `god` role exists. Claude Code and Codex alone may invoke their existing native `god` models. The SDK bridge independently enforces the role pins and the effective model, effort, and tool allowlists, so Pi settings or a project override cannot silently select another model for bridge workers.

## Install

Run `sh sync plan`, `sh sync`, and `sh sync doctor` from the `usr` checkout. The default tool set includes Pi, Node.js and Command Code. The bridge's pinned SDK dependency is installed within `tools/pi-subagent-bridge`, and its MCP entry is registered for Claude, Pi and OpenCode; Codex uses its tracked MCP entry. Sync migrates recognized legacy `usr-opencode-worker` registrations without disturbing unrelated MCP connections.

Pi authenticates to OpenCode Go using the existing OpenCode login. In the **untracked and private** ``/.pi/agent/auth.json`:

```json
{
  "opencode-go": {
    "type": "api_key",
    "key": "!opencode2 auth export opencode | jaq -r '.[] | select(.active) | .value.access'"
  }
}
```

Pi resolves the command at runtime; OpenCode's OAuth session may need refreshing with `opencode2`. The fallback uses a separate interactive `cmd login`. No credentials are committed.

## Worker runtime

Each assignment gets a clean linked worktree under `.work/wt/` and an explicit scope (base HEAD, writable paths, acceptance proof, bounded attempts, stop conditions). `pi-subagent-bridge` starts a dedicated Node process running `createAgentSession` from the Pi SDK. It selects the exact model, sets the effort, permits only the role's tools and disables ambient extensions and skill-triggered child launches. Conversation state persists in the ignored `.work/worker-bridge/pi-sessions` directory; corrections reopen that exact session. The worker writes a terminal JSON outcome atomically after the SDK prompt finishes. An absent or malformed outcome stays blocked.

Only an unavailable exact model/provider or a recognized quota/usage failure can fall back to the pinned Command Code runner, and **only when the worktree is untouched and admission is unambiguous**. A task/test failure or an interrupted process does not warrant a retry with another provider. A runner report is not verification: the parent independently checks proof, changed paths, HEAD and the diff.

This is a Git write-scope check, not an OS sandbox. Ignored paths and host-side effects require additional containment such as `sbx` or a VM.

## CLI entrypoint

The `pi-subagent-bridge` executable in ``/.local/bin` invokes the same SDK bridge when a harness cannot speak MCP:

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

Pi SDK upstream reference: https://pi.dev/docs/latest/sdk
