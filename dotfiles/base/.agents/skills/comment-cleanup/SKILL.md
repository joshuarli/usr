---
name: comment-cleanup
description: "Use for /comment-cleanup: remove redundant comments and enforce the constraints behind useful warnings before deleting them. Skip strings, fixtures, and out-of-scope comments."
disable-model-invocation: true
metadata:
  opencode/autoinvoke: "false"
---

# Comment Cleanup

A comment is prose nothing enforces. Remove narration; turn a useful constraint into code or a check that rejects its violation. Delete its warning only after that protection is proven or the constraint is proven obsolete. Irreducible design rationale belongs in the commit body or the doc that owns the topic.

Scope is the caller's files or diff; otherwise the current change. Read each comment against the code before judging it, including line comments, block comments, and docstrings. Leave user-facing strings and fixture content alone.

## What survives

Permanent keeps follow the comment rule in the global `AGENTS.md`. Verify them against live code. Preserve an existing warning about an unresolved constraint until its replacement is proven; uncertainty is not evidence that deleting it is safe. Report that temporary keep and what would permit removal.

## Each comment

Check for an unresolved constraint before applying any deletion category below.

- **Narration, banners, changelogs, `TODO` and `FIXME`, commented-out code:** delete when they carry no unresolved constraint. Version control is the archive, and a deferred task becomes a `todo` ticket when ticket edits are in scope. Judge the content, not the marker.
- **Pointers** to docs, plans, milestones, phases, or acceptance criteria: delete. Do not rewrite them into prose; the rationale goes through the next bullet. Accurate citations of external standards such as RFCs stay when they explain protocol behavior.
- **Issue and PR links** stay only beside a comment that already states the constraint, so it reads without the link. A bare "see #123" for our own code's why is deleted and its cause fixed.
- **A why, a constraint, or an excuse for a workaround in our own code:** check the claim against the code, callers, and relevant history. Remove the cause: rename, extract, narrow the type, split the state, delete the dead path, use the real API. A constraint that remains needs the cheapest check that rejects its violation, with an error naming the fix. Prove the protection before deleting its warning, using [verifier assessment](../do/references/verification.md) and historical replay for recurring defects. A ticket alone is not a replacement. Preserve a warning whose relevance or enforcement remains unresolved.
- **Rationale no code shape can hold,** such as a rejected alternative, goes in the commit body, or once in the doc that owns the topic. Never back into the source.
- **Lint and type suppressions:** look up the rule. If it protects correctness or safety, remove the suppression and fix the code. Keep it only when the rule is wrong for that line, and say why in one line.

## Limits

Respect the caller's edit boundary. `review` and other read-only requests change nothing, including comments and tickets. When comment edits are allowed but behavior changes are not (`ultrareview`, `docs-refresh`), remove narration and proven stale claims; preserve unresolved constraint warnings. Report each remaining finding with its symbol, constraint, proposed fix, comment evidence, `comment-cleanup` as `Fix with`, and a priority from its impact. File tickets only when the caller permits them. If enforcement is out of scope or unavailable, leave the warning and report that gap. Do not widen scope to fix other instances.

## Verify

Search the scope for comments and for documentation pointers before and after. With `mdtool` installed use `mdtool pointers`; otherwise `rg -n 'README|AGENTS|docs/|\.md|Phase|M[0-9]+'` over source comments, inspecting each match. The diff holds comment deletions and the named root-cause fixes only, with no fixture or executable strings changed.

**The test:** every removed constraint is proven obsolete or protected by a demonstrated guard; unresolved warnings remain visible, permitted comments retain their meaning, and the diff respects the caller's edit boundary.

**Report:** comments deleted by count; fixes and the evidence that permits removal; constraints now enforced; unresolved warnings kept, with symbols and the condition for removal; permanent keeps and their reasons.
