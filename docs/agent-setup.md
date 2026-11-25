# Agent setup

Use [`sbx`](sbx-spec.md) when running coding agents in a native macOS Seatbelt process sandbox; Linux sandboxing is out of scope. It exposes the current directory read/write and makes the tracked global skills/instructions available read-only without importing host agent authentication state. This is weaker than a VM; review the security specification and run its platform integration checks before using it for sensitive projects.

## Advisory decision routing

`orchestrate` consults the local `decide route` CLI by default when a nontrivial delegated task has evidence suitable for safe external inference. **Reuse your existing `cf auth login` session:** create a structured, validated JSON `TaskBrief` using `decide route --guide`, then pipe it into `decide route --baseline worker`. With no explicit REST credentials, it runs `cf ai run @cf/cloudflare/clef-flash --body @/dev/stdin`. cf resolves the OAuth profile and account, and refreshes tokens without exposing them to `decide`. Check sign-in with `cf auth whoami`. `decide doctor` checks local config and CLI presence, not live OAuth validity.

Explicit `CLOUDFLARE_API_TOKEN` and `CLOUDFLARE_ACCOUNT_ID` still take priority for the direct REST client. This does not create credentials or change Cloudflare settings. Use a recent cf CLI with the `ai run` command. Live `decide eval --live` still uses direct REST credentials.

Do not send repository source, credentials, full transcripts, sensitive internal logs, or customer data. The route command accepts only a bounded, evidence-bearing JSON brief on stdin; plain-text task titles are rejected, and missing evidence causes a local abstention. It never prints the brief. Missing cf/login credentials, quota, provider errors, or an explicit `DECIDE_ROUTING=off` cause the existing deterministic router to remain in control; they do not block coding work. The CLI's tier advice never grants extra tools or model/provider changes. See [decide CLI](../tools/decide/README.md) and [orchestrate](../dotfiles/base/.agents/skills/orchestrate/SKILL.md) for limitations, confidence heuristics, and evaluation.

## Instructions and skills

Copilot CLI is an unqualified native-only pilot. See [Copilot setup and qualification](copilot-native.md) before installing or using the MAI lanes.

Proactive cleanup uses [disk-pressure events](agent-disk-pressure.md) and runs only below 16 GiB available system space. Codex/Claude hooks and the Pi run-entry extension stay silent on healthy disks. Other harnesses use the shared one-shot fallback in their working contract; there is no model polling loop.

[`dotfiles/base/.codex/AGENTS.md`](../dotfiles/base/.codex/AGENTS.md) remains the normal shared contract. Other harness adapters point to it; Antigravity has an equivalent regular-file policy projection. Claude's `CLAUDE.md` and Codex's higher-precedence `AGENTS.override.md` instead load a small bootstrap; startup hooks select the normal contract or the lean contract for Opus 5.5 in Claude and Sol 6.2 in Codex. The contracts are alternatives, not layers. See [instruction profiles](model-profiles.md) for activation, fallback, and fresh-session boundaries.

| Harness | Global instructions | Shared skills |
| --- | --- | --- |
| Codex | `~/.codex/AGENTS.override.md` (profile bootstrap) | `~/.agents/skills/` |
| Claude Code | `~/.claude/CLAUDE.md` | `~/.claude/skills/` |
| Muse Code | `~/.config/muse/AGENTS.md` | `~/.agents/skills/` |
| OpenCode | `~/.config/opencode/AGENTS.md` | `~/.agents/skills/` |
| Devin | `~/.config/devin/AGENTS.md` | `~/.agents/skills/` |
| Antigravity CLI | `~/.gemini/config/AGENTS.md` | `~/.gemini/antigravity-cli/skills/` |
| DeepSeek Harness | `${DSH_HOME:-~/.dsh}/AGENTS.md` | `${DSH_AGENTS_HOME:-~/.agents}/skills/` |
| Pi | `~/.pi/agent/AGENTS.md` | `~/.agents/skills/` |
| Command Code (`cmd`) | `~/.commandcode/AGENTS.md` | `~/.agents/skills/` |
| Copilot CLI (pilot) | `~/.copilot/copilot-instructions.md` | `~/.agents/skills/` |
| Vercel fx (opt-in) | `~/.fx/AGENTS.md` | `~/.agents/skills/` |

**Native-only hosts:** the Pi bridge stays the default. A host or session without bridge providers, such as a cloud agent environment, sets `USR_DELEGATION=native`; the Claude and Codex startup hook then tells the session to use the tier-matched native subagents in `orchestrate`, and the generated policy treats that switch like bridge exhaustion. Any other value, or none, keeps the bridge.

**Routing coverage:** both instruction profiles and all harnesses share [orchestrate](../dotfiles/base/.agents/skills/orchestrate/SKILL.md). OpenCode, Devin, top-level Command Code, Antigravity CLI and the Copilot CLI pilot delegate only through their native subagents; other harnesses use the shared bridge except for the documented lower-tier native quota and host-access exceptions. This is instruction policy, not an interception hook. `decide` is advisory only.

<!-- policy:begin routing-summary -->
<!-- Generated from tools/pi-subagent-bridge/src/policy.ts; run make generate. -->
Bridge tiers: `scout`, `mechanic`, `worker`, `expert`. The `expert` tier has one route, Pi `devin/swe-2.1` (`max`), and no fallback: when that route is unavailable or exhausted the expert lane is blocked, never moved to another model. Top-level OpenCode, Devin, Command Code, Antigravity and Copilot CLI parents keep their native expert agents (below). There is no `god` tier. The model families `gemini-3.8` and `gemini-4-argon` and `gemini-4-carbon` and `gpt-6-astra` and `gpt-6.1-astra` and `gpt-6.2-astra` and `claude-fable` and `fable` are prohibited, including every effort variant.
<!-- policy:end routing-summary -->

After updating `usr`, review `sh sync plan`, then use `sh sync` and `sh sync doctor` to apply and inspect home configuration.

Install Node.js 26.13.1 and its distribution-bundled npm (without an npm registry query) with `sh sync tools nodejs` on macOS arm64 or Linux x86_64 and arm64. No-argument `sync tools` also installs Node.js on those platforms, preferring the sync-managed runtime over any `node` earlier on `PATH` when it exists. Command Code requires Node.js 26.12.0+ and is installed by default with `sh sync` (or individually with `sh sync tools cmd`), into `~/.local/share/command-code` (or `$XDG_DATA_HOME/command-code`). Sync the tracked configuration with `sh sync`, then run `cmd login` yourself. The installer never touches Command's `~/.commandcode` credentials or sessions.

Command shares the canonical global instructions and discovers `~/.agents/skills/` without duplication. Its settings start in unrestricted `yolo` mode and omit the default commit co-author trailer. Taste learning is off per host via `cmd config set taste-learning false --scope user`, persisted in the untracked `~/.commandcode/config.json`; `/taste` re-enables it, and a project can override with `taste-learning-project`. This keeps it from creating `.commandcode/taste/` in every repository. Use `/skill:<name>` if a built-in command shadows a skill. Command sessions retain the pinned `deepseek/deepseek-v4.1-flash` parent model at `max` effort. Top-level Command Code sessions delegate only to the tracked `usr-*` native agents in `~/.commandcode/agents/` (individual links installed by `sh sync`); they do not launch the Pi bridge. See [Command Code native tiers](command-code-delegation.md) for the model roster, HY4-medium pilot, quota caveats, and host qualification checks. Antigravity CLI uses [Neon/Hydrogen native tiers](antigravity-native.md) exclusively: its documented `flash`/`pro` custom-agent selectors do not enforce exact model or effort pins.

fx is opt-in via `sh sync tools fx` (pinned, checksum-verified native Vercel Labs release for macOS or Linux on arm64/x86_64). The tracked `~/.fx/AGENTS.md` links to the canonical instructions. fx reads settings only from a regular file, never through a symlink, so `sh sync tools fx` merges `tools/sync/fx-settings.json` into `~/.fx/settings.json` (mode 0600, keeping keys fx saved itself); it selects Vercel AI Gateway's `meta/muse-spark-1.3-contributor` for main sessions; delegated work uses the shared bridge. No secrets, sessions, or auth tokens are checked into Git. Authenticate interactively with `fx login vercel` or `fx setup`; then use `fx`, `fx ask --json "task"`, `/skills`, and `$orchestrate`. Meta's Contributor tier permits training on prompts and outputs: do not use it for code or data that cannot be shared under those terms.

fx uses `auto` permissions with Contributor for permission reviews (instead of its more expensive default reviewer); it disables generated titles and binary auto-upgrades. This is not a sandbox: verify fx's state/auth access before placing it in `sbx`. `~/.fx/sessions/` and credentials remain local. `/resume-session fx <ID>` does an exact, read-only file handoff where possible, while `fx resume <ID>` resumes the original conversation. Use `fx status --json`, `fx doctor`, and `fx usage` for diagnosis and bills.

The [Pi SDK + pi-subagents bridge](../tools/pi-subagent-bridge/README.md) owns approved routes, durable worker state and typed native Pi nesting. Parents retain worktree scope, independent proof, diff review and integration. The CLI executors are leaves. Muse Contributor routes allow Meta to use prompts, code and outputs for training. [Pi setup](pi.md) covers pinned release installation, authentication and the intercom boundary.

`cleanup-sessions [AGE]` (default `7d`) removes session transcripts and per-session state last modified before AGE ago from Claude, Codex, Pi, Muse, Command Code, Antigravity, FX and OpenCode (whole sessions from `opencode.db`, with their messages). It never follows symlinks, leaves settings, credentials, memory and indexes alone, and does not cover Devin or the Copilot pilot. Preview with `--dry-run`; `--json` reports per-harness counts and unsupported harnesses.

For cross-harness continuation, `/resume-session <agent> <session-id>` recovers a named local transcript and continues work in the **current** agent; it does not reopen the old agent's native process. It reads supported harnesses' local transcripts directly; DeepSeek TUI and fx use their local files when readable. Copilot named-session recovery, reset and quota reporting remain [pilot qualification work](copilot-native.md). In Pi, invoke it as `/skill:resume-session <agent> <session-id>`; in Codex, use `$resume-session <agent> <session-id>`.

### Browser-native WebMCP

The [webmcp skill](../dotfiles/base/.agents/skills/webmcp/SKILL.md)
covers sites that expose structured in-page tools through the experimental
browser API. In a bctl-managed session, use `bctl webmcp list/call` without
adding an MCP server or JS package. bctl remains opt-in through
`sh sync tools bctl`; its browser images are not yet WebMCP-qualified.
Fall back to the existing [agent-browser skill](../dotfiles/base/.agents/skills/agent-browser/SKILL.md)
and CDP/DOM actions when a page lacks the API. See
[bctl's implementation notes](https://github.com/joshuarli/bctl/blob/main/docs/webmcp.md).
The tracked skills live in `dotfiles/base/.agents/skills/`. Directory links and allowlists keep harness state outside the repository. Removed native profiles are not installed. For a custom `DSH_HOME`, install the DeepSeek adapter at `${DSH_HOME}/AGENTS.md`; `DSH_AGENTS_HOME` controls shared skill discovery.

[`SKILLS.md`](../SKILLS.md) explains skill selection and the `/do` and `/yea` workflows. To invoke `/do` directly, use `$do <task>` in Codex or fx, `/do <task>` in Claude Code, Muse Code, or OpenCode. Codex also provides `/skills`. Antigravity uses `/<skill-name>`. DeepSeek Harness loads matching skills through its skill tool. In interactive Muse Code, invoke an explicit skill with a leading `/<skill-name>` (for example `/standardize`, not `/skill <name>`); `/skills` lists skills and `/skills reload` refreshes after changes. A mid-sentence mention does not inject the body. Muse Code API, `muse serve` raw text, and headless (`muse exec`) sessions have no slash injection: when the user explicitly names an explicit-only skill and the skill tool rejects it as disabled, read the skill body directly (`~/.agents/skills/<name>/SKILL.md`, project skills under `.agents/skills/`) and work under it within existing scope and authority.

Codex native memories are enabled for advisory cross-session hints. Native extraction uses Luna, consolidation uses Terra, and background work waits at least 12 hours after activity with at least 50% rate-limit headroom.

Antigravity CLI reads skill descriptions and may activate eligible skills automatically, and its skill frontmatter allows only `name` and `description`. Keep explicit-only workflows out of its automatic selection; the user requests one in plain language or with `/<skill-name>`.

Harnesses use native skill metadata and discovery paths. The checker at [`skills.ts`](../tools/skills/skills.ts) validates tracked skill metadata. See [the skills guide](../SKILLS.md) for invocation rules.

### Coding standards

Coding standards are plain files in [`dotfiles/base/.agents/standards/`](../dotfiles/base/.agents/standards/), linked to `~/.agents/standards/`, not skills. A skill's description sits in every session's context and loads only when the model decides it applies; a standard costs nothing until a change triggers it. Each standard's frontmatter lists the paths, shebangs, and added-line patterns that trigger it, and `standards select` matches them against the working tree diff. Both contracts tell the agent to run it before reporting code changes done and to apply what it lists through the [gate](../dotfiles/base/.agents/instructions/coding-standards.md): `standards gate` prepares a worktree holding the committed diff, the standards it triggers and a reviewer brief, and one scout-tier reviewer reads them and returns findings, so the main session never loads the standard text. `do` and `review` run the same gate. Each standard opens with TOML frontmatter whose `[[trigger]]` tables combine gitignore-style `paths`, `shebang`, and added-line `content` conditions, and whose `[examples]` `standards check` proves; `standards explain FILE` shows each trigger's verdict. A standard's body splits into `## Code`, which the gate applies to touched code, and `## Adoption`, repository-wide work that only an explicit `/standardize` run performs; `/standardize` selects standards with `standards select --tree` and owns the shared process: scope, contract inspection, ordered passes, and verification. In Claude Code and Codex, a PostToolUse hook runs `standards hook`, which announces each standard once per session when an edited file first triggers it; other harnesses rely on the gate alone. Rules for how code must look (CLI design, error models, lifecycle and concurrency, OS boundaries, portability across macOS and Linux, security, durable state, and the language standards) are standards; methods and workflows such as `architect`, `root-cause`, and `make-it-fast` stay skills. Prefer a lint or test for any rule a tool can check.

## Harness configuration

The [lean harness defaults](harness-lean.md) use small launch shims alongside native settings to disable unwanted daemon and startup work. OpenCode and Codex retain native browsing; Claude keeps native Chrome off and uses agent-browser. Web search, coding tools, MCP, subagents and session hooks remain available. The shims live separately from native launchers.

Codex session defaults remain in its tracked configuration. Delegated work follows the generated policy above. Multi-agent V2 has eight resident-thread slots including the parent; `agents.max_depth` is a V1 setting and does not impose V2 nesting limits. The orchestration contract requires CLI workers to remain leaves.

Devin's user config (`~/.config/devin/config.json`) and its `pi-bridge-guard` PreToolUse hook are dotfiles-managed links; the config disables Claude and Devin Cloud imports and selects bypass permissions. The tracked configs are under [`dotfiles/base`](../dotfiles/base/). Review changes after a harness writes its own config. Claude may rewrite `settings.json`, Codex may append trusted projects to `config.toml`. Antigravity CLI owns `~/.gemini/antigravity-cli/settings.json` outright, rewriting model selection and `trustedWorkspaces` on launch, so that file is untracked and left in place. Direct Antigravity model selection follows the approved policy in `orchestrate` and requires a successful `agy models` check. OpenCode restores its `cli.json` when missing, so install its tracked symlink while the client is stopped.

The configured harnesses allow unrestricted actions. Claude disables sandboxing and uses `bypassPermissions`; Codex sets `approval_policy = "never"` and `sandbox_mode = "danger-full-access"`; Muse uses `:unrestricted`; OpenCode has an allow-all permissions rule; Command Code defaults to `yolo`. fx uses `auto` permissions with the Contributor reviewer instead of the default higher-priced reviewer. See the tracked configs for hook and notification details.

`reset-agents` clears Claude, Codex, Muse, and OpenCode state under `$HOME`; pass one harness name to reset only that harness. It keeps dotfiles-managed files and `.credentials.json`, `auth.json`, and `mcp_credentials.json`. It rejects paths outside the resolved home and paths with symlinked components. Run it only when you intend to reset state. See its [implementation](../dotfiles/base/.local/bin/reset-agents) for supported paths.

## Model policy, privacy and attestation

Fable (`fable*` and `claude-fable*`) is prohibited, including qualified IDs; the shared typed bridge policy and `claude-api` wrapper reject it. Historical Fable price estimates remain in the wrapper for correct audit of old logs; they do not authorize launching the model. Native Claude CLI model selection cannot be globally intercepted by this repository, so use the model policy contract and verify actual sessions. The native model/effort attestation checker is `model-attest < receipt.json`; it validates supplied evidence fields but does not independently observe a provider. See [model economics](model-economics.md).

For repositories that cannot share code/prompts under Contributor training terms, track an empty `.agents/no-contributor` marker in the **primary repository** or set `USR_CONTRIBUTOR_MODE=deny` on the host. The bridge skips Contributor Pi fallbacks, the Pi SDK refuses direct Contributor workers, and the FX worker refuses its Contributor model. The marker does not disable native OpenCode, native FX main sessions, or other independent harnesses; route those through non-Contributor models manually, or do not use them on sensitive work. Inspect the effective runtime model before sharing data.
