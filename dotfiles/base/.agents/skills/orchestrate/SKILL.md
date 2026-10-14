---
name: orchestrate
description: "Route substantial, routine, mechanical, exploratory, or context-heavy work across subagents to control cost, isolate context, and parallelize independent work, and run a multi-lane campaign over a backlog. Delegate whenever the work is economical to specify and verify. Skip a task cheaper to do directly."
---

# Orchestrate

Delegate when specification and verification cost less than doing the work locally. Keep the parent responsive and responsible for integration and final verification.

## Routing

Route by difficulty, uncertainty, and risk. Use the column for the harness you are running in.

| Work | Codex | Claude |
| --- | --- | --- |
| Read-only scouting, searches, inventories, documentation lookup, log triage, straightforward fact gathering | `gpt-6-luna`, `medium` | `scout` |
| Mechanical edits, routine implementation, straightforward documentation, crisp acceptance criteria | `gpt-6-luna`, `high` | `mechanic` |
| Normal implementation, debugging, tests, ordinary review | `gpt-6-luna`, `xhigh` | `worker` |
| Difficult debugging, cross-cutting implementation, architecture, integration, demanding review | `gpt-6.1-sol`, `medium` | `expert` |
| The hardest work: a failure an `expert` could not explain, a design others will build on, the final adversarial review before landing | `gpt-6.1-sol`, `high` | `god` |

**Default to `worker`.** Size is not difficulty. A big lane with a clear method and acceptance (a profiled optimization, a port with a reference, a mock built from a design doc, an investigation with a known procedure, a bug fix with a reproduction) is a `worker` task, and so is most campaign lane work. Use `expert` only when the path is unknown and a wrong turn is costly: a cross-cutting design, a failure with no hypothesis, an integration that spans owners. If the brief can name the steps and the acceptance check, it is not an `expert` brief. Start with `worker` and escalate on evidence that the work was harder than briefed.

If work exceeds the parent's delegation ceiling, keep it local at the highest suitable effort rather than spawning above the parent, except for the Codex child profile specified below. If a selected model is unavailable, use a suitable allowed model at the same or lower tier or report the limitation. A failed command, missing dependency, or unavailable environment does not by itself justify model escalation.

### Codex

Use the model and effort in the Codex column for each Codex child. This profile overrides the parent's effort ceiling; if the assigned model is unavailable, report the limitation instead of substituting a model.

Assign a child only the model and effort in the Codex column. Never use any other model, including GPT-5.x, Terra, and the `astra` tier, and never use `ultra`: its automatic delegation conflicts with this skill.

Always specify `model`, `reasoning_effort`, and `fork_turns`. Prefer `fork_turns: "none"` with a self-contained brief; otherwise use the smallest positive turn count needed.

### Claude

Spawn children only as `scout`, `mechanic`, `worker`, `expert`, or `god`, never a built-in type. They rank `scout` < `mechanic` < `worker` < `expert` < `god`, and an agent spawns only tiers strictly below its own (`scout` spawns nothing). Claude cannot restrict spawn types per nested subagent in a definition, so the `agent-tier-gate` PreToolUse hook enforces the order on every spawn, and `CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH` caps nesting at 3. A subagent's model and reasoning effort come from its agent definition in `~/.claude/agents` (frontmatter `model`, `effort`), not from the call, which can override only the model. Those definitions are the single source of truth: change a type's model or effort there, not here. Built-in agent types do not pin effort. Reserve `expert` for the difficult row, and `god` for work an `expert` has failed on with evidence of the difficulty, or for a decision others build on. When a task needs a model and effort none of the five provide, add a definition instead of settling for the nearest. Prefer a fresh agent with a self-contained brief over a fork; fork only when the child needs the conversation itself.

Give every parallel writer its own worktree, created by you with `git worktree add .work/wt/<name> -b <branch>` and named in the brief as the only place it may write. `isolation: "worktree"` also lands in `.work/wt/` through the WorktreeCreate hook, but its branch name is generated and the tree outlives the child, so campaigns create their own. A child's final report is not shown to the user: relay what matters. Background children notify on completion, so do not poll them, and send a running child a message when the rules change instead of restarting it.

## Delegation

Delegate coherent component-sized work; do not delegate a one-command or one-edit task when the handoff costs more than doing it locally. Batch related trivial work into one assignment. When one script or codemod can apply the change to every unit in a single pass, write and run it yourself instead of fanning out children to hand-apply it, and prove it by rerunning it on the unit you did by hand.

Maximize parallel work without overlap. Split the task by what each piece owns, and run one child per disjoint ownership set, as wide as the machine's headroom allows. Width follows the task: one child for a single coupled change, many for a wide one. Overlapping writes are the only limit on width, so serialize them inside one child. Give each child the largest coherent slice it can finish end to end, not a fragment that needs a second handoff.

Idle capacity is a defect. Whenever a child reports, a merge lands, a check finishes, or the owner asks, list the ready work that has no owner and launch it before starting anything slow yourself. Stagger rather than wait: a child may start on the current base while other children are unmerged, when the files it owns are disjoint from theirs; the parent merges and resolves conflicts later, which costs less than an idle child.

Carry forward findings and failed approaches. Every child gets:

- Clear ownership and write boundaries.
- A concrete deliverable with only the needed context.
- Proportionate checks and a stopping condition.
- No further delegation unless the brief grants it, and then only to lower tiers (Claude) within the depth cap. Codex children are all one tier, so `agents.max_depth` is the only limit.

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
