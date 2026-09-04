---
name: orchestrate
description: Route substantial, routine, mechanical, exploratory, or context-heavy work across subagents to control cost, isolate context, and parallelize independent work. Delegate whenever the work is economical to specify and verify.
---

# Orchestrate

Balance total cost and progress, including delegation overhead, retries, and integration. Keep the parent available to the user and apply this policy to every subagent spawn.

## Cost routing

Use only the following models. Sol (`gpt-5.6-sol`) and GPT-5.5 (`gpt-5.5`) are banned, including as fallbacks.

| Work | Model | Reasoning effort |
| --- | --- | --- |
| Read-only scouts: repository mapping, searches, inventories, documentation lookup, log triage, and fact gathering | `gpt-5.6-luna` | `low` |
| Trivial implementation, mechanical edits, straightforward documentation updates, and small bounded tasks with clear acceptance criteria | `gpt-5.6-luna` | `medium` |
| Normal implementation, debugging, tests, and review | `gpt-5.6-terra` | `xhigh` by default; `max` for more demanding work |
| Complex design, cross-cutting contracts, difficult reasoning, or problems beyond the normal implementation lane | `gpt-6-astra` | `medium` by default; `high` for the hardest work |

Terra and Astra subagents are authorized under this policy; no additional model-specific permission is needed. Model authorization does not expand the task's scope or action permissions.

Route by reasoning difficulty and risk, not file count alone. A small unsafe or semantic change may need Terra or Astra. Keep ordinary read-only scouting on Luna; delegate difficult interpretation of its findings separately when needed.

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

Escalate when evidence shows reasoning difficulty: Luna to Terra, or Terra to Astra, carrying forward findings and failed approaches. Start complex work on Astra when warranted; do not pay for predictable failures in cheaper lanes first. A failed command, missing dependency, or unavailable environment is not by itself a reason to escalate models.
