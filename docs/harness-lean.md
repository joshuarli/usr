# Lean harnesses: native tool surfaces before wrapper shims

Goal: keep coding, MCP, the `agent-browser` skill/CLI, native expert subagents,
the Pi bridge, session lifecycle hooks, and session recovery. Remove
unneeded *model-facing* browser/computer-use tools and bundled prompt material
where there is a verified switch. Do not confuse reduced tool-schema tokens
with smaller installed binaries, lower process RSS, or lower API latency.

This is intentionally **not** a universal `PATH` interception shim. The
clients use different config formats, many are installed into
`~/.local/bin` by sync, and some use themselves as headless SDK subprocesses.
A wrapper can shadow an installed executable, recurse, drop auth/signal
handling, or silently break bridge launches. A wrapper that just execs the
original also saves no tokens. Prefer the native mechanism.

## Status by harness

| Harness | Default lean mechanism | Kept intact / limitation |
| --- | --- | --- |
| Codex | `daemon_auto_start = false` (already set); Apps/plugins/remote plugins already off. Browser, unified computer-use, and computer-use plugin entries now off. The browser-only `node_repl` MCP server is disabled, as is `cua_repl`. | The normal remote MCP servers (`sentry`, `notion`), `pi-subagent-bridge`, `codex-intercom`, multi-agent V2, memory, hooks and CLI remain. The CLI/app-server protocol is **not** stripped from the binary. |
| Claude Code | `disableBundledSkills = true`, and deny only the built-in `claude-in-chrome` MCP server. Remote Control and Workflows were already disabled. | Normal MCP, project/user/plugin skills, LSP plugins, native subagents, worktree hooks, and agent-browser remain. `--chrome` will not override the MCP deny; undo this opt-out before using native Chrome. |
| Pi | Already defaults to four core tools (`read`, `bash`, `edit`, `write`) with extension/MCP tools governed separately. | No global `--no-tools` or blanket MCP removal; would break Pi-subagent-bridge, web-search extensions and nesting. |
| Command Code | Existing native-tier agents and tracked minimal settings; taste learning already disabled through host-local config. | No unverified flag injection into `cmd`; native children and subscriptions must keep working. |
| OpenCode | Already uses a small TUI config and native tier agents. No stock Chrome/Computer Use tool configured. | Keep `webfetch` and `websearch` independent of browser automation, and leave native subagent tools intact. |
| Muse Code | Telemetry already off; known MCP servers explicitly configured. | Keep `sentry` and `notion` MCP and native skills; no verified browser daemon to remove. |
| Devin CLI | Claude/Cloud config imports already off; explicit bridge guard remains. | Preserve `run_subagent` and headless hooks; no unsupported feature flag. |
| Antigravity CLI (`agy`) | Settings are rewritten by the upstream CLI, so no durable tracked feature switch. | Preserve Neon/Hydrogen native subagents and shared skills; audit its advertised browser tools on a live host before adding a wrapper or launcher flag. |
| DeepSeek Harness (`dsh`) | Existing POSIX launcher only selects headless/TUI and the tracked patch. | Do not nest another launcher; no verified redundant browser or daemon process. |
| Vercel fx | `auto_upgrade = false`, `session_titles = false` already; no tracked browser integration. | Keep skills, agent delegation and the CLI. |

**Important Codex distinction:** upstream labels `browser_use`,
`browser_use_external`, `browser_use_full_cdp_access`, `computer_use`,
and `in_app_browser` as *requirements-only* feature gates. Writing those
keys in `~/.codex/config.toml` would falsely promise enforcement. The
tracked configuration instead turns off the actual plugin entries and
browser-backed MCP processes. Administratively disabling the feature gates
requires a separate system-managed `/etc/codex/requirements.toml` or
managed policy, not a user launcher shim. We deliberately do **not** touch
system requirements or the desktop app's own installation.

Native tool inventories may change in upstream releases. Do not add
undocumented settings or pattern-match tool names to delete things blindly.
A denied/permission-gated tool may still be present in the model's tool
catalog: verify **declared tool names and schemas**, not just whether
execution is denied.

## Apply and verify

1. `sh sync plan` to review link reconciliation; then `sh sync` on the
   intended Mac/Linux host (not in CI or a disposable SDK session).
2. Start fresh Codex/Claude sessions. In Codex, check `codex features list`,
   `codex mcp list`, and the loaded plugins; in Claude, inspect `/mcp` and
   verify native Chrome is not connected. Do a normal MCP call and a
   `pi-subagent-bridge` scout/worker smoke test.
3. Compare initial tool lists / model-visible tool-schema token counts and
   startup process trees against an unmodified host baseline. Check for
   absent browser/computer-use tools, no unwanted daemon, and intact MCP.
   Do not claim performance wins before measuring the same model/version.

Offline guard: `python3 -I -S dotfiles/harness-lean-test.py`. It proves
the tracked configuration invariants only; it cannot prove a native
harness's live tool advertisement, plugin load behavior, or process/RSS.

## Re-enable deliberately

- Codex: set the relevant `[plugins.*].enabled` value to `true`,
  re-enable `[mcp_servers.node_repl]` only if that browser companion is
  required, and explicitly opt into daemon auto-start only for a workflow
  that uses it. Keep `cua_repl` disabled unless necessary.
- Claude Code: remove the `claude-in-chrome` deny entry. Set
  `disableBundledSkills = false` if you want the upstream bundled skill
  catalog again. Your own skills remain available either way.

This configuration is an ergonomic optimization, not a security boundary:
project config, upstream updates, and other enabled entry points may expose
capabilities. Use OS sandbox/permissions for enforcement.
