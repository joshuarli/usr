---
name: orchestrate
description: Route substantial, routine, mechanical, exploratory, or context-heavy work across subagents to control cost, isolate context, and parallelize independent work. Delegate whenever the work is economical to specify and verify.
---

# Orchestrate

Remain available to the user. Let Astra plan, coordinate, and integrate while applying this routing policy to every subagent spawn.

## Cost routing

Always specify `model`, `reasoning_effort`, and `fork_turns` explicitly. Never let a child implicitly inherit the Astra parent.

### Scout

- `model: "gpt-5.6-luna"`
- `reasoning_effort: "low"`
- `fork_turns: "none"`
- Read-only.
- Use for repository mapping, searches, inventories, documentation lookup, log and test-output triage, and independent fact gathering.

### Routine worker

- `model: "gpt-5.6-luna"`
- `reasoning_effort: "medium"`
- `fork_turns: "none"` or the smallest positive turn count necessary.
- Use for mechanical edits, repetitive tests, straightforward migrations, formatting, linting, documentation cleanup, and other narrowly bounded grunt work.

### Implementer

- `model: "gpt-5.6-terra"`
- `reasoning_effort: "xhigh"`
- Use the minimum context necessary.
- Use for bounded implementation where requirements, design, and ownership are clear.

### Critical implementer or reviewer

- `model: "gpt-5.6-terra"`
- `reasoning_effort: "max"`
- Use the minimum context necessary.
- Reserve for difficult or high-risk implementation, independent verification, or escalation after a cheaper lane fails because of reasoning difficulty.

Never use a Sol model. Never use Astra as a subagent unless the user explicitly requests it.

## Delegation policy

Delegate routine, mechanical, exploratory, or context-heavy work to Luna whenever it has a clear scope and stopping condition.

Do not spawn a child for a one-command or one-edit task when describing and integrating the delegation would cost more than performing it directly.

Tightly sequential work may still be delegated. Assign the complete sequence to one child rather than splitting dependent steps across parallel agents.

Batch related trivial operations into one bounded Luna assignment.

Use parallel agents only for genuinely independent branches. Use the smallest useful fan-out; the configured concurrency limit is a ceiling, not a target.

Give every child:

- Distinct ownership.
- A concrete deliverable.
- A stopping condition.
- Instructions not to delegate further.

Prefer parallel read-only investigation. Avoid overlapping file writes. Keep integration, cross-cutting decisions, and final verification in the Astra parent.

If a cheaper agent is blocked by reasoning difficulty, retry once in the next capability lane. Do not escalate merely because a command or test failed; first return the failure evidence to the parent.