---
name: performance-by-mechanism
description: Improve performance by measuring and removing unnecessary work, fitting data structures to operations, cutting copies, and bounding buffers and streaming.
disable-model-invocation: true
---

# Performance by Mechanism, Not Folklore

You are improving this codebase so performance-sensitive paths are improved by identifying and removing measurable unnecessary work from first principles.

The goal is to make performance-sensitive paths simpler, more measurable, and cheaper without sacrificing correctness or readability.

Scope: measurable hot paths and costs from algorithms and data-structure choice, allocation, copying, representation churn, parsing, serialization, syscalls, I/O round trips, locking, task creation, buffering, and whole-input loading.

Applicability: Apply this prompt only when performance is a material concern, input size makes accidental scans or whole-input loading relevant, or inspection reveals repeated/unnecessary work worth measuring. If the condition is materially absent, report that evidence and make no speculative changes.

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
- loops nested over collections, linear lookup in frequently queried collections, and repeated sorting
- repeated clones and bytes -> string -> bytes style conversions
- `read_to_end`, `read_to_string`, whole-file loading, and full response or query-result buffering
- long-lived caches, queues, and closures that retain large data
- expected input sizes, so complexity is judged against the real workload

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

### 6. Match data structures to the operations the program performs

State each important collection's dominant operations (append, membership, keyed
lookup, min/max, range, dedup, stable order) and choose the structure for those,
not from habit.

- Replace accidental quadratic work (a lookup or `contains` inside a loop over the
  same data) with an index or set when input size makes it material.
- Sort once at the ownership boundary instead of repeatedly; use a heap or a
  min/max scan when a full sort is not needed.
- Use set-like representations for membership, dedup, and intersection.
- Distinguish insertion order, sorted order, stable deterministic order, and
  arbitrary order, and do not pay for ordering no consumer requires.
- A derived index is derived state: make its ownership and invalidation explicit
  so it cannot become a second source of truth.
- Bound recursion and traversal over graphs, trees, and filesystems (cycles,
  depth, visited sets, adversarial input).
- Document a non-obvious structure with the operation pattern that justifies it.
  Reproduce a representative N before replacing clear code with a clever structure.

### 7. Keep ownership clear and avoid allocation and representation churn

- For important data, know who creates it, who owns it, who only borrows it, and
  why any shared ownership (`Rc`/`Arc`) is genuinely required.
- For each significant clone, decide whether it is needed for ownership or
  isolation, small and harmless, or avoidable by borrowing or moving. Do not
  contort lifetimes to remove tiny copies.
- Remove repeated representation changes (bytes -> string -> bytes,
  owned -> borrowed -> owned, JSON -> map -> JSON); keep data in the form its
  consumers use.
- Prefer slices and views for read-only access when they stay simple.
- Audit peak memory, not only total allocation: concurrency, queue depth, batch
  size, decompression, parallel reads, and fan-out.
- Reuse buffers only where measured. Do not introduce unsafe code merely to avoid
  an allocation.

### 8. Stream large or unbounded data with bounded buffers

- Classify each input as small and bounded, potentially large, or unbounded. Do
  not add streaming complexity for tiny bounded data.
- For large data, process incrementally across file, HTTP, database, compression,
  archive, and parsing boundaries when the operation permits it.
- Give every buffer an intentional capacity and growth policy, and define
  backpressure: whether producers block, await, spill, reject, or drop.
- Incremental parsing must handle records split across chunks; never assume a
  chunk is a logical record.
- Define partial-output behavior on failure: discarded, retained, marked
  incomplete, or committed atomically at the end.
- Trace copy chains (kernel -> buffer -> parser buffer -> owned value -> output
  buffer) and remove unnecessary ones. Flush deliberately for interactive output,
  protocols, and durable files.
- Bound decompression and other expansion that external input controls.
- Test awkward chunk boundaries: one byte at a time, at delimiters, inside
  multibyte encodings, and at the header/body boundary.

### Migration and compatibility policy

Do not create parallel legacy and canonical implementations as part of this work.
If a rename, move, replacement, or contract change becomes necessary, inventory all
references first, keep one canonical path, and retain compatibility only when the
invoking request or an existing external contract requires it.

## Explicit anti-patterns

Do not:

- replace every vector with a hash map, or assume hash structures are always faster
- optimize tiny bounded collections for asymptotics
- eliminate every clone mechanically, or use reference counting by default
- stream everything mechanically, or buffer an unbounded "stream"
- read arbitrary external input fully into memory
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
- collections match their dominant operations, and accidental quadratic work is removed where material
- ownership of important data is clear, and significant avoidable clones and representation conversions are reduced
- large or unbounded inputs are identified, streamed where it materially helps, and buffered within explicit bounds
- representative performance does not regress
- correctness and public behavior remain intact

The architectural principle is: **the fastest operation is usually the one you stop doing.**
