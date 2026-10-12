---
name: renovate-tests
description: "Apply when asked to renovate, slim down, or restructure a project's test suite toward fewer, wider integration tests, or to decide whether line coverage is worth tracking. Skip auditing a few tests (use test-audit), writing tests for one change, and fixing a failing test."
---

# Renovate Tests

Reshape a suite so each test earns its cost: few tests, wide reach, deterministic, isolated. Tests protect behavior at the boundary users and callers touch. They are not a mirror of the code. Use `test-audit` for the per-test judgment (oracle test, retention bar); this skill decides the suite's shape.

## Method

1. **Map the boundaries.** List the real entry points: CLI commands, HTTP routes, public library API, file formats, protocols, jobs. Note which already have an end-to-end test and how long the suite takes.
2. **Baseline.** Run the suite twice and record time and any test that differs between runs. Flakes are fixed or quarantined first; a flaky wide test is worse than none.
3. **Classify each test.** Keep, widen, merge into a boundary test, or delete. A unit test survives only when it guards logic with a large input space (parsers, codecs, state machines, math) that the boundary cannot reach cheaply, ideally as a property or table test.
4. **Write the boundary tests first**, then delete the unit tests they now cover. A deletion with no stronger remaining proof is not ready.
5. **Check the new tests catch something.** Break the code in two or three plausible ways (wrong output, dropped error, off-by-one) and confirm a test fails. This replaces coverage as the signal that the suite works.
6. **Compare.** Report suite time, test count, and flake rate before and after.

## Cut

- Tests of getters, constructors, wiring, config defaults, or one-line delegations.
- Mock-heavy tests that assert calls were made rather than outcomes.
- Several tests for one contract at different layers; keep the outermost that still pins it.
- Snapshot or fixture files nobody reads; keep a snapshot only when a human reviews its diff.
- Ceremony: base classes, builders, and helpers used by one or two tests, and test-only exports or seams in production code. Remove the seam when its last test goes.

## Wide tests

- Drive the real thing through its public surface (spawn the binary, call the endpoint, run the job) and assert on observable output, exit status, files, and emitted data.
- Fake only the edges you do not own (third-party network, payment, email), at the narrowest seam, and keep the fake honest by exercising it with a contract check against the real service when one is reachable.
- One test may cover a scenario with several steps; prefer a few scenarios over many micro-cases. Failure messages must say which step and why.

## Isolation and determinism

- Every test builds its own world: a fresh temp directory under the repo's `.work/tmp`, its own database or schema, its own `HOME`, config, and environment, torn down on success and failure.
- Ephemeral ports and unique names; never a fixed port, shared file, or global singleton. Tests must pass in any order and in parallel.
- No real clock, randomness, or network. Inject a clock and a seeded RNG; wait on a condition with a deadline, never a bare sleep.
- A test that touches the user's real home, shared services, or the network is a defect.
- If a wide test cannot be made deterministic, narrow it until it can. Do not add retries.

## Coverage

Line coverage is not a gate and not a target. It rewards executing code, not checking it, and drives the trivial tests this skill removes. Drop coverage thresholds and the CI step that enforces them. Keep a coverage report only as an on-demand way to find a boundary no scenario reaches. Mutation or fault-injection spot checks (step 5) answer "would a test notice?" better.

## Scope and handback

Work one project or one subsystem at a time, on the narrowest commands that run the affected tests; run the full suite once at the end, saying why. Removing a coverage gate or deleting many tests changes the project's contract: say so. Leave commits to the user.

**Reply:** boundaries found, tests cut/merged/added with counts, the fault-injection results, suite time and flake rate before and after, and anything I must decide (coverage gate removal, tests kept for doubt).
