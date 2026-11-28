---
name: campaign-winddown
description: "Use for /campaign-winddown on a running campaign: pause it, let the lanes already working finish and integrate, start nothing new, leave the handoff in docs/roadmap.md Status that survives a machine reboot, and stop."
disable-model-invocation: true
metadata:
  opencode/autoinvoke: "false"
---

# Campaign Winddown

Winddown takes a running campaign, and with it the whole roadmap, to a clean stop. In-flight lanes finish or park, green work integrates, checkouts are removed, nothing new starts, and the **Status** block of `docs/roadmap.md` says where to resume. After a reboot, the repo, its branches, and the roadmap must be enough to continue when the owner says "resume the roadmap". Mechanics are as in the Campaigns section of `orchestrate`. If the coordinator session is gone, rebuild lane state from `git worktree list`, `git branch`, and the roadmap. A repository with a legacy `docs/CAMPAIGN-*.md` gets its live content moved into the roadmap first, as `orchestrate`'s campaign reference describes.

This workflow commits locally. Do not use it when the user has forbidden commits.

## Rules

- **Freeze first.** Set **Status** to `winding down`, commit it, and run `codex-campaign-closeout.py begin` from the integration worktree. Launch nothing. Cancel every loop, cron, or wakeup that would resume the campaign. In Codex, review the `Stop` command in `/hooks` before the guard's first use.
- **Finish, don't extend.** Message each running lane to commit what it has, report, and stop. Do not wait on a lane past its current attempt; commit its worktree to its branch yourself.
- **Integrate only green work.** Merge a lane only when its acceptance command and the narrowest affected suite pass on the integrated tree. Everything else stays on its branch, named in **Status** with its cause. Never merge red or unverified work to retire a branch.
- **Reclaim checkouts, preserve durable state.** Before removing a worktree, check `git -C <path> status --porcelain --ignored=matching`. Commit necessary conclusions, reproduction instructions and resume state in the roadmap; copy any required sanitized fixtures to tracked repository paths. `.work/` is strictly disposable and may hold only optional, regenerable artifacts. Follow [`orchestrate`'s worktree lifecycle](../orchestrate/SKILL.md#worktree-lifecycle). Never force-remove.
- **No push.**

## Reboot audit

Run each check and fix what fails:

1. `git worktree prune && git worktree list`: only the main checkout remains, plus any tree named in **Status** with a current consumer and allowed with `codex-campaign-closeout.py allow`.
2. `git branch --no-merged`: every branch is named in **Status** or is empty and deleted per `orchestrate`'s worktree lifecycle.
3. No campaign process, cron, or wakeup remains. The roadmap does not reference `/tmp` or `$TMPDIR`.
4. The main checkout is clean, and `docs/roadmap.md` is committed there. No other plan, status, or handoff file exists. Deleting `.work/` would not remove the handoff or anything required to resume. Link this durable path in the final reply, never a scratch-worktree path.

## The handoff

The handoff is the roadmap's **Status** block, never a separate file or section. Rewrite it in place, under 20 lines, and do not keep the previous handoff.

- `paused <date>`, the campaign and slice where work stopped, and the first command. The resume prompt is always "resume the roadmap".
- The last accepted revision, and whether the integration branch is green.
- Each parked branch with its item, cause, and retry condition. A parked item is a branch; name no checkout as retained unless a process still uses it, and never record retention without a cause.
- The next slice, which may belong to a different campaign in **Sequence**.

Commit the roadmap alone as `docs(roadmap): pause ...` and stop.

**The test:** after a reboot, an agent told only "resume the roadmap" can start the next slice by reading **Status**.

**Report:** what merged, what is parked and where, and any audit check that failed or could not run.
