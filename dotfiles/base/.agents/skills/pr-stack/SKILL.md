---
name: pr-stack
description: "Use for /pr-stack: drive a PR or stack to merge-ready (check, threads, drive), or land a verified stack bottom-up (ship). Merging happens only on an explicit ask."
disable-model-invocation: true
metadata:
  opencode/autoinvoke: "false"
---

# PR Stack

Clear the lowest unmerged PR, and land only what someone other than the author verified. GitHub through `gh`. Declare one mode before any poll.

## Modes

- **check:** one status pass and a report. The default for a small or docs-only PR and for "is it green".
- **threads:** answer review comments and touch nothing else.
- **drive:** loop until merge-ready. The default for "babysit this" and "get it green". Read and follow [afk](../afk/SKILL.md) in this mode.
- **ship:** land a verified run. Only when the user asked to merge, land, or ship.

## Babysit rules (check, threads, drive)

- **Frontier first.** Only the lowest unmerged PR matters until it merges. Read and batch upstack threads, and never fix them while the frontier is red.
- **One babysitter per stack.** Check that nothing else is already on it.
- **Never change topology.** No base retarget, rebase, force-push, or stack-wide submit. Fix on the branch that owns the code. Report a conflict with the branch that needs the rebase and any trunk callers of code the stack moves.
- **Conflicts, then review threads, then CI.** Batch every known fix into one push, and push before replying so each reply cites the commit.
- **Ready is the forge's verdict, not a green list.** Read `gh pr view <n> --json state,mergeable,mergeStateStatus,reviewDecision,statusCheckRollup` and the unresolved threads.
- **Classify CI before any retry.** Flake or infrastructure earns one fresh run, and an identical second failure is real. A failure in code the diff never touched is a stale base: check `git merge-base --is-ancestor` and report it.
- **Triage bot comments skeptically.** Verify each claim against the code. Fix a real one with a failing test first, and dismiss noise with a concrete reason instead of churning code.
- **Approval is a wait, not a blocker.** Babysitting never authorizes merging.
- **Pushes:** invoking this skill authorizes pushing fixes to that PR's own branch. The harness still prompts for each push.

## Ship

Merging is outward-facing and hard to undo, so it needs an explicit ask in this session and a named list of PRs, bottom to top.

1. **Verify each PR independently.** One fresh `worker` per PR that did not write the code, exercising the real surface at base against head. It returns `PASS`, `PASS+NOTES`, or `FAIL` and posts it on the PR. Green CI is not a verdict.
2. **Land only the contiguous verified run from the bottom.** Stop at the first PR without a passing verdict, and report that ceiling.
3. **Check the verdict still describes the patch.** Compare `git patch-id --stable` of the base-to-head diff at verdict time with now, since a rebase or retarget can silently invalidate it. Re-verify on any difference beyond tests and docs.
4. **Prepare only the bottom PR.** Fetch trunk, rebase it onto the tip if needed, push, and retarget only that PR. Leave descendants alone.
5. **Land one at a time** with `gh pr merge <n> --squash`, adding `--auto` only when asked for merge-when-ready. Wait for `mergedAt`, then fetch trunk, confirm the merged SHA is present, and inspect the new bottom.
6. **Do not mutate the queue around the frontier.** Hard-fail on a PR closed without merging or a required check failing after arming.

**The test:** every merged PR had a passing verdict from an agent that did not write it, matching its landed patch, and nothing above the ceiling moved.

**Report:** the mode; PR state and blockers; for ship, each PR's verdict and who produced it, what landed, the ceiling, and what verifying the next gap needs.
