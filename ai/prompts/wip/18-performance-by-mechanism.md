# Performance by Mechanism, Not Folklore

You are improving this codebase so performance-sensitive paths are improved by identifying and removing measurable unnecessary work from first principles.

The goal is to make performance-sensitive paths simpler, more measurable, and cheaper without sacrificing correctness or readability.

Scope: measurable hot paths and costs from allocation, copying, parsing, serialization, syscalls, I/O round trips, locking, task creation, and buffering.

Applicability: Apply this prompt only when performance is a material concern or inspection reveals repeated/unnecessary work worth measuring. If the condition is materially absent, report that evidence and make no speculative changes.

Preserve: Existing valid behavior, public contracts, persisted data and formats, output, side effects, permissions, state transitions, and supported-platform semantics unless this request explicitly changes them.

Intentional changes: Only changes explicitly authorized by the invoking request; otherwise none.

If inspection shows that the relevant contract already holds, do not manufacture
changes. Verify it, correct only concrete gaps, and report the evidence.

## First inspect the repository

Before editing:

Identify likely hot paths and cost centers involving:

- allocations
- copies
- parsing passes
- serialization
- syscalls
- filesystem traversal
- database round trips
- network requests
- lock contention
- context switches
- task creation
- repeated hashing
- repeated decoding
- cache misses
- unnecessary buffering

Use existing benchmarks/profiling if available.

- Record failures that predate the work.

## Non-negotiable design

Each numbered requirement defines an invariant or observable behavior, its
authoritative owner or boundary, the shortcut or ambiguous state it prohibits,
and the evidence that proves it. Do not prescribe incidental implementation
structure unless that structure is itself part of the contract.

### 1. Measure representative cost and remove work before optimizing it

#### Measure before changing


Establish a representative baseline when performance is the reason for a change.

Prefer wall-clock, throughput, allocation, syscall, query-count, or profile data relevant to the actual mechanism.

#### Remove work first


Prefer:

- fewer passes
- fewer queries
- fewer syscalls
- fewer copies
- fewer allocations
- less serialization
- less repeated parsing

over micro-optimizing unavoidable work.

### 2. Keep data useful and batch expensive boundary crossings

#### Keep data in useful form


Avoid parse -> stringify -> parse cycles, repeated conversions, and unnecessary intermediate representations.

#### Batch across expensive boundaries


Where semantics permit, batch:

- database operations
- network calls
- filesystem metadata queries
- writes
- IPC messages

Do not batch so aggressively that latency, memory, or failure semantics become worse.

### 3. Reduce allocation/copy and synchronization cost

#### Reduce allocation/copy churn


Inspect ownership and lifetime opportunities before introducing pools or unsafe code.

Prefer borrowing/reuse where it remains readable.

#### Audit synchronization costs


Find lock contention, oversized critical sections, unnecessary atomics, and excessive task/thread handoff.

### 4. Treat caches and fast-path abstraction as measured choices

#### Avoid speculative caches


A cache adds:

- invalidation
- memory
- concurrency
- staleness
- observability complexity

Introduce or preserve one only when measurement justifies it.

#### Keep fast paths obvious


Do not bury critical paths under generic abstraction layers that make cost invisible.

### 5. Benchmark replacements and protect material performance contracts

#### Benchmark replacements


If replacing a dependency or algorithm for performance, compare representative before/after behavior.

#### Protect performance contracts


For important regressions, add:

- benchmark baselines
- query-count assertions
- allocation checks
- complexity tests
- size limits

where maintainable.

### Migration and compatibility policy

Do not create parallel legacy and canonical implementations as part of this work.
If a rename, move, replacement, or contract change becomes necessary, inventory all
references first, keep one canonical path, and retain compatibility only when the
invoking request or an existing external contract requires it.

## Explicit anti-patterns

Do not:

- optimize based on intuition alone
- add unsafe code for hypothetical gains
- introduce object pools by default
- cache everything
- micro-optimize code dominated by I/O
- trade large readability losses for negligible gains
- hide regressions behind noisy benchmarks


## Verification

After editing:

- Run the nearest hard judge for measurable hot paths and costs from allocation, copying, parsing, serialization, syscalls, I/O round trips, locking, task creation, and buffering: the compiler, type checker, schema/build check, or focused tests that can reject an invalid change.
- Test the observable success behavior, failure behavior, edge cases, and invariants established by the numbered requirements.
- Audit baseline metrics, repeated work, boundary crossings, copies/allocations, synchronization, caches, and benchmark evidence; classify every remaining exception rather than assuming it is harmless.
- Broaden checks only when the changed boundary warrants it, and distinguish pre-existing failures from regressions introduced by this work.

## Acceptance criteria

The work is complete only when:

- important performance claims have measurements
- removed work is preferred over cleverer work
- expensive boundary crossings are intentional
- unnecessary conversions/copies are reduced
- synchronization cost is understood
- caches have evidence and explicit invalidation semantics
- critical paths remain readable
- representative performance does not regress
- correctness and public behavior remain intact

The architectural principle is: **the fastest operation is usually the one you stop doing.**
