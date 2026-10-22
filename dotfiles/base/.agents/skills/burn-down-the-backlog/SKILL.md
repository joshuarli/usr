---
name: burn-down-the-backlog
description: "Use for /burn-down-the-backlog: work every ticket in TODO.md through orchestrate, one commit per ticket that also deletes the ticket, and park what needs the owner."
disable-model-invocation: true
metadata:
  opencode/autoinvoke: "false"
---

# Burn Down the Backlog

Close the tickets in `TODO.md` unattended, in dependency order, then priority order, one commit each. Delegation, lanes, and merging follow `orchestrate`; read `~/.agents/skills/orchestrate/references/campaigns.md` for the lane contract before launching. Ticket format and ID rules belong to `todo`. Use an existing `ultratriage` result as the decision handoff; do not invoke that decision workflow unless asked.

Read and follow [afk](../afk/SKILL.md) for this workflow.

## Rules

- **Invoking this skill asks for the commits,** one per ticket, on a branch named `backlog-<date>` cut from the current one. It never pushes, merges to the default branch, or formats.
- **Only eligible tickets run.** Park a ticket, leaving it in `TODO.md`, when it:
  - links a draft RFC, or otherwise needs a decision only the owner can make;
  - has a recorded blocker or deferral whose unblock condition or revisit trigger is still unmet; honor it unless current evidence satisfies it or the owner changes the decision;
  - needs an outward or irreversible step: a push, a download, `sudo`, a system or `~` mutation, or deleting outside the repo;
  - stays `unproven` after one attempt to prove its fact (the first attempt on an `unproven` ticket proves the fact with a failing test or a command, and reports it before changing code).
- **Prerequisites gate readiness.** Read dependencies in the tickets and accepted RFCs. A settled design does not implement its prerequisite. Hold a dependent until the prerequisite commit is integrated and verified, then reconsider it; do not park it permanently while its prerequisite is runnable. If a prerequisite parks, park its dependents with that same blocker. A missing prerequisite or cycle gets one bounded investigation; if it cannot be resolved within scope, park the affected work with the exact gap.
- **Priority orders ready work.** P1 first, then P2, P3, and P4, and by ID within a priority. Launch and commit in that order among runnable tickets; a finished lane waits for higher-priority runnable work. A ticket blocked by an existing lane's file ownership is not runnable; integrate or park that owning lane first. A prerequisite may commit before its higher-priority dependent. Report ordering forced by prerequisites or existing ownership without changing priorities. Recompute readiness after each integration so newly unblocked work takes its proper place.
- **One lane per ticket,** in its own worktree at `.work/wt/<ID>`, by orchestrate's ownership rules. Tickets that touch the same files run one after another: follow dependency order, then priority, and brief the next on the updated branch. Tickets never share a lane, so a lane's tier is its own ticket's. The brief is the ticket, its prerequisites and accepted decisions, its `Fix with` skill, and the rule that a bug gets a failing test first.
- **The ticket sets the tier,** using orchestrate's routing table for the harness in use:
  - **P1 and P2:** the difficult row (`expert`; `gpt-6.1-sol` on Codex).
  - **P3 and P4, Effort S, and a `Recommendation` that names one change:** the mechanical row (`mechanic`; `gpt-6-luna`, `high`).
  - **Any other P3 or P4:** the normal row (`worker`; `gpt-6-luna`, `xhigh`).
  - A ticket whose `Recommendation` offers a choice ("A or B") is not mechanical. Park it if the choice is the owner's, otherwise use the normal row.
- **Attempts escalate.** A lane gets two attempts at its tier, the second briefed with the integrator's rejection and the command output. A third attempt runs one row up. After that the ticket parks with the failures reported. Never skip a row, and never go above the difficult row for P3 and P4.
- **Steer the backlog.** Apply the [parent steering checkpoint](../orchestrate/references/campaigns.md#parent-steering-checkpoint) without changing ticket priority, commit authority, or required per-ticket checks. Bound prepared work by integration capacity. A shared missing prerequisite gets one owner and a retry condition, not fresh attempts from every ticket. An unchanged environment or permission failure does not trigger the model-escalation rule.
- **A lane never writes `TODO.md`.** It reports the diff, the narrowest checks it ran, and any defect it found outside its ticket.
- **The integrator checks every lane, at every tier, before committing.** The lane's report is a claim, not evidence. For each lane, in the dependency and priority order above:
  1. Read the whole diff against the ticket's `Recommendation`. Reject edits outside the ticket's `Where` files, unrelated cleanups, new dependencies the brief did not name, and a weakened or deleted test.
  2. For a bug, check out the base commit with only the new test applied and confirm it fails, then confirm it passes with the fix.
  3. Apply the diff to the branch, rerun the lane's named tests, and run the narrowest lint and type checks for the touched files on the merged tree.
  4. Delete the ticket from `TODO.md`. Delete its RFC in that same commit when `todo` counts the RFC done. Commit once, so the fix and those removals are one commit.
  A failed check goes back to the lane under the attempt rule above. A weaker tier gets the same checks, never fewer.
- **Commit message:** a Conventional Commit, `type(scope): subject` with the body saying why, a `!` or `BREAKING CHANGE:` footer for a contract change, and `Closes ABC-123` last.
- **A ticket that exhausts its attempts parks.** Nothing is committed for it and the ticket is untouched.
- **New defects become new tickets** at the end, in one `docs(todo)` commit, with IDs from `Next`. Never reuse a deleted ID.

## Steps

1. Read `AGENTS.md`, `TODO.md`, and linked decisions. Map prerequisites, sort by priority then ID, and distinguish runnable, waiting, and parked tickets.
2. Cut the branch and prepare the lanes, then launch ready work in priority order within ownership, machine, and integration-capacity limits. Revisit waiting tickets as prerequisites land.
3. Integrate each report as above. Run broader checks at bounded integration milestones for areas the tickets cross and at the end, reporting their scope first. Keep the per-ticket focused proof above; do not mark a ticket globally verified while its required milestone is pending.
4. File the new tickets, then confirm `TODO.md` holds only parked and new tickets.

**The test:** `git log` shows exactly one commit for each closed ID, each containing that ticket's removal and a `Closes` footer, with prerequisites before dependents and priority order among runnable tickets, and no ticket both stays and has a commit.

**Report:** the branch; closed tickets with their commits and the tier that closed each, noting escalation or ordering forced by prerequisites or ownership; parked tickets with the reason and exact unblock condition; new tickets filed; the checks run; and that nothing was pushed.
