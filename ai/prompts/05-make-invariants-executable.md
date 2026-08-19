# Make Invariants Executable

You are improving this codebase so important assumptions are enforced by types, constructors, assertions, validation, database constraints, protocol checks, or tests rather than existing only in comments and caller discipline.

The goal is to identify statements of the form "this must always be true" and give each one a machine-enforced home.

Scope: repository invariants currently enforced by comments, repeated guards, caller discipline, weak validation, or tests alone.

Applicability: Apply this prompt only when important assumptions exist that can be violated without a machine-enforced rejection. If the condition is materially absent, report that evidence and make no speculative changes.

Preserve: Existing valid behavior, public contracts, persisted data and formats, output, side effects, permissions, state transitions, and supported-platform semantics unless this request explicitly changes them.

Intentional changes: Only changes explicitly authorized by the invoking request; otherwise none.

If inspection shows that the relevant contract already holds, do not manufacture
changes. Verify it, correct only concrete gaps, and report the evidence.

## First inspect the repository

Before editing:

- search comments for `must`, `never`, `always`, `assume`, `requires`, `invariant`, `cannot`, `only after`, `before`, `after`, and similar language
- inventory repeated guards and validation logic
- inventory assertions and panics
- inspect database constraints and migrations
- inspect constructors and mutation APIs
- inspect tests for invariant-like behavior
- identify bugs that are only prevented by call ordering or convention
- run narrow baseline checks

- Record failures that predate the work.

## Non-negotiable design

Each numbered requirement defines an invariant or observable behavior, its
authoritative owner or boundary, the shortcut or ambiguous state it prohibits,
and the evidence that proves it. Do not prescribe incidental implementation
structure unless that structure is itself part of the contract.

### 1. Inventory invariants and choose the strongest practical enforcement

#### Inventory invariants explicitly


Create a working inventory of important invariants such as:

```text
worker_count > 0
start <= end
completed jobs have a completion timestamp
only the lease owner may complete a job
a persisted record has a stable identifier
this operation must not follow symlinks
```

For each invariant, identify:

- who currently establishes it
- who currently relies on it
- whether it can be violated by user input, external state, or programmer error
- the narrowest enforcement point

#### Choose the strongest practical enforcement mechanism


Prefer, roughly in this order when appropriate:

1. representation/type system
2. validated construction
3. database/schema constraint
4. boundary validation
5. assertion for internal programmer invariants
6. focused invariant/property/regression test

Do not force an invariant into the type system if doing so makes the code substantially harder to understand.

### 2. Distinguish invalid external input from programmer-impossible states

#### Distinguish user errors from programmer errors


User-controlled or environmental invalid input must return explicit errors.

Programmer-only impossible states may justify assertions/panics according to project conventions.

Do not:

- panic on malformed user input
- silently recover from an internal invariant violation that indicates corruption
- turn programmer bugs into vague runtime errors merely to avoid assertions

#### Validate once at the ownership boundary


If a constructor or parser establishes an invariant, downstream code should rely on the resulting type.

Avoid repeated defensive checks scattered throughout consumers.

If repeated checks remain necessary, reconsider whether the invariant truly belongs to the type.

### 3. Protect persisted and internal structural invariants

#### Use database constraints for persisted invariants


If an invariant must hold regardless of which code path writes data, application validation alone may be insufficient.

Where appropriate, use:

- NOT NULL
- UNIQUE
- CHECK
- FOREIGN KEY
- transactional constraints
- database-native exclusion/consistency mechanisms

Application code should still provide useful errors where needed, but the persistence boundary should protect durable truth.

Do not add schema constraints without considering existing data and migration behavior.

#### Assert internal structural assumptions


Assertions are appropriate for assumptions that indicate a bug if violated and cannot reasonably be caused by ordinary external input.

Make the assertion message identify the violated invariant.

Avoid assertions that merely duplicate type guarantees.

### 4. Use generative and regression tests where enforcement needs behavioral evidence

#### Add property tests where the invariant spans many cases


Use property-based or generative testing when it materially improves coverage for things such as:

- parser round trips
- encoding/decoding
- ordering
- normalization
- state transitions
- arithmetic bounds
- idempotence

Do not add a property-test dependency when a small deterministic table covers the meaningful state space.

#### Add regression tests before fixing behavioral bugs


When the cleanup exposes an actual bug:

- reproduce it with the narrowest useful test
- then fix the implementation
- preserve the test as the executable statement of the invariant

Do not silently change behavior under the guise of architectural cleanup.

### 5. Keep rationale local and remove redundant defensive checks

#### Keep rationale next to enforcement


A non-obvious invariant should be documented near the mechanism that enforces it.

Explain **why** the invariant exists, especially when it comes from:

- an external protocol
- concurrency
- durability
- security
- lifecycle ordering
- platform behavior

Do not leave the only explanation in a distant architecture document.

#### Remove redundant defensive code after enforcement


Once an invariant is structurally guaranteed, simplify consumers that still defensively re-check it.

Do not retain stale comments warning about impossible states that can no longer occur.


## Explicit anti-patterns

Do not:

- turn every assumption into a runtime check
- panic on user-controlled invalid input
- use assertions as a substitute for input validation
- scatter identical validation across consumers
- rely solely on application checks for critical persisted invariants
- add complex type machinery when a constructor check is clearer
- write tests that only restate implementation details
- weaken or remove constraints to make tests pass
- change public behavior without documenting the intentional change


## Verification

After editing:

- search for invariant-related comments and repeated checks
- confirm each important invariant has an authoritative enforcement point
- test invalid boundary input
- test programmer-invariant failures where practical
- test persistence constraints
- run property/regression tests where introduced
- run focused compiler/type-checker and broader checks as needed


- Distinguish failures that predate the work from regressions introduced by this change.

## Acceptance criteria

The work is complete only when:

- important invariants have explicit owners
- invalid external input is rejected at boundaries
- programmer-only impossible states are asserted or structurally prevented where appropriate
- persisted invariants are protected at the persistence layer when necessary
- repeated validation has been reduced
- downstream code can rely on established contracts
- non-obvious invariants have nearby rationale
- behavioral bugs discovered during the work have regression coverage
- enforcement is proportional and readable
- existing behavior and public contracts are preserved unless intentionally changed

The architectural principle is: **an invariant that matters should be enforced by something that can fail when it is violated.**
