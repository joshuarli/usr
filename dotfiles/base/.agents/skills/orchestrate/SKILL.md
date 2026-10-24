---
name: orchestrate
description: "Route substantial, routine, mechanical, exploratory, or context-heavy work across subagents to control cost, isolate context, and parallelize independent work, and run a multi-lane campaign over a backlog. Delegate whenever the work is economical to specify and verify. Skip a task cheaper to do directly."
---

# Orchestrate

Delegate only when specification and verification cost less than local work. The parent owns direction, integration, and final verification.

## Routing

Route by difficulty, uncertainty, and risk. Use the column for the harness you are running in.

| Work | Codex | Claude and Grok | OpenCode | Command Code | Muse Code | Antigravity CLI | DeepSeek TUI |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Read-only scouting, searches, inventories, documentation lookup, log triage, straightforward fact gathering | `gpt-6-luna`, `medium` | `scout` | `opencode-go/muse-spark-1.3-contributor`, `explore` | `meta/muse-spark-1.3-contributor`, `Explore` | `muse-spark-1.3`, `low` | `gemini-3.8-flash-medium` | `deepseek-flash`, `low` |
| Mechanical edits, routine implementation, straightforward documentation, crisp acceptance criteria | `gpt-6-luna`, `high` | `mechanic` | `opencode-go/muse-spark-1.3-contributor`, `general` | `meta/muse-spark-1.3-contributor`, `General` | `muse-spark-1.3`, `medium` | `gemini-3.8-flash-high` | `deepseek-flash`, `low` |
| Normal implementation, debugging, tests, ordinary review | `gpt-6-luna`, `xhigh` | `worker` | `opencode-go/muse-spark-1.3-contributor`, `general` | `meta/muse-spark-1.3-contributor`, `General` | `muse-spark-1.3`, `high` | `gemini-3.8-flash-high` | `deepseek-flash`, `high` |
| Difficult debugging, cross-cutting implementation, architecture, integration, demanding review | `gpt-6.1-sol`, `medium` | `expert` | `opencode-go/muse-spark-1.3-contributor`, `general` | `meta/muse-spark-1.3-contributor`, `General` | `muse-spark-1.3`, `xhigh` | `gemini-4-argon-medium` | `deepseek-flash`, `max` |
| The hardest work: a failure an `expert` could not explain, a design others will build on, the final adversarial review before landing | `gpt-6.1-sol`, `high` | `god` | `opencode-go/muse-spark-1.3-contributor`, `general` | `meta/muse-spark-1.3-contributor`, `General` | `muse-spark-1.3`, `xhigh` | `gemini-4-argon-high` | `deepseek-flash`, `max` |

**Default to `worker`.** Size is not difficulty: a large lane with a known method and acceptance is still worker work. Use `expert` only for unknown paths with costly wrong turns (cross-cutting designs, unexplained failures, multi-owner integration). If the brief specifies steps and acceptance, start with `worker`; escalate only when evidence warrants it.

### Optional tier advice

Consult once per unchanged decision only when `USR_DECIDE_TIER` is already `shadow` or `advisory`; never set it. For bounded, consequential uncertainty, use `decide` only when your harness has a meaningful cheaper-tier choice; skip OpenCode's and Command Code's pinned-model children. Run `vault CLOUDFLARE_API_TOKEN CLOUDFLARE_ACCOUNT_ID -- decide` with sanitized JSON on stdin; read its structured result. Shadow never routes. Advisory is parent-assessed within existing tier/model/permission/authorization rules and cannot override user-selected models or mandatory escalation. Exclude `god` and mutating `scout`. Unavailable or invalid advice leaves routing unchanged; notify the user. Details: `~/usr/docs/agent-setup.md`.

If work exceeds the parent's delegation ceiling, keep it local at the highest suitable effort, except for the Codex profile and Grok pins below. If a model is unavailable, use a suitable allowed model at the same or lower tier or report it. Failed commands, missing dependencies, or unavailable environments alone do not justify model escalation.

### Codex

Use the model and effort in the Codex column for each Codex child. This profile overrides the parent's effort ceiling; if the assigned model is unavailable, report the limitation instead of substituting a model.

Assign a child only the model and effort in the Codex column. Never use any other model, including GPT-5.x, Terra, the `astra` tier, or `ultra`; this repository keeps delegation explicit through the orchestration instructions.

Always specify `model`, `reasoning_effort`, and `fork_turns`. Prefer `fork_turns: "none"` with a self-contained brief; otherwise use the smallest positive turn count needed.

### Claude and Grok

Spawn only `scout`, `mechanic`, `worker`, `expert`, or `god`, ranked in that order. A caller spawns only a lower tier, and `scout` spawns nothing. `agent-tier-gate` enforces that: Claude matches `Agent`, Grok matches `spawn_subagent`. `CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH` caps Claude nesting at 3. Model and effort come from `~/.claude/agents` or `~/.grok/agents`, not from the call. Every Grok definition pins `grok-4.7`. Do not use another model or `xhigh`. If `grok-4.7` is unavailable, report it. Change a type's model or effort in its file. Reserve `expert` for the difficult row, and `god` for work an `expert` has failed, or a decision others build on. Add a definition when none of the five fit. Prefer a fresh agent; fork only when the child needs the conversation.

### OpenCode

Run OpenCode sessions with `opencode-go/muse-spark-1.3-contributor`. Children inherit the session model: `explore` is read-only; use `general` otherwise. Pass no model override; default to `general`. Never use another model; if `opencode-go/muse-spark-1.3-contributor` is unavailable, report it. Keep briefs self-contained.

### Command Code

Run Command Code sessions with `meta/muse-spark-1.3-contributor`. Built-in `Explore` (read-only) and `General` (other work) inherit the session model. Never use another model; if `meta/muse-spark-1.3-contributor` is unavailable, report it. Children may run in parallel or background but cannot nest; give parallel writers separate worktrees.

In either harness, give every parallel writer its own worktree, created by you with `git worktree add .work/wt/<name> -b <branch>` and named in the brief as the only place it may write. `isolation: "worktree"` also lands in `.work/wt/` through the WorktreeCreate hook, but its branch name is generated and the tree outlives the child, so campaigns create their own. A child's final report is not shown to the user: relay what matters. Background children notify on completion, so do not poll them, and send a running child a message when the rules change instead of restarting it.

### Muse Code

Pass `model: muse-spark-1.3` and the row's `effort` on every child. Never use another model or `none`, `minimal`, `max`, or `ultra`; if `muse-spark-1.3` is unavailable, report it. `god` repeats `xhigh` with a fresh child: brief the earlier failures, review adversarially. A child spawns only when the brief grants it, and only at lower efforts. Give parallel writers disjoint worktrees under `.work/wt/`.

### Antigravity CLI

Select the model from the Antigravity CLI column with `agy --model <model>`. Use only Gemini models, even though the CLI also lists other providers. Antigravity custom agents accept only `inherit`, `flash`, or `pro` in their `model` field, not exact model IDs. Set each child to `inherit` and select the row's model for the parent session.

### DeepSeek TUI

Use only the DeepSeek TUI table route for DSH work. DSH has `off`, `low`, `high`, and `max`, not `medium`: use `high` for workers and `max` for experts and gods. Do not switch providers or substitute; report unavailable models or efforts.

## Delegation

Delegate coherent component-sized work; do not delegate a one-command or one-edit task when the handoff costs more than doing it locally. Batch related trivial work into one assignment. When one script or codemod can apply the change to every unit in a single pass, write and run it yourself instead of fanning out children to hand-apply it, and prove it by rerunning it on the unit you did by hand.

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

After a child finishes, review its changes and decide whether to integrate or park them. For accepted changes, inspect the integrated diff and bind evidence to it. Reuse worker evidence when the relevant inputs and assumptions are unchanged; rerun checks only when integration or changed inputs could invalidate them. Remove the child worktree only after applicable proof is complete, the child has stopped, and all work worth keeping is in the integration branch or a preserved branch.

Before removal, run `git -C <child-worktree> status --porcelain --ignored=matching --untracked-files=all`. Keep the worktree if it has modified or untracked files. Review ignored files and preserve any local data worth keeping. Remove the worktree with `git -C <integration-worktree> worktree remove <child-worktree>`. Delete its branch only when `git -C <integration-worktree> merge-base --is-ancestor <branch> HEAD` succeeds, then run `git -C <integration-worktree> branch -d <branch>`. Keep the branch when that check fails, including after squash integration. Never force-delete a branch or worktree.

When you park unfinished work and commits are authorized, commit the work, remove its clean worktree, and keep its branch. Without commit authorization, keep the worktree and report its path. Keep a worktree while its child is running, its changes remain unreviewed, or it contains uncommitted work.

## Campaigns

For a backlog run as parallel lanes, read [campaign mechanics and lane contract](references/campaigns.md) before preparing or launching work.

The parent must perform the [steering checkpoint](references/campaigns.md#parent-steering-checkpoint), not just replenish lanes. It reviews substantive outcomes and rejected proposals, distinguishes new regressions from newly exposed debt, and corrects the limiting stage within authority. Apply it after validation waves, on resume, and when repeated failures or queue growth appear; do not wait for the owner to complain.

Commit size and global verification size need not match. Use the reference's bounded validation waves, exact accepted checkpoints, and qualified evidence reuse. A loop-speed repair must unblock a named real deliverable; stop expanding infrastructure once that path works. Record rulings in the existing campaign artifact and notify affected children.

**The test:** the parent can show verified progress toward the owner's goal, explain the current bottleneck and next milestone, and intervene without weakening required acceptance or manufacturing authority.

**Report:** substantive work accepted, provisional work, decisive checks, the bottleneck and steering decision, contract changes, and blockers needing the owner. Report tooling and metadata cleanup separately; lane counts alone are not progress.
