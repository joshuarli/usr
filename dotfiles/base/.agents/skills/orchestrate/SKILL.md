---
name: orchestrate
description: "Route substantial, routine, mechanical, exploratory, or context-heavy work across subagents to control cost, isolate context, and parallelize independent work, and run a multi-lane campaign over a backlog. Delegate whenever the work is economical to specify and verify. Skip a task cheaper to do directly."
---

# Orchestrate

Delegate when specification and verification cost less than doing the work locally. Keep the parent responsive and responsible for integration and final verification.

## Routing

Route by difficulty, uncertainty, and risk. Use the column for the harness you are running in.

| Work | Codex | Claude and Grok | OpenCode | Muse Code |
| --- | --- | --- | --- | --- |
| Read-only scouting, searches, inventories, documentation lookup, log triage, straightforward fact gathering | `gpt-6-luna`, `medium` | `scout` | same model, `explore` | `muse-spark-1.3`, `low` |
| Mechanical edits, routine implementation, straightforward documentation, crisp acceptance criteria | `gpt-6-luna`, `high` | `mechanic` | same model, `general` | `muse-spark-1.3`, `medium` |
| Normal implementation, debugging, tests, ordinary review | `gpt-6-luna`, `xhigh` | `worker` | same model, `general` | `muse-spark-1.3`, `high` |
| Difficult debugging, cross-cutting implementation, architecture, integration, demanding review | `gpt-6.1-sol`, `medium` | `expert` | same model, `general` | `muse-spark-1.3`, `xhigh` |
| The hardest work: a failure an `expert` could not explain, a design others will build on, the final adversarial review before landing | `gpt-6.1-sol`, `high` | `god` | same model, `general` | `muse-spark-1.3`, `xhigh` |

**Default to `worker`.** Size is not difficulty. A big lane with a clear method and acceptance (a profiled optimization, a port with a reference, a mock built from a design doc, an investigation with a known procedure, a bug fix with a reproduction) is a `worker` task, and so is most campaign lane work. Use `expert` only when the path is unknown and a wrong turn is costly: a cross-cutting design, a failure with no hypothesis, an integration that spans owners. If the brief can name the steps and the acceptance check, it is not an `expert` brief. Start with `worker` and escalate on evidence that the work was harder than briefed.

If work exceeds the parent's delegation ceiling, keep it local at the highest suitable effort rather than spawning above the parent, except for the Codex profile and the Grok pins below. If a selected model is unavailable, use a suitable allowed model at the same or lower tier or report the limitation. A failed command, missing dependency, or unavailable environment does not by itself justify model escalation.

### Codex

Use the model and effort in the Codex column for each Codex child. This profile overrides the parent's effort ceiling; if the assigned model is unavailable, report the limitation instead of substituting a model.

Assign a child only the model and effort in the Codex column. Never use any other model, including GPT-5.x, Terra, the `astra` tier, or `ultra`; this repository keeps delegation explicit through the orchestration instructions.

Always specify `model`, `reasoning_effort`, and `fork_turns`. Prefer `fork_turns: "none"` with a self-contained brief; otherwise use the smallest positive turn count needed.

### Claude and Grok

Spawn only `scout`, `mechanic`, `worker`, `expert`, or `god`, ranked in that order. A caller spawns only a lower tier, and `scout` spawns nothing. `agent-tier-gate` enforces that: Claude matches `Agent`, Grok matches `spawn_subagent`. `CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH` caps Claude nesting at 3. Model and effort come from `~/.claude/agents` or `~/.grok/agents`, not from the call. Every Grok definition pins `grok-4.7`. Do not use another model or `xhigh`. If `grok-4.7` is unavailable, report it. Change a type's model or effort in its file. Reserve `expert` for the difficult row, and `god` for work an `expert` has failed, or a decision others build on. Add a definition when none of the five fit. Prefer a fresh agent; fork only when the child needs the conversation.

### OpenCode

There is no tiering: every child runs the model already in use, and OpenCode supplies the only two child types, `explore` for read-only scouting and `general` for everything else. Pass no model override and invent no hierarchy. Size is still not difficulty, so default to `general`.

A child does not get a different model, so report rather than substitute if the running model is unavailable. Briefs stay self-contained, and parallel writers still get disjoint worktrees owned and created by the parent.

Give every parallel writer its own worktree, created by you with `git worktree add .work/wt/<name> -b <branch>` and named in the brief as the only place it may write. `isolation: "worktree"` also lands in `.work/wt/` through the WorktreeCreate hook, but its branch name is generated and the tree outlives the child, so campaigns create their own. A child's final report is not shown to the user: relay what matters. Background children notify on completion, so do not poll them, and send a running child a message when the rules change instead of restarting it.

### Muse Code

Pass `model: muse-spark-1.3` and the row's `effort` on every child. Never use another model or `none`, `minimal`, `max`, or `ultra`; if `muse-spark-1.3` is unavailable, report it. `god` repeats `xhigh` with a fresh child: brief the earlier failures, review adversarially. A child spawns only when the brief grants it, and only at lower efforts. Give parallel writers disjoint worktrees under `.work/wt/`.

## Delegation

Delegate coherent component-sized work; do not delegate a one-command or one-edit task when the handoff costs more than doing it locally. Batch related trivial work into one assignment. When one script or codemod can apply the change to every unit in a single pass, write and run it yourself instead of fanning out children to hand-apply it, and prove it by rerunning it on the unit you did by hand.

Maximize parallel work without overlap. Split the task by what each piece owns, and run one child per disjoint ownership set, as wide as the machine's headroom allows. Width follows the task: one child for a single coupled change, many for a wide one. Overlapping writes are the only limit on width, so serialize them inside one child. Give each child the largest coherent slice it can finish end to end, not a fragment that needs a second handoff.

Idle capacity is a defect. Whenever a child reports, a merge lands, a check finishes, or the owner asks, list the ready work that has no owner and launch it before starting anything slow yourself. Stagger rather than wait: a child may start on the current base while other children are unmerged, when the files it owns are disjoint from theirs; the parent merges and resolves conflicts later, which costs less than an idle child.

Carry forward findings and failed approaches. Every child gets:

- Clear ownership and write boundaries.
- A concrete deliverable with only the needed context.
- Proportionate checks and a stopping condition.
- No further delegation unless the brief grants it, and then only to lower tiers (Claude and Grok) within the depth cap. Codex children are all one tier, so `agents.max_depth` is the only limit.

## Campaigns

For a backlog run as parallel lanes, read [campaign mechanics and lane contract](references/campaigns.md) before preparing or launching work.

Treat the iteration loop as shared campaign infrastructure. When serialized
build or verification work becomes the critical path, assign a loop-speed lane
before adding more implementation width. It owns measuring selected work,
removing unexpectedly broad gates, exposing exact checks, and preserving safe
artifact reuse; it does not weaken final acceptance. Re-evaluate this bottleneck
after merges and failed gates instead of assuming the initial tooling remains
adequate.

**Reply:** what was delegated and integrated, checks and measurements, contract changes, and any blockers or decisions the owner needs to resolve.
