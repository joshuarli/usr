Prefix: USR
Next: 69







### USR-68 · P3 · Retire worktrees without failing branch cleanup against an older main

- **Area:** Delegation
- **Where:** dotfiles/base/.local/bin/worktree-retire:65-80; macOS source-link install e5018dceb8c7
- **Problem:** With a clean child whose HEAD is an ancestor of an explicit integration SHA but ahead of canonical main, worktree-retire CHILD --into INTEGRATION_SHA removes CHILD and then exits 1 because git branch -d runs from older main. Reproduced retiring Stats platform-review at 9fdd75d8338 while canonical master remained a480b731f09. The checkout is already gone despite the failure result. --into HEAD also resolves against canonical main rather than the invoking integration worktree, producing a misleading not-integrated refusal.
- **Recommendation:** Resolve caller-relative integration revisions before changing context. Keep branch deletion safe against the verified integration target, or retain the branch without treating successful worktree retirement as failure. Add a two-worktree regression with an integration branch ahead of canonical main.
- **Fix with:** root-cause
- **Effort:** S

