---
name: comment-cleanup
description: Review code comments and docstrings for stale references while preserving useful links to current documentation and technical rationale.
---

# Comment Cleanup

Use this skill when asked to audit or clean comments and docstrings in source code.

Inspect the requested scope before editing. Follow repository instructions and use local code behavior to understand each comment. Include line comments, block comments, and docstrings that contain potentially stale pointers; leave user-facing strings and test fixture content alone unless the user explicitly includes them.

Search for document names and paths, links, section or clause numbers, milestone labels such as `M1`, phase names, roadmap entries, issues, PRs, and acceptance-criterion IDs. Look for varied forms such as “plan section 1a,” “section 1a,” “milestone 1,” and “M1”; do not rely on one exact filename or spelling. Classify each match by whether it points to durable technical documentation or to planning/project tracking.

Preserve precise references to relevant, durable technical documentation, including maintained README files and guides that explain source-of-truth behavior, architecture, APIs, development, or operations. README files are often durable source-of-truth documents: never remove a README pointer solely because it names a document or path. Verify local targets and named sections where practical.

Preserve accurate citations to external technical standards, such as RFCs and web-platform specifications, when they explain protocol or parser behavior. Their absence from the repository does not make them planning pointers; remove or revise them only when they are inaccurate, obsolete, misleading, or irrelevant to the code.

Do not retain pointers to planning or project-tracking material in code comments, even when the referenced file or artifact still exists. This includes plans, roadmaps, milestones, phases used as project stages, acceptance criteria, issues, and pull requests. Remove the pointer; if the comment also contains a lasting technical invariant or rationale, rewrite that explanation so it stands on its own. Runtime/domain phases are not planning references and should be left alone.

For each finding:

- Remove planning and project-tracking pointers regardless of whether they are still live. For other documentation pointers, remove or update them only when they are broken, obsolete, misleading, or no longer relevant to the code.
- If a planning pointer accompanies a useful invariant, constraint, rationale, or non-obvious behavior, keep the explanation and remove only the planning reference. Preserve valid durable documentation pointers alongside it.
- Preserve accurate comments that already explain the code without relying on documentation.
- Do not move code, change behavior, or rewrite unrelated prose as part of this cleanup.

Search the requested source scope for documentation and planning references before and after editing. Review the diff to ensure each changed comment is still clear and no executable strings or fixture text were changed accidentally. Report the files reviewed, changes made, durable references preserved, and any ambiguous references left untouched. Do not run tests unless asked; a focused search and diff review are sufficient for this editorial task.
