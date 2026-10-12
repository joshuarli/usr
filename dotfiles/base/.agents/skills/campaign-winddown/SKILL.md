---
name: campaign-winddown
description: "Use for /campaign-winddown on a running campaign: pause it, let the lanes already working finish and integrate, start nothing new, leave a handoff in the campaign doc that survives a machine reboot, and stop."
disable-model-invocation: true
---

# Campaign Winddown

Winddown takes a running campaign to a clean stop. Work already in flight lands, no work begins, and the campaign doc says exactly how to resume. The bar is a reboot: after power loss, the repo, its branches, and the doc alone must be enough to continue, so nothing the campaign needs may live in `/tmp` or in a process. Mechanics (lanes, merges) are as in the Campaigns section of `orchestrate`. You are the coordinator; if that session is gone, rebuild the lane state from `git worktree list`, `git branch`, and the doc.

## Rules

- **Freeze first.** Before anything else set the doc's status to `winding down` and commit it, so a crash mid-winddown still reads as a stop. Select no items, launch no lanes, start no wave, and cancel every loop, cron, or wakeup that would resume the campaign.
- **Finish, don't extend.** Tell each running lane (send a message, do not restart it) to finish the item it holds, commit, report, and take no further item. A lane that is stuck or failing is time-boxed at the doc's attempt limit, then parked: commit its work to its branch and record the finding. Nothing new is picked up, and no defect found on the way is fixed unless it blocks landing an in-flight item.
- **Integrate as normal.** Review, rebase, fast-forward, and verify each reported lane on the merged tree. Remove its worktree and delete its branch once merged. Close with the checks the doc names for a wave close, and skip the repository-wide rewrites, which are new work.
- **Nothing lives only in a worktree, a process, or `/tmp`.** Each of these is committed to a branch or the campaign branch, or deleted as disposable.
- **No push.** Commit the handoff and merges; never push.

## Reboot audit

Run each check and fix what fails. Do not report from memory.

1. `git worktree prune`, then `git worktree list`: every path is under `<repo>/.work/`, each belongs to a lane still unmerged, and `git -C <path> status --porcelain` is empty for each. The main checkout is clean too.
2. `rg -n '/tmp|/var/folders|/private/tmp|\$TMPDIR'` over the campaign doc, lane briefs, and agent definitions: every hit is moved under `.work/` or removed. `.work/` must be ignored by `.git/info/exclude` and on disk, not tmpfs (`df -T .work` on Linux).
3. `git branch --no-merged <campaign-branch>`: every branch is either named in the handoff as parked or in-flight, or deleted because it was empty.
4. No process remains: no lane, build, test run, or watcher started by the campaign (`ps`), and no scheduled wakeup or cron job.
5. The campaign doc and everything it points to are committed on the campaign branch. Nothing it needs is untracked or ignored.
6. Rehearse the resume. From a shell with a clean environment (`env -i HOME=$HOME PATH=$PATH sh`), run every command the handoff gives and open every path and branch it names. One that fails is a defect in the handoff.

## The handoff

Replace any earlier one, placed directly under the header with status `paused <date>`:

- **Resume:** the one-line prompt that restarts the executor on the doc, and the first command to run.
- **State:** the campaign branch, what merged this session, and the known red on it.
- **Open lanes:** for each unmerged branch, its item IDs, its state (`parked` with the finding, or `wip` with what remains), and the next step. Worktrees are recreated at `.work/wt/<lane>` from the branch.
- **Not started:** the next items in order, and the decisions the owner owes.
- **Verified:** the audit checks that passed, and anything that could not be checked.

Append one campaign-log line, commit the doc alone as a Conventional Commit (`docs(campaign): ...`), and stop. No further waves, no check-in.

**The test:** after a reboot, an agent with only the repo, its branches, and the doc can resume at the next item, and every file the campaign created in `/tmp` is one it could lose without noticing.

**Reply:** what merged, what is parked or in flight and where, the audit results (any check you could not run), and the path to the handoff.
