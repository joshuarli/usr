---
name: test-audit
description: "Apply when asked to review existing tests in a bounded scope for weak, redundant, or implementation-coupled coverage and unnecessary test-only production seams. Skip writing new tests."
---

# Test Audit

Judge the tests in a bounded scope, one test at a time, with evidence. The preferred suite shape (few wide, deterministic, isolated tests; no coverage gate) belongs to `renovate-tests`; this skill applies it test by test. Optimize for confidence and maintainability, not deletion count. A test that resembles the implementation can still be the cheapest independent guard of a real contract.

## Audit

1. Read `AGENTS.md`, identify the tests in scope and the commands or CI paths that own them, and do not widen the scope without a clear reason.
2. Read each suspect in full with its production owner, callers, overlapping tests, and history. If it claims behavior supplied by a dependency, read the dependency.
3. Decide what it asserts and what plausible failure it detects, and whether a stronger test already covers that contract at its owning boundary.
4. Settle the disposition and evidence before editing. Review-only means report without changing files. When cleanup is in scope, change only high-confidence candidates.
5. Run the narrowest validation and report what you ran.

## Keep, fix, or cut

**Retain** tests that independently guard a public API, protocol, config, migration, storage, security, platform behavior, default, wire or prompt bytes, package or release boundary, observable call order, or a regression with a credible failure mode. Source inspection stays only if it is the cheapest independent guard and survives identifier-only refactors. A failing baseline may be a product defect: understand it first. Static, slow, or refactor-sensitive tests are not deletable for those reasons alone.

**The oracle test:** would this still pass if every function it imports returned nothing or a wrong value? If so it detects nothing. Usual shapes:
- loose or absent assertions (`toBeDefined`, `toBeTruthy`, `not.toThrow`, `toBeGreaterThan(0)`), or call-only and absence-only checks;
- an expected value computed by the code under test, a restated constant or default, or assertions on data the test built;
- mocks that implement the behavior they assert, or one mock standing in for different APIs;
- a negative control that passes for an unrelated reason, or fixtures that supply an ordering or receipt production should produce;
- capability tests that restate declared flags, names or fixtures that promise more than the input exercises.

Fix by calling the subject with one concrete input and asserting the literal output or effect: for a mock, the payload received; for an absence, also the presence on another input; for a constant, the mechanism that reads it.

**Other junk leads** (investigate, never delete automatically): coverage probes with no assertion, copied fixtures or export lists, exact source or string greps, private-predicate tests duplicated at real boundaries, duplicate invocations of one contract, provider-local replays of shared helpers, tests that only preserve test-only exports or wrappers, and production code whose only callers are tests.

## Decisions

For each candidate, say in a line: the failure it can detect, the stronger proof that remains, and the focused command. One disposition each:
- **Retain:** name the contract and failure caught.
- **Fix:** keep the contract, repair the vacuous assertion.
- **Consolidate:** name the suite that absorbs it, preferring the wider boundary test.
- **Delete:** name the remaining proof, or explain why no independent contract exists.

Judge assertions, not names; inspect parameterized rows. Missing evidence means not ready to delete.

## Editing

Make one coherent owner-boundary change. Remove test-only exports, globals, and wrappers and dead production paths after checking callers. Move valuable regressions to their owners. Add no replacement test that restates the implementation or preserves an alias for tests. Inspect the final diff and separate production changes from test changes.

**Report:** scope reviewed, strongest findings with evidence, changes made, checks run, suspicious tests kept and why, open defects.
