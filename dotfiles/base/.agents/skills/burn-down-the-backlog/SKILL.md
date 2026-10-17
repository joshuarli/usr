---
name: burn-down-the-backlog
description: "Use for /burn-down-the-backlog: work every ticket in TODO.md through orchestrate, one commit per ticket that also deletes the ticket, and park what needs the owner."
disable-model-invocation: true
---

# Burn Down the Backlog

Close the tickets in `TODO.md` unattended, in priority order, one commit each. Delegation, lanes, and merging follow `orchestrate`; read `~/.agents/skills/orchestrate/references/campaigns.md` for the lane contract before launching. Ticket format and ID rules belong to `todo`.

## Rules

- **Invoking this skill asks for the commits,** one per ticket, on a branch named `backlog-<date>` cut from the current one. It never pushes, merges to the default branch, or formats.
- **Only eligible tickets run.** Park a ticket, leaving it in `TODO.md`, when it:
  - links a draft RFC, or otherwise needs a decision only the owner can make;
  - needs an outward or irreversible step: a push, a download, `sudo`, a system or `~` mutation, or deleting outside the repo;
  - stays `unproven` after one attempt to prove its fact (the first attempt on an `unproven` ticket proves the fact with a failing test or a command, and reports it before changing code).
- **Priority order governs everything.** P1 first, then P2, P3, and P4, and by ID within a priority. Lanes launch in that order, so when ownership or the machine limits the width, the more important tickets take the slots. A finished lane waits for every higher-priority ticket to be committed or parked before its own commit, so `git log` reads from most to least important.
- **One lane per ticket,** in its own worktree at `.work/wt/<ID>`, by orchestrate's ownership rules. Tickets that touch the same files run one after another: the higher priority merges first, then the next is briefed on the updated branch. Tickets never share a lane, so a lane's tier is its own ticket's. The brief is the ticket, its `Fix with` skill, and the rule that a bug gets a failing test first.
- **The ticket sets the tier,** using orchestrate's routing table for the harness in use:
  - **P1 and P2:** the difficult row (`expert`; `gpt-6.1-sol` on Codex).
  - **P3 and P4, Effort S, and a `Recommendation` that names one change:** the mechanical row (`mechanic`; `gpt-6-luna`, `high`).
  - **Any other P3 or P4:** the normal row (`worker`; `gpt-6-luna`, `xhigh`).
  - A ticket whose `Recommendation` offers a choice ("A or B") is not mechanical. Park it if the choice is the owner's, otherwise use the normal row.
- **Attempts escalate.** A lane gets two attempts at its tier, the second briefed with the integrator's rejection and the command output. A third attempt runs one row up. After that the ticket parks with the failures reported. Never skip a row, and never go above the difficult row for P3 and P4.
- **A lane never writes `TODO.md`.** It reports the diff, the narrowest checks it ran, and any defect it found outside its ticket.
- **The integrator checks every lane, at every tier, before committing.** The lane's report is a claim, not evidence. For each lane, in the priority order above:
  1. Read the whole diff against the ticket's `Recommendation`. Reject edits outside the ticket's `Where` files, unrelated cleanups, new dependencies the brief did not name, and a weakened or deleted test.
  2. For a bug, check out the base commit with only the new test applied and confirm it fails, then confirm it passes with the fix.
  3. Apply the diff to the branch, rerun the lane's named tests, and run the narrowest lint and type checks for the touched files on the merged tree.
  4. Delete the ticket from `TODO.md`. Delete its RFC in that same commit when `todo` counts the RFC done. Commit once, so the fix and those removals are one commit.
  A failed check goes back to the lane under the attempt rule above. A weaker tier gets the same checks, never fewer.
- **Commit message:** a Conventional Commit, `type(scope): subject` with the body saying why, a `!` or `BREAKING CHANGE:` footer for a contract change, and `Closes ABC-123` last.
- **A ticket that exhausts its attempts parks.** Nothing is committed for it and the ticket is untouched.
- **New defects become new tickets** at the end, in one `docs(todo)` commit, with IDs from `Next`. Never reuse a deleted ID.

## Steps

1. Read `AGENTS.md` and `TODO.md`. Sort the tickets by priority, then ID, and sort each into run or park.
2. Cut the branch and prepare the lanes, then launch them in priority order as wide as ownership and the machine allow.
3. Integrate each report as above. Run a wider check only at the end, for an area the tickets crossed, and report it first.
4. File the new tickets, then confirm `TODO.md` holds only parked and new tickets.

**The test:** `git log` shows exactly one commit for each closed ID, each containing that ticket's removal and a `Closes` footer, in priority order, and no ticket both stays and has a commit.

**Reply:** the branch; closed tickets with their commits and the tier that closed each, noting any escalation; parked tickets with the reason and the decision the owner owes; new tickets filed; the checks run; and that nothing was pushed.
