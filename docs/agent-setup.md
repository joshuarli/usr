# Agent setup

For disposable, isolated Linux coding-agent sessions on macOS, run [`agent-vm`](agent-vm.md) from a project directory. It loads tracked skills and global instructions without mounting host authentication state.

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

Automatic eligibility lets an agent select a method from an ordinary request when the skill's conditions fit. An explicit workflow must be requested by its outcome or name; a slash command is a convenient request, not an authorization token. A workflow already within scope may reuse a relevant procedure from another skill, including an explicit-only skill, without inheriting unrelated commands or authority. Plain requests can select the global `do` workflow when uncertainty, dependent steps, consequences, or acceptance requirements warrant it. Small edits and one-step questions stay on the short path. `do` preserves the request mode and authority through completion. `yea` remains explicit-only; it accepts every recommendation in the previous reply and carries out authorized effects within its rules.

`/do` remains available as an explicit shortcut:

| Harness | Invocation |
| --- | --- |
| Codex CLI or IDE | `$do <task>`; interactive sessions also provide `/skills` to select a skill. |
| Claude Code | `/do <task>` in the prompt. |
| Muse Code | `/do <task>` in the TUI. |
| Grok Code | `/do <task>` in the TUI. |
| OpenCode | `/do <task>` in the TUI; the skill metadata exposes this shortcut. |

You do not need to name an automatically eligible skill in a normal request. Codex, Claude Code, Muse Code, Grok Code, and OpenCode can select eligible skills from their descriptions. Codex reads `agents/openai.yaml`; Claude, Muse, Grok, and DeepSeek Harness use `disable-model-invocation`; OpenCode uses `metadata.opencode/autoinvoke`. OpenCode defaults to listing skills for model selection, so every shared explicit-only skill sets `opencode/autoinvoke: "false"`. Antigravity CLI reads only `name` and `description` from skill frontmatter; its global instruction file keeps explicit-only workflows out of automatic selection. A plain-language request or slash command can request an explicit workflow, and an already-requested workflow can reuse its procedure within the same scope and authority. Auto-eligible descriptions name their useful entry conditions and a `Skip` case.

The global `do` skill is automatically eligible for substantial work. `architect`, `review`, and `blast-radius` are eligible only when their descriptions' conditions apply. Broad audits, verifier creation, accepting recommendations, unattended execution, and publication workflows remain explicit-only. The user must request an explicit workflow or its outcome; its slash shortcut is not a separate authorization. A selected workflow may read a referenced explicit-only procedure without starting that procedure's unrelated actions.

Codex, Muse, Grok, OpenCode, and DeepSeek Harness discover shared skills in `~/.agents/skills`; Codex, Muse, OpenCode, and DeepSeek Harness also scan project `.agents/skills`. Claude uses `~/.claude/skills` and project `.claude/skills`. Antigravity CLI uses `~/.gemini/antigravity-cli/skills`, linked to `dotfiles/base/.agents/skills/`. Codex accepts `$do` or `/skills`; Claude Code, Muse Code, and Grok expose user-invocable skills as `/do`; OpenCode exposes `/do` through `opencode/slash`; Antigravity CLI exposes `/<skill-name>`. DeepSeek Harness loads matching skills through its skill tool. Bare `dsh` and `dsh tui` start the tracked TUI launcher on its `dsh-tui` profile; it supplies `DEEPSEEK_API_KEY` from `vault`, or uses the exported variable when `vault` is unavailable. `dsh web` selects the core Web profile with the same key. Use the equivalent host syntax for `create-verification-skill`.

The `/do` router follows a local verifier pointer in the repository instructions, then selects a local verification skill for the interface under change. Use `create-verification-skill` when a reusable project procedure is missing or stale. The `verify-usr` skill covers the safe `sym` scratch-home journey; `dotfiles-health` owns setup policy and structural invariants.

Native syntax and metadata differ by host. See [Codex skills](https://learn.chatgpt.com/docs/build-skills), [Claude Code skills](https://code.claude.com/docs/en/skills), [Muse Code skills](https://meta-models.github.io/muse-code-sdk/next/guides/extend/skills/), [Grok skills](https://docs.x.ai/build/features/skills-plugins-marketplaces), [OpenCode skills](https://docs.opencode.ai/docs/skills/), [Antigravity skills](https://antigravity.google/docs/skills), [DeepSeek Harness instructions](https://github.com/deepseek-ai/deepseek-harness/blob/master/packages/context/agent-instructions/README.md), and [DeepSeek Harness skills](https://github.com/deepseek-ai/deepseek-harness/blob/master/docs/subsystems/skills.md).

The configured coding harnesses use unrestricted permissions: Claude Code runs `bypassPermissions` with sandboxing disabled; Codex uses `approval_policy = "never"` and `sandbox_mode = "danger-full-access"`; Muse uses `:unrestricted`; Grok uses `yolo = true` and sandbox profile `off`; OpenCode allows everything with a `permissions` allow-all rule. Grok imports Claude's hooks, but does not load Claude's `env`. The Grok config turns telemetry off, caps concurrent subagents at 64, caps nest depth at 3, and sets the status line. Grok has no worktree hook, so `worktree-create` and `worktree-remove` stay on Claude.

A session that needs you rings the terminal bell. `notify-sound` writes BEL to the pane, tmux marks that window, and Alacritty plays Glass for the bell. Claude's `Notification` hook calls `notify-sound`. Grok runs that hook and sets `[ui.notifications] method = "none"`, so it does not ring a second time. Codex sends BEL from the TUI on a finished turn or an approval. Muse calls `notify-sound` from `Stop` and `Notification`. OpenCode calls it when a session goes idle. Antigravity sets `notifications` on, which rings the terminal bell.

Codex stores trusted projects in `dotfiles/base/.codex/config.toml` and the OpenRouter profile in `or.config.toml`. Claude may rewrite `settings.json`, Codex may append trusted projects to `config.toml`, and Grok may rewrite `config.toml` from `/settings`. The OpenCode client owns `cli.json` and restores it when missing, so install its tracked symlink with the client stopped. Review their diffs before committing.

Claude retains its `agent-tier-gate` subagent hook and the official Slack plugin. The configured OpenCode `permissions` allow-all rule applies globally; there are no per-agent permission overrides in this tree.

`claude-api [--budget usd] [--model name] [--] <prompt...>` runs Claude Code with API credits. The default budget is `$100`, passed to `--max-budget-usd`. Claude Code estimates this cap, and actual spend can exceed it ([CLI reference](https://code.claude.com/docs/en/cli-reference)). The running display shows an estimate. The final result uses Claude's reported total. Put `/skill-name` at the start of the prompt to invoke a skill. In print mode, Claude Code loads only the first skill and treats the remaining prompt as that skill's arguments. Run `claude-api --help` to see this caveat from the command. The launcher writes the raw event stream to `<repo>/.work/logs` and prints its path. File permissions follow the shell's `umask`; with `umask 022`, log files are readable by other local accounts that can access the repository. Treat these logs as sensitive.

`claude-or` and `claude-ds` start Claude Code through the OpenRouter and DeepSeek profiles with `--dangerously-skip-permissions`, taking the key from `vault`, so no permission prompt or deny rule applies in those sessions. `codex-or` starts Codex with the OpenRouter profile. `skill-usage` reads existing Claude, Codex, Muse, and Grok sessions; Grok does not persist its skill catalog, so `skill-eval` cannot calculate its listed-to-loaded rate.

`reset-agents` clears harness state under `$HOME`. With no argument it resets Claude, Codex, Grok, Muse, and OpenCode. Pass one name to reset only that harness, such as `reset-agents claude`. Muse follows `XDG_CONFIG_HOME` and `XDG_DATA_HOME`, defaulting to `~/.config/muse` and `~/.local/share/muse`. OpenCode resets `~/.config/opencode`, `~/.local/share/opencode`, and the `XDG_CACHE_HOME` `opencode` directory, defaulting to `~/.cache/opencode`. The command keeps dotfiles-managed files and the credential files `.credentials.json`, `auth.json`, and `mcp_credentials.json`. It resolves a symlinked `HOME`, then refuses target paths outside that resolved home or with symlinked components beneath it. Do not run it without an explicit request.

## Configure optional Workers AI decisions

`decide` sends one validated request to Cloudflare Workers AI. It uses the Workers AI REST API directly and does not deploy a Worker. `cf` login authenticates the administration CLI; it does not give `decide` a runtime token.

### Create a scoped token

1. If `cf` is not authenticated, run `cf auth login`. Run `cf auth whoami` to check the CLI session.
2. Run `cf accounts list` and choose the account that owns Workers AI. Copy that account ID for the current shell session.
3. Confirm that the token permission groups include `Workers AI Read` and `Workers AI Write`.

   ```sh
   cf user tokens permission-groups list | jaq -r '.[] | select(.name == "Workers AI Read" or .name == "Workers AI Write") | .name'
   ```

4. Build an account-only policy and create a token. Choose a future UTC expiry when you repeat these steps.

   ```sh
   (
     set -eu
     printf '%s' 'Paste the account ID and press Enter: '
     IFS= read -r account_id
     expires_on='2027-10-22T00:00:00Z'
     workers_ai_groups=$(
       cf user tokens permission-groups list |
         jaq -e -c '[.[] | select(.name == "Workers AI Read" or .name == "Workers AI Write") | {id}] | select(length == 2)'
     )
     policies=$(jaq -n --arg account "$account_id" --argjson groups "$workers_ai_groups" '[{effect:"allow",resources:{("com.cloudflare.api.account." + $account):"*"},permission_groups:$groups}]')
     cf user tokens create --name usr-decision-models --expires-on "$expires_on" --policies "$policies"
   )
   ```

   The policy grants Workers AI access on the selected account only. The token command prints the token once.
5. Copy that token into `vault`, then store the account ID. `vault set` prompts for each value.

   ```sh
   vault set CLOUDFLARE_API_TOKEN
   vault set CLOUDFLARE_ACCOUNT_ID
   vault isset CLOUDFLARE_API_TOKEN
   vault isset CLOUDFLARE_ACCOUNT_ID
   vault CLOUDFLARE_API_TOKEN CLOUDFLARE_ACCOUNT_ID -- decide doctor
   ```

`doctor` checks local configuration only. It sends no request. `decide` reads `CLOUDFLARE_API_TOKEN` and `CLOUDFLARE_ACCOUNT_ID` from its environment. Use `vault` to inject them for a command without putting the token in shell history.

### Ask a decision question

Pass one JSON object on standard input. The client prints one JSON result. `clef-flash` is the default model; use `--model clef` to select Clef.

```sh
vault CLOUDFLARE_API_TOKEN CLOUDFLARE_ACCOUNT_ID -- decide <<'JSON'
{"state":"A sanitized brief","questions":{"tier":{"type":"choice","instructions":"Which eligible tier fits this uncertainty?","criteria":{"worker":"Known method and acceptance","expert":"Unknown path with costly failure"}}}}
JSON
```

`choice` returns one option and its probabilities. `noul` returns the probability that a statement is true.

```json
{"state":"A sanitized brief","questions":{"urgent":{"type":"noul","instructions":"Is this blocking the requested outcome?","criteria":{"true":"A required step cannot proceed","false":"The workflow can continue"}}}}
```

`orchestrate` consults `decide` only when `USR_DECIDE_TIER` is `shadow` or `advisory`. An unset variable disables requests. An unsupported value makes no request and leaves ordinary routing in place. Consult once after a concrete brief when a bounded uncertainty has real cost. Offer no `god` tier or `scout` for mutating work. Send only the objective, effect, known facts, uncertainty, scope and coupling, and acceptance. Remove transcripts, diffs, source files, environment values, secret traces, and session histories. Skip the request if sensitive details cannot be separated. `shadow` never changes routing. `advisory` informs routing only within existing tier, model, permission, and authorization rules; justify any changed choice against them. If advice is unavailable or invalid, briefly notify the user and continue ordinary routing. The skill guidance is not runtime-enforced.

### Evaluate labeled cases

Offline evaluation reads recorded predictions from a JSONL file and makes no requests. Each line has a unique `case_id`, a `source_group`, optional `split` (`development` or `held-out`), sanitized `state`, a Clef `choice` question, `expected_tier` or `acceptable_tiers`, optional `existing_choice`, and a recorded `prediction`. Keep all cases from one source group in the same split. Mark synthetic cases as synthetic.

```json
{"case_id":"synthetic-1","source_group":"synthetic-demo","split":"development","state":"Synthetic sanitized brief","question":{"type":"choice","instructions":"Choose the tier.","criteria":{"worker":"Known method","expert":"Unknown path"}},"expected_tier":"worker","existing_choice":"worker","prediction":{"status":"ok","tier":"worker","confidence":0.8,"input_tokens":16,"elapsed_ms":120.0,"model":"clef-flash"}}
```

Run the offline report with `decide eval cases.jsonl`. The report contains aggregate metrics only. It does not save prompts or results. Latency percentiles are `unknown` below 20 successful cases. Cost and missing usage are `unknown`.

Exact agreement counts cases with one `expected_tier`. Acceptable agreement and confidence correctness count predictions that match `expected_tier` or one of `acceptable_tiers`.

With `existing_choice`, `policy_comparison` reports existing-policy agreement, standalone Clef agreement, and paired correctness delta on successful decisions. `hypothetical_unconditional_adoption` assumes every successful Clef prediction is adopted. It keeps `existing_choice` when advice is unavailable or abstains. This is a hypothetical simulation, not measured advisory behavior. The parent decides whether to apply each recommendation. The format does not record the parent's actual advisory choice or task verification outcome. Cases without baselines and unavailable decisions are counted separately. Development and held-out splits stay separate. Synthetic cases are not session evidence. Incomplete usage and cost remain unknown. Classification accuracy alone does not establish session savings.

Live evaluation requires separate owner authorization. It accepts cases without recorded predictions and requires a maximum of 1 to 50 calls. The number of cases cannot exceed that maximum.

Live cases may offer only `mechanic`, `worker`, and `expert`. `decide` rejects `scout` because a case cannot establish that the work is read-only, and rejects `god` because automatic selection is forbidden.

```sh
vault CLOUDFLARE_API_TOKEN CLOUDFLARE_ACCOUNT_ID -- decide eval --live --max-calls 30 cases.jsonl
```

### Workers AI quota reporting

We do not provide a remaining-quota estimate in `usage`. Cloudflare does not document an authoritative live counter. GraphQL analytics is sampled ([sampling](https://developers.cloudflare.com/analytics/graphql-api/sampling/)). Billable usage updates daily ([API](https://developers.cloudflare.com/billing/manage/billable-usage/)). Neither source establishes whether the next request fits.

Workers AI Free provides 10,000 Neurons per day and resets at 00:00 UTC ([pricing](https://developers.cloudflare.com/workers-ai/platform/pricing/)). Use the Free allocation until Cloudflare returns HTTP 429, code 3036 ([Workers AI errors](https://developers.cloudflare.com/workers-ai/platform/errors/)). `decide` reports unavailable advice. `orchestrate` notifies the user and continues ordinary routing.

This account has no Workers Paid subscription. Do not upgrade Workers or enable AI Gateway credits. `decide` returns unavailable advice at quota exhaustion and does not retry.

No account-wide budget alert was created. Alerts notify but do not cap spending ([budget alerts](https://developers.cloudflare.com/billing/manage/budget-alerts/)). The existing R2 Paid subscription was left unchanged. No Worker or AI Gateway resource was deployed.

One synthetic Clef-flash request verified the live REST envelope and all three answer types. It used 346 input tokens, 0 output tokens, and 214 ms. No live task evaluation or savings measurement has been run.

