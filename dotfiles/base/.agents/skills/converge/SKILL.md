---
name: converge
description: "Use for /converge: reduce a repository to its default branch by retiring every lane, branch, process and scratch path whose work the default branch already holds, then list everything withheld with its reason and remove it only after one owner confirmation. Skip merging unmerged work (use settle), pausing a campaign (use campaign-winddown), and disk-pressure sweeps (use cleanup)."
disable-model-invocation: true
metadata:
  opencode/autoinvoke: "false"
---

# Converge

Bring a repository back to one checkout on its default branch. Treat the default branch as the record. Anything whose work it already holds goes without asking. Everything else goes on one list that the owner confirms once. Converge never merges: [settle](../settle/SKILL.md) brings unmerged work into the default branch, and converge removes what is left after integration, abandonment or supersession.

`/converge` authorizes retiring lane worktrees and deleting local branches whose work the default branch provably holds, and editing durable docs that tell agents to keep them. Everything else needs the owner's confirmation of the withheld list: stopping processes, deleting scratch or data, and dropping branches or stashes with unique work. Converge never force pushes, rewrites history or deletes remote branches.

## Inventory

Find the default branch and fetch as in settle's **Find the target**. Then take settle's **Inventory** (branches, pull requests, worktrees, stashes) and add:

- processes whose working directory or arguments are inside the repository, with their parent (`ps -o ppid=`, `lsof -a -p <pid> -d cwd`), start time and the last write to any file they follow;
- the entries of `.work/`, each with its size, newest modification time and any reference from build scripts or docs (`rg -n '\.work/<entry>'`);
- directories under `.work/wt/` that `git worktree list` does not know;
- lines in durable docs (`docs/roadmap.md` **Status**, `TODO.md`, `AGENTS.md`) that tell agents to keep a lane, branch or path.

## Classify by content, not by name

Put each item in exactly one class and keep the evidence:

- **Held:** the default branch contains the work. The branch is an ancestor, `git cherry` shows only `-`, or `worktree-retire --dry-run` accepts it. A squash merge counts when one default-branch commit has the lane's net diff: compare `git diff --stat <commit>^ <commit>` with `git diff --stat <default>...<branch>`, then the diffs themselves.
- **Superseded:** the default branch reached the same end state by another route. Prove it on the changed lines, for example a pin that already matches or a dependency that is already gone. A matching subject is not proof.
- **Unique:** commits, stashes or files whose content the default branch lacks.
- **Orphaned:** a process whose parent is init or launchd, whose owning session is gone, or whose inputs stopped changing long before now. A process with a live owning session is **Live**.
- **Cache:** regenerable output that a current build or the default branch's scripts still use.
- **Scratch:** anything else under `.work/`. `.work/` is disposable by contract, but scratch that cannot be regenerated still goes on the list.

## Act without asking

1. Retire each **Held** lane with `worktree-retire <path> --into <default> --dry-run`, then again without `--dry-run`. Pass `--discard-ignored` only when the listed ignored files are scratch. When the tool refuses a lane you proved Held or Superseded, put the lane on the withheld list with the tool's reason. Do not use `git worktree remove --force`.
2. Delete each **Held** local branch with `git branch -d`, or with `-D` after a proven squash merge or patch equivalence. Record each branch's tip SHA in the report so it can be restored from the reflog.
3. Remove the durable-doc lines that name retired items, commit them with a Conventional Commit, and push. A stale "keep this" line is what stops the next session, so do not leave it behind.

## Withhold and confirm once

Everything not removed above goes in one table: the item (path, branch, stash or PID), its class, size or commit count, the evidence, and a recommendation of **delete** or **keep**, with the reason. Recommend **keep** for **Live** items and for a **Cache** that a build still reads. Recommend **delete** for **Superseded** and **Orphaned** items. Recommend **delete** for scratch only when it can be regenerated or nothing depends on it. Mark anything that cannot be regenerated as such.

Ask for confirmation once, with the whole table, and do not ask item by item. After the owner answers, delete exactly the confirmed items and nothing else. Stop a process with `kill`, and escalate to `kill -9` only when it survives. Delete scratch by its exact path; never recursively sweep `.work/`. Recreate `.work/tmp` if you removed it.

## Verify and report

**The test:** `git worktree list` shows only the primary checkout, `.work/wt/` is empty, no process from the inventory is still running, `git status` is clean, and every remaining local branch is unique work that the owner chose to keep.

**Report:**

- items removed without asking, each with its class and evidence, and the SHA of each deleted branch tip;
- the withheld table and the owner's answer;
- items deleted after confirmation, and before/after sizes of `.work/`;
- everything kept, each with its reason, and the docs commit.
