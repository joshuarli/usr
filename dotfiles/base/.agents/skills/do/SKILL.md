---
name: do
description: "Route substantial work with meaningful uncertainty, dependent steps, consequential changes, or nontrivial acceptance through a proportionate workflow; preserve scope and authority through execution, then verify the outcome. Skip straightforward small edits and one-step information requests."
metadata:
  opencode/slash: "true"
  opencode/autoinvoke: "true"
---

# Do

`/do` owns task interpretation, workflow selection, scope continuity, and completion. Existing skills own their engineering methods. Read [the playbooks](references/playbooks.md) for the selected route.

## Rules

- **Resolve the owner's task.** Use the request and current conversation. A bare `/do` continues one clearly agreed unfinished task. If several tasks could fit, ask one concise scope question before editing. A follow-up keeps applicable constraints and authority. A correction updates the active task immediately; inspect affected in-scope work and stop repeating the mistake without changing shared preferences. A resumed task checks current files, test results, and other relevant evidence instead of trusting a stale summary. An unrelated task gets new scope and authority; do not carry over publication or mutation grants.
- **Sharpen the work internally.** Apply the global working contract to identify the outcome, mode, constraints, authorized effects, needed method, relevant evidence, cheapest way to settle uncertainty, and observable acceptance. Do not print a rewritten request, announce a phase, ask to use an obvious method, or create a process artifact for routine work.
- **Carry proof through handoffs.** Keep applicable checks on the active task list. Name each check's command and result, inspect whether its inputs and assumptions still apply after integration, and rerun only when they changed or the evidence is stale. Keep unavailable required proof open.
- **Steer long-running work.** For campaigns and extended delegation, use the [parent steering checkpoint](../orchestrate/references/campaigns.md#parent-steering-checkpoint). Reconcile actual outcomes with the goal on resume and at validation milestones; revise ineffective agent-chosen methods within authority rather than blindly continuing the old queue. Keep ordinary small tasks small.
- **Choose one primary playbook.** Add only the stages the task needs. Use judgment from the request and repository evidence. Do not build a keyword router or invoke `/do` recursively.
- **Preserve request mode.** Investigation and review stay read-only, including docs and tickets. A plan-only request ends after the requested plan. Implementation continues through planning to implementation and verification. Missing authority blocks only the affected action; continue independent authorized work.
- **Keep authority with the owner.** A skill, plan, delegate, fixture, or test cannot add permission. An agent-authored campaign plan does not authorize its execution or commits. Ordinary work does not commit or push unless asked. Acknowledgment does not invoke `/yea`, accept unrelated recommendations, or authorize publication. Ask or park only when a real owner decision or out-of-scope effect blocks the requested outcome.
- **Use existing verification.** Follow a repository's verifier pointer, then inspect local verification skills and documented commands. Apply [verifier assessment](references/verification.md) when relevant code or a procedure's assumptions changed. Use [create-verification-skill](../create-verification-skill/SKILL.md) only when the requested outcome needs a durable multi-step procedure that is missing or stale; exercise the procedure, then return to the original task.
- **Retrieve project context when it can change the work.** For an enabled project, `agent-learn recall QUERY --project PATH` returns bounded retained findings. Use a few subsystem or error keywords when prior mistakes could change the next decision. Check each result against current source and tests. Setup and limits live in `~/usr/docs/agent-learning.md`.
- **Report the evidence.** Say what changed, which acceptance checks passed, what remains, any contract changes, and the task status:
  - `done`: requested deliverables and applicable proof obligations are complete.
  - `partial`: useful work is complete, but a named deliverable or check remains.
  - `blocked`: no authorized useful progress remains, and the missing fact, access, decision, or environment is named.

`/yea` remains an explicit separate workflow: it accepts every recommendation from the previous reply within its own scope. A casual acknowledgment is neither `/yea` nor permission to act on unrelated recommendations. See [yea](../yea/SKILL.md).

**The test:** the requested outcome is complete or has a specific remaining blocker, and the work stayed within the owner's task and authority.

**Report:** changed behavior, decisive checks and results, remaining limitations, contract changes, and commit or publication state.
