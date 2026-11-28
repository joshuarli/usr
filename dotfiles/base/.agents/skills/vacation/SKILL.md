---
name: vacation
description: "Use for /vacation: leave a repository so that its .work/ can be deleted with nothing lost. Pause any running campaign, find what in .work/, lane checkouts, branches and stashes is unique, ship it to the default branch, pushed branches or a pushed archive branch, record the rebuild order in docs/roadmap.md Status, then delete .work/ after one owner confirmation. Skip pausing a campaign without freeing disk (use campaign-winddown) and disk-pressure sweeps (use cleanup)."
disable-model-invocation: true
metadata:
  opencode/autoinvoke: "false"
---

# Vacation

The owner is leaving the repository for a while and wants its disk back. When this skill finishes, deleting `.work/`, or the whole clone, loses nothing. Resuming needs only the remote and the external inputs that **Status** names.

`/vacation` authorizes these effects:

- running `campaign-winddown`;
- retiring lanes and deleting local branches whose work the default branch holds;
- pushing branches, including a new archive branch;
- committing and pushing **Status**.

Merging into the default branch, stopping processes, dropping unique work, and deleting `.work/` need the owner's one confirmation. Never force push, rewrite history, delete remote branches or drop stashes. Work without stopping until the confirmation; it is the only question.

## Pause

If a campaign is running, run [campaign-winddown](../campaign-winddown/SKILL.md) first. List the processes whose working directory or arguments are inside the repository, with each one's parent, start time, and the last write to any file it follows. A process whose parent is init or launchd, or whose inputs stopped changing long ago, is orphaned and goes in the table. A process with a live owning session blocks deletion: name it in the table and keep `.work/`.

## Classify `.work/`

Put each top-level `.work/` entry, and each large subtree, in one class and record its size:

- **Rebuildable:** a tracked target, script or pin recreates it. Name it: a setup target, a capture target, or a source pinned as `<name>@<rev>`. "Probably regenerable" is not a class.
- **Recorded:** its conclusions are already in tracked docs or receipts. A path cited in a committed run record is provenance, not a dependency. A consumer is a tracked script or target that reads the path; search for those with `rg`.
- **Recoverable:** its producer was retired but is still in git history. Name the commit and path to restore.
- **Unique:** none of the above. Find hand-written files by comparing each `.py`, `.sh`, `.md` or source file outside environments and caches with its tracked namesake (`git ls-files "*/<name>"`, `cmp`).

## Classify lanes, branches and stashes

- **Held:** the default branch has the work. Either the branch is an ancestor, `git cherry` shows only `-`, or `worktree-retire --dry-run --discard-ignored` accepts it. A squash merge that was edited later counts when, for each file, `git apply -R --check` accepts the lane's diff, or every line the lane added exists in the default branch's version. Check uncommitted changes the same way.
- **Unique:** commits or changes the default branch lacks. Read the whole diff, the commits' reasons, and the roadmap entry it serves, then recommend **merge** (wanted, consistent and complete), **keep** (wanted but unfinished; say what it waits on), or **drop** (obsolete or a failed experiment).

## Ship

1. Retire each **Held** lane and delete its branch under [`orchestrate`'s worktree lifecycle](../orchestrate/SKILL.md#worktree-lifecycle). If the tool refuses a lane you proved held, put it in the table with your evidence. Record every deleted tip SHA.
2. For each **merge** candidate, merge it with `git merge --no-edit` in a scratch worktree, never squashing or rebasing. Run the narrowest checks covering it. If that fails, recommend **keep**.
3. Push every local branch that is ahead of its upstream or lacks one, with `git push -u`.
4. Put unique small text on an orphan branch named `archive/<campaign or repo>-scratch`. That covers probes, reports, logs and other hand-written files. Build it with a temporary `GIT_INDEX_FILE`, `git hash-object -w`, `git update-index --cacheinfo`, `write-tree` and `commit-tree`, so the primary checkout is untouched. Paths mirror `.work/`. Add a README saying what the branch holds and where its conclusions live. Scan the files for credentials before hashing them, and leave out any file that may hold one. Push the branch.
5. Unique large data cannot go to the remote. Put it in the table with **keep** or **delete**, and with what deleting it costs.

## Record the resume path

Rewrite the roadmap's **Status** in place, or the **Status** of the repository's equivalent if it has no roadmap. State the date `.work/` was deleted. Give the rebuild order before the first gate, as exact commands. List each **Recoverable** item with its restore command, and the archive branch. Remove lines that name retired lanes, or that tell agents to keep them. Commit with a Conventional Commit and push.

## Confirm once

Ask once, with one table. Each row gives the item, its size, its class with the recipe or evidence, and a recommendation. The rows cover:

- every `.work/` entry;
- refused lanes;
- unique branches with their merge, keep or drop recommendation;
- orphaned processes;
- stashes, each with its base branch and a one-line diff summary.

Then act on exactly what the owner confirms:

- Land confirmed merges, rerun their checks and push.
- Stop orphaned processes with `kill`.
- Remove the remaining clean lane checkouts with `git worktree remove`, without `--force`. Discard a lane's uncommitted changes only after proving the default branch holds them.
- Delete `.work/` whole, then run `git worktree prune`.

## Verify and report

**The test:** `git worktree list` shows only the primary checkout and `.work/` is gone. `git branch -vv` shows no branch ahead of its upstream and none without one. `git status` is clean. **Status** on the remote says how to rebuild everything.

**Report:**

- what was shipped, and where;
- retired lanes and deleted branches, with their tip SHAs;
- the table and the owner's answer;
- disk free before and after;
- stashes left in place;
- every rebuild recipe that is listed but untested. Recipes are not run, so the first resume pays for any mistake in them.
