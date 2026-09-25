---
name: comment-cleanup
description: Review and clean code comments and docstrings that depend on planning or other documentation, while preserving useful technical rationale.
---

# Comment Cleanup

Use this skill when asked to audit or clean comments and docstrings in source code.

Inspect the requested scope before editing. Follow repository instructions and use local code behavior to understand each comment. Include line comments, block comments, and docstrings that contain stale document pointers; leave user-facing strings and test fixture content alone unless the user explicitly includes them.

Remove references to planning files and all other documentation, including document names or paths, links, section or clause numbers, milestone labels such as `M1`, phase names, roadmap entries, issues, PRs, and acceptance-criterion IDs. Look for varied forms such as “plan section 1a,” “section 1a,” “milestone 1,” and “M1”; do not rely on one exact filename or spelling.

For each finding:

- If it only points to a document or project-tracking artifact, delete the comment.
- If it explains a real invariant, constraint, rationale, or non-obvious behavior, rewrite it so that explanation stands on its own and names the relevant domain behavior directly.
- Preserve accurate comments that already explain the code without relying on documentation.
- Do not move code, change behavior, or rewrite unrelated prose as part of this cleanup.

Search the requested source scope for documentation and planning references before and after editing. Review the diff to ensure each changed comment is still clear and no executable strings or fixture text were changed accidentally. Report the files reviewed, changes made, and any ambiguous references left untouched. Do not run tests unless asked; a focused search and diff review are sufficient for this editorial task.
