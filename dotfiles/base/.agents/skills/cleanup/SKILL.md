---
name: cleanup
description: "Apply when a campaign leaves worktrees or scratch behind, or the user asks to merge useful lane work and clean up: retire completed worktrees after confirming integration and reclaim campaign scratch. Skip in-flight or parked worktrees, live fixtures, and generic disk cleanup."
---

# Cleanup

When a campaign leaves worktrees behind, delegate one bounded inventory and cleanup pass to a `mechanic`-tier worker per `orchestrate` routing. The coordinator supplies the repository, current campaign branch and head, campaign scope, and known active worktrees. Worktree and branch removal follow `orchestrate`'s worktree lifecycle; this skill adds the checks below.

The worker inventories with `git worktree list --porcelain` and removes a checkout only with `worktree-retire <path> --into <campaign-head>`, which refuses locked, dirty, or unintegrated checkouts (ancestor, or patch-equivalent with no merges) and lists ignored files. Before running it, confirm what the tool cannot see: the checkout belongs to the named campaign, its lane is complete per the coordinator or campaign record, and no agent, process, or session is using it. Preserve useful ignored data at a repo-local ignored path, or keep the checkout when it has a current consumer, before passing `--discard-ignored`.

Keep the integration checkout, in-flight or parked work, unknown ownership, and anything the tool refuses; report its reason. A "not integrated" refusal means the lane holds useful work (`git cherry <campaign-head> <checkout-head>` shows `+` entries): integrate it before retiring that lane. Never use `git worktree remove --force` or `rm` on a worktree. Do not expand to other repositories or recursively spawn workers.

Before removing scratch, establish the live set and never touch it: the active fixture, runner roots created or written since the live run started, prepared inputs the live run consumes, uncommitted changes in any checkout, and checkouts named as retained in the campaign record. Identify the live fixture by recency plus the running process, not by name pattern alone.

Reclaim stale scratch directly with `rm -rf`: superseded run fixtures, runner roots older than the live run, previous days' native scratch (VM disks, checkpoints, staging, command logs), and dead build caches. These hold no source changes. Lane-internal build scratch inside a retained worktree stays until that lane is declared complete; report it as a per-lane resume-vs-rebuild decision.

The coordinator checks the worker's evidence, runs `git worktree list --porcelain` again, and confirms each removed path is gone. Leave ambiguous cases for later review.

**The test:** every removed path is verified integrated and gone, every retained path has a stated reason, and no live fixture or unique lane work was touched.

**Report:** the campaign head used, removed and retained paths with the exact reason each was kept, the per-lane merge verdict, integration and cleanliness evidence, before/after disk usage, and anything unresolved.
