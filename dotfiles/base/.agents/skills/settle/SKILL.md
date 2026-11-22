---
name: settle
description: "Use for /settle: make the GitHub default branch the cutting edge by merging every open and partial branch, pull request and lane into it, pushing every branch that remains, then pruning merged local branches with git-branch-consolidation --delete. Skip PR-only CI repair (use green), campaign shutdown, and disk cleanup."
disable-model-invocation: true
metadata:
  opencode/autoinvoke: "false"
---

# Settle

Make the default branch the one place where all work lives. Merge every branch that carries work the default branch lacks, including incomplete work. Push the result, push whatever could not merge, and prune the local branches that are now merged. `/settle` itself authorizes these merges, the pushes to the default branch and other branches, and the local branch deletions. It does not authorize force pushes, history rewrites, deleting remote branches, or dropping stashes.

Use [sleep](../sleep/SKILL.md) for this workflow.

## Find the target

- **Default branch:** read it from GitHub with `gh repo view --json defaultBranchRef --jq .defaultBranchRef.name`. Without `gh` or a GitHub remote, use `git symbolic-ref --short refs/remotes/origin/HEAD`. Never assume `main` or `master`.
- **Remote:** use the remote that GitHub's default branch lives on, normally `origin`. Run `git fetch --prune <remote>` before anything else.
- **Start current:** check out the default branch in the primary checkout and fast-forward it to the remote. If it has diverged, merge the remote into it; do not reset it. If the primary checkout has uncommitted changes, do the merges in a scratch worktree at `.work/wt/settle` instead, and leave the dirty files untouched.

State the default branch, the remote and its head before the first merge.

## Inventory

List every source of work the default branch might lack:

- local branches, with `git log --oneline <default>..<branch>`;
- remote branches that have no local copy;
- open pull requests (`gh pr list --state open --json number,headRefName,isDraft,isCrossRepository`), drafts included;
- linked worktrees and their status (`git worktree list --porcelain`, `git -C <path> status --short`);
- stashes, and submodule commits that are not on a submodule remote.

For each branch, run `git cherry <default> <branch>`. A branch whose commits are all patch-equivalent (`-` lines) is already integrated and needs no merge. Use a branch's newest local or remote tip, whichever contains the other. If the local and remote copies have diverged, merge both.

## Merge

- **Merge, do not squash or rebase.** Use `git merge --no-edit <branch>`, which fast-forwards when it can. A squash or rebase leaves the branch tip outside the default branch, so `git-branch-consolidation` would keep the branch and GitHub would leave its pull request open. Merging a pull request's head commit into the default branch and pushing marks the pull request merged.
- **Order:** merge branches whose commits other branches build on first, then the oldest work first. Merge a stacked branch after its base.
- **Partial work counts.** An incomplete feature is merged, not left on its branch. If the feature is unsafe to expose, gate it the way the repository already gates unfinished work. Do not invent a flag system for it.
- **Uncommitted work in lanes.** A linked worktree under `.work/wt/` with uncommitted source changes is an unfinished lane. Commit those changes on its branch with a Conventional Commit, then merge it. Leave uncommitted changes in the primary checkout and in worktrees you cannot attribute alone, and report them.
- **Conflicts:** resolve each conflict so that both sides' intent survives. Read both versions and the commits that produced them. Do not resolve by picking one side wholesale.
- **Keep the default branch working.** After each merge, run the narrowest checks that cover the files the merge changed, per the repository's development docs. Fix a failure on the default branch in a separate commit. If a branch cannot be made to pass without a decision only the owner can make, abort the merge (`git merge --abort`, or revert it if it is already committed), push that branch as it is, and report why it stayed out.
- **Merge commit subjects** follow the repository's commit convention, for example `chore(merge): integrate <branch>`.
- **Forks:** a pull request from a fork is merged the same way, by fetching its head (`gh pr checkout <n>` in a scratch worktree, or `git fetch <remote> pull/<n>/head`).

## Push

1. Push the default branch: `git push <remote> <default>`. If a ruleset or branch protection rejects the push, keep the local merges, push the integrated result to a `settle/<date>` branch, and open no pull request. Report the exact rejection.
2. Push every local branch that is left unmerged, ahead of its upstream, or without an upstream: `git push -u <remote> <branch>`. Never `--force`. A branch that diverged from its remote copy is merged with that copy first, as above.
3. If a pre-push hook refuses because the session has no terminal, do not bypass it. Give the owner the fully resolved push command and continue with any other independent work.

## Prune

1. Retire lane worktrees whose branch is now merged and whose tree is clean, using `worktree-retire <lane> --into <default> --dry-run` and then without `--dry-run`. `git-branch-consolidation` skips any branch still checked out in a worktree. Never `--force`, and never delete a worktree recursively.
2. From the primary checkout, preview with `git-branch-consolidation <remote> <default>`. Then run `git-branch-consolidation --delete <remote> <default>`. It deletes only local branches merged into `<remote>/<default>` and never touches remote branches.
3. Leave remote branches in place unless the owner asks for them to go.

## What git does not carry

Stashes, untracked files, and ignored local data do not reach the remote. Report each stash with its base branch and a one-line summary of its diff; do not apply, drop, or convert it. Report untracked source files and local data that the project needs, with exact paths and without printing anything that may hold credentials.

## Verify and report

Fetch again. Then confirm that:

- `git log <remote>/<default>..<branch>` is empty for every merged branch, local and remote;
- every remaining local branch exists on the remote at the same commit (`git branch -vv` shows no `ahead` and no missing upstream);
- each pull request you merged shows as merged (`gh pr view <n> --json state`);
- the checks run after the last merge passed on the pushed head.

**The test:** a fresh clone of the default branch contains all work that existed in any branch, pull request, or lane, except the items reported as left out, and every left-out branch is on the remote.

**Report:**

- the branches and pull requests merged, with the default branch's new head;
- the branches left unmerged, and why for each;
- the local branches deleted, and the worktrees retired;
- uncommitted changes, stashes, and local files that remain and that git does not carry;
- the checks run, and any push the owner must make by hand.
