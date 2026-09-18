---
name: orchestrate
description: Route substantial, routine, mechanical, exploratory, or context-heavy work across subagents to control cost, isolate context, and parallelize independent work. Delegate whenever the work is economical to specify and verify.
---

# Orchestrate

Balance total cost and progress, including delegation overhead, retries, and integration. Keep the parent available to the user and apply this policy to every subagent spawn.

## Parent Intelligence Boundary

Parents must be the highest-intelligence agents in their descendant tree. The known ordering is
Astra > Terra > Luna, so a parent may spawn only agents at its own level or lower. Never select a
higher-intelligence model or alias as a child, including as an escalation or fallback. If either
model's identity or ranking is unclear, do not delegate to it. This rule overrides the cost-routing
table below.

## Cost routing

Use only the following models. Sol (`gpt-5.6-sol`) and GPT-5.5 (`gpt-5.5`) are banned, including as fallbacks.

| Work | Model | Reasoning effort |
| --- | --- | --- |
| Read-only scouts: repository mapping, searches, inventories, documentation lookup, log triage, and fact gathering | `gpt-5.6-luna` | `low` |
| Trivial implementation, mechanical edits, straightforward documentation updates, and small bounded tasks with clear acceptance criteria | `gpt-5.6-luna` | `xhigh` |
| Normal implementation, debugging, tests, and review | `gpt-5.6-terra` | `xhigh` by default; `max` for more demanding work |
| Complex design, cross-cutting contracts, difficult reasoning, or problems beyond the normal implementation lane | `gpt-6-astra` | `low` by default; `medium` for the hardest work |

The parent intelligence boundary applies to every selection. Model authorization does not expand
the task's scope or action permissions.

Route by reasoning difficulty and risk, not file count alone, while respecting the parent
intelligence boundary. Keep ordinary read-only scouting on Luna; delegate difficult interpretation
of its findings separately when needed.

Always specify `model`, `reasoning_effort`, and `fork_turns` explicitly. Prefer `fork_turns: "none"` with a self-contained brief, or the smallest positive turn count needed. Do not use a full-history fork that implicitly inherits the parent's model and effort.

If a selected model is unavailable, use another allowed model appropriate to the task and budget, or report the limitation. Never substitute a banned model.

## Delegation policy

Delegate work when it is economical to specify and verify and can run independently alongside useful parent work. Choose the lane above; do not funnel all implementation through Luna merely because it is cheaper per call.

Do not spawn a child for a one-command or one-edit task when describing and integrating the delegation would cost more than performing it directly.

Assign coherent component-sized tasks, including their dependent steps and focused validation, to one child. Batch related trivial operations into one Luna assignment instead of spawning a child per edit. Avoid fragmented handoffs and repeated status or validation rituals.

Use parallel agents only for genuinely independent branches. Use the smallest useful fan-out; the configured concurrency limit is a ceiling, not a target.

Give every child:

- Distinct ownership and any read-only or file-write boundary.
- A concrete deliverable and the minimum relevant context and constraints.
- Proportionate acceptance checks and a stopping condition.
- Instructions not to delegate further unless the parent explicitly assigns a nested delegation budget and scope.

Parallelize independent investigation and implementation. Avoid overlapping file writes. Keep integration, cross-cutting decisions, and final verification under parent ownership, using delegated analysis or checks where useful.

Do not escalate a child above its parent. If a task needs higher capability than the parent can
delegate, keep it local. Carry forward findings and failed approaches. A failed command, missing
dependency, or unavailable environment is not by itself a reason to escalate models.
