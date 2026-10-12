# Working Contract

## Before editing

- Read the relevant code, callers, tests, and local instructions. Follow existing conventions.
- Resolve ordinary ambiguity with the smallest reversible assumption. Ask only when a choice changes the contract, the user's intent, or carries real risk.

## Code

- Name things for the domain, one name per concept. Mark legacy paths as legacy.
- Prefer precise types and narrow interfaces that make invalid states hard to represent. Don't loosen a contract or hide a fallback to make a patch fit.
- Comment the why, constraints, and non-obvious behavior above the definition. Keep existing comments that do this.
- Keep changes focused. Temporary workarounds must say why they exist and what removes them.
- Dependencies are your call. Vet maintenance, transitive weight, license, and whether the standard library or a few lines would do, and say why in your reply. A dependency must stay within the project's performance gates (build time, binary size, startup, runtime); measure when it could move one. If the repo defines no gates, state the build-time and binary-size impact. Remove ones you stop using.
- Keep bookkeeping to the minimum. No provenance, checksums, hashes, manifests, registers, logs, backups, or state files unless a reader or a concrete failure needs them. Check the thing itself (run it, compare it) instead of recording where it came from.
- No speculative abstractions, config knobs, or backward-compat shims unless asked. Delete dead code instead of deprecating it.
- Fail loudly. Don't swallow errors or add silent defaults.

## Tests and verification

- Test observable behavior and invariants, not trivia. Write tests first when behavior is clear.
- Bug fixes: reproduce with a minimal failing test, then fix the root cause. Keep the test.
- Never weaken or delete a test to make it pass unless the test is wrong, and say so.
- Verify the changed behavior with the narrowest hard check (compiler, type checker, focused test). Reuse existing build artifacts.
- A slow check is a defect in the loop, not a cost to accept. Find the narrowest command that covers the change (a test by name, one crate, one file) and iterate on it. When no fast check exists, say so and make one before relying on the slow one.
- Do not expand to workspace-wide builds/tests or full CI by default. Widen only for a specific uncovered integration risk or an explicit request for the wider run; state that reason first.
- Treat generic verification checklists as suggestions: run targeted repository equivalents, and report expensive verification before starting it.

## Skills

- A skill applies to the scope named. Audit or sweep the whole repo only when asked.
- Skills marked explicit-only are absent from the skill list. To use one, read `~/.agents/skills/<name>/SKILL.md`.

## Contract changes

Always surface changes to APIs, types, schemas, permissions, invariants, or transaction boundaries to the user. Update code, tests, and docs together.

## Replies

Keep final replies short: what changed and anything I need to decide. Say what you verified and what you did not.

## Workflow Rules

- Do not run formatters. It's a waste of tokens and unnecessary churn.
- Never push. Commit only when asked; a campaign plan counts as asking.
- Reserve release builds for final verification, or when performance is the primary concern.

## Environment

macOS and Linux. Use `rg`, `fd`, and `jaq` for search and JSON. Rust builds go through the `kache` rustc wrapper, and Linux musl targets link with `mold`.

## Keep code comments self-contained

- Never use code comments or docstrings to point to planning documentation. Do not cite document names, paths, links, sections, numbered clauses, milestones (such as `M1`), phases, roadmap items, issues, PRs, or acceptance-criterion labels.
- Comments must remain useful if every planning and documentation file is renamed or deleted. State the local reason, invariant, constraint, or behavior directly in domain terms.
