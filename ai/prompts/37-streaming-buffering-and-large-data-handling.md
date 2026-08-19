# Streaming, Buffering, and Large-Data Handling

You are improving an existing codebase so large or unbounded data is processed incrementally, with explicit buffering, limits, backpressure, and partial-failure behavior.

The goal is to prevent accidental whole-input loading, unbounded buffering, repeated copies, and latency caused by waiting for complete datasets unnecessarily.

Preserve observable behavior unless streaming changes are explicitly intended.

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

## 1. Classify input size

For each input, determine whether it is:

- small and bounded
- potentially large
- unbounded/streaming

Do not introduce streaming complexity for tiny bounded data.

## 2. Stream across expensive boundaries

For large data, prefer incremental:

- file reads/writes
- HTTP bodies
- database row processing
- compression/decompression
- archive processing
- parsing

when the operation permits it.

## 3. Bound buffers

Every streaming buffer should have an intentional capacity/growth policy.

Do not accumulate chunks indefinitely merely because the API is asynchronous.

## 4. Preserve record/message boundaries

Incremental parsing must handle values split across chunks.

Never assume a chunk corresponds to a logical record.

## 5. Propagate backpressure

If consumers are slower than producers, define whether producers:

- block
- await
- spill
- reject
- drop

according to semantics.

## 6. Define partial-output behavior

If processing fails after producing output, determine whether partial results are:

- discarded
- retained
- marked incomplete
- atomically committed at end

## 7. Avoid copy chains

Trace data movement across:

```text
kernel -> buffer -> parser buffer -> owned value -> output buffer
```

Remove unnecessary copies where simple.

## 8. Flush deliberately

Output flush semantics matter for:

- interactive tools
- protocols
- durable files
- pipelines

Do not flush every tiny write without reason; do not indefinitely buffer user-visible progress.

## 9. Bound decompression and expansion

Compressed or encoded input may expand dramatically.

Enforce limits where external input controls expansion.

## 10. Test chunk boundaries

Tests should intentionally split input at awkward boundaries:

- one byte at a time
- delimiter boundary
- multibyte encoding boundary
- header/body boundary

## Explicit anti-patterns

Do not:

- stream everything mechanically
- buffer unbounded "streams"
- assume chunk boundaries equal records
- read arbitrary external input fully into memory
- add copy-heavy adapter layers
- ignore partial-output semantics
- let decompression expansion go unbounded

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
