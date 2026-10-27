---
name: campaign-winddown
description: "Use for /campaign-winddown on a running campaign: pause it, let the lanes already working finish and integrate, start nothing new, leave a handoff in the campaign doc that survives a machine reboot, and stop."
disable-model-invocation: true
metadata:
  opencode/autoinvoke: "false"
---

# Campaign Winddown

Winddown takes a running campaign to a clean stop. In-flight lanes finish or park, green work integrates, checkouts are removed, nothing new starts, and the campaign doc's **Status** says how to resume. After a reboot, the repo, its branches, and the doc must be enough to continue. Mechanics are as in the Campaigns section of `orchestrate`. If the coordinator session is gone, rebuild lane state from `git worktree list`, `git branch`, and the doc.

This workflow commits locally. Do not use it when the user has forbidden commits. It should take minutes, not hours.

## Rules

- **Freeze first.** Set **Status** to `winding down`, commit it, and run `codex-campaign-closeout.py begin` from the integration worktree. Launch nothing. Cancel every loop, cron, or wakeup that would resume the campaign. In Codex, review the `Stop` command in `/hooks` before the guard's first use.
- **Finish, don't extend.** Message each running lane to commit what it has, report, and stop. Do not wait on a lane past its current attempt; commit its worktree to its branch yourself.
- **Integrate only green work.** Merge a lane only when its acceptance command and the narrowest affected suite pass on the integrated tree. Everything else stays on its branch, named in **Status** with its cause. Never merge red or unverified work to retire a branch.
- **Reclaim checkouts, keep data.** Before removing a worktree, check `git -C <path> status --porcelain --ignored=matching` and move logs or artifacts worth keeping under the repo's ignored `.work/`. Follow [`orchestrate`'s worktree lifecycle](../orchestrate/SKILL.md#worktree-lifecycle). Never force-remove.
- **No push.**

## Reboot audit

Run each check and fix what fails:

1. `git worktree prune && git worktree list`: only the main checkout remains, plus any tree named in **Status** with a current consumer and allowed with `codex-campaign-closeout.py allow`.
2. `git branch --no-merged`: every branch is named in **Status** or deleted because it is empty.
3. No campaign process, cron, or wakeup remains. The doc does not reference `/tmp` or `$TMPDIR`.
4. The main checkout is clean, and the doc is committed.

## The handoff

Rewrite **Status** in place, under 20 lines. Do not add a new section or keep the previous handoff.

- `paused <date>`, the resume prompt, and the first command.
- The last accepted revision, and whether the integration branch is green.
- Each parked branch with its item, cause, and retry condition.
- The next slice.

Commit the doc alone as `docs(campaign): pause ...` and stop.

**The test:** after a reboot, an agent with only the repo and the doc can start the next slice by reading **Status**.

**Report:** what merged, what is parked and where, and any audit check that failed or could not run.
