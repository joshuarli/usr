# Improve Test-Suite Signal and Contract Coverage

You are improving this codebase so it clearly states what behavior the codebase guarantees, fails for meaningful reasons, and avoids redundant or implementation-coupled coverage.

The goal is not "more tests." The goal is a test suite with high signal: each test should protect a useful behavior, invariant, compatibility contract, or failure mode.

Scope: the test suite and its unit, integration, property, snapshot, fixture, timing, and external-boundary behavior.

Applicability: Apply this prompt only when tests exist whose signal, determinism, naming, boundary choice, or contract coverage can be materially improved. If the condition is materially absent, report that evidence and make no speculative changes.

Preserve: Existing valid behavior, public contracts, persisted data and formats, output, side effects, permissions, state transitions, and supported-platform semantics unless this request explicitly changes them.

Intentional changes: Only changes explicitly authorized by the invoking request; otherwise none.

If inspection shows that the relevant contract already holds, do not manufacture
changes. Verify it, correct only concrete gaps, and report the evidence.

## First inspect the repository

Before editing:

- inventory test layers and naming conventions
- identify unit, integration, end-to-end, property, snapshot, fixture-heavy, and external-service tests
- identify duplicated coverage
- identify tests asserting private implementation details
- identify sleeps, retries, timing races, nondeterministic values, random ordering, real network access, and unnecessary external dependencies
- identify important behavior with no observable test oracle
- identify tests whose names do not explain the protected contract
- identify skipped/ignored/flaky tests and their rationale
- run the narrowest useful baseline suite and record pre-existing failures


## Non-negotiable design

Each numbered requirement defines an invariant or observable behavior, its
authoritative owner or boundary, the shortcut or ambiguous state it prohibits,
and the evidence that proves it. Do not prescribe incidental implementation
structure unless that structure is itself part of the contract.

### 1. Make tests state observable contracts

#### Make every test answer "what contract does this protect?"


A good test name should expose:

- operation
- condition
- expected behavior or invariant

Prefer:

```text
rejects_duplicate_non_repeatable_option
preserves_opaque_arguments_after_double_dash
retry_backoff_is_capped_at_maximum
```

over:

```text
test_parser
works
test_case_3
```

#### Test observable behavior, not incidental implementation


Prefer assertions on:

- return values
- emitted events
- persisted state
- external calls at a meaningful boundary
- output
- errors
- state transitions
- invariants

Avoid testing:

- private helper call counts without semantic meaning
- exact internal data structure choices
- implementation ordering that is not part of the contract
- mock choreography that simply mirrors source code

A refactor that preserves behavior should not require rewriting large portions of the test suite.

### 2. Keep only distinct coverage at the narrowest useful boundary

#### Remove redundant tests


Identify tests that protect the same behavior through nearly identical inputs.

Keep the smallest set that provides distinct semantic coverage.

Do not delete tests simply because they look similar; identify what failure each one would uniquely detect.

#### Put tests at the narrowest useful boundary


Use unit tests for pure logic and local invariants.

Use integration tests when the contract depends on real boundaries such as:

- filesystem semantics
- database behavior
- process execution
- serialization
- CLI behavior
- networking

Do not mock a boundary whose real semantics are precisely what the test is supposed to protect.

### 3. Eliminate timing and scheduling nondeterminism

#### Eliminate nondeterminism


Replace avoidable nondeterminism from:

- wall-clock time
- sleeps
- random seeds
- hash iteration
- filesystem ordering
- background scheduling
- port races
- locale/environment inheritance

with explicit control.

Prefer deterministic clocks, seeded randomness, stable ordering, temporary resources, and synchronization on observable conditions.

#### Remove sleep-driven synchronization


Tests should not use arbitrary sleeps to "give something time."

Prefer:

- readiness signals
- events/channels
- polling with a bounded semantic condition when unavoidable
- deterministic schedulers/clocks
- process/PTY synchronization

A timeout may bound a test, but it should not be the mechanism that makes the test correct.

### 4. Keep fixtures comprehensible and errors contract-focused

#### Make fixtures local and comprehensible


Avoid giant shared fixtures whose hidden setup makes tests difficult to understand.

Prefer fixtures that expose only the state relevant to the test.

Use builders/factories when they reduce noise, but keep significant values visible at the call site.

Do not hide the behavior under test behind a generic "create everything" fixture.

#### Test errors as contracts


For important failure paths, verify:

- error category/type
- relevant context
- observable exit/status behavior
- side-effect behavior
- cleanup behavior

Avoid brittle full-string assertions unless exact text is a user-facing compatibility contract.

### 5. Use snapshots and property tests only where they add signal

#### Use snapshots selectively


Snapshots are useful for broad stable output such as:

- CLI help
- diagnostics
- rendered documents
- protocol fixtures

Do not snapshot huge structures when a few semantic assertions would better identify the failure.

If snapshots are used, keep them deterministic and reviewable.

#### Add property tests only where they buy state-space coverage


Good candidates:

- parser round trips
- codecs
- normalization
- ordering
- idempotence
- arithmetic constraints
- state-machine invariants

Do not add generative testing because it sounds rigorous.

### 6. Make regressions first-class and slow layers intentional

#### Make regression tests first-class


When fixing a bug, add the smallest test that fails before the fix and demonstrates the actual user-visible or invariant violation.

Name the behavior, not the issue number alone.

#### Keep slow layers intentional


Clearly distinguish fast local tests from expensive integration/end-to-end tests.

A developer or coding agent should know the narrowest useful command for validating a change.

Document relevant test commands in the repository conventions file when not obvious.


## Explicit anti-patterns

Do not:

- maximize test count
- assert implementation details for convenience
- rely on arbitrary sleeps
- make tests depend on execution order
- access real network services unnecessarily
- hide important values in giant fixtures
- mock every dependency
- use brittle entire-error-string comparisons without reason
- add snapshots for tiny scalar behavior
- delete failing tests merely because they expose existing bugs
- weaken assertions to reduce flakiness instead of fixing nondeterminism


## Verification

After editing:

- run the focused suite repeatedly where flakiness was addressed
- verify tests fail when the protected behavior is intentionally broken
- verify common refactors do not require rewriting behavior tests
- verify slow/external tests are clearly separated
- verify regression tests reproduce their pre-fix failure
- run broader checks appropriate to changed boundaries


- Distinguish failures that predate the work from regressions introduced by this change.

## Acceptance criteria

The work is complete only when:

- test names expose protected behavior or invariants
- redundant tests have been reduced without losing semantic coverage
- implementation-coupled assertions have been removed where unnecessary
- important failure paths have meaningful coverage
- nondeterminism and sleep-based synchronization are minimized
- fixtures make relevant state visible
- boundary behavior is tested at the appropriate real boundary
- property/snapshot tests are used only where they add signal
- developers and agents can run the narrowest relevant suite easily
- existing behavior and public contracts are preserved

The architectural principle is: **tests should describe what must remain true, not narrate how the current implementation happens to work.**
