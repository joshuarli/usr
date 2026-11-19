---
name: cleanup
description: "Apply to an agent-disk-pressure notice below 10% system free space, or an explicit cleanup request. Reclaim only owned completed worktrees and known stale scratch. Skip unsolicited sweeps on healthy disks, live or parked work, and generic system cleanup."
---

# Cleanup

For a proactive sweep, first run `agent-disk-pressure status`. It prints a fresh system-volume reading: exit 1 means strictly below 10% available; 0 means healthy; 2 means unknown. Do not inventory or remove anything on 0 or 2. Recheck before each removal batch and after it; stop at >=10%, unknown, or no safe candidates. A notice can be stale by the time you read it. Do one bounded pass per notice, not a polling loop. Explicit user-requested cleanup and ordinary retirement of the current task's completed lanes do not need pressure.

The coordinator owns cleanup and all removals. A worker may provide a bounded read-only inventory when that saves time; workers never delete worktrees, branches or scratch. Supply the repository, integration worktree and head, campaign scope, and exact known-owned and active paths. Do not expand a pressure notice into an all-repository or home-directory sweep. Skip candidates on unrelated disks that cannot relieve the pressured system volume.

Inventory with `git worktree list --porcelain` and retire a checkout only with `worktree-retire <path> --into <campaign-head>` from the surviving integration worktree. The tool refuses unsafe paths, leases, locks, dirty or unintegrated checkouts and lists ignored files. Confirm what the tool cannot prove: the checkout belongs to this campaign, the lane is complete, and no agent, process or session still consumes it. A clean Git status is not evidence of inactivity. Preserve useful ignored data outside the lane, or keep the checkout when it has a current consumer, before passing `--discard-ignored`.

Keep the integration checkout, in-flight or parked work, unknown ownership, and anything the tool refuses; report its reason. A "not integrated" refusal means proof is insufficient, not that the changes were never accepted: multi-commit squashes or later edits can defeat simple comparisons. Review the actual diff and preserve its branch; never waive the guard to save space. Never use `git worktree remove --force` or `rm` on a worktree. Do not recursively spawn workers.

Before removing scratch, establish the live set and never touch it: the active fixture, runner roots created or written since the live run started, prepared inputs the live run consumes, uncommitted changes in any checkout, and checkouts named as retained in the campaign record. Identify the live fixture by recency plus the running process, not by name pattern alone.

Remove only exact positively identified stale scratch paths: superseded fixtures, stopped runner roots, regenerable VM disks or build caches with no live consumer or unique source. Age or a name pattern alone is insufficient. Do not delete `.work/` wholesale, active bridge state, host caches, or another agent's outputs. Lane-internal scratch inside a retained worktree stays until the owner declares that lane complete.

The coordinator checks the worker's evidence, runs `git worktree list --porcelain` again, and confirms each removed path is gone. Leave ambiguous cases for later review.

**The test:** every removed path is verified integrated and gone, every retained path has a stated reason, and no live fixture or unique lane work was touched.

**Report:** the campaign head used, removed and retained paths with the exact reason each was kept, the per-lane merge verdict, integration and cleanliness evidence, before/after disk usage, and anything unresolved.
