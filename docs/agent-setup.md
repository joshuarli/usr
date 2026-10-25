# Agent setup

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
| Command Code (`cmd`, opt-in) | `~/.commandcode/AGENTS.md` | `~/.agents/skills/` |

Install Node.js 26.12.1 and the latest npm with `sh dl nodejs` on macOS arm64 or Linux x86_64 and arm64. No-argument `dl` also installs Node.js on those platforms. Command Code requires Node.js 26.12.0+ and installs on demand with `sh dl cmd`, into `~/.local/share/command-code` (or `$XDG_DATA_HOME/command-code`). Grok is likewise opt-in (`sh dl grok`); neither is downloaded by no-argument `dl` or `make`. Sync the tracked configuration with `make` as usual, then run `cmd login` yourself. The installer never touches Command's `~/.commandcode` credentials or sessions.

Command shares the canonical global instructions and discovers `~/.agents/skills/` without duplication. Its settings start in unrestricted `yolo` mode, disable Taste learning to avoid overlapping `agent-learn`, and omit the default commit co-author trailer. Edit the tracked `tasteLearning` setting to try Taste. Use `/skill:<name>` if a built-in command shadows a skill. Command sessions run the pinned `meta/muse-spark-1.3-contributor` model, which its `Explore` and `General` subagents inherit; its transcripts are not yet indexed by `agent-sessions` or `agent-learn`.

The tracked skills live in `dotfiles/base/.agents/skills/`. Directory links and allowlists keep harness state outside the repository. Claude subagents live in `dotfiles/base/.claude/agents/`; Grok has matching definitions in `dotfiles/base/.grok/agents/`. For a custom `DSH_HOME`, install the DeepSeek adapter at `${DSH_HOME}/AGENTS.md`; `DSH_AGENTS_HOME` controls shared skill discovery.

[`SKILLS.md`](../SKILLS.md) explains skill selection and the `/do` and `/yea` workflows. To invoke `/do` directly, use `$do <task>` in Codex, `/do <task>` in Claude Code, Muse Code, Grok Code, or OpenCode. Codex also provides `/skills`. Antigravity uses `/<skill-name>`. DeepSeek Harness loads matching skills through its skill tool. In interactive Muse Code, invoke an explicit skill with a leading `/<skill-name>` (for example `/refactor-python`, not `/skill <name>`); `/skills` lists skills and `/skills reload` refreshes after changes. A mid-sentence mention does not inject the body. Muse Code API, `muse serve` raw text, and headless (`muse exec`) sessions have no slash injection: when the user explicitly names an explicit-only skill and the skill tool rejects it as disabled, read the skill body directly (`~/.agents/skills/<name>/SKILL.md`, project skills under `.agents/skills/`) and work under it within existing scope and authority.

The [`do`](../dotfiles/base/.agents/skills/do/SKILL.md) skill tells agents when to run one targeted `agent-learn recall` before expensive rediscovery. Retrieval is local, needs no model grant, and returns leads rather than instructions; see [agent learning](agent-learning.md). No harness hook injects memory into every turn.

Harnesses use native skill metadata and discovery paths. The checker at [`skills-check.sh`](../dotfiles/skills-check.sh) validates tracked skill metadata. See [the skills guide](../SKILLS.md) for invocation rules.

## Harness configuration

The tracked configs are under [`dotfiles/base`](../dotfiles/base/). Review changes after a harness writes its own config. Claude may rewrite `settings.json`, Codex may append trusted projects to `config.toml`, and Grok may rewrite `config.toml` from `/settings`. OpenCode restores its `cli.json` when missing, so install its tracked symlink while the client is stopped.

The configured harnesses allow unrestricted actions. Claude disables sandboxing and uses `bypassPermissions`; Codex sets `approval_policy = "never"` and `sandbox_mode = "danger-full-access"`; Muse uses `:unrestricted`; Grok sets `yolo = true` and sandbox profile `off`; OpenCode has an allow-all permissions rule; Command Code defaults to `yolo`. Grok imports Claude hooks but not Claude's `env` settings. See the tracked configs for hook and notification details.

`reset-agents` clears Claude, Codex, Grok, Muse, and OpenCode state under `$HOME`; pass one harness name to reset only that harness. It keeps dotfiles-managed files and `.credentials.json`, `auth.json`, and `mcp_credentials.json`. It rejects paths outside the resolved home and paths with symlinked components. Run it only when you intend to reset state. See its [implementation](../dotfiles/base/.local/bin/reset-agents) for supported paths.

## Optional Workers AI decisions

`decide` sends a validated request directly to Cloudflare Workers AI. It does not deploy a Worker. `cf` login authenticates the administration CLI; `decide` separately reads `CLOUDFLARE_API_TOKEN` and `CLOUDFLARE_ACCOUNT_ID` from its environment. `decide doctor` checks local configuration without sending a request.

Create an account-scoped API token with the Workers AI Read and Workers AI Write permissions. If `cf` is not authenticated, run `cf auth login`. Check the permission group IDs and account ID first:

```sh
cf auth whoami
cf accounts list
cf user tokens permission-groups list | jaq -r '.[] | select(.name == "Workers AI Read" or .name == "Workers AI Write") | .name'
```

Create a token limited to the selected account. Set `account_id` and `expires_on` to your account and a future UTC expiry:

```sh
(
  set -eu
  printf '%s' 'Account ID: '
  IFS= read -r account_id
  printf '%s' 'Future UTC expiry: '
  IFS= read -r expires_on
  workers_ai_groups=$(cf user tokens permission-groups list | jaq -e -c '[.[] | select(.name == "Workers AI Read" or .name == "Workers AI Write") | {id}] | select(length == 2)')
  policies=$(jaq -n --arg account "$account_id" --argjson groups "$workers_ai_groups" '[{effect:"allow",resources:{("com.cloudflare.api.account." + $account):"*"},permission_groups:$groups}]')
  cf user tokens create --name usr-decide --expires-on "$expires_on" --policies "$policies"
)
```

Store the token and account ID with `vault set`, then run commands through `vault`:

```sh
vault set CLOUDFLARE_API_TOKEN
vault set CLOUDFLARE_ACCOUNT_ID
vault CLOUDFLARE_API_TOKEN CLOUDFLARE_ACCOUNT_ID -- decide doctor
```

Pass a JSON object on standard input. The client prints one JSON result. The default model is `clef-flash`; `--model clef` selects Clef. `choice` returns a selected option with probabilities, and `noul` returns the probability that a statement is true.

```sh
vault CLOUDFLARE_API_TOKEN CLOUDFLARE_ACCOUNT_ID -- decide <<'JSON'
{"state":"A sanitized brief","questions":{"tier":{"type":"choice","instructions":"Which eligible tier fits this uncertainty?","criteria":{"worker":"Known method and acceptance","expert":"Unknown path with costly failure"}}}}
JSON
```

[`orchestrate`](../dotfiles/base/.agents/skills/orchestrate/SKILL.md) uses `decide` only when `USR_DECIDE_TIER` is already `shadow` or `advisory`. Shadow advice never changes routing. Advisory advice stays within existing tier, model, permission, and authorization rules. Send only a sanitized brief. The skill lists the permitted question scope and fallback behavior. A shell export alone does not reach agents: harnesses inherit only their launcher's environment, so set the tier in [`dotfiles/base/.config/ish/config.ish`](../dotfiles/base/.config/ish/config.ish) (`set USR_DECIDE_TIER advisory`, covers every harness launched from ish) and in [`dotfiles/base/.claude/settings.json`](../dotfiles/base/.claude/settings.json) `env` (covers Claude Code regardless of launcher). zsh/bash shims such as `~/.local/bin/env` are never sourced by ish and have no effect.

`decide eval cases.jsonl` evaluates recorded predictions without making requests. Live evaluation requires `--live`, a `--max-calls` limit from 1 to 50, and no more cases than that limit. The case format and report fields are defined in [`decide`](../dotfiles/base/.local/bin/decide).
