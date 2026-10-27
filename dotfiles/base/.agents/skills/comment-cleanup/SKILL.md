---
name: comment-cleanup
description: "Apply when auditing comments, or about to write one that explains a why, constraint, or workaround: delete it and fix the code it excuses. Skip strings, fixtures, and out-of-scope comments."
---

# Comment Cleanup

A comment is prose nothing enforces. It goes stale, and agents copy the nearest one, so a single workaround note breeds more hacks. Delete the comment and move what it said into something that fails when it is wrong: a name, a type, a test, a lint rule, or the commit body.

Scope is the caller's files or diff; otherwise the current change. Read each comment against the code before judging it, including line comments, block comments, and docstrings. Leave user-facing strings and fixture content alone.

## What survives

Only what the comment rule in the global `AGENTS.md` allows. A surprise in our own code is never on the list. When unsure, the comment goes. A keep needs proof it is true today on a live path and that the code cannot say it.

## Each comment

- **Narration, banners, changelogs, `TODO` and `FIXME`, commented-out code:** delete. Version control is the archive, and a deferred task becomes a `todo` ticket, not a comment.
- **Pointers** to docs, plans, milestones, phases, or acceptance criteria: delete. Do not rewrite them into prose; the rationale goes through the next bullet. Accurate citations of external standards such as RFCs stay when they explain protocol behavior.
- **Issue and PR links** stay only beside a comment that already states the constraint, so it reads without the link. A bare "see #123" for our own code's why is deleted and its cause fixed.
- **A why, a constraint, or an excuse for a workaround in our own code:** the comment reports a defect. First check the claim against the code and callers. Then remove the cause: rename, extract, narrow the type, split the state, delete the dead path, use the real API. A constraint that cannot be removed gets the cheapest test or check that fails when it is violated, with an error that names the fix. Then delete the comment. A claim you cannot confirm is deleted, not polished into a shorter alibi.
- **Rationale no code shape can hold,** such as a rejected alternative, goes in the commit body, or once in the doc that owns the topic. Never back into the source.
- **Lint and type suppressions:** look up the rule. If it protects correctness or safety, remove the suppression and fix the code. Keep it only when the rule is wrong for that line, and say why in one line.

## Limits

Without permission to edit code (`review`, `ultrareview`, `docs-refresh`), still delete comments that need no code change, and report the rest as findings naming the symbol, the excuse, and the fix, with the comment as evidence, `comment-cleanup` as `Fix with`, and a priority from the workaround's impact. If a fix is out of scope, delete the comment anyway and report the symbol, so the hack is flagged once, to the owner, instead of in the tree. Do not widen the scope to fix instances outside it.

## Verify

Search the scope for comments and for documentation pointers before and after. With `mdtool` installed use `mdtool pointers`; otherwise `rg -n 'README|AGENTS|docs/|\.md|Phase|M[0-9]+'` over source comments, inspecting each match. The diff holds comment deletions and the named root-cause fixes only, with no fixture or executable strings changed.

**The test:** a reader who deleted every remaining comment would lose only an external quirk or a public contract, and every deleted excuse is gone from the code or reported open.

**Report:** comments deleted by count; fixes made and what each replaced; constraints now enforced by a test or check; hacks and constraints left open, with symbols; keeps with the reason each stays.
