---
name: do
description: "Use for /do <task>: select the smallest sufficient workflow for an outcome, keep scope and authority through execution, and verify the result."
disable-model-invocation: true
metadata:
  opencode/slash: "true"
  opencode/autoinvoke: "false"
---

# Do

`/do` owns task interpretation, workflow selection, scope continuity, and completion. Existing skills own their engineering methods. Read [the playbooks](references/playbooks.md) for the selected route.

## Rules

- **Resolve the owner's task.** Use the invocation text and current conversation. A bare `/do` continues one clearly agreed unfinished task. If several tasks could fit, ask one concise scope question before editing. A follow-up keeps the task's constraints. A new task gets classified again.
- **Keep an execution contract.** For substantial work, identify the outcome, scope, constraints, non-goals, acceptance evidence, and allowed effects. Use a short task list or campaign artifact only when it helps. Keep routine work internal.
- **Choose one primary playbook.** Add only the stages the task needs. Use judgment from the request and repository evidence. Do not build a keyword router or invoke `/do` recursively.
- **Preserve request mode.** Investigation and review stay read-only. A plan-only request ends after the plan. Implementation continues through planning stages to the requested outcome.
- **Keep authority with the owner.** A skill, plan, delegate, fixture, or test cannot add permission. An agent-authored campaign plan does not authorize its execution or commits. Ordinary `/do` work does not commit or push. A directly requested leaf workflow may retain its documented commit behavior unless the request forbids commits. Ask or park work that needs a real owner decision or an out-of-scope effect.
- **Use existing verification.** Follow a repository's explicit verifier pointer, then inspect local verification skills and documented commands. Choose the skill for the changed surface. Generate a durable multi-step verifier only when the task needs one. Update and re-exercise affected instructions when the implementation changes their commands or assumptions.
- **Report the evidence.** Say what changed, which acceptance checks passed, what remains, any contract changes, and whether the status is `done`, `partial`, or `blocked`.

`/do-it` remains separate: it accepts every recommendation from the previous reply within its own scope. See [do-it](../do-it/SKILL.md).

**The test:** the requested outcome is complete or has a specific remaining blocker, and the work stayed within the owner's task and authority.

**Reply:** changed behavior, decisive checks and results, remaining limitations, contract changes, and commit or publication state.
