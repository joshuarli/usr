# Memory Ownership, Allocation, and Lifetime Audit

You are improving this codebase so memory ownership is clear and avoidable allocation, copying, retention, and lifetime extension are reduced.

The goal is to make memory cost proportional, ownership obvious, and large/long-lived data intentional.

Scope: large allocations, clones/copies, conversions, buffers, caches, shared ownership, captured data, streaming opportunities, and peak retention.

Applicability: Apply this prompt only when memory cost, allocation churn, retention, or ownership complexity is material to the subsystem. If the condition is materially absent, report that evidence and make no speculative changes.

Preserve: Existing valid behavior, public contracts, persisted data and formats, output, side effects, permissions, state transitions, and supported-platform semantics unless this request explicitly changes them.

Intentional changes: Only changes explicitly authorized by the invoking request; otherwise none.

If inspection shows that the relevant contract already holds, do not manufacture
changes. Verify it, correct only concrete gaps, and report the evidence.

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

- Record failures that predate the work.

## Non-negotiable design

Each numbered requirement defines an invariant or observable behavior, its
authoritative owner or boundary, the shortcut or ambiguous state it prohibits,
and the evidence that proves it. Do not prescribe incidental implementation
structure unless that structure is itself part of the contract.

### 1. Make ownership clear and remove significant representation churn

#### Make ownership obvious


For important data, determine:

- who creates it?
- who owns it?
- who borrows/views it?
- when may it be freed?
- why is shared ownership required?

Avoid shared ownership merely to simplify signatures.

#### Remove accidental clones


For each significant clone/copy, ask whether it is:

- required for ownership
- required for isolation
- small and harmless
- avoidable with borrowing/moving/reference semantics

Do not eliminate tiny copies at the cost of complex lifetimes.

#### Avoid repeated representation changes


Look for:

```text
bytes -> string -> bytes
owned -> borrowed -> owned
JSON -> map -> JSON
```

Keep data in the representation consumers actually need.

### 2. Bound buffers and prevent unintended retention

#### Bound buffers and growth


For buffers/collections fed by external or unbounded input, define:

- expected size
- maximum size where appropriate
- growth behavior
- truncation/backpressure policy

#### Avoid retaining large object graphs


Inspect caches, queues, closures, async tasks, callbacks, and global registries for references that unintentionally keep data alive.

### 3. Use shared ownership and borrowed views deliberately

#### Use shared ownership intentionally


Reference counting/shared pointers are appropriate when ownership is genuinely shared.

Do not use them as a universal escape hatch around ownership design.

#### Prefer slices/views for read-only access


When callers need only a view, avoid forcing allocation of a new owned object.

Use idiomatic zero-copy representations when they remain simple.

### 4. Reuse storage only where measured and account for peak memory

#### Reuse buffers selectively


Reuse can help hot loops and I/O paths.

Do not introduce pools or complex buffer management without measurement.

#### Audit peak memory, not only total allocation


A system can allocate efficiently yet retain too much simultaneously.

Consider:

- concurrency
- queue depth
- batch size
- decompression
- parallel file reads
- fan-out

### 5. Keep unsafe memory optimization exceptional


Do not introduce unsafe code merely to avoid allocation unless the measured gain clearly justifies the new correctness burden.

### Migration and compatibility policy

Do not create parallel legacy and canonical implementations as part of this work.
If a rename, move, replacement, or contract change becomes necessary, inventory all
references first, keep one canonical path, and retain compatibility only when the
invoking request or an existing external contract requires it.

## Explicit anti-patterns

Do not:

- eliminate every clone mechanically
- create lifetime-heavy APIs for negligible savings
- use reference counting by default
- add object pools without measurement
- load unbounded data eagerly
- hide memory growth behind queues/caches
- use unsafe code for speculative gains


## Verification

After editing:

- Run the nearest hard judge for large allocations, clones/copies, conversions, buffers, caches, shared ownership, captured data, streaming opportunities, and peak retention: the compiler, type checker, schema/build check, or focused tests that can reject an invalid change.
- Test the observable success behavior, failure behavior, edge cases, and invariants established by the numbered requirements.
- Audit ownership/lifetime, significant clones, representation churn, buffer bounds, retained graphs, shared ownership, views, reuse, and peak memory; classify every remaining exception rather than assuming it is harmless.
- Broaden checks only when the changed boundary warrants it, and distinguish pre-existing failures from regressions introduced by this work.

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
