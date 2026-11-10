---
name: test-audit
description: "Apply when asked to review tests for weak, redundant, or implementation-coupled coverage, execution drag, or test-only seams, or to renovate or restructure a suite toward fewer, wider integration tests, or to decide whether line coverage is worth tracking. Skip writing tests for one change, and fixing a failing test."
---

# Test Audit

Judge tests in a bounded scope one at a time, or reshape a whole suite when the scope is the suite. Few tests, wide reach, deterministic and isolated, protecting behavior at the boundary users and callers touch — not a mirror of the code. Optimize for confidence, not deletion count.

## Audit

1. Read `AGENTS.md`, identify the tests in scope and the commands or CI paths that own them; do not widen scope without a clear reason.
2. When scope is a whole suite, map boundaries first: CLI commands, HTTP routes, public library API, file formats, protocols, jobs. Note which have end-to-end tests and how long the suite takes.
3. Read each suspect with owner, callers, overlapping tests, and history. If it claims dependency behavior, read the dependency.
4. Decide what it asserts, what plausible failure it detects, and whether a stronger test covers that contract at its owning boundary.
5. Settle disposition and evidence before editing. Review-only means report without changing files. When cleanup is in scope, change only high-confidence candidates.
6. Run the narrowest validation and report what you ran.

**Baseline.** When cheap or asked for, run twice and record time and differing tests; otherwise report cost first and baseline a subset. Fix flakes first; a flaky wide test is worse than none.

## Keep, fix, or cut

**Retain** tests that independently guard a public API, protocol, config, migration, storage, security, platform behavior, default, wire or prompt bytes, package or release boundary, observable call order, or a regression with a credible failure mode. Source inspection only if the cheapest guard surviving identifier-only refactors. A failing baseline may be a product defect; understand it first. Static, slow, or refactor-sensitive tests are not deletable for those reasons alone. A unit survives only when it guards large-input-space logic (parsers, codecs, state machines, math) the boundary cannot reach cheaply, ideally as a property or table test.

**Cut.** Getters, constructors, wiring, config defaults no caller depends on, one-line delegations. Mock-heavy tests asserting calls rather than outcomes. Several tests for one contract across layers; keep the outermost that pins it. Snapshot or fixture files nobody reads; keep a snapshot only when a human reviews its diff. Ceremony: base classes, builders, helpers used by one or two tests, test-only exports or seams. Remove the seam when its last test goes.

**The oracle test:** would this still pass if every function it imports returned nothing or a wrong value? If so it detects nothing. Usual shapes:
- loose or absent assertions (`toBeDefined`, `toBeTruthy`, `not.toThrow`), call-only and absence-only checks;
- an expected value computed by the code under test, a restated constant, or assertions on data the test built;
- mocks implementing the behavior they assert, or one mock for different APIs;
- a negative control passing for an unrelated reason, or fixtures supplying an ordering production should produce;
- capability tests restating declared flags or names.

Fix by calling the subject with one concrete input and asserting the literal output or effect: for a mock, the payload received; for an absence, also the presence on another input; for a constant, the mechanism that reads it.

**Execution drag** (repair, never delete to speed up): waiting out production timeouts instead of a virtual clock or a 50-200ms test timeout; sequential loops over independent seeds or matrix rows; re-reading or re-digesting immutable assets (migrations, queries, schemas) per test instead of caching them.

**Other junk leads** (investigate, never delete automatically): coverage probes with no assertion, copied fixtures or export lists, exact source greps, private-predicate tests duplicated at boundaries, duplicate invocations of one contract, provider-local replays of shared helpers, tests preserving test-only exports, and production code whose only callers are tests.

## Wide tests

- Drive the real thing through its public surface (spawn the binary, call the endpoint, run the job) and assert observable output, exit status, files, and emitted data.
- Fake only edges you do not own (third-party network, payment, email) at the narrowest seam; keep the fake honest with a contract check against the real service when reachable.
- One test may cover a multi-step scenario; prefer few scenarios over many micro-cases. Failure messages must say which step and why.
- Merge into a boundary test where one exists. Write boundary tests first, then delete unit tests they now cover; a deletion with no stronger proof is not ready.

## Isolation and determinism

Each test builds its own world: fresh temp directory under `.work/tmp`, own database or schema, `HOME`, config, and environment, torn down on pass and fail, with no server, child process, socket, or connection outliving it. Ephemeral ports and unique names; never a fixed port, shared file, or global singleton, and assert on the test's own path, port, or handle rather than shared listings. Pass in any order and in parallel. No real clock, randomness, or network: inject a clock and seeded RNG; wait on a condition with a deadline, never a bare sleep. Touching the user's real home, shared services, or the network is a defect. If a wide test cannot be deterministic, narrow it until it can. No retries. Isolate mutable state while caching immutable assets.

## Coverage

Line coverage is not a gate and not a target. It rewards executing code, not checking it, and drives the trivial tests this removes. Recommend dropping thresholds and their CI step; remove them only when asked. Keep a coverage report only on demand to find a boundary no scenario reaches. Fault-injection spot checks answer "would a test notice?" better.

## Reshape

**Proof.** Check new tests catch something: break the code two or three plausible ways (wrong output, dropped error, off-by-one) and confirm a test fails. This replaces coverage as the signal the suite works.

**Compare.** Report suite time, test count, and flake rate before and after.

**Scope and handback.** Work one project or subsystem at a time on the narrowest commands that run affected tests; run the full suite once at the end only when asked, saying why. Comprehensive runs stay manual-only under `test-pyramid`. Removing a coverage gate or deleting many tests changes the project's contract: say so.

## Decisions

Give each candidate one disposition (**Retain**, **Fix**, **Consolidate** into a named wider suite, or **Delete**) in one line naming the failure it detects, the proof that remains, and the focused command. Judge assertions, not names; inspect parameterized rows. Missing evidence means not ready to delete.

## Editing

Make one coherent owner-boundary change. Remove test-only exports, globals, and wrappers and dead production paths after checking callers. Move valuable regressions to their owners. Add no replacement restating the implementation or preserving an alias. Inspect the final diff and separate production from test changes.

**The test:** another agent can judge each test from evidence, reshape a suite toward wider checks without losing a contract, and confirm the reshaped suite notices a real defect.

**Report:** scope, boundaries, findings with evidence, tests cut/merged/added with counts, fault-injection results, suite time and flake rate before and after, changes made, checks run, suspicious tests kept and why, open defects, and anything you must decide (coverage gate removal, tests kept for doubt).
