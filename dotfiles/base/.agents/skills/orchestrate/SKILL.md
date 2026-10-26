---
name: orchestrate
description: "Delegate to subagents when parallel independent work, disposable context, independent scrutiny, or lower cost clearly beats the main loop, and run a multi-lane campaign over a backlog. Skip tightly coupled work and any task cheaper to do directly."
---

# Orchestrate

The parent keeps tightly coupled investigation, design, and integration, and owns direction and final verification. Delegate only for a concrete advantage: parallel independent work, disposable context, independent scrutiny, a harness-enforced permission boundary, or execution cheaper after counting briefing, waiting, review, and integration. A cheaper child model alone is not enough.

## Routing

Route by difficulty, uncertainty, and risk. Use the column for the harness you are running in.

| Work | Codex | Claude and Grok | OpenCode | Command Code | Muse Code | Antigravity CLI | DeepSeek TUI | Pi |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Read-only scouting, searches, inventories, documentation lookup, log triage, straightforward fact gathering | `gpt-6-luna`, `medium` | `scout` | `opencode-go/muse-spark-1.3-contributor#low`, `explore` | `meta/muse-spark-1.3-contributor`, `Explore` | `muse-spark-1.3`, `low` | `gemini-3.8-flash-medium` | `deepseek-flash`, `low` | `google/gemini-3.8-flash`, `scout`, `low` |
| Mechanical edits, routine implementation, straightforward documentation, crisp acceptance criteria | `gpt-6-luna`, `high` | `mechanic` | `opencode-go/muse-spark-1.3-contributor#high`, `general` | `meta/muse-spark-1.3-contributor`, `General` | `muse-spark-1.3`, `medium` | `gemini-3.8-flash-high` | `deepseek-flash`, `low` | `google/gemini-3.8-flash`, `mechanic`, `medium` |
| Normal implementation, debugging, tests, ordinary review | `gpt-6-luna`, `xhigh` | `worker` | `opencode-go/muse-spark-1.3-contributor#xhigh`, `general` | `meta/muse-spark-1.3-contributor`, `General` | `muse-spark-1.3`, `high` | `gemini-3.8-flash-high` | `deepseek-flash`, `high` | `google/gemini-3.8-flash`, `worker`, `high` |
| Difficult debugging, cross-cutting implementation, architecture, integration, demanding review | `gpt-6.1-sol`, `medium` | `expert` | `opencode-go/deepseek-v4.1-flash#high`, `general` | `meta/muse-spark-1.3-contributor`, `General` | `muse-spark-1.3`, `xhigh` | `gemini-4-argon-medium` | `deepseek-flash`, `max` | `google/gemini-3.8-flash`, `expert`, `high` |
| The hardest work: a failure an `expert` could not explain, a design others will build on, the final adversarial review before landing | `gpt-6.1-sol`, `high` | `god` | `opencode-go/deepseek-v4.1-flash#max`, `general` | `meta/muse-spark-1.3-contributor`, `General` | `muse-spark-1.3`, `xhigh` | `gemini-4-argon-high` | `deepseek-flash`, `max` | `google/gemini-3.8-flash`, `god`, `high` |

**Default to `worker`.** Size is not difficulty: a large lane with a known method and acceptance is still worker work. Use `expert` only for unknown paths with costly wrong turns (cross-cutting designs, unexplained failures, multi-owner integration). If the brief specifies steps and acceptance, start with `worker`; escalate only when evidence warrants it.

If work exceeds the parent's delegation ceiling, keep it local at the highest suitable effort, except for the Codex profile and the Grok and Pi pins below. If a model is unavailable, use a suitable allowed model at the same or lower tier or report it.

### Codex

Use the model and effort in the Codex column for each Codex child. This profile overrides the parent's effort ceiling; if the assigned model is unavailable, report the limitation instead of substituting a model.

Assign a child only the model and effort in the Codex column. Never use any other model, including GPT-5.x, Terra, the `astra` tier, or `ultra`; this repository keeps delegation explicit through the orchestration instructions.

Always specify `model`, `reasoning_effort`, and `fork_turns`. Prefer `fork_turns: "none"` with a self-contained brief; otherwise use the smallest positive turn count needed.

### Claude and Grok

Spawn only `scout`, `mechanic`, `worker`, `expert`, or `god`, ranked in that order. A caller spawns only a lower tier, and `scout` spawns nothing. `agent-tier-gate` enforces that: Claude matches `Agent`, Grok matches `spawn_subagent`. `CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH` caps Claude nesting at 3. Model and effort come from `~/.claude/agents` or `~/.grok/agents`, not from the call. Every Grok definition pins `grok-4.7`. Do not use another model or `xhigh`. If `grok-4.7` is unavailable, report it. Change a type's model or effort in its file. Reserve `expert` for the difficult row, and `god` for work an `expert` has failed, or a decision others build on. Add a definition when none of the five fit. Prefer a fresh agent; fork only when the child needs the conversation.

### OpenCode

Keep scout, mechanic, and worker OpenCode lanes on `opencode-go/muse-spark-1.3-contributor`; run expert and god lanes on `opencode-go/deepseek-v4.1-flash`. Pass the model and effort from the table to every child. Use `explore` read-only for scouting, `general` otherwise. If the model is unavailable, report it. Keep briefs self-contained.

### Command Code

Run Command Code sessions with `meta/muse-spark-1.3-contributor`. Built-in `Explore` (read-only) and `General` (other work) inherit the session model. Never use another model; if `meta/muse-spark-1.3-contributor` is unavailable, report it. Children may run in parallel or background but cannot nest; give parallel writers separate worktrees.

In either harness, give every parallel writer its own worktree, created by you with `git worktree add .work/wt/<name> -b <branch>` and named in the brief as the only place it may write. `isolation: "worktree"` also lands in `.work/wt/` through the WorktreeCreate hook, but its branch name is generated and the tree outlives the child, so campaigns create their own. A child's final report is not shown to the user: relay what matters. Background children notify on completion, so do not poll them, and send a running child a message when the rules change instead of restarting it.

### Pi

Run Pi with `google/gemini-3.8-flash` and use pi-subagents' native `scout`, `mechanic`, `worker`, `expert`, or `god` definitions in `~/.pi/agent/agents/`. Every tier pins that exact provider/model. Use `low` thinking for scout, `medium` for mechanic, and `high` for worker, expert, and god; never request `xhigh` or `max`. Expert and god change the brief and scrutiny, not the model; give god a fresh context with the earlier failures.

The tracked `subagents.modelScope` strictly rejects other models, including per-run overrides; do not weaken it, switch providers, or use external-runner agents. If Gemini is unavailable or rate-limited, report the limitation rather than substituting or spawning retries. These children have explicit tool allowlists and do not delegate. Scout has only read/search tools, not bash. Give parallel writers separate worktrees under `.work/wt/`, set each child's `cwd` to its worktree, and keep concurrency conservative on the free API quota. See `~/usr/docs/pi.md` for installation and authentication.

### Muse Code

Pass `model: muse-spark-1.3` and the row's `effort` on every child. Never use another model or `none`, `minimal`, `max`, or `ultra`; if `muse-spark-1.3` is unavailable, report it. `god` repeats `xhigh` with a fresh child: brief the earlier failures, review adversarially. A child spawns only when the brief grants it, and only at lower efforts. Give parallel writers disjoint worktrees under `.work/wt/`.

### Antigravity CLI

Select the model from the Antigravity CLI column with `agy --model <model>`. Use only Gemini models, even though the CLI also lists other providers. Antigravity custom agents accept only `inherit`, `flash`, or `pro` in their `model` field, not exact model IDs. Set each child to `inherit` and select the row's model for the parent session.

### DeepSeek TUI

Use only the DeepSeek TUI table route for DSH work. DSH has `off`, `low`, `high`, and `max`, not `medium`: use `high` for workers and `max` for experts and gods. Do not switch providers or substitute; report unavailable models or efforts.

## Delegation

Delegate coherent component-sized work. Do not spawn an agent for one command or edit, to restate a plan, or to summarize code the parent must understand anyway. Batch related trivial work into one assignment. When one script or codemod can apply the change to every unit in a single pass, write and run it yourself instead of fanning out children to hand-apply it, and prove it by rerunning it on the unit you did by hand.

Size concurrency for accepted progress. Give parallel writers disjoint ownership, but also bound shared-service contention, review work, and the verification queue. Resource headroom is a ceiling, not a target. Stagger independent preparation when it helps; reduce or pause writers when acceptance is saturated. Give each child a coherent end-to-end slice, not a fragment requiring another handoff.

When a child reports, a merge lands, or a check fails, reassess the ready work and the limiting stage before launching more. The parent investigates technical blockers within authority, assigns shared prerequisites once, and changes agent-authored tactics when they obstruct the goal. Do not requeue unchanged failures or escalate models merely for missing infrastructure. Owner intent, public contracts, required proof, and permission limits remain fixed unless the owner changes them.

Carry forward findings and failed approaches. Every child gets:

- Clear ownership and write boundaries.
- A concrete deliverable with only the needed context.
- Proportionate checks, an attempt limit, and a stopping condition.
- The current campaign ruling, plus a duty to report misleading metrics, repeated gate failures, or shared blockers rather than work around them.
- No further delegation unless the brief grants it, and then only to lower tiers (Claude and Grok) within the depth cap. Codex children are all one tier, so `agents.max_depth` is the only limit.

## Worktree lifecycle

The parent owns each child worktree from creation through removal. Record its exact path, its branch when it has one, and the integration worktree when you create it or the harness creates it. A child finishing does not remove its worktree. Remove only the recorded path, never every entry under `.work/wt/`.

After a child finishes, review its changes and decide whether to integrate or park them. For accepted changes, inspect the integrated diff and reuse worker evidence unless integration or changed inputs could invalidate it. Remove the child worktree only after applicable proof is complete, the child has stopped, and all work worth keeping is in the integration branch or a preserved branch.

Before removal, run `git -C <child-worktree> status --porcelain --ignored=matching --untracked-files=all`. Keep the worktree if it has modified or untracked files. Review ignored files and preserve any local data worth keeping. Remove the worktree with `git -C <integration-worktree> worktree remove <child-worktree>`. Delete its branch only when `git -C <integration-worktree> merge-base --is-ancestor <branch> HEAD` succeeds, then run `git -C <integration-worktree> branch -d <branch>`. Keep the branch when that check fails, including after squash integration. Never force-delete a branch or worktree.

When you park unfinished work and commits are authorized, commit the work, remove its clean worktree, and keep its branch. Without commit authorization, keep the worktree and report its path. Keep a worktree while its child is running, its changes remain unreviewed, or it contains uncommitted work.

## Campaigns

For a backlog run as parallel lanes, read [campaign mechanics and lane contract](references/campaigns.md) before preparing or launching work.

The parent must perform the [steering checkpoint](references/campaigns.md#parent-steering-checkpoint), not just replenish lanes. It reviews substantive outcomes and rejected proposals, distinguishes new regressions from newly exposed debt, and corrects the limiting stage within authority. Apply it after validation waves, on resume, and when repeated failures or queue growth appear; do not wait for the owner to complain.

Commit size and global verification size need not match. Use the reference's bounded validation waves, exact accepted checkpoints, and qualified evidence reuse. A loop-speed repair must unblock a named real deliverable; stop expanding infrastructure once that path works. Record rulings in the existing campaign artifact and notify affected children.

**The test:** the parent can show verified progress toward the owner's goal, explain the current bottleneck and next milestone, and intervene without weakening required acceptance or manufacturing authority.

**Report:** substantive work accepted, provisional work, decisive checks, the bottleneck and steering decision, contract changes, and blockers needing the owner. Report tooling and metadata cleanup separately; lane counts alone are not progress.
