# Lean harness defaults

Keep coding tools, web search, MCP, shared skills, subagents, session hooks
and `agent-browser`. Keep native browsing in OpenCode and Codex; Claude's
Chrome integration stays off by default. Disable unused background work
with supported switches. These defaults do not shrink installed binaries;
token, RSS and latency improvements need separate measurement.

## Launch shims

The tracked shims live in `~/.local/lib/harness-shims`. The sh, ish and xshi
configs put that directory before `~/.local/bin`. Each shim directly execs
the native launcher in `~/.local/bin`, so installers and vendor updates
retain ownership of their launchers. No PATH search or binary renaming is
needed. Programs launched with an absolute binary path, or from a GUI that
does not inherit this PATH, bypass the shims.

| Command | Shim default | Explicit override |
| --- | --- | --- |
| `codex` | Adds `--no-daemon`, which avoids both starting and reusing the shared daemon. Does not duplicate an existing flag; leaves explicit `--remote` invocations alone. | Use `~/.local/bin/codex` for the native launcher. |
| `claude` | Sets `CLAUDE_CODE_ENABLE_CFC=0`, so native Chrome starts off and browser work uses `agent-browser`. | `claude --chrome` explicitly opts back in. |
| `copilot` (pilot) | Disables automatic updates, client telemetry and session export. | Use `~/.local/bin/copilot` for the native launcher. |
| `cmd` | Disables startup notices, the automatic updater and telemetry with `CMD_DISABLE_NOTICES`, `COMMANDCODE_SKIP_UPDATES` and `DO_NOT_TRACK`. | Use `~/.local/bin/cmd` for the native launcher. |

`codex-or`, `claude-or` and `claude-ds` inherit these defaults when they
resolve the underlying command through that PATH. Direct invocation of a
native launcher bypasses only its shim; tracked configuration still applies.
The Copilot pilot requires the manual installation and qualification described
in [Copilot setup](copilot-native.md); sync currently installs only its configuration and shim.

## Configuration by harness

| Harness | Native configuration and scope |
| --- | --- |
| Codex | Enables the native `browser@openai-bundled` plugin and its `node_repl` MCP companion. The plugin framework is on, with `[plugins._default].enabled=false` and other plugin entries explicitly off. Keeps `daemon_auto_start=false`, Apps/remote plugins off, full computer-use plugins and `cua_repl` off, and the Sky notification callback removed. Terminal BEL notifications remain. |
| Claude Code | `disableBundledSkills=true` removes vendor-bundled skills and model-visible built-in commands while retaining personal/project/plugin skills. Existing Remote Control and Workflows opt-outs remain. Chrome stays off by default through the shim; web search/fetch remain available. |
| OpenCode v2 | Native browser, web search/fetch, MCP and native subagents remain enabled under the existing permissions. |
| Devin | `auto_update=false` stops automatic downloads/installation; update checks may still occur. Existing Claude/Cloud import opt-outs remain. |
| DeepSeek Harness | Its existing launcher sets `DSH_TELEMETRY_DISABLED=1` for both TUI and headless paths. This disables OTel delivery, not the separate session-log contribution plugin. |
| Pi | Existing offline package policy, four core coding tools and explicit extensions remain. No additional shim or browser toggle needed for this profile. |
| Muse | Existing telemetry opt-out remains; the Notion and Sentry MCP servers were removed from the tracked settings. No browser/tool removal was verified. |
| Antigravity CLI | Native settings remain upstream-owned. Its documented `/browser` is on demand; no supported persistent browser-off switch was verified. |
| Vercel fx | Existing automatic-update and generated-title opt-outs remain. No additional browser automation integration was found in the reviewed profile. |
| Copilot CLI (pilot) | Disables IDE auto-connect and remote session/export defaults. Native agents are candidate pins; see [qualification](copilot-native.md). |
| Command Code | Existing native-tier agents and host-local taste-learning opt-out remain alongside the shim defaults. |

Codex's `daemon_auto_start=false` alone still permits attaching to a running
daemon, and `codex agents` can initiate one; this is why the shim matters.
The browser plugin requires `features.plugins=true`; enabling only its
individual entry while that global switch is off would leave it inactive.
The default-off plugin policy keeps other installed plugins from being
enabled as a side effect. The native web-search settings in Codex, Claude
and OpenCode were not disabled by this cleanup.

Codex marks `browser_use`, `computer_use` and related gates as
requirements-only. CLI parsing accepts these names, but that does not prove
they control the desktop integrations. This setup uses the configured
browser plugin and MCP companion and leaves managed browser requirements
unchanged. The existing companion paths require the installed ChatGPT
runtime; configuration validation is not a live browser smoke test.

## Apply and check

After updating `~/usr`, review `sh sync plan`, apply with `sh sync`, and
start a fresh shell/session. `command -v codex`, `command -v claude` and
`command -v cmd` should resolve to the shim directory. For a POSIX shell,
`. "$HOME/.config/sh/config.sh"` also refreshes the shared PATH.

`python3 -I dotfiles/harness-lean-test.py` checks launcher forwarding and
failure behavior with fake upstream binaries. `sh dotfiles/dsh-launcher-test.sh`
checks the existing DeepSeek launcher. These do not authenticate or call
models. On the intended host, check the fresh tool inventory, make a normal
MCP call and exercise delegation before attributing performance gains.

## Upstream references

- Codex: [no-daemon option](https://github.com/openai/codex/blob/ead489ac4d06b13a69909173469a17be126348a4/codex-rs/tui/src/cli.rs), [startup decisions](https://github.com/openai/codex/blob/ead489ac4d06b13a69909173469a17be126348a4/codex-rs/tui/src/startup_orchestration.rs), [feature gates](https://github.com/openai/codex/blob/ead489ac4d06b13a69909173469a17be126348a4/codex-rs/features/src/lib.rs).
- Codex 0.169.0: [plugin activation defaults](https://github.com/openai/codex/blob/rust-v0.169.0/codex-rs/config/src/types.rs).
- Claude: [environment variables](https://code.claude.com/docs/en/env-vars), [settings reference](https://code.claude.com/docs/en/settings-reference).
- OpenCode: [browser catalog](https://opencode.ai/docs/tools#browser), [permission ordering](https://opencode.ai/docs/permissions).
- Command Code: [environment variables](https://commandcode.ai/docs/settings#environment-variables).
- Devin: [automatic updates](https://docs.devin.ai/cli/reference/configuration/config-file#auto_update-user-only).
- DeepSeek: [telemetry variables](https://github.com/deepseek-ai/deepseek-harness/blob/master/apps/cli/reference/README.md).
