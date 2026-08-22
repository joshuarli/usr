# Streaming, Buffering, and Large-Data Handling

You are improving this codebase so large or unbounded data is processed incrementally, with explicit buffering, limits, backpressure, and partial-failure behavior.

The goal is to prevent accidental whole-input loading, unbounded buffering, repeated copies, and latency caused by waiting for complete datasets unnecessarily.

Scope: large/unbounded files, bodies, database results, archives, parsers, buffers, streaming pipelines, flushes, and decompression/expansion.

Applicability: Apply this prompt only when the subsystem handles potentially large or unbounded data. If the condition is materially absent, report that evidence and make no speculative changes.

Preserve: Existing valid behavior, public contracts, persisted data and formats, output, side effects, permissions, state transitions, and supported-platform semantics unless this request explicitly changes them.

Intentional changes: Only changes explicitly authorized by the invoking request; otherwise none.

If inspection shows that the relevant contract already holds, do not manufacture
changes. Verify it, correct only concrete gaps, and report the evidence.

## First inspect the repository

Before editing:

- identify `read_to_end`, `read_to_string`, whole-file loading, full response buffering, archive extraction, bulk parsing, large query materialization, and giant in-memory collections
- identify chained buffers/copies
- identify streaming APIs currently converted back into full buffers
- identify output buffering/flush behavior
- identify size limits
- identify partial-record/framing logic
- identify producer/consumer imbalance
- run memory/performance baselines where relevant

- Record failures that predate the work.

## Non-negotiable design

Each numbered requirement defines an invariant or observable behavior, its
authoritative owner or boundary, the shortcut or ambiguous state it prohibits,
and the evidence that proves it. Do not prescribe incidental implementation
structure unless that structure is itself part of the contract.

### 1. Classify data size and stream with bounded buffers where justified

#### Classify input size


For each input, determine whether it is:

- small and bounded
- potentially large
- unbounded/streaming

Do not introduce streaming complexity for tiny bounded data.

#### Stream across expensive boundaries


For large data, prefer incremental:

- file reads/writes
- HTTP bodies
- database row processing
- compression/decompression
- archive processing
- parsing

when the operation permits it.

#### Bound buffers


Every streaming buffer should have an intentional capacity/growth policy.

Do not accumulate chunks indefinitely merely because the API is asynchronous.

### 2. Preserve framing and propagate backpressure

#### Preserve record/message boundaries


Incremental parsing must handle values split across chunks.

Never assume a chunk corresponds to a logical record.

#### Propagate backpressure


If consumers are slower than producers, define whether producers:

- block
- await
- spill
- reject
- drop

according to semantics.

### 3. Define partial output while minimizing copy and flush overhead

#### Define partial-output behavior


If processing fails after producing output, determine whether partial results are:

- discarded
- retained
- marked incomplete
- atomically committed at end

#### Avoid copy chains


Trace data movement across:

```text
kernel -> buffer -> parser buffer -> owned value -> output buffer
```

Remove unnecessary copies where simple.

#### Flush deliberately


Output flush semantics matter for:

- interactive tools
- protocols
- durable files
- pipelines

Do not flush every tiny write without reason; do not indefinitely buffer user-visible progress.

### 4. Bound expansion and test adversarial chunk boundaries

#### Bound decompression and expansion


Compressed or encoded input may expand dramatically.

Enforce limits where external input controls expansion.

#### Test chunk boundaries


Tests should intentionally split input at awkward boundaries:

- one byte at a time
- delimiter boundary
- multibyte encoding boundary
- header/body boundary

### Migration and compatibility policy

Do not create parallel legacy and canonical implementations as part of this work.
If a rename, move, replacement, or contract change becomes necessary, inventory all
references first, keep one canonical path, and retain compatibility only when the
invoking request or an existing external contract requires it.

## Explicit anti-patterns

Do not:

- stream everything mechanically
- buffer unbounded "streams"
- assume chunk boundaries equal records
- read arbitrary external input fully into memory
- add copy-heavy adapter layers
- ignore partial-output semantics
- let decompression expansion go unbounded


## Verification

After editing:

- Run the nearest hard judge for large/unbounded files, bodies, database results, archives, parsers, buffers, streaming pipelines, flushes, and decompression/expansion: the compiler, type checker, schema/build check, or focused tests that can reject an invalid change.
- Test the observable success behavior, failure behavior, edge cases, and invariants established by the numbered requirements.
- Audit input-size classification, streaming boundaries, buffer bounds, record framing, backpressure, partial output, copy chains, flush policy, expansion limits, and chunk-boundary tests; classify every remaining exception rather than assuming it is harmless.
- Broaden checks only when the changed boundary warrants it, and distinguish pre-existing failures from regressions introduced by this work.

## Acceptance criteria

The work is complete only when:

- large/unbounded inputs are identified explicitly
- streaming is used where it materially improves behavior
- buffers are bounded
- chunk boundaries are handled correctly
- backpressure is explicit
- partial-output semantics are defined
- unnecessary copy chains are reduced
- flush behavior is deliberate
- expansion limits exist where required
- tests cover awkward incremental boundaries

The architectural principle is: **large data should flow through the program, not accumulate inside it by accident.**
