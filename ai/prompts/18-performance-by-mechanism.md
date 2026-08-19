# Performance by Mechanism, Not Folklore

You are improving an existing codebase by identifying unnecessary work and performance costs from first principles rather than applying generic optimization tricks.

The goal is to make performance-sensitive paths simpler, more measurable, and cheaper without sacrificing correctness or readability.

Do not change semantics unless explicitly required.

## First inspect the repository

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

## 1. Measure before changing

Establish a representative baseline when performance is the reason for a change.

Prefer wall-clock, throughput, allocation, syscall, query-count, or profile data relevant to the actual mechanism.

## 2. Remove work first

Prefer:

- fewer passes
- fewer queries
- fewer syscalls
- fewer copies
- fewer allocations
- less serialization
- less repeated parsing

over micro-optimizing unavoidable work.

## 3. Keep data in useful form

Avoid parse -> stringify -> parse cycles, repeated conversions, and unnecessary intermediate representations.

## 4. Batch across expensive boundaries

Where semantics permit, batch:

- database operations
- network calls
- filesystem metadata queries
- writes
- IPC messages

Do not batch so aggressively that latency, memory, or failure semantics become worse.

## 5. Reduce allocation/copy churn

Inspect ownership and lifetime opportunities before introducing pools or unsafe code.

Prefer borrowing/reuse where it remains readable.

## 6. Audit synchronization costs

Find lock contention, oversized critical sections, unnecessary atomics, and excessive task/thread handoff.

## 7. Avoid speculative caches

A cache adds:

- invalidation
- memory
- concurrency
- staleness
- observability complexity

Introduce or preserve one only when measurement justifies it.

## 8. Keep fast paths obvious

Do not bury critical paths under generic abstraction layers that make cost invisible.

## 9. Benchmark replacements

If replacing a dependency or algorithm for performance, compare representative before/after behavior.

## 10. Protect performance contracts

For important regressions, add:

- benchmark baselines
- query-count assertions
- allocation checks
- complexity tests
- size limits

where maintainable.

## Explicit anti-patterns

Do not:

- optimize based on intuition alone
- add unsafe code for hypothetical gains
- introduce object pools by default
- cache everything
- micro-optimize code dominated by I/O
- trade large readability losses for negligible gains
- hide regressions behind noisy benchmarks

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
