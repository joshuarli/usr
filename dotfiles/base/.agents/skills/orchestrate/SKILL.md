---
name: orchestrate
description: Route substantial, routine, mechanical, exploratory, or context-heavy work across subagents to control cost, isolate context, and parallelize independent work. Delegate whenever the work is economical to specify and verify.
---

# Orchestrate

Balance total cost and progress, including delegation overhead, retries, and integration. Keep the parent available to the user and apply this policy to every subagent spawn.

## Parent Intelligence Boundary

Parents must be the highest-intelligence agents in their descendant tree. The known ordering is
Astra > Sol > Luna:

- `gpt-6-astra`
- `gpt-6-sol`
- `gpt-6-luna`

A parent may spawn only agents at its own level or lower. Never select a higher-intelligence model
or alias as a child, including as an escalation or fallback. If the parent model is outside this
known ordering, do not delegate under this skill. This rule overrides the routing table below.

## Model routing

Use only the exact GPT-6 model IDs above. GPT-5.x models and Terra are banned, including as
fallbacks.

Do not use `ultra` reasoning inside this skill. Astra and Sol expose `ultra` as an automatic
delegation mode; this skill already owns delegation, fan-out, model selection, and nesting.
Explicit orchestration keeps cost, ownership, and concurrency predictable.

| Work | Model | Reasoning effort |
| --- | --- | --- |
| Read-only scouts: repository mapping, searches, inventories, documentation lookup, log triage, and straightforward fact gathering | `gpt-6-luna` | `low` |
| Mechanical edits, small bounded implementations, straightforward documentation, and narrow tasks with crisp acceptance criteria | `gpt-6-luna` | `high` by default; `max` when the bounded task is unusually subtle |
| Normal implementation, debugging, tests, and ordinary review | `gpt-6-sol` | `medium` by default; `high` when correctness risk or ambiguity is elevated |
| Difficult debugging, cross-cutting implementation, architecture, integration, or demanding review | `gpt-6-sol` | `max` |
| Frontier design or synthesis where Sol is not enough | `gpt-6-astra` | `medium` by default; `high` or `max` only when the extra depth is justified |

The Astra lane is available only when the parent itself is Astra. A Sol parent must not spawn Astra;
keep work local at Sol `max` if the task exceeds what it can safely delegate.

Route by reasoning difficulty, uncertainty, and risk rather than file count. Prefer raising effort
within the selected tier before moving to a more expensive model. Keep routine read-only discovery
on Luna and delegate difficult interpretation or decisions separately.

Always specify `model`, `reasoning_effort`, and `fork_turns` explicitly. Prefer
`fork_turns: "none"` with a self-contained brief, or the smallest positive turn count needed.
Do not use a full-history fork that implicitly inherits the parent's model and effort.

If the selected model is unavailable, use another allowed model at the same or lower intelligence
level that is suitable for the task, or report the limitation. Never silently substitute a banned
or higher-intelligence model.

## Delegation policy

Delegate work when it is economical to specify and verify and can run independently alongside
useful parent work. Choose the lane above; do not funnel normal implementation through Luna merely
because it is cheaper.

Do not spawn a child for a one-command or one-edit task when describing and integrating the
delegation would cost more than performing it directly.

Assign coherent component-sized tasks, including their dependent steps and focused validation, to
one child. Batch related trivial operations into one Luna assignment instead of spawning a child
per edit. Avoid fragmented handoffs and repeated status or validation rituals.

Use parallel agents only for genuinely independent branches. Use the smallest useful fan-out; the
configured concurrency limit is a ceiling, not a target.

Give every child:

- Distinct ownership and any read-only or file-write boundary.
- A concrete deliverable and the minimum relevant context and constraints.
- Proportionate acceptance checks and a stopping condition.
- Instructions not to delegate further unless the parent explicitly assigns a nested delegation
  budget and scope.

Parallelize independent investigation and implementation. Avoid overlapping file writes. Keep
integration, cross-cutting decisions, and final verification under parent ownership, using
delegated analysis or checks where useful.

Do not escalate a child above its parent. If a task needs higher capability than the parent can
delegate, keep it local. Carry forward findings and failed approaches. A failed command, missing
dependency, or unavailable environment is not by itself a reason to escalate models.
