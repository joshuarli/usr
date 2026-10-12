---
name: performance-by-mechanism
description: "Use when improving performance by removing measurable work: repeated passes, queries, syscalls, copies, conversions, accidental quadratic scans, unbounded buffers, whole-input loading. Mechanism over folklore."
disable-model-invocation: true
---

# Performance by Mechanism

The fastest operation is the one you stop doing. Work on the scope named; sweep the whole repo only when asked.

- **Measure first.** Take a baseline on a representative workload and a release build. Use the metric the mechanism implies (wall time, allocations, syscalls, query count, peak memory). Vet every number with `benchmark-checklist` before acting on it.
- **Remove work before speeding it up:** fewer passes, queries, syscalls, copies, and serializations. Kill parse, stringify, parse cycles. Batch across expensive boundaries only while latency, memory, and failure semantics stay acceptable.
- **Fit the structure to the operations.** List each collection's dominant operations. A lookup inside a loop over the same data is a quadratic scan: index it. Sort once at the ownership boundary. Use a set for membership. Treat a derived index as derived state with an owner and an invalidation. Bound recursion and traversal against cycles and adversarial input. Keep clear code until a measured N says otherwise.
- **Ownership before cleverness.** Know who owns, who borrows, and why anything is shared (`Rc`, `Arc`). Remove a clone only if the lifetime stays simple. Prefer slices and views for read-only access. Reuse buffers or add pools only where measured. Never reach for `unsafe` to save an allocation.
- **Large input flows through, it does not pile up.** Classify each input as small and bounded, large, or unbounded. Stream the large and unbounded, with every buffer bounded and backpressure chosen (block, reject, spill, drop). Never assume a chunk is a record. Decide what partial output means on failure. Bound decompression and expansion that external input controls.
- **A cache needs measured cost, a named authority, and an invalidation.** Do not add one on intuition.

**The test:** name the work you removed and the measurement that shows it. If you can name neither, you have not optimized anything.

Test streaming at awkward chunk boundaries: one byte at a time, at a delimiter, inside a multibyte character. Keep correctness tests green and record the before and after numbers.

**Reply:** the removed work, before and after numbers with their limiter, and anything left unmeasured.
