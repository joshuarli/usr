---
name: pr-ready
description: "Bring an open pull request up to mergeable: resolve conflicts, judge bot review comments, and loop on gh until required CI is green. Use when finishing, landing, or unblocking a PR, or when CI, reviews, or conflicts are what stand in the way. Skip drafting a PR, reviewing code nobody asked to land, and any request to merge, approve, or enable auto-merge."
---

# PR ready

Get the named pull request into a state where the owner can merge it by hand. Stop there. Merging, approving, enabling auto-merge, and clicking the merge button are the owner's, even when they say "finish", "land", or "get it over the line".

## Rules

- **Do not merge.** Do not run `gh pr merge`, do not push to the base branch, and do not turn on auto-merge. Say when it is ready and leave the merge to the owner.
- **Do not approve.** A missing human approval is a report, not something you submit. You may request reviewers who are not already requested.
- **Push only the PR head.** Conflict fixes and CI fixes go on the pull request's head branch. Confirm the remote allows it before the first push. If the pre-push hook refuses because the session has no terminal, stop. Do not allocate a terminal, and do not push through the API. Leave the commits and give the owner the exact push command.
- **Bot comments are claims.** Read every unresolved review thread and review body from a bot (Bugbot, Seer, Sentry, Copilot, and the rest). A bot is wrong often enough that its patch is not evidence. Fix a comment only when you can show the bug in the current code or with a failing test. When it is a false positive, reply on that thread with the reason and resolve it. Do not leave a real bug with a reply and no fix.
- **Required CI is the bar.** Read the repo's rulesets for the required check names. Other checks matter only when they fail for a reason that also breaks a required one, or when the owner asked. A red check on a stale base is not a code bug until the branch is current and the check fails again.
- **Watch with gh, and loop.** Poll `gh pr checks` and `gh pr view` until every required check has finished. On failure, read the failed log, fix the cause or rerun a flake once you have evidence it is a flake, push, and watch again. Stop after two reruns of the same flake and report it. Do not sit idle past the first failure.

## Steps

1. Record the PR URL, head branch, base branch, review decision, mergeable state, and required checks.
2. If the head conflicts with the base, merge the base in (or rebase if that is what the branch already does) and resolve conflicts in a worktree. Run the narrowest test that covers the resolution. Push to the head branch.
3. If it is merely behind and the repo requires the branch to be up to date, update it with `gh api -X PUT repos/<owner>/<repo>/pulls/<n>/update-branch`. If that API is unavailable, merge the base the same way as a conflict.
4. Work the unresolved bot threads as in the rules. Push fixes. Re-watch CI after each push.
5. Loop on the required checks until they are green, or until a failure needs a decision you cannot make from the code.
6. Re-read mergeable state. Ready means: no conflicts, required checks green, bot threads resolved or answered, and nothing left but the owner's merge (and a human approval, if the ruleset still wants one).

**The test:** `gh pr view` reports the head mergeable with the base, required checks are green on that head, and every bot thread is resolved or has your reply. You did not merge or approve.

**Reply:** the PR URL; what you changed and pushed; bot comments fixed and bot comments you rejected, each with the reason; required checks and their conclusions; anything still blocking, including a human approval. End with whether the owner can merge it now.
