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
  - stays `unproven` after one attempt to prove its fact.
- **Priority order governs everything.** P1 first, then P2, P3, and P4, and by ID within a priority. Lanes launch in that order, so when ownership or the machine limits the width, the more important tickets take the slots. A finished lane waits for every higher-priority ticket to be committed or parked before its own commit, so `git log` reads from most to least important.
- **One lane per ticket,** as a `worker` in its own worktree at `.work/wt/<ID>`, by orchestrate's ownership rules: tickets that touch the same files go to one lane in order. The brief is the ticket, its `Fix with` skill, and the rule that a bug gets a failing test first.
- **A lane never writes `TODO.md`.** It reports the diff, the narrowest checks it ran, and any defect it found outside its ticket.
- **The integrator makes the commit.** For each reported lane, in the priority order above, apply its diff to the branch, delete the ticket from `TODO.md`, and commit once, so the fix and the ticket's removal are one commit. Verify the narrowest checks on the merged tree before moving on.
- **Commit message:** a Conventional Commit, `type(scope): subject` with the body saying why, a `!` or `BREAKING CHANGE:` footer for a contract change, and `Closes ABC-123` last.
- **A lane that fails its attempt limit parks.** Nothing is committed for it and the ticket is untouched.
- **New defects become new tickets** at the end, in one `docs(todo)` commit, with IDs from `Next`. Never reuse a deleted ID.

## Steps

1. Read `AGENTS.md` and `TODO.md`. Sort the tickets by priority, then ID, and sort each into run or park.
2. Cut the branch and prepare the lanes, then launch them in priority order as wide as ownership and the machine allow.
3. Integrate each report as above. Run a wider check only at the end, for an area the tickets crossed, and report it first.
4. File the new tickets, then confirm `TODO.md` holds only parked and new tickets.

**The test:** `git log` shows exactly one commit for each closed ID, each containing that ticket's removal and a `Closes` footer, in priority order, and no ticket both stays and has a commit.

**Reply:** the branch; closed tickets with their commits; parked tickets with the reason and the decision the owner owes; new tickets filed; the checks run; and that nothing was pushed.
