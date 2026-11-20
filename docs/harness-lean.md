# Lean harness defaults

Keep coding tools, MCP, shared skills, subagents, session hooks and
`agent-browser`. Disable unused browser integrations and background work
with supported switches. These defaults do not shrink installed binaries;
token, RSS and latency improvements need separate measurement.

## Launch shims

The tracked shims live in `~/.local/lib/harness-shims`. The sh, ish and xshi
configs put that directory before `~/.local/bin`. Each shim directly execs
the sync-managed binary in `~/.local/bin`, so installers and vendor updates
retain ownership of their launchers. No PATH search or binary renaming is
needed. Programs launched with an absolute binary path, or from a GUI that
does not inherit this PATH, bypass the shims.

| Command | Shim default | Explicit override |
| --- | --- | --- |
| `codex` | Adds `--no-daemon`, which avoids both starting and reusing the shared daemon. Does not duplicate an existing flag; leaves explicit `--remote` invocations alone. | Use `~/.local/bin/codex` for the native launcher. |
| `claude` | Sets `CLAUDE_CODE_ENABLE_CFC=0`, so native Chrome starts off without changing subcommand arguments. | `claude --chrome` explicitly opts back in. |
| `cmd` | Disables startup notices, the automatic updater and telemetry with `CMD_DISABLE_NOTICES`, `COMMANDCODE_SKIP_UPDATES` and `DO_NOT_TRACK`. | Use `~/.local/bin/cmd` for the native launcher. |

`codex-or`, `claude-or` and `claude-ds` inherit these defaults when they
resolve the underlying command through that PATH. Direct invocation of a
native launcher bypasses only its shim; tracked configuration still applies.

## Configuration by harness

| Harness | Native configuration and scope |
| --- | --- |
| Codex | Keeps `daemon_auto_start=false`, Apps/plugins/remote plugins off, and browser MCP servers `node_repl`/`cua_repl` off. The three browser/computer-use plugin entries are also off if plugins are later re-enabled. Removes the unused Sky Computer Use `notify` process launch; terminal BEL notifications remain. |
| Claude Code | `disableBundledSkills=true` removes vendor-bundled skills and model-visible built-in commands while retaining personal/project/plugin skills. Existing Remote Control and Workflows opt-outs remain. Chrome is default-off through the shim, rather than permanently denied. |
| OpenCode v2 | A `browser` deny after the general allow removes the built-in browser Code Mode catalog. Web search/fetch, MCP and native subagents remain. |
| Devin | `auto_update=false` stops automatic downloads/installation; update checks may still occur. Existing Claude/Cloud import opt-outs remain. |
| DeepSeek Harness | Its existing launcher sets `DSH_TELEMETRY_DISABLED=1` for both TUI and headless paths. This disables OTel delivery, not the separate session-log contribution plugin. |
| Pi | Existing offline package policy, four core coding tools and explicit extensions remain. No additional shim or browser toggle needed for this profile. |
| Muse | Existing telemetry opt-out and MCP configuration remain. No additional browser/tool removal was verified. |
| Antigravity CLI | Native settings remain upstream-owned. Its documented `/browser` is on demand; no supported persistent browser-off switch was verified. |
| Vercel fx | Existing automatic-update and generated-title opt-outs remain. No additional browser automation integration was found in the reviewed profile. |
| Command Code | Existing native-tier agents and host-local taste-learning opt-out remain alongside the shim defaults. |

Codex's `daemon_auto_start=false` alone still permits attaching to a running
daemon, and `codex agents` can initiate one; this is why the shim matters.
Disabling individual plugin entries adds no baseline savings while plugins
are globally off. The direct MCP opt-outs and removed notification callback
are independent of that global plugin switch.

Codex marks `browser_use`, `computer_use` and related gates as
requirements-only. CLI parsing accepts these names, but that does not prove
they control the desktop integrations. This setup disables the configured
integration sources; it does not install system-managed requirements or
claim to prohibit every desktop browser entry point.

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
- Claude: [environment variables](https://code.claude.com/docs/en/env-vars), [settings reference](https://code.claude.com/docs/en/settings-reference).
- OpenCode: [browser catalog](https://opencode.ai/docs/tools#browser), [permission ordering](https://opencode.ai/docs/permissions).
- Command Code: [environment variables](https://commandcode.ai/docs/settings#environment-variables).
- Devin: [automatic updates](https://docs.devin.ai/cli/reference/configuration/config-file#auto_update-user-only).
- DeepSeek: [telemetry variables](https://github.com/deepseek-ai/deepseek-harness/blob/master/apps/cli/reference/README.md).
