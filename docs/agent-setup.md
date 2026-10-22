# Agent setup

`dotfiles/base/.codex/AGENTS.md` is the canonical global instruction file. Each harness adapter links to it; the table gives the installed path and shared skill discovery path.

| Harness | Global instructions | Shared skills |
| --- | --- | --- |
| Codex | `~/.codex/AGENTS.md` | `~/.agents/skills/` |
| Claude Code | `~/.claude/CLAUDE.md` | `~/.claude/skills/` |
| Muse Code | `~/.config/muse/AGENTS.md` | `~/.agents/skills/` |
| Grok Code | `~/.grok/AGENTS.md` | `~/.agents/skills/` |
| OpenCode | `~/.config/opencode/AGENTS.md` | `~/.agents/skills/` |
| Antigravity CLI | `~/.gemini/config/AGENTS.md` | `~/.gemini/antigravity-cli/skills/` |
| DeepSeek Harness | `${DSH_HOME:-~/.dsh}/AGENTS.md` | `${DSH_AGENTS_HOME:-~/.agents}/skills/` |

The adapter files under `dotfiles/base/` link to the canonical contract. Claude's `CLAUDE.md` adapter supplies its documented user-level instruction path. The DeepSeek adapter targets the default `~/.dsh`; if `DSH_HOME` is customized, put the same adapter at `${DSH_HOME}/AGENTS.md`. Shared skills follow `DSH_AGENTS_HOME`, defaulting to `~/.agents`. Antigravity's skills directory and Claude's skills directory link to `dotfiles/base/.agents/skills/`. Antigravity settings omit machine-specific `trustedWorkspaces`. `dotfiles/base/.claude/agents/` holds Claude subagents. `dotfiles/base/.grok/agents/` holds the same five types for Grok, each pinned to `grok-4.7`. A same-named file there wins over the Claude copy. `dotfiles/base/.grok/config.toml` is the Grok user config.

The repository-specific skills live under `.agents/skills/`; `.claude/skills` links to that directory. Antigravity CLI also scans workspace `.agents/skills/`. The root `skills` link points to the global skills. Whole-directory links use `.sym-dir` markers and allowlists so harness-written state stays outside the repository.

`dotfiles/skills-check.sh` enforces skill frontmatter and invocation rules. A new hard agent rule needs enforcement in the same change. The repository working contract asks agents not to format, commit, or push unless asked; these are instructions, not harness permission rules.

## Outcome-driven work

[SKILLS.md](../SKILLS.md) is the owner's guide to the meta skills: which to reach for, and how review, steering, and campaign skills fit together.

Skill descriptions determine when an agent loads a reusable method. Plain requests can select the global `do` workflow when uncertainty, dependent steps, consequences, or acceptance requirements warrant it. Small edits and one-step questions stay on the short path. `do` preserves the request mode and authority through completion. `yea` remains explicit-only; it accepts every recommendation in the previous reply and carries out authorized effects within its rules.

`/do` remains available as an explicit shortcut:

| Harness | Invocation |
| --- | --- |
| Codex CLI or IDE | `$do <task>`; interactive sessions also provide `/skills` to select a skill. |
| Claude Code | `/do <task>` in the prompt. |
| Muse Code | `/do <task>` in the TUI. |
| Grok Code | `/do <task>` in the TUI. |
| OpenCode | `/do <task>` in the TUI; the skill metadata exposes this shortcut. |

You do not need to name a skill in a normal request. Codex, Claude Code, Muse Code, Grok Code, and OpenCode can select eligible skills from their descriptions. Codex reads `agents/openai.yaml`; Claude, Muse, Grok, and DeepSeek Harness use `disable-model-invocation`; OpenCode uses `metadata.opencode/autoinvoke`. OpenCode defaults to listing skills for model selection, so every shared explicit-only skill sets `opencode/autoinvoke: "false"`. Antigravity CLI reads only `name` and `description` from skill frontmatter; its global instruction file keeps shared skills with `disable-model-invocation: true` explicit-only. Auto-eligible descriptions name their useful entry conditions and a `Skip` case.

The global `do` skill is automatically eligible for substantial work. `architect`, `review`, and `blast-radius` are eligible only when their descriptions' conditions apply. Broad audits, verifier creation, accepting recommendations, unattended work, and publication workflows remain explicit-only. The explicit shortcuts remain available where the host supports them.

Codex, Muse, Grok, OpenCode, and DeepSeek Harness discover shared skills in `~/.agents/skills`; Codex, Muse, OpenCode, and DeepSeek Harness also scan project `.agents/skills`. Claude uses `~/.claude/skills` and project `.claude/skills`. Antigravity CLI uses `~/.gemini/antigravity-cli/skills`, linked to `dotfiles/base/.agents/skills/`. Codex accepts `$do` or `/skills`; Claude Code, Muse Code, and Grok expose user-invocable skills as `/do`; OpenCode exposes `/do` through `opencode/slash`; Antigravity CLI exposes `/<skill-name>`. DeepSeek Harness loads matching skills through its skill tool. Bare `dsh` and `dsh tui` start the tracked TUI launcher on its `dsh-tui` profile; it supplies `DEEPSEEK_API_KEY` from `vault`, or uses the exported variable when `vault` is unavailable. `dsh web` selects the core Web profile with the same key. Use the equivalent host syntax for `create-verification-skill`.

The `/do` router follows a local verifier pointer in the repository instructions, then selects a local verification skill for the interface under change. Use `create-verification-skill` when a reusable project procedure is missing or stale. The `verify-usr` skill covers the safe `sym` scratch-home journey; `dotfiles-health` owns setup policy and structural invariants.

Native syntax and metadata differ by host. See [Codex skills](https://learn.chatgpt.com/docs/build-skills), [Claude Code skills](https://code.claude.com/docs/en/skills), [Muse Code skills](https://meta-models.github.io/muse-code-sdk/next/guides/extend/skills/), [Grok skills](https://docs.x.ai/build/features/skills-plugins-marketplaces), [OpenCode skills](https://docs.opencode.ai/docs/skills/), [Antigravity skills](https://antigravity.google/docs/skills), [DeepSeek Harness instructions](https://github.com/deepseek-ai/deepseek-harness/blob/master/packages/context/agent-instructions/README.md), and [DeepSeek Harness skills](https://github.com/deepseek-ai/deepseek-harness/blob/master/docs/subsystems/skills.md).

The configured coding harnesses use unrestricted permissions: Claude Code runs `bypassPermissions` with sandboxing disabled; Codex uses `approval_policy = "never"` and `sandbox_mode = "danger-full-access"`; Muse uses `:unrestricted`; Grok uses `yolo = true` and sandbox profile `off`; OpenCode allows everything with a `permissions` allow-all rule. Grok imports Claude's hooks, but does not load Claude's `env`. The Grok config turns telemetry off, caps concurrent subagents at 64, caps nest depth at 3, and sets the status line. Grok has no worktree hook, so `worktree-create` and `worktree-remove` stay on Claude.

A session that needs you rings the terminal bell. `notify-sound` writes BEL to the pane, tmux marks that window, and Alacritty plays Glass for the bell. Claude's `Notification` hook calls `notify-sound`. Grok runs that hook and sets `[ui.notifications] method = "none"`, so it does not ring a second time. Codex sends BEL from the TUI on a finished turn or an approval. Muse calls `notify-sound` from `Stop` and `Notification`. OpenCode calls it when a session goes idle. Antigravity sets `notifications` on, which rings the terminal bell.

Codex stores trusted projects in `dotfiles/base/.codex/config.toml` and the OpenRouter profile in `or.config.toml`. Claude may rewrite `settings.json`, Codex may append trusted projects to `config.toml`, and Grok may rewrite `config.toml` from `/settings`. The OpenCode client owns `cli.json` and restores it when missing, so install its tracked symlink with the client stopped. Review their diffs before committing.

Claude retains its `agent-tier-gate` subagent hook and the official Slack plugin. The configured OpenCode `permissions` allow-all rule applies globally; there are no per-agent permission overrides in this tree.

`claude-api [--budget usd] [--model name] [--] <prompt...>` runs Claude Code with API credits. The default budget is `$100`, passed to `--max-budget-usd`. Claude Code estimates this cap, and actual spend can exceed it ([CLI reference](https://code.claude.com/docs/en/cli-reference)). Put `/skill-name` at the start of the prompt to invoke a skill. In print mode, Claude Code loads only the first skill and treats the remaining prompt as that skill's arguments. Run `claude-api --help` to see this caveat from the command.

`claude-or` and `claude-ds` start Claude Code through the OpenRouter and DeepSeek profiles with `--dangerously-skip-permissions`, taking the key from `vault`, so no permission prompt or deny rule applies in those sessions. `codex-or` starts Codex with the OpenRouter profile. `skill-usage` reads existing Claude, Codex, Muse, and Grok sessions; Grok does not persist its skill catalog, so `skill-eval` cannot calculate its listed-to-loaded rate.

`reset-agents` clears harness state under `$HOME`. With no argument it resets Claude, Codex, Grok, Muse, and OpenCode. Pass one name to reset only that harness, such as `reset-agents claude`. Muse follows `XDG_CONFIG_HOME` and `XDG_DATA_HOME`, defaulting to `~/.config/muse` and `~/.local/share/muse`. OpenCode resets `~/.config/opencode`, `~/.local/share/opencode`, and the `XDG_CACHE_HOME` `opencode` directory, defaulting to `~/.cache/opencode`. The command keeps dotfiles-managed files and the credential files `.credentials.json`, `auth.json`, and `mcp_credentials.json`. It resolves a symlinked `HOME`, then refuses target paths outside that resolved home or with symlinked components beneath it. Do not run it without an explicit request.

