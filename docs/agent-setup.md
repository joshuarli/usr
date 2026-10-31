# Agent setup

Use [`sbx`](sbx-spec.md) when running coding agents in a native macOS Seatbelt process sandbox; Linux sandboxing is out of scope. It exposes the current directory read/write and makes the tracked global skills/instructions available read-only without importing host agent authentication state. This is weaker than a VM; review the security specification and run its platform integration checks before using it for sensitive projects.

## Instructions and skills

[`dotfiles/base/.codex/AGENTS.md`](../dotfiles/base/.codex/AGENTS.md) is the canonical global instruction file. The adapters under `dotfiles/base/` point each harness to it.

| Harness | Global instructions | Shared skills |
| --- | --- | --- |
| Codex | `~/.codex/AGENTS.md` | `~/.agents/skills/` |
| Claude Code | `~/.claude/CLAUDE.md` | `~/.claude/skills/` |
| Muse Code | `~/.config/muse/AGENTS.md` | `~/.agents/skills/` |
| Grok Code | `~/.grok/AGENTS.md` | `~/.agents/skills/` |
| OpenCode | `~/.config/opencode/AGENTS.md` | `~/.agents/skills/` |
| Antigravity CLI | `~/.gemini/config/AGENTS.md` | `~/.gemini/antigravity-cli/skills/` |
| DeepSeek Harness | `${DSH_HOME:-~/.dsh}/AGENTS.md` | `${DSH_AGENTS_HOME:-~/.agents}/skills/` |
| Pi | `~/.pi/agent/AGENTS.md` | `~/.agents/skills/` |
| Command Code (`cmd`, opt-in) | `~/.commandcode/AGENTS.md` | `~/.agents/skills/` |
| Vercel fx (opt-in) | `~/.fx/AGENTS.md` | `~/.agents/skills/` |

Install Node.js 26.12.1 and the latest npm with `sh dl nodejs` on macOS arm64 or Linux x86_64 and arm64. No-argument `dl` also installs Node.js on those platforms, preferring the dl-managed runtime over any `node` earlier on `PATH` when it exists. Command Code requires Node.js 26.12.0+ and installs on demand with `sh dl cmd`, into `~/.local/share/command-code` (or `$XDG_DATA_HOME/command-code`). Grok and Freebuff are likewise opt-in (`sh dl grok`, `sh dl freebuff`); none of the three is downloaded by no-argument `dl` or `make`. Sync the tracked configuration with `make` as usual, then run `cmd login` yourself. The installer never touches Command's `~/.commandcode` credentials or sessions.

Command shares the canonical global instructions and discovers `~/.agents/skills/` without duplication. Its settings start in unrestricted `yolo` mode and omit the default commit co-author trailer. Taste learning is off per host via `cmd config set taste-learning false --scope user`, persisted in the untracked `~/.commandcode/config.json`; `/taste` re-enables it, and a project can override with `taste-learning-project`. This keeps it from overlapping `agent-learn` and from creating `.commandcode/taste/` in every repository. Use `/skill:<name>` if a built-in command shadows a skill. Command sessions run the pinned `deepseek/deepseek-v4.1-flash` model at `max` effort, which its `Explore` and `General` subagents inherit; its transcripts are not yet indexed by `agent-sessions` or `agent-learn`.

fx is opt-in via `sh dl fx` (pinned, checksum-verified native Vercel Labs release for macOS or Linux on arm64/x86_64). The tracked `~/.fx/AGENTS.md` links to the canonical instructions and `~/.fx/settings.json` selects Vercel AI Gateway's `meta/muse-spark-1.3-contributor` for both main sessions and subagents. No secrets, sessions, or auth tokens are checked into Git. Authenticate interactively with `fx login vercel` or `fx setup`; then use `fx`, `fx ask --json "task"`, `/skills`, and `$orchestrate`. Meta's Contributor tier permits training on prompts and outputs: do not use it for code or data that cannot be shared under those terms.

fx uses `auto` permissions with Contributor for permission reviews (instead of its more expensive default reviewer); it disables generated titles and binary auto-upgrades. This is not a sandbox: verify fx's state/auth access before placing it in `sbx`. `~/.fx/sessions/` and credentials remain local. fx's local event log is not yet supported by `agent-sessions`; `/resume-session fx <ID>` does an exact, read-only file handoff where possible, while `fx resume <ID>` resumes the original conversation. Use `fx status --json`, `fx doctor`, and `fx usage` for diagnosis and bills.

Freebuff runs sandboxed by default: `~/.local/bin/freebuff` is a shim that execs the dl-installed npm launcher through `sbx` with full network access, read/write confined to the invoking directory plus `~/.config/manicode` (where Freebuff keeps its downloaded native binary and auth), and read-only access to its install and node runtime trees. The shim prefers the dl-managed Node.js, canonicalizes executable paths before granting them (Seatbelt resolves the checked path, so a symlinked `node` would otherwise fail closed), and refuses to run when `sbx` is missing. On macOS `sbx` confines the child to a private home, so each run re-downloads and re-authenticates. Linux is out of scope.

For cross-harness continuation, `/resume-session <agent> <session-id>` recovers a named local transcript and continues work in the **current** agent; it does not reopen the old agent's native process. The session index covers Codex, Claude, Muse, Grok, OpenCode, and Pi; Command Code, Antigravity CLI, DeepSeek TUI, and fx use their local files when readable. In Pi, invoke it as `/skill:resume-session <agent> <session-id>`; in Codex, use `$resume-session <agent> <session-id>`.

The tracked skills live in `dotfiles/base/.agents/skills/`. Directory links and allowlists keep harness state outside the repository. Claude subagents live in `dotfiles/base/.claude/agents/`; Grok has matching definitions in `dotfiles/base/.grok/agents/`. For a custom `DSH_HOME`, install the DeepSeek adapter at `${DSH_HOME}/AGENTS.md`; `DSH_AGENTS_HOME` controls shared skill discovery.

[`SKILLS.md`](../SKILLS.md) explains skill selection and the `/do` and `/yea` workflows. To invoke `/do` directly, use `$do <task>` in Codex or fx, `/do <task>` in Claude Code, Muse Code, Grok Code, or OpenCode. Codex also provides `/skills`. Antigravity uses `/<skill-name>`. DeepSeek Harness loads matching skills through its skill tool. In interactive Muse Code, invoke an explicit skill with a leading `/<skill-name>` (for example `/refactor-python`, not `/skill <name>`); `/skills` lists skills and `/skills reload` refreshes after changes. A mid-sentence mention does not inject the body. Muse Code API, `muse serve` raw text, and headless (`muse exec`) sessions have no slash injection: when the user explicitly names an explicit-only skill and the skill tool rejects it as disabled, read the skill body directly (`~/.agents/skills/<name>/SKILL.md`, project skills under `.agents/skills/`) and work under it within existing scope and authority.

The [`do`](../dotfiles/base/.agents/skills/do/SKILL.md) skill tells agents when to run one targeted `agent-learn recall` before expensive rediscovery. Retrieval is local, needs no model grant, and returns leads rather than instructions; see [agent learning](agent-learning.md). No harness hook injects memory into every turn. Codex native memories are enabled separately for advisory cross-session hints; `agent-learn` remains the source-verified path for engineering decisions. Native extraction uses Luna, consolidation uses Terra, and background work waits at least 12 hours after activity with at least 50% rate-limit headroom.

Antigravity CLI reads skill descriptions and may activate eligible skills automatically, and its skill frontmatter allows only `name` and `description`. Keep explicit-only workflows out of its automatic selection; the user requests one in plain language or with `/<skill-name>`.

Harnesses use native skill metadata and discovery paths. The checker at [`skills-check.sh`](../dotfiles/skills-check.sh) validates tracked skill metadata. See [the skills guide](../SKILLS.md) for invocation rules.

## Harness configuration

Codex defaults to `gpt-6.1-terra` at `high` effort and to `gpt-6-luna` at `high` effort for unspecified children; the `orchestrate` tiers explicitly select their own models and efforts. These models select multi-agent V2, whose eight resident-thread slots include the parent. The V1 `agents.max_depth` setting does not restrict V2 nesting; the orchestration skill instructs V2 children not to spawn other children.

The tracked configs are under [`dotfiles/base`](../dotfiles/base/). Review changes after a harness writes its own config. Claude may rewrite `settings.json`, Codex may append trusted projects to `config.toml`, and Grok may rewrite `config.toml` from `/settings`. Antigravity CLI owns `~/.gemini/antigravity-cli/settings.json` outright, rewriting model selection and `trustedWorkspaces` on launch, so that file is untracked and left in place. OpenCode restores its `cli.json` when missing, so install its tracked symlink while the client is stopped.

The configured harnesses allow unrestricted actions. Claude disables sandboxing and uses `bypassPermissions`; Codex sets `approval_policy = "never"` and `sandbox_mode = "danger-full-access"`; Muse uses `:unrestricted`; Grok sets `yolo = true` and sandbox profile `off`; OpenCode has an allow-all permissions rule; Command Code defaults to `yolo`. fx uses `auto` permissions with the Contributor reviewer instead of the default higher-priced reviewer. Grok imports Claude hooks but not Claude's `env` settings. See the tracked configs for hook and notification details.

`reset-agents` clears Claude, Codex, Grok, Muse, and OpenCode state under `$HOME`; pass one harness name to reset only that harness. It keeps dotfiles-managed files and `.credentials.json`, `auth.json`, and `mcp_credentials.json`. It rejects paths outside the resolved home and paths with symlinked components. Run it only when you intend to reset state. See its [implementation](../dotfiles/base/.local/bin/reset-agents) for supported paths.
