# Agent setup

`dotfiles/base/.codex/AGENTS.md` is the canonical global instruction file. The Claude and OpenCode `AGENTS.md` paths link to it. `dotfiles/base/.agents/skills/` holds the global skills. `dotfiles/base/.claude/agents/` holds Claude subagents. `dotfiles/base/.grok/agents/` holds the same five types for Grok, each pinned to `grok-4.7`. A same-named file there wins over the Claude copy. `dotfiles/base/.grok/config.toml` is the Grok user config.

The repository-specific skills live under `.agents/skills/`; `.claude/skills` links to that directory. The root `skills` link points to the global skills. Whole-directory links use `.sym-dir` markers and allowlists so harness-written state stays outside the repository.

`dotfiles/skills-check.sh` enforces skill frontmatter and invocation rules. A new hard agent rule needs enforcement in the same change. The repository working contract asks agents not to format, commit, or push unless asked; these are instructions, not harness permission rules.

## Outcome-driven work

The global `do` skill selects a workflow for a task and follows it through verification. The global `do-it` skill keeps its separate meaning: it accepts every recommendation in the previous reply.

Invoke `/do <task>` using the host's syntax:

| Harness | Invocation |
| --- | --- |
| Codex CLI or IDE | `$do <task>`; interactive sessions also provide `/skills` to select a skill. |
| Claude Code | `/do <task>` in the prompt. |
| Muse Code | `/do <task>` in the TUI. |
| Grok Code | `/do <task>` in the TUI. |
| OpenCode | `/do <task>` in the TUI; the skill metadata exposes this shortcut. |

For example, ask Codex to `Use the $do skill to fix the reconnect notification bug.` Invoke `/do fix the reconnect notification bug` in Claude Code, Muse Code, Grok Code, or OpenCode.

Codex, Muse, Grok, and OpenCode discover shared skills in `~/.agents/skills`; Codex, Muse, and OpenCode also scan project `.agents/skills`. Claude uses `~/.claude/skills` and project `.claude/skills`. The home links expose `dotfiles/base/.agents/skills/` to global discovery, while `.claude/skills` links to project `.agents/skills`. Codex explicitly selects a skill with `$do` or `/skills`; Claude Code, Muse Code, and Grok expose user-invocable skills as `/do`; OpenCode uses the slash metadata. Use the equivalent host syntax for `create-verification-skill`.

The `/do` router follows a local verifier pointer in the repository instructions, then selects a local verification skill for the interface under change. Use `create-verification-skill` when a reusable project procedure is missing or stale. The `verify-usr` skill covers the safe `sym` scratch-home journey; `dotfiles-health` owns setup policy and structural invariants.

Native syntax and metadata differ by host. See [Codex skills](https://developers.openai.com/codex/skills/), [Claude Code skills](https://code.claude.com/docs/en/skills), [Muse Code skills](https://meta-models.github.io/muse-code-sdk/next/guides/extend/skills/), [Grok skills](https://docs.x.ai/build/features/skills-plugins-marketplaces), and [OpenCode skills](https://docs.opencode.ai/docs/skills/).

The configured coding harnesses use unrestricted permissions: Claude Code runs `bypassPermissions` with sandboxing disabled; Codex uses `approval_policy = "never"` and `sandbox_mode = "danger-full-access"`; Muse uses `:unrestricted`; Grok uses `yolo = true` and sandbox profile `off`; OpenCode sets `permission` to `allow`. Grok imports Claude's `notify-sound` hook, but does not load Claude's `env`. The Grok config turns telemetry off, caps concurrent subagents at 64, caps nest depth at 3, and sets the status line. Grok has no worktree hook, so `worktree-create` and `worktree-remove` stay on Claude.

Codex stores trusted projects in `dotfiles/base/.codex/config.toml` and the OpenRouter profile in `or.config.toml`. Claude may rewrite `settings.json`, Codex may append trusted projects to `config.toml`, and Grok may rewrite `config.toml` from `/settings`. Review their diffs before committing.

Claude retains its `agent-tier-gate` subagent hook and the official Slack plugin. The configured OpenCode permission applies globally; there are no per-agent permission overrides in this tree.

`claude-or` and `claude-ds` start Claude Code through the OpenRouter and DeepSeek profiles with `--dangerously-skip-permissions`, taking the key from `vault`, so no permission prompt or deny rule applies in those sessions. `codex-or` starts Codex with the OpenRouter profile. `skill-usage` reads existing Claude, Codex, Muse, and Grok sessions; Grok does not persist its skill catalog, so `skill-eval` cannot calculate its listed-to-loaded rate.

`reset-claude` and `reset-codex` delete harness state under `$HOME`. Do not run them without an explicit request.

