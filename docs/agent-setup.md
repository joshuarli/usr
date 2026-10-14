# Agent setup

`dotfiles/base/.codex/AGENTS.md` is the canonical global instruction file. The Claude, Pi, and OpenCode `AGENTS.md` paths link to it. `dotfiles/base/.agents/skills/` holds the global skills. `dotfiles/base/.claude/agents/` holds Claude subagents. `dotfiles/base/.grok/agents/` holds the same five types for Grok, each pinned to `grok-4.7`. A same-named file there wins over the Claude copy. `dotfiles/base/.grok/config.toml` is the Grok user config.

The repository-specific skills live under `.agents/skills/`; `.claude/skills` links to that directory. The root `skills` link points to the global skills. Whole-directory links use `.sym-dir` markers and allowlists so harness-written state stays outside the repository.

`dotfiles/skills-check.sh` enforces skill frontmatter and invocation rules. A new hard agent rule needs enforcement in the same change. The no-formatter rule is enforced in Claude permissions and Codex prefix rules. Codex lists prompt decisions for direct push commands, but its profile sets `approval_policy = "never"`, and `git -C ... push` matches no rule. The global Git pre-push hook only refuses when stderr is not a terminal.

Grok loads those Claude permission rules, and the `notify-sound` hook, from `~/.claude/settings.json`. An `ask` rule still prompts when Grok is in always-approve. Grok does not load Claude's `env`. The Grok config turns telemetry off, caps concurrent subagents at 64, caps nest depth at 3, and sets the status line. Grok has no worktree hook, so `worktree-create` and `worktree-remove` stay on Claude.

Codex stores trusted projects in `dotfiles/base/.codex/config.toml` and the OpenRouter profile in `or.config.toml`. Claude may rewrite `settings.json`, Codex may append trusted projects to `config.toml`, and Grok may rewrite `config.toml` from `/settings`. Review their diffs before committing.

`claude-or` and `claude-ds` start Claude Code through the OpenRouter and DeepSeek profiles with `--dangerously-skip-permissions`, taking the key from `vault`, so no permission prompt or deny rule applies in those sessions. `codex-or` starts Codex with the OpenRouter profile. `skill-usage` reads existing Claude and Codex sessions; `skill-eval` uses those counts and session examples to evaluate auto-triggered skills.

`reset-claude` and `reset-codex` delete harness state under `$HOME`. Do not run them without an explicit request.

