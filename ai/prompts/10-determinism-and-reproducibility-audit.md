# Determinism and Reproducibility Audit

You are improving an existing codebase so identical inputs produce stable, reproducible behavior wherever semantics do not require nondeterminism.

The goal is to eliminate accidental variance that makes tests flaky, output unstable, caches ineffective, builds irreproducible, and debugging harder.

Preserve behavior unless nondeterministic behavior is itself an accidental defect.

## First inspect the repository

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

## 1. Stabilize ordering

If output order is not semantically meaningful, make it deterministic.

Examples:

- sort filesystem entries
- sort map-derived output
- define tie-breakers
- use ordered collections only where the cost is justified

Do not impose ordering on hot paths when it has no observable value.

## 2. Make time an explicit input

Do not let timestamps appear unpredictably in logic or output unless required.

Separate:

- wall-clock time
- monotonic elapsed time
- logical event time
- build time

Inject or pass explicit time values where tests need deterministic behavior.

## 3. Control randomness

Use explicit seeds in tests.

Keep cryptographic randomness separate from reproducibility-oriented randomness.

Do not weaken security merely to make tests deterministic.

## 4. Normalize environment dependence

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

## 5. Stabilize generated output

Generated files, diagnostics, help, manifests, snapshots, and machine-readable output should avoid incidental differences.

Exclude or isolate:

- timestamps
- random ordering
- absolute temp paths
- machine-specific values

unless they are part of the intended contract.

## 6. Make concurrency deterministic where semantics permit

Do not assert accidental task completion order.

Where ordering matters, encode it.

Where ordering does not matter, compare sets/multisets or normalize output rather than relying on scheduler behavior.

## 7. Make builds reproducible where practical

Audit:

- embedded timestamps
- host paths
- unordered inputs
- environment-derived version data
- code generation

Prefer explicit build inputs.

## 8. Preserve nondeterminism where required

Do not remove:

- cryptographic randomness
- load balancing randomness
- intentional jitter
- unique IDs

Instead isolate and test the policy around them.

## Explicit anti-patterns

Do not:

- sort everything blindly
- freeze time globally in production
- replace secure randomness with deterministic PRNGs
- make tests pass by ignoring unstable output
- rely on hash iteration order
- assume filesystem order
- hide environment dependence

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
