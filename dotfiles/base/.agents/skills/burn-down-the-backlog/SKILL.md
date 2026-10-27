---
name: burn-down-the-backlog
description: "Use for /burn-down-the-backlog: work the starting TODO.md queue through orchestrate, honoring prerequisites and priority, one commit per closed ticket, and park blocked work."
disable-model-invocation: true
metadata:
  opencode/autoinvoke: "false"
---

# Burn Down the Backlog

Close the bounded queue captured from `TODO.md`. Dependencies and existing ownership determine readiness; priority chooses the next ready ticket. A ticket is a delivery and accounting unit, not an agent unit. Use an existing [ultratriage](../ultratriage/SKILL.md) result as the decision handoff; do not invoke that workflow unless asked. Use [AFK unattended execution](../afk/SKILL.md#unattended-execution) for this workflow.

## Rules

- **Work on a branch.** Use a branch named `backlog-<date>` cut from the current branch. Never push, merge to the default branch, or format.
- **Keep the active queue bounded.** Capture the tickets already in `TODO.md` at the start. Record newly discovered tickets for a later run; do not add them to the active queue unless the user asks. Keep incomplete tickets open.
- **Honor prerequisites and recorded deferrals.** Read dependencies in tickets and accepted RFCs. Hold a dependent until its prerequisites are integrated and verified. If a prerequisite parks, keep its dependents open with the same blocker. Revisit a recorded deferral only when its trigger or evidence changes, or the owner changes the decision. Keep an unresolved owner decision or draft RFC parked. An accepted design does not replace prerequisite implementation.
- **Let priority schedule ready work.** Start the highest-priority ready ticket first, then work down by priority and ID. Dependencies, file conflicts, and acceptance determine integration. A ticket blocked by active lane ownership is not ready; integrate or park that owner before starting conflicting work. Recompute readiness after integrations. Do not delay an independent verified fix solely to make commit history follow priority order.
- **Choose lanes economically.** Complete a trivial ticket directly when that costs less than a handoff. A worker may take a coherent group of small related tickets when that reduces briefing and integration cost. Use separate worktrees when concurrency, isolation, or conflict risk justifies them; do not create one per ticket by default. For multiple lanes, follow [orchestrate](../orchestrate/SKILL.md) and its [lane contract](../orchestrate/references/campaigns.md#lane-contract).
- **Route by difficulty.** Follow `orchestrate` for model choice. Actual difficulty, uncertainty, and consequences determine implementation effort. Priority affects scheduling and proportionate scrutiny, not the model tier. Escalate when evidence shows the task is harder than briefed, not because another attempt slot exists.
- **Prove uncertain reports before fixing.** For an `unproven` ticket, establish its fact with a failing test or command and report that evidence before changing code. If the fact cannot be established within scope, leave the ticket open and explain what would prove it.
- **Park blocked actions precisely.** Assess each required action against the current request, prior authorization, repository rules, and available means. A routine download alone is not a reason to park a ticket. Park only work that requires an unavailable action, missing authority, or an owner decision. Continue independent authorized work. Do not close a ticket while its required acceptance remains blocked.
- **Give shared prerequisites one owner.** Retry only when evidence or conditions change. An unchanged environment or permission failure does not trigger another attempt or model escalation.
- **Keep ticket ownership clear.** Workers do not edit `TODO.md`. They report each ticket's diff, checks, acceptance evidence, and any defect outside the ticket. The parent owns integration and ticket accounting.
- **Reuse valid acceptance evidence.** Read each diff against the ticket's `Recommendation`. Reject unrelated edits, changes outside its `Where` files, unbriefed dependencies, and weakened or deleted tests. Reuse successful checks while relevant inputs and assumptions remain valid. Repeat them only when integration, changed inputs, or a binding requirement could invalidate them. Retain before-fix failure evidence for bug fixes and rerun it only when the source, test, or assumptions changed, or the evidence is unavailable.
- **Commit each closed ticket separately.** Put the accepted change and ticket removal in the same commit. Delete a linked RFC in that commit only when `todo` defines the ticket as complete. Use a Conventional Commit with a `Closes ABC-123` footer. A worker handling several tickets still delivers a separate commit for each. Do not close an incomplete ticket.
- **Record discoveries for later.** Add newly found defects under `Next` in `TODO.md` in one `docs(todo)` commit after the active queue. Do not work those tickets in this run unless requested.

## Steps

1. Read `AGENTS.md`, `TODO.md`, linked decisions, and any existing ultratriage result. Capture the active queue and map prerequisites, conflicts, and owner decisions.
2. Start the highest-priority ready work. Choose direct work, a coherent worker group, and worktrees according to `orchestrate` economics.
3. Integrate accepted work when its dependencies and acceptance allow. Keep one accepted commit and ticket removal for each closed ticket. Reuse valid proof and run the narrowest check when integration changes relevant inputs.
4. Record new defects for later, then confirm `TODO.md` contains only open, parked, and newly filed tickets.

**The test:** each closed ticket has exactly one commit containing its accepted change and removal with a `Closes` footer; incomplete tickets remain open; prerequisites land before their dependents; priority schedules ready work without imposing priority-sorted history or one lane per ticket; and nothing was pushed.

**Report:** the branch; closed tickets and commits; parked tickets with the exact blocker and unblock condition; newly filed tickets; checks and reused evidence; and confirmation that nothing was pushed.
