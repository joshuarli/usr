---
name: comment-cleanup
description: Review code comments and docstrings and remove pointers to documentation and planning material, keeping the technical rationale self-contained.
---

# Comment Cleanup

Use this skill when asked to audit or clean comments and docstrings in source code.

Inspect the requested scope before editing. Follow repository instructions and use local code behavior to understand each comment. Include line comments, block comments, and docstrings that contain potentially stale pointers; leave user-facing strings and test fixture content alone unless the user explicitly includes them.

A comment must stay useful if every documentation and planning file is renamed or deleted. Search for document names and paths, links, section or clause numbers, milestone labels such as `M1`, phase names, roadmap entries, issues, PRs, and acceptance-criterion IDs. Look for varied forms such as “plan section 1a,” “section 1a,” “milestone 1,” and “M1”; do not rely on one exact filename or spelling.

Remove every such pointer, even when its target still exists. That includes READMEs, guides, and design notes as well as plans, roadmaps, milestones, phases used as project stages, acceptance criteria, issues, and pull requests. If the comment also holds a lasting technical invariant, constraint, or rationale, rewrite that explanation so it stands on its own. Runtime and domain phases are not planning references and should be left alone.

Keep accurate citations to external technical standards, such as RFCs and web-platform specifications, when they explain protocol or parser behavior. Their absence from the repository does not make them pointers to project documentation; revise or remove them only when they are inaccurate, obsolete, misleading, or irrelevant to the code.

For each finding:

- Remove the pointer and keep any explanation it accompanied.
- Preserve accurate comments that already explain the code without relying on documentation.
- Do not move code, change behavior, or rewrite unrelated prose as part of this cleanup.

Search the requested source scope for documentation and planning references before and after editing. Review the diff to ensure each changed comment is still clear and no executable strings or fixture text were changed accidentally. Report the files reviewed, changes made, external citations preserved, and any ambiguous references left untouched. Do not run tests unless asked; a focused search and diff review are sufficient for this editorial task.
