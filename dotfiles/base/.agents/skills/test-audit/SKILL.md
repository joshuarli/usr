---
name: test-audit
description: Review existing tests in a bounded scope for weak, redundant, implementation-coupled coverage and unnecessary test-only production seams.
---

# Test Audit

Run one evidence-based audit of the tests in the requested scope. Keep the scope bounded and do not expand it into a whole-subsystem cleanup without a clear reason. Optimize for confidence and maintainability, not deletion count. A test that resembles implementation can still be the cheapest independent guard of a real contract.

## Audit

1. Read repository-level and scoped `AGENTS.md` instructions. Identify the tests within the requested scope and the commands or CI paths that own them. Do not expand scope without a clear reason.
2. Read each relevant test in full, along with its production owner, entry point, callers, callees, sibling implementations, overlapping tests, relevant history, and CI routing. If the test claims behavior supplied by a dependency, inspect that dependency's source or types.
3. For each suspicious test, determine what it actually asserts and what plausible failure it detects. Check whether a stronger test already covers the same contract at its owning boundary.
4. Record the evidence and disposition before editing. If the user asked for review only, report findings without changing files. If cleanup is in scope, change only high-confidence candidates within the requested boundary.
5. Run the narrowest relevant validation allowed by the task and repository instructions. Report what you actually ran and any unresolved risk.

## Value and Retention Bar

Tests earn their maintenance cost by protecting observable behavior, a credible regression, or an independently meaningful contract. Retain tests that independently enforce public APIs, protocols, configuration, migrations, storage, security, platform behavior, defaults, wire or prompt bytes, generated cross-language behavior, package or release boundaries, and architecture constraints. Also retain:

- call ordering when order is observable;
- regressions with a credible failure mode;
- source inspection when it is the cheapest independent guard, changes when a user-facing key, byte, or path changes, and survives identifier-only refactors;
- a test that fails on the baseline until the behavior is understood; it may expose a product defect.

Static or slow tests are not deletable for those reasons alone. A test that changes during source reorganization is a candidate for review, not automatic deletion. A failing baseline may be a product defect; understand it before changing or deleting coverage.

## Junk Patterns

Treat these as leads for investigation, not automatic reasons to delete:

- assertion-free coverage probes;
- self-comparisons and identity copiers;
- copied fixtures, inventories, manifests, or export lists;
- exact source, import, or string greps;
- private predicate or call-shape tests duplicated at real boundaries;
- duplicate invocations of the same contract;
- provider-local replays of shared helpers;
- tests whose only purpose is preserving test-only exports, globals, or wrappers;
- dead production code whose only callers are tests;
- expected values produced by the helper or renderer under test;
- mocks that implement the asserted behavior, or one identical mock standing in for different APIs;
- fixtures that supply a receipt, admission, or callback ordering the production owner should produce, or persistence asserted against a store the path never writes;
- capability tests that restate declared flags instead of exercising the delivery or acknowledgement the flags promise;
- negative controls that pass for an unrelated reason, such as a different guard denying the request or the production path never reaching the rejection;
- names or fixtures that promise more than the input exercises.

## Evidence and Decisions

For each candidate, record:

- exact test name and location;
- the failure it can actually detect;
- non-test callers of the covered production or support seam;
- stronger remaining owner-boundary proof, or why no proof is needed;
- relevant history and why the test or seam exists;
- production or test-support deletion unlocked;
- risk and the focused validation command.

Use one disposition per candidate:

- **Retain:** name the contract and plausible failure it catches.
- **Fix:** retain the contract but repair an assertion that is vacuous, unreachable, or otherwise fails to prove it.
- **Consolidate:** name the stronger suite or owner that will absorb the assertion.
- **Delete:** name the proof that remains or explain why no independent contract exists.

Judge assertions by behavior, not test names. For parameterized tests, inspect the rows; record them separately only when they protect different contracts or need different decisions. Missing evidence means the candidate is not ready for deletion.

## If Editing Is in Scope

Choose one coherent owner-boundary change. Remove obsolete test-only exports, globals, wrappers, and dead production paths only after caller inspection confirms they are unnecessary. Move valuable regressions to their canonical owners and consolidate repeated package or dependency assertions into one generic contract.

Do not add replacement tests that restate the same implementation, preserve aliases solely for tests, or turn uncertain candidates into cleanup. Validate through the real owner boundary using the repository's narrowest relevant commands; include sibling implementations when a shared contract changes. When removing source inspections or plan assertions, exercise the executable behavior that owns the contract. Inspect the final diff and distinguish production changes from test and support changes.

## Handoff

Report the scope reviewed, the strongest findings and their evidence, changes made if any, focused checks actually run, retained suspicious tests and why they remain, plus unresolved defects or follow-ups. Commit, push, open a pull request, or merge only when explicitly authorized.
