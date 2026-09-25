---
name: comment-cleanup
description: Review code comments and docstrings for stale references while preserving useful links to current documentation and technical rationale.
---

# Comment Cleanup

Use this skill when asked to audit or clean comments and docstrings in source code.

Inspect the requested scope before editing. Follow repository instructions and use local code behavior to understand each comment. Include line comments, block comments, and docstrings that contain potentially stale pointers; leave user-facing strings and test fixture content alone unless the user explicitly includes them.

Search for document names and paths, links, section or clause numbers, milestone labels such as `M1`, phase names, roadmap entries, issues, PRs, and acceptance-criterion IDs. Look for varied forms such as “plan section 1a,” “section 1a,” “milestone 1,” and “M1”; do not rely on one exact filename or spelling. Treat matches as candidates to review, not automatic deletions: a precise reference can be useful when it points to current, relevant documentation.

README files are often durable source-of-truth documents. Preserve a README reference by default when the target exists and remains relevant to the comment. Never remove a README pointer solely because it names a document or path. Apply the same check to other documentation links: verify local targets and named sections where practical; if an external target cannot be checked, leave the reference and report that uncertainty rather than assuming it is stale.

For each finding:

- Remove or update a pointer only when there is evidence that it is broken, obsolete, misleading, or no longer relevant to the code. Project-tracking references can become stale, but do not remove them based on form alone.
- If a stale pointer accompanies a useful invariant, constraint, rationale, or non-obvious behavior, keep the explanation and remove or correct only the stale part. Preserve valid documentation pointers alongside it.
- Preserve accurate comments that already explain the code without relying on documentation.
- Do not move code, change behavior, or rewrite unrelated prose as part of this cleanup.

Search the requested source scope for documentation and planning references before and after editing. Review the diff to ensure each changed comment is still clear and no executable strings or fixture text were changed accidentally. Report the files reviewed, changes made, valid references preserved, and any ambiguous references left untouched. Do not run tests unless asked; a focused search and diff review are sufficient for this editorial task.
