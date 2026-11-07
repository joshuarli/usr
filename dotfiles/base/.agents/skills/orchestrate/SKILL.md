---
name: orchestrate
description: "Delegate to subagents when parallel independent work, disposable context, independent scrutiny, or lower cost clearly beats the main loop, and run a multi-lane campaign over a backlog. Skip tightly coupled work and any task cheaper to do directly."
---

# Orchestrate

Except for Claude Code’s mandatory DeepSeek executor path below, the parent keeps tightly coupled investigation, design, and integration, and owns direction and final verification. Delegate only for a concrete advantage: parallel independent work, disposable context, independent scrutiny, a harness-enforced permission boundary, or execution cheaper after counting briefing, waiting, review, and integration. A cheaper child model alone is not enough.

## Routing

Route by difficulty, uncertainty, and risk. Use the column for the harness you are running in.

| Work | Codex | Grok | OpenCode | Command Code | Muse Code | Antigravity CLI | DeepSeek TUI | fx | Pi |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Read-only scouting, searches, inventories, documentation lookup, log triage, straightforward fact gathering | `gpt-6-luna`, `medium` | `scout` | `opencode-go/muse-spark-1.3-contributor`, `explore` | `deepseek/deepseek-v4.1-flash`, `Explore` | `muse-spark-1.3`, `low` | `gemini-3.8-flash-medium` | `deepseek-flash`, `low` | `meta/muse-spark-1.3-contributor`, `low` | `opencode-go/muse-spark-1.3-contributor`, `scout`, `low` |
| Mechanical edits, routine implementation, straightforward documentation, crisp acceptance criteria | `gpt-6-luna`, `high` | `mechanic` | `opencode-go/muse-spark-1.3-contributor`, `general` | `deepseek/deepseek-v4.1-flash`, `General` | `muse-spark-1.3`, `medium` | `gemini-3.8-flash-high` | `deepseek-flash`, `low` | `meta/muse-spark-1.3-contributor`, `medium` | `opencode-go/muse-spark-1.3-contributor`, `mechanic`, `medium` |
| Normal implementation, debugging, tests, ordinary review | `gpt-6.1-terra`, `medium` | `worker` | `opencode-go/muse-spark-1.3-contributor`, `general` | `deepseek/deepseek-v4.1-flash`, `General` | `muse-spark-1.3`, `high` | `gemini-3.8-flash-high` | `deepseek-flash`, `high` | `meta/muse-spark-1.3-contributor`, `high` | `opencode-go/muse-spark-1.3-contributor`, `worker`, `high` |
| Difficult debugging, cross-cutting implementation, architecture, integration, demanding review | `gpt-6.1-terra`, `high` | `expert` | `opencode-go/muse-spark-1.3-contributor`, `general` | `deepseek/deepseek-v4.1-flash`, `General` | `muse-spark-1.3`, `xhigh` | `gemini-4-argon-high` | `deepseek-flash`, `max` | `meta/muse-spark-1.3-contributor`, `xhigh` | `opencode-go/muse-spark-1.3-contributor`, `expert`, `xhigh` |
| The hardest work: a failure an `expert` could not explain, a design others will build on, the final adversarial review before landing | `gpt-6.1-sol`, `high` | `god` | unavailable — keep local; do not delegate | unavailable — keep local; do not delegate | `muse-spark-1.3`, `xhigh` | `gemini-4-argon-high` | `deepseek-flash`, `max` | `meta/muse-spark-1.3-contributor`, `xhigh` | `opencode-go/muse-spark-1.3-contributor`, `god`, `xhigh` |

**Default to `worker`.** Size is not difficulty: a large lane with a known method and acceptance is still worker work. Use `expert` only for unknown paths with costly wrong turns (cross-cutting designs, unexplained failures, multi-owner integration).

**Clef-flash advisory routing is enabled by default** for each distinct, nontrivial delegated task, not each tool call or retry. First select a defensible baseline tier from the table and any harness-specific rules. If the task may be safely summarized for Cloudflare, pass a *sanitized, no-more-than-2-KiB summary* (never code, secrets, internal logs, full prompts, transcripts, or private data) via stdin to `decide route --baseline worker` (substitute the actual baseline). Use `--tiers mechanic,worker,expert` by default; include `scout` with `--tiers scout,mechanic,worker,expert` only for read-only assignments. Restrict tiers further when the parent or harness has a lower delegation ceiling. Do not call an external model when disclosure is disallowed, the decision is trivial, or only one tier is eligible.

Consume `selected_tier` only when the command returns a valid advisory result. The CLI uses **Clef-flash only**, keeps the baseline on unavailable/uncertain results, and cannot propose `god`. Treat its confidence as an uncalibrated heuristic, not evidence. Never allow routing to overrule the table, current capability ceiling, owner permissions, read-only/write boundaries, security-critical risk, evidence-based expert escalation, or harness-specific restrictions. In particular, a model must not downgrade a proven difficult or security-sensitive task. If `decide` or authenticated `cf` is absent, authentication/quota fails, or private context prevents a safe summary, continue immediately with the deterministic baseline: no retries, no provider substitution, no new secrets. `DECIDE_ROUTING=off` explicitly disables calls. See [decide](../../../../../tools/decide/README.md) for the response contract and offline evaluation.

If work exceeds the parent's delegation ceiling, keep it local at the highest suitable effort, except where a harness section below pins the model and effort. If a pinned model or effort is unavailable, report it; never substitute.

### Codex

Assign each Codex child only the model and effort in the Codex column. This profile overrides the parent's effort ceiling. Always specify `model`, `reasoning_effort`, and `fork_turns`. Prefer `fork_turns: "none"` with a self-contained brief; otherwise use the smallest positive turn count needed.

For V2, spawn children only from the root and explicitly forbid further spawning in every child brief. `agents.max_depth` limits only V1; V2 has a separate resident-thread cap, not a nesting limit.

### Claude Code: Opus coordinates; DeepSeek executes

**Default and exclusive path when Claude invokes `orchestrate`.** The main Opus session owns task framing, worker scheduling, evidence inspection, one bounded diff review, and integration. Opus does **not** perform substantive implementation, source investigation, debugging, or testing, even for a cheap task; it batches tiny tasks into one assignment. Delegate all such work through the `usr-opencode-worker` MCP bridge. Native Claude `Agent`/`Task` subagents, Sonnet/Haiku/Opus workers, free-model routes, or another provider are **not** fallback options. If the bridge and both approved DeepSeek backends are unavailable, stop and report the blocker. This Claude-specific rule overrides the general optional-delegation advice above.

The bridge prefers **OpenCode Go DeepSeek V4.1 Flash** and automatically falls back to **Command Code `deepseek/deepseek-v4.1-flash`** when the selected OpenCode model/variant is unavailable or is explicitly quota/usage-limited. Command Code has independent credits. Do not switch on a generic test failure or after OpenCode has modified the tree. Never choose another model to escape a limit.

| Tier | OpenCode Go | Command Code effort | Allowed task |
| --- | --- | --- | --- |
| `scout` | `deepseek-v4.1-flash#low` | `low` | Read-only evidence |
| `mechanic` | `deepseek-v4.1-flash#low` | `low` | Precisely specified edits |
| `worker` | `deepseek-v4.1-flash#high` | `high` | Ordinary coding, debugging, tests |
| `expert` | `deepseek-v4.1-flash#max` | `max` | Evidenced difficult task |

All OpenCode entries use provider `opencode-go`; all Command Code entries use model `deepseek/deepseek-v4.1-flash`. The tier is an effort budget and task contract, **not** permission to expand scope. There is no `god` tier here. If an `expert` worker fails, the Opus coordinator takes the work on themselves rather than delegating again.

**Before each launch:** create a clean dedicated linked worktree under `.work/wt/` and one contract. Call `worker_model_check(cwd, tier)` and `worker_start(cwd, title, tier, scope, brief)` with `scope` fields: exact `base_revision` matching HEAD, explicit `writable_paths` (an empty list for read-only scout; file paths or directory prefixes for a writer), `acceptance_proof` (one named check and expected observation, or source `file:line` proof), `attempt_limit` (1 normally; 2 for a justified targeted correction), and `stop_on` (ambiguity, new dependency, changed contract, expanded scope, or unavailable proof). State one outcome; forbid adjacent cleanup, unrelated refactors, new tasks, and downstream delegation. The worker cannot approve its own scope changes.

**Proof, not a summary:** require the worker’s exact changed files, command lines and exit codes with decisive output, or read-only `file:line` references. Treat the final prose as a claim. `worker_status` exposes the actual backend, effort, changed paths, out-of-scope paths, and unchanged HEAD. Confirm evidence independently with the narrowest appropriate verifier. Reject out-of-scope edits, changed HEAD, or missing verification.

**One-step Opus review:** after proof, check `git diff --check`, the diff against the base revision, and untracked files **once**. Confirm only the requested outcome, within the approved paths, with no glaring broken imports, regressions, altered invariants, or churn. No separate review agent or recursive review cycle. If clearly off, use at most one targeted `worker_resume` correction without expanding scope; otherwise reject/park. Opus integrates accepted work and owns worktree cleanup. The bridge may switch from OpenCode to Command Code only on a known availability/quota failure **before any edit**.

The bridge instructions in `tools/opencode-worker/README.md` explain one-time global MCP registration and live validation. The repository defaults to this routing immediately; until its MCP server is registered in Claude’s user configuration, stop rather than silently reverting to native agents.

### Grok

Use Grok’s native `scout`, `mechanic`, `worker`, `expert`, or `god` tiers, ranked in that order. A caller may spawn only lower tiers, and scout spawns none; `agent-tier-gate` enforces this on Grok’s `spawn_subagent` calls. Models and effort come from `~/.grok/agents`, all pinned to `grok-4.7`. Prefer fresh context. This rule does not authorize native Claude delegation.

### OpenCode

When OpenCode is itself the parent harness, run its lanes on `opencode-go/muse-spark-1.3-contributor` (1017 snapshot). Claude-triggered OpenCode workers instead follow the mandatory DeepSeek route above. OpenCode parents use regular `orchestrate` routing with OpenCode-native subagents and the table model; do not call the `usr-opencode-worker` bridge tools. Do not delegate `god` work in OpenCode; keep it local. Pass the model and effort from the table to every child. Use `explore` read-only for scouting, `general` otherwise. Keep briefs self-contained.

### Command Code

Run Command Code sessions with `deepseek/deepseek-v4.1-flash` at `max` effort. Built-in `Explore` (read-only) and `General` (other work) inherit the session model. Command Code parents use regular `orchestrate` routing with `Explore`/`General` and the table model; do not call the `usr-opencode-worker` bridge tools. Do not delegate `god` work in Command Code; keep it local. Never use another model. Children may run in parallel or background but cannot nest.

### Pi

Run Pi with `opencode-go/muse-spark-1.3-contributor` and use pi-subagents' native `scout`, `mechanic`, `worker`, `expert`, or `god` definitions in `~/.pi/agent/agents/`. The parent and every tier pin this exact OpenCode Go provider/model. Take the thinking level from the Pi column: `low` for scout, `medium` for mechanic, `high` for worker, and `xhigh` for expert and god. Pi's catalog maps `max` to unsupported, so `xhigh` is the ceiling; never request `max`. Expert and god change the brief and scrutiny, not the model; give god a fresh context with the earlier failures.

The tracked `subagents.modelScope` strictly rejects other models, including per-run overrides; do not weaken it, switch providers, or use external-runner agents. If OpenCode Go is unavailable or over its usage limit, stop and report the blocker instead of switching providers or spawning retry storms. These children have explicit tool allowlists and do not delegate. Scout has only read/search tools, not bash. Give parallel writers separate worktrees under `.work/wt/`, set each child's `cwd` to its worktree, and keep concurrency conservative because Go usage is billed against monthly allowances. See `~/usr/docs/pi.md` for authentication and verification.

### Muse Code

Pass `model: muse-spark-1.3` and the row's `effort` on every child. Never use another model or `none`, `minimal`, `max`, or `ultra`. `god` repeats `xhigh` with a fresh child: brief the earlier failures, review adversarially. A child spawns only when the brief grants it, and only at lower efforts. Give parallel writers disjoint worktrees under `.work/wt/`.

### Antigravity CLI

Select the model from the Antigravity CLI column with `agy --model <model>`. Use only Gemini models, even though the CLI also lists other providers. Antigravity custom agents accept only `inherit`, `flash`, or `pro` in their `model` field, not exact model IDs. Set each child to `inherit` and select the row's model for the parent session.

### DeepSeek TUI

Use only the DeepSeek TUI table route for DSH work. DSH has `off`, `low`, `high`, and `max`, not `medium`: use `high` for workers and `max` for experts and gods. Do not switch providers.

### fx

Keep the parent and every child on Vercel AI Gateway `meta/muse-spark-1.3-contributor`; explicitly choose the fx column's reasoning effort when launching a child. The named tiers are roles in the brief, not built-in fx agent types. Never silently use a stronger, more expensive model. A `god` child repeats `xhigh` in fresh context with evidence of previous failures.

fx children cannot spawn further children. They inherit the parent's workspace and permission limits, so subagent naming does not isolate writes. Default to serial writers. When independent writers justify parallelism, the parent first creates separate `.work/wt/` worktrees, grants additional workspace access as needed, and tells each child to write only its assigned path; do not assume fx changes the child's working directory. Parent owns diff review, integration, and cleanup.

## Delegation

Delegate coherent component-sized work. Do not spawn an agent for one command or edit, to restate a plan, or to summarize code the parent must understand anyway. Batch related trivial work into one assignment. When one script or codemod can apply the change to every unit in a single pass, write and run it yourself instead of fanning out children to hand-apply it, and prove it by rerunning it on the unit you did by hand.

Size concurrency for accepted progress. Serial is the default for work that shares files. Give parallel writers disjoint ownership, but also bound shared-service contention, review work, and the verification queue. Resource headroom is a ceiling, not a target. Stagger independent preparation when it helps; reduce or pause writers when acceptance is saturated. Give each child a coherent end-to-end slice, not a fragment requiring another handoff.

When a child reports, a merge lands, or a check fails, reassess ready work and the limiting stage. **Procedural escalation:** diagnose briefing, environment, or verification failures; fix the cause and retry at most once at the same tier with a materially changed approach. **Capability escalation:** use a stronger pinned model only for evidenced reasoning limits. Where tiers reuse a model, use fresh context and independent scrutiny, never a provider switch. Never repeat an unchanged failure. The parent resolves shared prerequisites and obstructive tactics. Owner intent, public contracts, required proof, and permissions stay fixed unless the owner changes them.

Give every parallel writer its own worktree, created by you with `git worktree add .work/wt/<name> -b <branch>` and named in the brief as the only place it may write. `isolation: "worktree"` also lands in `.work/wt/` through the WorktreeCreate hook, but its branch name is generated and the tree outlives the child, so campaigns create their own. A child's final report is not shown to the user: relay what matters. Background children notify on completion, so do not poll them, and send a running child a message when the rules change instead of restarting it.

Carry forward findings and failed approaches. Every child gets:

- Clear ownership and write boundaries.
- A concrete deliverable with only the needed context.
- Proportionate checks, an attempt limit, and a stopping condition.
- The current campaign ruling, plus a duty to report misleading metrics, repeated gate failures, or shared blockers rather than work around them.
- No further delegation unless the brief grants it; Grok may delegate to lower tiers within its depth cap. Claude-triggered DeepSeek executors never delegate. Codex V2 children never delegate because V1's `agents.max_depth` does not apply.

## Worktree lifecycle

The parent owns each child worktree from creation through removal. Every skill that removes worktrees or branches follows this section. Record its exact path, its branch when it has one, and the integration worktree when you create it or the harness creates it. A child finishing does not remove its worktree. Remove only the recorded path, never every entry under `.work/wt/`.

After a child finishes, review its changes and decide whether to integrate or park them. For accepted changes, inspect the integrated diff and reuse worker evidence unless integration or changed inputs could invalidate it. Remove the child worktree only after applicable proof is complete, the child has stopped, and all work worth keeping is in the integration branch or a preserved branch.

Before removal, run `git -C <child-worktree> status --porcelain --ignored=matching --untracked-files=all`. Keep the worktree if it has modified or untracked files. Review ignored files and preserve any local data worth keeping. Remove the worktree with `git -C <integration-worktree> worktree remove <child-worktree>`. Delete a branch only when `git -C <integration-worktree> merge-base --is-ancestor <branch> HEAD` succeeds, then run `git -C <integration-worktree> branch -d <branch>`. Keep the branch when that check fails, including after squash integration. Never force-delete a branch or worktree.

When you park unfinished work, commit it, remove its clean worktree, and keep its branch.

## Campaigns

For a backlog too large for one session, read [campaign mechanics and lane contract](references/campaigns.md) before preparing or launching work. The default is one writer on one slice until it is accepted. Add lanes only when they own disjoint files.

The parent runs the [steering checkpoint](references/campaigns.md#parent-steering-checkpoint) after each accepted slice, on resume, and after repeated failures, without waiting for the owner to complain.

**The test:** the parent can name the accepted slices that landed and the next one, and the integration branch is green.

**Report:** accepted slices and the checks that proved them, what is open and why, contract changes, and blockers needing the owner. Lane counts, doc commits, and audits are not progress.
