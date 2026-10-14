# Agent setup

`dotfiles/base/.codex/AGENTS.md` is the canonical global instruction file. The Claude and OpenCode `AGENTS.md` paths link to it. `dotfiles/base/.agents/skills/` holds the global skills. `dotfiles/base/.claude/agents/` holds Claude subagents. `dotfiles/base/.grok/agents/` holds the same five types for Grok, each pinned to `grok-4.7`. A same-named file there wins over the Claude copy. `dotfiles/base/.grok/config.toml` is the Grok user config.

The repository-specific skills live under `.agents/skills/`; `.claude/skills` links to that directory. The root `skills` link points to the global skills. Whole-directory links use `.sym-dir` markers and allowlists so harness-written state stays outside the repository.

`dotfiles/skills-check.sh` enforces skill frontmatter and invocation rules. A new hard agent rule needs enforcement in the same change. The repository working contract asks agents not to format, commit, or push unless asked; these are instructions, not harness permission rules.

The configured coding harnesses use unrestricted permissions: Claude Code runs `bypassPermissions` with sandboxing disabled; Codex uses `approval_policy = "never"` and `sandbox_mode = "danger-full-access"`; Muse uses `:unrestricted`; Grok uses `yolo = true` and sandbox profile `off`; OpenCode sets `permission` to `allow`. Grok imports Claude's `notify-sound` hook, but does not load Claude's `env`. The Grok config turns telemetry off, caps concurrent subagents at 64, caps nest depth at 3, and sets the status line. Grok has no worktree hook, so `worktree-create` and `worktree-remove` stay on Claude.

Codex stores trusted projects in `dotfiles/base/.codex/config.toml` and the OpenRouter profile in `or.config.toml`. Claude may rewrite `settings.json`, Codex may append trusted projects to `config.toml`, and Grok may rewrite `config.toml` from `/settings`. Review their diffs before committing.

Claude retains its `agent-tier-gate` subagent hook and the official Slack plugin. The configured OpenCode permission applies globally; there are no per-agent permission overrides in this tree.

`claude-or` and `claude-ds` start Claude Code through the OpenRouter and DeepSeek profiles with `--dangerously-skip-permissions`, taking the key from `vault`, so no permission prompt or deny rule applies in those sessions. `codex-or` starts Codex with the OpenRouter profile. `skill-usage` reads existing Claude, Codex, Muse, and Grok sessions; Grok does not persist its skill catalog, so `skill-eval` cannot calculate its listed-to-loaded rate.

`reset-claude` and `reset-codex` delete harness state under `$HOME`. Do not run them without an explicit request.

