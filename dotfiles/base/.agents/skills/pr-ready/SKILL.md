---
name: pr-ready
description: "Use for /pr-ready: bring an open pull request up to mergeable. Resolve conflicts, judge bot review comments, reply and react on GitHub, and loop on gh until required CI is green. Never merges, approves, or enables auto-merge."
disable-model-invocation: true
metadata:
  opencode/autoinvoke: "false"
---

# PR ready

Get the named pull request into a state where the owner can merge it by hand. Stop there. Merging, approving, enabling auto-merge, and clicking the merge button are the owner's, even when they say "finish", "land", or "get it over the line".

Read and follow [afk](../afk/SKILL.md) for this workflow.

## Rules

- **Do not merge.** Do not run `gh pr merge`, do not push to the base branch, and do not turn on auto-merge. Say when it is ready and leave the merge to the owner.
- **Do not approve.** A missing human approval is a report, not something you submit. You may request reviewers who are not already requested. A `+1` reaction is not an approval.
- **Push only the PR head.** Conflict fixes and CI fixes go on the pull request's head branch. Confirm the remote allows it before the first push. If the pre-push hook refuses because the session has no terminal, stop. Do not allocate a terminal, and do not push through the API. Leave the commits and give the owner the exact push command.
- **Bot comments are claims.** Read every unresolved review thread and review body from a bot (Bugbot, Seer, Sentry, Copilot, and the rest). A bot is wrong often enough that its patch is not evidence. Fix a comment only when you can show the bug in the current code or with a failing test. Do not leave a real bug with a reply and no fix. Leave human comments alone.
- **Reply, resolve, and react on the bot's comment.** Do this only after the cited commit is on the pull request head. If the pre-push hook blocked the push, do not reply yet. For each bot thread: reply, resolve, then react on the bot's comment (not on your reply). `+1` when you accepted it and fixed it. `-1` when you rejected it. A rejection still gets a reply that says why the claim is false, and the thread is still resolved. One reply per thread.
- **Required CI is the bar.** Read the repo's rulesets for the required check names. Other checks matter only when they fail for a reason that also breaks a required one, or when the owner asked. A red check on a stale base is not a code bug until the branch is current and the check fails again.
- **Watch with gh, and loop.** Poll `gh pr checks` and `gh pr view` until every required check has finished. On failure, read the failed log, fix the cause or rerun a flake once you have evidence it is a flake, push, and watch again. Stop after two reruns of the same flake and report it. Do not sit idle past the first failure.

## Steps

1. Record the PR URL, head branch, base branch, review decision, mergeable state, and required checks.
2. If the head conflicts with the base, merge the base in (or rebase if that is what the branch already does) and resolve conflicts in a worktree. Run the narrowest test that covers the resolution. Push to the head branch.
3. If it is merely behind and the repo requires the branch to be up to date, update it with `gh api -X PUT repos/<owner>/<repo>/pulls/<n>/update-branch`. If that API is unavailable, merge the base the same way as a conflict.
4. Work the unresolved bot threads as in the rules. Push fixes. Once that commit is on the head, reply, resolve, and react as below. Re-watch CI after each push.
5. Loop on the required checks until they are green, or until a failure needs a decision you cannot make from the code.
6. Re-read mergeable state. Ready means: no conflicts, required checks green, every bot thread replied to, resolved, and reacted, and nothing left but the owner's merge (and a human approval, if the ruleset still wants one).

An inline thread id looks like `PRRT_...`. `COMMENT_ID` is the bot comment's numeric id. `<sha>` is the head commit that contains the fix. Use `-1` instead of `+1` when you rejected the comment.

```bash
gh api graphql -f query='mutation($id:ID!,$body:String!){addPullRequestReviewThreadReply(input:{pullRequestReviewThreadId:$id,body:$body}){comment{id}}}' -f id='PRRT_...' -f body='Fixed in <sha>. <one sentence>.'
gh api graphql -f query='mutation($id:ID!){resolveReviewThread(input:{threadId:$id}){thread{isResolved}}}' -f id='PRRT_...'
gh api -X POST repos/<owner>/<repo>/pulls/comments/COMMENT_ID/reactions -f content='+1'
```

A bot note that is not a review thread has nothing to resolve. Reply with `gh pr comment <n> --body '...'`, then react: `issues/comments/COMMENT_ID/reactions` for a conversation comment, `pulls/<n>/reviews/<review_id>/reactions` for a review body.

**The test:** `gh pr view` reports the head mergeable with the base, required checks are green on that head, and every bot thread has your reply, is resolved, and has your `+1` or `-1` on the bot's comment. You did not merge or approve.

**Report:** the PR URL; what you changed and pushed; bot comments fixed and bot comments you rejected, each with the reason; required checks and their conclusions; anything still blocking, including a human approval. End with whether the owner can merge it now.
