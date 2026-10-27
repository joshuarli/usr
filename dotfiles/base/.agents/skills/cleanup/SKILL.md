---
name: cleanup
description: Apply when a campaign leaves worktrees or scratch behind, or the user asks to merge useful lane work and clean up: retire completed worktrees after confirming integration and reclaim campaign scratch. Skip in-flight or parked worktrees, live fixtures, and generic disk cleanup.
---

# Cleanup

When a campaign leaves worktrees behind, delegate one bounded inventory and cleanup pass to a `mechanic`-tier worker per `orchestrate` routing. The coordinator supplies the repository, current campaign branch and head, campaign scope, and known active worktrees. Worktree and branch removal follow `orchestrate`'s worktree lifecycle; this skill adds the checks below.

The worker may remove a checkout only when all of these are true:

- The checkout belongs to the named campaign and its lane is confirmed complete by the coordinator or campaign record.
- No active agent, process, or session owns or uses it; it is not locked.
- Its `git status --porcelain --untracked-files=all` is empty.
- Its committed changes are already in the campaign head. First check `git merge-base --is-ancestor <checkout-head> <campaign-head>`. If that fails, accept patch-equivalence only when `git rev-list --merges <campaign-head>..<checkout-head>` is empty and `git cherry <campaign-head> <checkout-head>` has no `+` entries. Retain it if this cannot be proven.
- Ignored files and local artifacts have been inspected. Preserve useful data at a repo-local ignored path or retain the checkout when it has a current consumer.

Keep the integration checkout, in-flight or parked work, dirty checkouts, unknown ownership, and any checkout whose integration or completion is uncertain. Never use `git worktree remove --force` or remove worktree directories with `rm`. Leave branches to `orchestrate`'s lifecycle.

The worker inventories with `git worktree list --porcelain`, verifies each candidate against the supplied campaign head and active-worktree list, then removes verified paths with `git worktree remove <path>`. If removal refuses, retain the path and report the reason. Do not expand to other repositories or recursively spawn workers.

Settle the merge question per lane with `git cherry <campaign-head> <checkout-head>`: all `-` entries and no `+` entries means there is nothing to merge. Any `+` entry is useful work; integrate it into the campaign head before retiring anything from that lane.

Before removing scratch, establish the live set and never touch it: the active fixture, runner roots created or written since the live run started, prepared inputs the live run consumes, uncommitted changes in any checkout, and checkouts named as retained in the campaign record. Identify the live fixture by recency plus the running process, not by name pattern alone.

Reclaim stale scratch directly with `rm -rf`: superseded run fixtures, runner roots older than the live run, previous days' native scratch (VM disks, checkpoints, staging, command logs), and dead build caches. These hold no source changes. Lane-internal build scratch inside a retained worktree stays until that lane is declared complete; report it as a per-lane resume-vs-rebuild decision.

The coordinator checks the worker's evidence, runs `git worktree list --porcelain` again, and confirms each removed path is gone. Leave ambiguous cases for later review.

**The test:** every removed path is verified integrated and gone, every retained path has a stated reason, and no live fixture or unique lane work was touched.

**Report:** the campaign head used, removed and retained paths with the exact reason each was kept, the per-lane merge verdict, integration and cleanliness evidence, before/after disk usage, and anything unresolved.
