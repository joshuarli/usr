# Determinism and Reproducibility Audit

You are improving this codebase so identical inputs produce stable, reproducible behavior wherever semantics do not require nondeterminism.

The goal is to eliminate accidental variance that makes tests flaky, output unstable, caches ineffective, builds irreproducible, and debugging harder.

Scope: observable ordering, time, randomness, environment dependence, generated output, concurrency ordering, and build metadata.

Applicability: Apply this prompt only when identical inputs can produce accidental variance or tests/builds depend on uncontrolled nondeterminism. If the condition is materially absent, report that evidence and make no speculative changes.

Preserve: Existing valid behavior, public contracts, persisted data and formats, output, side effects, permissions, state transitions, and supported-platform semantics unless this request explicitly changes them.

Intentional changes: Only changes explicitly authorized by the invoking request; otherwise none.

If inspection shows that the relevant contract already holds, do not manufacture
changes. Verify it, correct only concrete gaps, and report the evidence.

## First inspect the repository

Before editing:

Inventory sources of nondeterminism:

- hash/map/set iteration
- filesystem enumeration
- current time
- randomness
- temporary names
- process environment
- locale
- timezone
- current directory
- parallel scheduling
- thread/task races
- network ordering
- unstable sorting
- generated IDs
- build metadata
- external command output

Run representative operations more than once and compare observable output where useful.

- Record failures that predate the work.

## Non-negotiable design

Each numbered requirement defines an invariant or observable behavior, its
authoritative owner or boundary, the shortcut or ambiguous state it prohibits,
and the evidence that proves it. Do not prescribe incidental implementation
structure unless that structure is itself part of the contract.

### 1. Stabilize observable ordering, time, and randomness

#### Stabilize ordering


If output order is not semantically meaningful, make it deterministic.

Examples:

- sort filesystem entries
- sort map-derived output
- define tie-breakers
- use ordered collections only where the cost is justified

Do not impose ordering on hot paths when it has no observable value.

#### Make time an explicit input


Do not let timestamps appear unpredictably in logic or output unless required.

Separate:

- wall-clock time
- monotonic elapsed time
- logical event time
- build time

Inject or pass explicit time values where tests need deterministic behavior.

#### Control randomness


Use explicit seeds in tests.

Keep cryptographic randomness separate from reproducibility-oriented randomness.

Do not weaken security merely to make tests deterministic.

### 2. Make environment-dependent and generated output reproducible

#### Normalize environment dependence


Inventory behavior influenced by:

- environment variables
- locale
- timezone
- PATH
- HOME
- current directory
- shell
- terminal capabilities

Make required inputs explicit and test default behavior.

#### Stabilize generated output


Generated files, diagnostics, help, manifests, snapshots, and machine-readable output should avoid incidental differences.

Exclude or isolate:

- timestamps
- random ordering
- absolute temp paths
- machine-specific values

unless they are part of the intended contract.

### 3. Remove scheduler and build variance where semantics do not require it

#### Make concurrency deterministic where semantics permit


Do not assert accidental task completion order.

Where ordering matters, encode it.

Where ordering does not matter, compare sets/multisets or normalize output rather than relying on scheduler behavior.

#### Make builds reproducible where practical


Audit:

- embedded timestamps
- host paths
- unordered inputs
- environment-derived version data
- code generation

Prefer explicit build inputs.

### 4. Preserve intentional nondeterminism explicitly


Do not remove:

- cryptographic randomness
- load balancing randomness
- intentional jitter
- unique IDs

Instead isolate and test the policy around them.

### Migration and compatibility policy

Do not create parallel legacy and canonical implementations as part of this work.
If a rename, move, replacement, or contract change becomes necessary, inventory all
references first, keep one canonical path, and retain compatibility only when the
invoking request or an existing external contract requires it.

## Explicit anti-patterns

Do not:

- sort everything blindly
- freeze time globally in production
- replace secure randomness with deterministic PRNGs
- make tests pass by ignoring unstable output
- rely on hash iteration order
- assume filesystem order
- hide environment dependence


## Verification

After editing:

- Run the nearest hard judge for observable ordering, time, randomness, environment dependence, generated output, concurrency ordering, and build metadata: the compiler, type checker, schema/build check, or focused tests that can reject an invalid change.
- Test the observable success behavior, failure behavior, edge cases, and invariants established by the numbered requirements.
- Audit unordered iteration, filesystem order, clock/random sources, environment inputs, generated output, and scheduler-dependent assertions; classify every remaining exception rather than assuming it is harmless.
- Broaden checks only when the changed boundary warrants it, and distinguish pre-existing failures from regressions introduced by this work.

## Acceptance criteria

The work is complete only when:

- repeated identical operations produce stable output where expected
- ordering is explicit where observable
- tests control time and randomness where necessary
- environment-sensitive behavior is visible
- generated output avoids incidental machine-specific variance
- concurrency tests do not rely on scheduler luck
- intentional nondeterminism remains deliberate and isolated

The architectural principle is: **nondeterminism should be a feature you can point to, not background noise.**
