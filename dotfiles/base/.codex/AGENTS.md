# Working Contract

## Before editing

- Read the relevant code, callers, tests, and local instructions. Follow existing conventions.
- Resolve ordinary ambiguity with the smallest reversible assumption. Ask only when a choice
  changes the contract, the user's intent, or carries real risk.

## Code

- Name things for the domain, one name per concept. Mark legacy paths as legacy.
- Prefer precise types and narrow interfaces that make invalid states hard to represent.
  Don't loosen a contract or hide a fallback to make a patch fit.
- Comment the why, constraints, and non-obvious behavior above the definition. Keep existing
  comments that do this. In docs, explain in domain terms and cite code in backticks.
- Keep changes focused. Add no dependency without asking. Temporary workarounds must say why
  they exist and what removes them.
- No speculative abstractions, config knobs, or backward-compat shims unless asked. Delete dead
  code instead of deprecating it.
- Fail loudly. Don't swallow errors or add silent defaults.

## Tests and verification

- Test observable behavior and invariants, not trivia. Write tests first when behavior is clear.
- Bug fixes: reproduce with a minimal failing test, then fix the root cause. Keep the test.
- Never weaken or delete a test to make it pass unless the test is wrong, and say so.
- Verify with the narrowest hard check (compiler, type checker, focused test), then widen as
  needed.

## Contract changes

Always surface changes to APIs, types, schemas, permissions, invariants, or transaction
boundaries to the user. Update code, tests, and docs together.

## Replies

Keep final replies short: what changed and anything I need to decide.

## Workflow Rules

- Do not run formatters. It's a waste of tokens and unnecessary churn.
- Do not git push.
- Reserve release builds for final verification, or when performance is the primary concern.

## Keep code comments self-contained

- Never use code comments or docstrings to point to planning documentation. Do not cite document names, paths, links, sections, numbered clauses, milestones (such as `M1`), phases, roadmap items, issues, PRs, or acceptance-criterion labels.
- Comments must remain useful if every planning and documentation file is renamed or deleted. State the local reason, invariant, constraint, or behavior directly in domain terms.
