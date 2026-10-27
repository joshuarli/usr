# Agent setup

Use [`sbx`](sbx-spec.md) when running coding agents in a native macOS Seatbelt or Linux Bubblewrap process sandbox. It exposes the current directory read/write and makes the tracked global skills/instructions available read-only without importing host agent authentication state. This is weaker than a VM; review the security specification and run its platform integration checks before using it for sensitive projects.

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

Install Node.js 26.12.1 and the latest npm with `sh dl nodejs` on macOS arm64 or Linux x86_64 and arm64. No-argument `dl` also installs Node.js on those platforms, preferring the dl-managed runtime over any `node` earlier on `PATH` when it exists. Command Code requires Node.js 26.12.0+ and installs on demand with `sh dl cmd`, into `~/.local/share/command-code` (or `$XDG_DATA_HOME/command-code`). Grok and Freebuff are likewise opt-in (`sh dl grok`, `sh dl freebuff`); none of the three is downloaded by no-argument `dl` or `make`. Sync the tracked configuration with `make` as usual, then run `cmd login` yourself. The installer never touches Command's `~/.commandcode` credentials or sessions.

Command shares the canonical global instructions and discovers `~/.agents/skills/` without duplication. Its settings start in unrestricted `yolo` mode, disable Taste learning to avoid overlapping `agent-learn`, and omit the default commit co-author trailer. Edit the tracked `tasteLearning` setting to try Taste. Use `/skill:<name>` if a built-in command shadows a skill. Command sessions run the pinned `meta/muse-spark-1.3-contributor` model, which its `Explore` and `General` subagents inherit; its transcripts are not yet indexed by `agent-sessions` or `agent-learn`.

Freebuff runs sandboxed by default: `~/.local/bin/freebuff` is a shim that execs the dl-installed npm launcher through `sbx` with full network access, read/write confined to the invoking directory plus `~/.config/manicode` (where Freebuff keeps its downloaded native binary and auth), and read-only access to its install and node runtime trees. The shim prefers the dl-managed Node.js, canonicalizes executable paths before granting them (Seatbelt resolves the checked path, so a symlinked `node` would otherwise fail closed), and refuses to run when `sbx` is missing. On Linux the config directory is the real one, so login and the downloaded binary persist; on macOS `sbx` confines the child to a private home, so each run re-downloads and re-authenticates.

The tracked skills live in `dotfiles/base/.agents/skills/`. Directory links and allowlists keep harness state outside the repository. Claude subagents live in `dotfiles/base/.claude/agents/`; Grok has matching definitions in `dotfiles/base/.grok/agents/`. For a custom `DSH_HOME`, install the DeepSeek adapter at `${DSH_HOME}/AGENTS.md`; `DSH_AGENTS_HOME` controls shared skill discovery.

[`SKILLS.md`](../SKILLS.md) explains skill selection and the `/do` and `/yea` workflows. To invoke `/do` directly, use `$do <task>` in Codex, `/do <task>` in Claude Code, Muse Code, Grok Code, or OpenCode. Codex also provides `/skills`. Antigravity uses `/<skill-name>`. DeepSeek Harness loads matching skills through its skill tool. In interactive Muse Code, invoke an explicit skill with a leading `/<skill-name>` (for example `/refactor-python`, not `/skill <name>`); `/skills` lists skills and `/skills reload` refreshes after changes. A mid-sentence mention does not inject the body. Muse Code API, `muse serve` raw text, and headless (`muse exec`) sessions have no slash injection: when the user explicitly names an explicit-only skill and the skill tool rejects it as disabled, read the skill body directly (`~/.agents/skills/<name>/SKILL.md`, project skills under `.agents/skills/`) and work under it within existing scope and authority.

The [`do`](../dotfiles/base/.agents/skills/do/SKILL.md) skill tells agents when to run one targeted `agent-learn recall` before expensive rediscovery. Retrieval is local, needs no model grant, and returns leads rather than instructions; see [agent learning](agent-learning.md). No harness hook injects memory into every turn.

Antigravity CLI reads skill descriptions and may activate eligible skills automatically, and its skill frontmatter allows only `name` and `description`. Keep explicit-only workflows out of its automatic selection; the user requests one in plain language or with `/<skill-name>`.

Harnesses use native skill metadata and discovery paths. The checker at [`skills-check.sh`](../dotfiles/skills-check.sh) validates tracked skill metadata. See [the skills guide](../SKILLS.md) for invocation rules.

## Harness configuration

The tracked configs are under [`dotfiles/base`](../dotfiles/base/). Review changes after a harness writes its own config. Claude may rewrite `settings.json`, Codex may append trusted projects to `config.toml`, and Grok may rewrite `config.toml` from `/settings`. OpenCode restores its `cli.json` when missing, so install its tracked symlink while the client is stopped.

The configured harnesses allow unrestricted actions. Claude disables sandboxing and uses `bypassPermissions`; Codex sets `approval_policy = "never"` and `sandbox_mode = "danger-full-access"`; Muse uses `:unrestricted`; Grok sets `yolo = true` and sandbox profile `off`; OpenCode has an allow-all permissions rule; Command Code defaults to `yolo`. Grok imports Claude hooks but not Claude's `env` settings. See the tracked configs for hook and notification details.

`reset-agents` clears Claude, Codex, Grok, Muse, and OpenCode state under `$HOME`; pass one harness name to reset only that harness. It keeps dotfiles-managed files and `.credentials.json`, `auth.json`, and `mcp_credentials.json`. It rejects paths outside the resolved home and paths with symlinked components. Run it only when you intend to reset state. See its [implementation](../dotfiles/base/.local/bin/reset-agents) for supported paths.
