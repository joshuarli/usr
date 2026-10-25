---
name: cleanup
description: Reclaim campaign working space and retire completed worktrees after confirming integration. Use when a campaign leaves worktrees or scratch behind, disk space needs reclaiming, or the user asks to merge useful lane work and clean up. Skip in-flight or parked worktrees and live fixtures.
---

# Cleanup

When a campaign leaves worktrees behind, delegate one bounded inventory and cleanup pass to a low-cost worker. Use `gpt-6-luna` at medium effort when available. The coordinator supplies the repository, current campaign branch and head, campaign scope, and known active worktrees.

The worker may remove a checkout only when all of these are true:

- The checkout belongs to the named campaign and its lane is confirmed complete by the coordinator or campaign record.
- No active agent, process, or session owns or uses it; it is not locked.
- Its `git status --porcelain --untracked-files=all` is empty.
- Its committed changes are already in the campaign head. First check `git merge-base --is-ancestor <checkout-head> <campaign-head>`. If that fails, accept patch-equivalence only when `git rev-list --merges <campaign-head>..<checkout-head>` is empty and `git cherry <campaign-head> <checkout-head>` has no `+` entries. Retain it if this cannot be proven.
- Ignored files and local artifacts have been inspected. Preserve useful data at a repo-local ignored path or retain the checkout when it has a current consumer.

Keep the integration checkout, in-flight or parked work, dirty checkouts, unknown ownership, and any checkout whose integration or completion is uncertain. Never delete branches, use `git worktree remove --force`, or remove worktree directories with `rm`.

The worker inventories with `git worktree list --porcelain`, verifies each candidate against the supplied campaign head and active-worktree list, then removes verified paths with `git worktree remove <path>`. If removal refuses, retain the path and report the reason. Do not expand to other repositories or recursively spawn workers.

Before removing scratch, establish the live set and never touch it: the active fixture, runner roots created or written since the live run started, prepared inputs the live run consumes, uncommitted changes in any checkout, and checkouts named as retained in the campaign record. Identify the live fixture by recency plus the running process, not by name pattern alone.

Reclaim stale scratch directly with `rm -rf`: superseded run fixtures, runner roots older than the live run, previous days' native scratch (VM disks, checkpoints, staging, command logs), and dead build caches. These hold no source changes. Lane-internal build scratch inside a retained worktree stays until that lane is declared complete; report it as a per-lane resume-vs-rebuild decision instead.

Settle the merge question with `git cherry <campaign-head> <checkout-head>` per lane. All `-` entries and no `+` entries means the lane holds no unique changes and there is nothing to merge. Any `+` entry is useful work: integrate it into the campaign head before retiring anything from that lane.

Return the campaign head used, removed paths, retained paths with the exact reason each was kept, the merge verdict per lane, and before/after disk usage. The coordinator checks the worker's evidence, runs `git worktree list --porcelain` again, and confirms each removed path is gone. Leave ambiguous cases for later review.

**Report:** report the campaign head, removed and retained paths with reasons, the per-lane merge verdict, integration and cleanliness evidence, reclaimed space, and anything unresolved.
