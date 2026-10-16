---
name: campaign-winddown
description: "Use for /campaign-winddown on a running campaign: pause it, let the lanes already working finish and integrate, start nothing new, leave a handoff in the campaign doc that survives a machine reboot, and stop."
disable-model-invocation: true
---

# Campaign Winddown

Winddown takes a running campaign to a clean stop. Work already in flight is integrated wherever applicable, redundant worktrees are removed to reclaim disk space, no new campaign work begins, and the campaign doc says exactly how to resume. The bar is a reboot: after power loss, the repo, its branches, and the doc alone must be enough to continue, so nothing the campaign needs may live in `/tmp` or in a process. Mechanics (lanes, merges) are as in the Campaigns section of `orchestrate`. You are the coordinator; if that session is gone, rebuild the lane state from `git worktree list`, `git branch`, and the doc.

This workflow requires owner-authorized local commits and does not override repository commit restrictions. Do not use its commit-dependent handoff when commits are forbidden.

## Rules

- **Freeze first.** Set the doc's status to `winding down` and commit it before doing anything else. A crash mid-winddown must still read as a stop. Then run `codex-campaign-closeout.py begin` from the integration worktree. Select no items. Launch no lanes or waves. Cancel every loop, cron, or wakeup that would resume the campaign.
- **Trust the guard.** Before its first use, run `/hooks` in Codex and review the configured `Stop` command. The guard does not run until Codex trusts it.
- **Finish, don't extend.** Tell each running lane (send a message, do not restart it) to finish the item it holds, commit, report, and take no further item. A lane that is stuck or failing is time-boxed at the doc's attempt limit, then parked: commit its work to its branch and record the finding. Nothing new is picked up, and no defect found on the way is fixed unless it blocks landing an in-flight item.
- **Integrate before parking.** Review every lane for applicable changes, including incomplete work. Integrate coherent partial changes when they preserve the integration branch's contracts; incompleteness alone is not a reason to retain a worktree. Verify the integrated scope and record what remains unfinished. Do not merge obsolete implementations, changes that introduce known regressions, or unsupported acceptance claims merely to retire a branch. A focused RED test exposing an existing defect may land with its failing status explicit, without claiming the defect is fixed. Preserve incompatible or unsafe partial work on a committed branch, then remove its checkout. Follow [`orchestrate`'s worktree lifecycle](../orchestrate/SKILL.md#worktree-lifecycle). Skip repository-wide rewrites and new feature work.
- **Reclaim checkout space; preserve useful local data.** Logs, caches, qualified artifacts and failed-run records are worth keeping. Inspect ignored and untracked files before removal; preserve them at a persistent repo-local path under ignored `.work/` or retain the specific tree when an actual consumer requires it. Preserve required consumer paths or update the handoff with their new locations. Keep durable source on the integration branch or a parked branch, so a removable checkout does not become its only copy. Do not blanket-delete ignored files or caches, force-remove trees, or retain every tree just because it once ran a gate. No campaign state may depend on a process or `/tmp`.
- **No push.** Commit the handoff and merges; never push.

## Reboot audit

Run each check and fix what fails. Do not report from memory.

1. Run `git worktree prune` and `git worktree list`. Remove committed campaign checkouts after integration review and preservation of useful local data, including checkouts of parked branches. Keep only baseline checkouts or clean worktrees under `<repo>/.work/` with a concrete current consumer named in the handoff. A historical run or an unmerged branch alone is not a retention reason. Run `git -C <path> status --porcelain` for each retained worktree. Run `codex-campaign-closeout.py allow --path <path> --reason <reason>` for each retained worktree. Record each retained path and reason under **Open lanes** or **Retained worktrees**. Confirm the main checkout is clean.
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
- **Cleanup:** how many worktrees were removed, disk space recovered, where preserved logs/caches/artifacts remain, and each remaining non-baseline worktree's path, branch or HEAD, clean status, and concrete consumer. Record parked branches so their checkouts can be recreated.
- **Not started:** the next items in order, and the decisions the owner owes.
- **Verified:** the audit checks that passed, and anything that could not be checked.

Append one campaign-log line, commit the doc alone as a Conventional Commit (`docs(campaign): ...`), and stop. No further waves, no check-in.

**The test:** after a reboot, an agent with only the repo, its branches, and the doc can resume at the next item, and every file the campaign created in `/tmp` is one it could lose without noticing.

**Reply:** what merged, what is parked or in flight and where, the audit results (any check you could not run), and the path to the handoff.
