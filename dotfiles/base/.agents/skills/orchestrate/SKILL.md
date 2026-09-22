---
name: orchestrate
description: Route substantial, routine, mechanical, exploratory, or context-heavy work across subagents to control cost, isolate context, and parallelize independent work. Delegate whenever the work is economical to specify and verify.
---

# Orchestrate

Delegate when specification and verification cost less than doing the work locally. Keep the parent responsive and responsible for integration and final verification.

## Routing

Allowed models, highest to lowest: `gpt-6-astra` > `gpt-6-sol` > `gpt-6-luna`.

A child must be at or below its parent. If the parent is outside this ordering, do not delegate. GPT-5.x and Terra are banned. Never use `ultra`; its automatic delegation conflicts with this skill.

| Work | Model | Reasoning effort |
| --- | --- | --- |
| Read-only scouting, searches, inventories, documentation lookup, log triage, straightforward fact gathering | `gpt-6-luna` | `low` |
| Mechanical edits, small bounded implementations, straightforward documentation, crisp acceptance criteria | `gpt-6-luna` | `medium` |
| Normal implementation, debugging, tests, ordinary review | `gpt-6-luna` | `xhigh`; `max` for elevated risk or ambiguity |
| Difficult debugging, cross-cutting implementation, architecture, integration, demanding review | `gpt-6-sol` | `high` |
| Frontier design or synthesis where Sol is insufficient; use sparingly | `gpt-6-astra` | `medium`; `high` when justified |

Route by difficulty, uncertainty, and risk. Prefer raising effort before moving up a tier. If work exceeds the parent's delegation ceiling, keep it local at the highest suitable effort rather than spawning above the parent; a Sol parent may use `max`. If a selected model is unavailable, use a suitable allowed model at the same or lower tier or report the limitation.

Always specify `model`, `reasoning_effort`, and `fork_turns`. Prefer `fork_turns: "none"` with a self-contained brief; otherwise use the smallest positive turn count needed.

## Delegation

Delegate coherent component-sized work; do not delegate a one-command or one-edit task when the handoff costs more than doing it locally. Batch related trivial work into one assignment.

Parallelize only independent ownership. Avoid overlapping writes, and use the smallest useful fan-out; concurrency is a ceiling, not a target.

Every child gets:

- Clear ownership and write boundaries.
- A concrete deliverable with only the needed context.
- Proportionate checks and a stopping condition.
- No further delegation unless explicitly given a nested budget and scope.

Carry forward findings and failed approaches. A failed command, missing dependency, or unavailable environment does not by itself justify model escalation.
