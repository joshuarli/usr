---
name: commit
description: Create a well-formed git commit from staged/unstaged changes
---

2 bash calls total.

**Call 1** — everything at once:
```
git status --short && git log --oneline -5 && git diff HEAD
```
If the diff is huge, replace `git diff HEAD` with `git diff --stat HEAD`.

**Call 2** — stage and commit:
```
git add <files> && git commit -m "subject"
```
Or for a body: `git commit -F - <<'EOF'\nsubject\n\nbody\nEOF`

Rules: imperative mood, ≤72 chars, no trailing period. Stage only files belonging to this change. Never `--no-verify`, `--amend`, `git add -A`, or push.
