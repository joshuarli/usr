# Memory Ownership, Allocation, and Lifetime Audit

You are improving an existing codebase so memory ownership is clear and avoidable allocation, copying, retention, and lifetime extension are reduced.

The goal is not allocation-free code. The goal is to make memory cost proportional, ownership obvious, and large/long-lived data intentional.

Preserve behavior and safety.

## First inspect the repository

Before editing:

- inventory large allocations and buffers
- identify repeated clones/copies
- identify string/byte conversions
- identify collection growth patterns
- identify long-lived caches and retained graphs
- identify reference-counted/shared ownership
- identify arenas/pools
- identify large values captured by closures/tasks
- identify data loaded fully when streaming would suffice
- inspect profiles/allocation metrics where available
- run baseline tests and benchmarks

## 1. Make ownership obvious

For important data, determine:

- who creates it?
- who owns it?
- who borrows/views it?
- when may it be freed?
- why is shared ownership required?

Avoid shared ownership merely to simplify signatures.

## 2. Remove accidental clones

For each significant clone/copy, ask whether it is:

- required for ownership
- required for isolation
- small and harmless
- avoidable with borrowing/moving/reference semantics

Do not eliminate tiny copies at the cost of complex lifetimes.

## 3. Avoid repeated representation changes

Look for:

```text
bytes -> string -> bytes
owned -> borrowed -> owned
JSON -> map -> JSON
```

Keep data in the representation consumers actually need.

## 4. Bound buffers and growth

For buffers/collections fed by external or unbounded input, define:

- expected size
- maximum size where appropriate
- growth behavior
- truncation/backpressure policy

## 5. Avoid retaining large object graphs

Inspect caches, queues, closures, async tasks, callbacks, and global registries for references that unintentionally keep data alive.

## 6. Use shared ownership intentionally

Reference counting/shared pointers are appropriate when ownership is genuinely shared.

Do not use them as a universal escape hatch around ownership design.

## 7. Prefer slices/views for read-only access

When callers need only a view, avoid forcing allocation of a new owned object.

Use idiomatic zero-copy representations when they remain simple.

## 8. Reuse buffers selectively

Reuse can help hot loops and I/O paths.

Do not introduce pools or complex buffer management without measurement.

## 9. Audit peak memory, not only total allocation

A system can allocate efficiently yet retain too much simultaneously.

Consider:

- concurrency
- queue depth
- batch size
- decompression
- parallel file reads
- fan-out

## 10. Keep unsafe memory optimization exceptional

Do not introduce unsafe code merely to avoid allocation unless the measured gain clearly justifies the new correctness burden.

## Explicit anti-patterns

Do not:

- eliminate every clone mechanically
- create lifetime-heavy APIs for negligible savings
- use reference counting by default
- add object pools without measurement
- load unbounded data eagerly
- hide memory growth behind queues/caches
- use unsafe code for speculative gains

## Acceptance criteria

The work is complete only when:

- ownership of important data is clear
- significant avoidable clones/copies are reduced
- repeated representation conversion is minimized
- externally driven buffers are bounded where necessary
- shared ownership is justified
- long-lived references do not retain unintended object graphs
- peak-memory contributors are understood
- buffer reuse exists only where useful
- safety and readability remain strong

The architectural principle is: **memory should remain owned for exactly as long as the program needs it, in the representation it actually uses.**
