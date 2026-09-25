---
name: orchestrate
description: Route substantial, routine, mechanical, exploratory, or context-heavy work across subagents to control cost, isolate context, and parallelize independent work. Delegate whenever the work is economical to specify and verify.
---

# Orchestrate

Delegate when specification and verification cost less than doing the work locally. Keep the parent responsive and responsible for integration and final verification.

## Routing

Never assign a child `gpt-6-astra`. Allowed child models, highest to lowest:
`gpt-6-sol` > `gpt-6-luna`. For parent-ceiling checks, the model order is
`gpt-6-astra` > `gpt-6-sol` > `gpt-6-luna`; children must remain at or below
their parent. If the parent is outside this ordering, do not delegate. GPT-5.x
and Terra are banned. Never use `ultra`; its automatic delegation conflicts
with this skill.

| Work | Model | Reasoning effort |
| --- | --- | --- |
| Read-only scouting, searches, inventories, documentation lookup, log triage, straightforward fact gathering | `gpt-6-luna` | `low` |
| Mechanical edits, routine implementation, straightforward documentation, crisp acceptance criteria | `gpt-6-luna` | `max` |
| Normal implementation, debugging, tests, ordinary review | `gpt-6-sol` | `medium` |
| Difficult debugging, cross-cutting implementation, architecture, integration, demanding review | `gpt-6-sol` | `high` |

Route by difficulty, uncertainty, and risk. Use Sol at medium for normal code work and high for difficult or high-risk work. Use Luna at max for routine implementation. If work exceeds the parent's delegation ceiling, keep it local at the highest suitable effort rather than spawning above the parent. If a selected model is unavailable, use a suitable allowed model at the same or lower tier or report the limitation.

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
