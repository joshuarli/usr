---
name: handoff
description: "Use for /handoff: make in-flight work resumable before you stop (pause), or take over another session's work from a branch, worktree, or transcript (pickup)."
disable-model-invocation: true
---

# Handoff

Work that stops mid-flight must be recoverable from the repo and one message. `campaign-winddown` does this for a running campaign.

## Pause

1. **Stop starting work.** Let running commands finish, and end what you started (`ps`). Nothing may live only in a process.
2. **Find what would be lost.** Read `git status` and `git worktree list`. Anything only in `.work/`, `/tmp`, or an uncommitted tree is at risk. Uncommitted work is the owner's to commit: say what is at risk, and commit only when asked.
3. **File the remainder as `todo` tickets.** Each names what is left, `Where`, the branch or worktree path, the known red, and the first command to run. A design that is not settled gets a draft RFC.
4. **Rehearse.** From a clean shell, run the first command a ticket names. One that fails is a defect in the handoff.

## Pickup

1. **Find the sources:** the branch and its `git log` since it left trunk, `git status`, the open tickets in `TODO.md`, and the prior transcript when given.
2. **Rebuild state from the repo, not the summary.** Run the narrow check the work relied on and compare it with the claimed result. A claim you cannot reproduce is unverified.
3. **Name what is done, in flight, decided, and open,** then continue from the first open item. Do not redo verified work or reopen a recorded decision.
4. **Treat uncommitted changes as the owner's work.** Never discard or reset them.

**The test:** an agent with only the repo, its branches, and the tickets can resume at the next item and reproduce the last result you claimed.

**Reply:** for pause, the branch and worktree state, the tickets filed, what is uncommitted, and the one-line prompt to resume. For pickup, what was verified, what could not be, and where you continue.
