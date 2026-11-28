---
name: converge
description: "Use for /converge: reduce a repository to its default branch. Retire every lane, branch, process and scratch path the default branch already holds, review and trial-merge each branch, pull request and lane with unique work, then present one table of merge, keep and delete recommendations and act only on what the owner confirms. Skip PR-only CI repair (use green), campaign pause (use campaign-winddown), and disk-pressure sweeps (use cleanup)."
disable-model-invocation: true
metadata:
  opencode/autoinvoke: "false"
---

# Converge

Bring a repository down to one checkout on its default branch. Work the branch already holds is retired without asking. Unique work is reviewed and trial-merged, never merged blindly. Everything else, including every proposed merge, goes in one table that the owner confirms once.

`/converge` authorizes retiring lanes and deleting local branches whose work the default branch holds, trial merges in a scratch worktree, pushing unmerged branches, and editing durable docs that tell agents to keep retired items. The owner's confirmation is needed for merging into the default branch, stopping processes, deleting scratch or data, and dropping unmerged branches. Never force push, rewrite history, delete remote branches or drop stashes. Work without stopping until the confirmation; it is the only question.

## Target

Read the default branch with `gh repo view --json defaultBranchRef --jq .defaultBranchRef.name`. Without `gh` or a GitHub remote, use `git symbolic-ref --short refs/remotes/origin/HEAD`. Never assume `main` or `master`. Run `git fetch --prune <remote>` and fast-forward the primary checkout. If it diverged, merge the remote in; never reset. Leave a dirty primary checkout alone and put its changes in the table.

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
- **Unique:** commits or uncommitted changes the default branch lacks and does not supersede. Use a branch's newest local or remote tip.
- **Orphaned:** a process whose parent is init or launchd, whose owning session is gone, or whose inputs stopped changing long ago. A process with a live owning session is **Live**.
- **Cache:** regenerable output that a current build or the default branch's scripts still use.
- **Scratch:** anything else under `.work/`. Mark scratch that cannot be regenerated.

## Retire held work

1. Retire each **Held** lane with `worktree-retire <path> --into <default> --dry-run`, then without `--dry-run`. Pass `--discard-ignored` only when the listed ignored files are scratch. If the tool refuses a lane, put it in the table with the tool's reason. Never use `git worktree remove --force` or `rm` on a registered worktree.
2. Preview `git-branch-consolidation <remote> <default>`, then run it with `--delete`. Delete a squash-merged or patch-equivalent branch it keeps with `git branch -D`. Record every deleted tip SHA so it can be restored from the reflog.
3. Remove the durable-doc lines that name retired items, commit with a Conventional Commit, and push. A stale "keep this" line blocks the next session.

## Review unique work

Review each **Unique** branch, pull request and lane before recommending anything. Read its whole diff against the current default branch, the commits' reasons, and the roadmap entry or ticket it serves. Recommend:

- **merge:** still wanted, consistent with current code, docs and invariants, and complete or gated the way the repository already gates unfinished work;
- **keep:** wanted but unfinished, unsafe, or waiting on an owner decision; say what it waits on;
- **drop:** obsolete because the code it touches was removed or redesigned, its approach contradicts the current direction, or it is a failed experiment.

Trial-merge each **merge** candidate in `.work/wt/converge` with `git merge --no-edit`, bases before stacked branches and then oldest first. Never squash or rebase: that leaves the tip outside the default branch and the pull request open. Resolve conflicts so both sides' intent survives; never pick one side wholesale. Run the narrowest checks covering the changed files. A candidate whose trial fails, or whose conflicts need an owner decision, becomes **keep** with the failure. Push every unmerged branch that is ahead of its upstream or lacks one, with `git push -u` and never `--force`, so that nothing exists only locally.

## Confirm once

Put everything not retired in one table: the item (branch, pull request, path, stash or PID), its class, its size or commit count, the evidence, and a recommendation of **merge**, **keep**, **drop** or **delete**, with the reason. A merge row names the checks its trial passed. Recommend **keep** for **Live** items and for a **Cache** a build still reads, and **delete** for **Superseded** and **Orphaned** items and for scratch nothing depends on. Report each stash with its base branch and a one-line diff summary. Never print anything that may hold credentials.

Ask once, with the whole table, not item by item. Then act on exactly the confirmed rows:

- Land confirmed merges on the default branch in trial order, rerun the checks on the result, and push. If a ruleset rejects the push, push to `converge/<date>` and report the rejection. If a pre-push hook needs a terminal, give the owner the exact command.
- Drop branches with `git branch -D` and record their tip SHAs.
- Stop processes with `kill`, using `kill -9` only if one survives. Delete scratch by its exact path; never sweep `.work/` recursively. Recreate `.work/tmp` if it was removed.
- Retire `.work/wt/converge` and any lanes that are now merged.

## Verify and report

**The test:** the default branch holds every confirmed merge, every kept branch is on the remote, nothing was merged or deleted without confirmation, `git worktree list` shows only the primary checkout, no inventoried process still runs, and `git status` is clean.

**Report:**

- items retired without asking, each with its class, evidence and deleted tip SHA;
- the table and the owner's answer;
- what was merged, with the new default-branch head and the checks run;
- what was dropped or deleted, and `.work/` size before and after;
- everything kept, each with its reason, and any push the owner must make.
