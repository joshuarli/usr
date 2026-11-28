---
name: converge
description: "Use for /converge: make the GitHub default branch the one place where all work lives. Merge every branch, pull request and lane with unique work, push what cannot merge, retire every lane, branch, process and scratch path the default branch already holds, then list everything withheld with its reason and remove it after one owner confirmation. Skip PR-only CI repair (use green), campaign pause (use campaign-winddown), and disk-pressure sweeps (use cleanup)."
disable-model-invocation: true
metadata:
  opencode/autoinvoke: "false"
---

# Converge

Bring a repository down to one checkout on its default branch, with all its work in that branch. Unique work merges in. Work the branch already holds is retired without asking. Everything else goes on one list that the owner confirms once, at the end.

`/converge` authorizes merges, pushes to the default branch and other branches, retiring lanes and deleting local branches whose work the default branch holds, and editing durable docs that tell agents to keep them. Stopping processes, deleting scratch or data, and dropping unmerged branches or stashes need the owner's confirmation of the withheld list. Never force push, rewrite history, delete remote branches or drop stashes.

Use [sleep](../sleep/SKILL.md) until the confirmation. The confirmation is the only stop.

## Target

Read the default branch with `gh repo view --json defaultBranchRef --jq .defaultBranchRef.name`. Without `gh` or a GitHub remote, use `git symbolic-ref --short refs/remotes/origin/HEAD`. Never assume `main` or `master`. Use the remote the default branch lives on and run `git fetch --prune <remote>`. Fast-forward the primary checkout to the remote. If it has diverged, merge the remote in; do not reset. If the primary checkout is dirty, merge in a scratch worktree at `.work/wt/converge` and leave the dirty files alone. State the branch, the remote and its head before the first merge.

## Inventory

- local branches, and remote branches with no local copy, with `git log --oneline <default>..<branch>`;
- open and draft pull requests (`gh pr list --state open --json number,headRefName,isDraft,isCrossRepository`);
- worktrees and their status (`git worktree list --porcelain`, `git -C <path> status --short`), plus directories under `.work/wt/` that git does not know;
- stashes, and submodule commits that are not on a submodule remote;
- processes whose working directory or arguments are inside the repository, with their parent (`ps -o ppid=`, `lsof -a -p <pid> -d cwd`), start time and the last write to any file they follow;
- the entries of `.work/`, each with its size, newest modification time and any reference from build scripts or docs;
- lines in durable docs (`docs/roadmap.md` **Status**, `TODO.md`, `AGENTS.md`) that tell agents to keep a lane, branch or path.

## Classify by content, not by name

Put each item in exactly one class and keep the evidence:

- **Held:** the default branch contains the work. The branch is an ancestor, `git cherry <default> <branch>` shows only `-`, or `worktree-retire --dry-run` accepts it. A squash merge counts when one default-branch commit has the lane's net diff: compare `git diff --stat <commit>^ <commit>` with `git diff --stat <default>...<branch>`, then compare the diffs.
- **Superseded:** the default branch reached the same end state by another route. Prove it on the changed lines, for example a pin that already matches or a dependency that is already gone. A matching subject is not proof.
- **Unique:** commits the default branch lacks and does not supersede. Use a branch's newest local or remote tip. Merge both copies if they diverged.
- **Orphaned:** a process whose parent is init or launchd, whose owning session is gone, or whose inputs stopped changing long ago. A process with a live owning session is **Live**.
- **Cache:** regenerable output that a current build or the default branch's scripts still use.
- **Scratch:** anything else under `.work/`. `.work/` is disposable by contract, but scratch that cannot be regenerated is marked as such.

## Merge unique work

- Run `git merge --no-edit <branch>`, which fast-forwards when it can. Never squash or rebase: that leaves the tip outside the default branch and the pull request open. Merging a pull request's head and pushing marks it merged. Fetch a pull request from a fork with `git fetch <remote> pull/<n>/head`.
- Merge bases before stacked branches, then the oldest work first. Partial work merges too. Gate unsafe work the way the repository already gates unfinished work; do not invent a flag system.
- Commit uncommitted source changes in a `.work/wt/` lane on its branch, then merge it. Leave uncommitted changes in the primary checkout and in worktrees you cannot attribute, and put them on the withheld list.
- Resolve conflicts so both sides' intent survives. Read both versions and the commits that produced them; never pick one side wholesale.
- After each merge, run the narrowest checks that cover the changed files. Fix failures in a separate commit. If a branch needs a decision only the owner can make, abort or revert the merge, push the branch as it is, and withhold it with the reason.
- Merge commit subjects follow the repository's convention, for example `chore(merge): integrate <branch>`.

## Push

Push the default branch. If a ruleset rejects it, push the result to `converge/<date>`, open no pull request, and report the rejection. Push every branch left unmerged, ahead or without an upstream with `git push -u`. If a pre-push hook needs a terminal, do not bypass it; give the owner the exact command.

## Retire held work

1. Retire each **Held** lane with `worktree-retire <path> --into <default> --dry-run`, then without `--dry-run`. Pass `--discard-ignored` only when the listed ignored files are scratch. If the tool refuses a lane proven Held or Superseded, withhold it with the tool's reason. Never use `git worktree remove --force` or `rm` on a registered worktree.
2. Run `git-branch-consolidation --delete <remote> <default>` after previewing without `--delete`. Delete a squash-merged or patch-equivalent branch it keeps with `git branch -D`. Record every deleted tip SHA so it can be restored from the reflog.
3. Remove the durable-doc lines that name retired items, commit with a Conventional Commit, and push. A stale "keep this" line blocks the next session.

## Withhold and confirm once

Put everything not merged or retired in one table: the item (path, branch, stash or PID), its class, its size or commit count, the evidence, and a recommendation of **delete** or **keep** with the reason. Recommend **keep** for **Live** items and for a **Cache** a build still reads. Recommend **delete** for **Superseded** and **Orphaned** items, and for scratch that can be regenerated or that nothing depends on. Mark anything that cannot be regenerated. Report each stash with its base branch and a one-line diff summary. Never print anything that may hold credentials.

Ask once, with the whole table, not item by item. Then delete exactly the confirmed items. Stop a process with `kill`, and use `kill -9` only if it survives. Delete scratch by exact path and never sweep `.work/` recursively. Recreate `.work/tmp` if you removed it.

## Verify and report

**The test:** a fresh fetch of the default branch contains the work of every branch, pull request and lane except the ones the owner chose to keep, which are on the remote. `git worktree list` shows only the primary checkout, `.work/wt/` is empty, no inventoried process still runs, and `git status` is clean.

**Report:**

- the branches and pull requests merged, and the new head of the default branch;
- items retired without asking, each with its class, evidence and the deleted tip SHA;
- the withheld table, the owner's answer, what was then deleted, and `.work/` size before and after;
- everything kept, each with its reason; the checks run; and any push the owner must make.
