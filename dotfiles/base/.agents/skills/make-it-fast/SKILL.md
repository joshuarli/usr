---
name: make-it-fast
description: "Apply when asked to make something faster or leaner, fix a slowdown or memory growth, or find where time and resources go. Skip isolated benchmark reviews and non-performance changes."
---

# Make It Fast

Optimize the work users experience, and the fastest operation is the one you stop doing. A faster inner loop matters only if it improves a relevant workflow or resource constraint.

## Establish what matters

- **Choose outcomes before counters.** Read the entry points, architecture, existing performance checks, and local instructions. Pick one primary outcome (completion time, startup, responsiveness, tail latency, throughput, memory, I/O, build time, or artifact size) and the one or two other costs the change could worsen. Do not benchmark every dimension.
- **Use representative work.** Prefer existing real workloads or fixtures with realistic size, skew, and concurrency, including a common case and a materially different demanding case when they behave differently. If real data is unavailable, use a bounded fixture and qualify conclusions; ask only when the missing workload changes which outcome to optimize.
- **Define successful completion.** Name where the measured workflow starts and ends, the input, the expected output, the production configuration, and warm or cold state. Count completed useful work and failures, including startup, queueing, and persistence when users pay for them. A fast rejection, partial result, or omitted durability step is not a speedup.

## Find and rank the limiting work

- **Baseline before editing.** Reuse the project's harness and production build settings, with a comparable workload and environment. Confirm that the measurement changes when useful workload changes and that it counts completed work. Prefer a short reproducible command over a new benchmark framework.
- **Rust harness:** the standard [rustybench](https://github.com/laputa-systems/rustybench): a dev dependency, `harness = false` targets, `#[rustybench::bench]`, and `rustybench::main()`. Reuse existing targets, check the installed version and CLI, and validate fixtures, sample counts, and timed regions against the representative workload.
- **Profile separately from timing.** Tell CPU work from storage or network waits, allocations, synchronization, queueing, and scheduling. A CPU hotspot does not explain an I/O-bound workflow. Profiling overhead stays outside reported timings.
- **Prioritize by attainable impact.** Ground each hypothesis in an observed mechanism. Name its share of the critical path or limiting resource, expected benefit, and correctness or maintenance cost. Recheck the limiter after each improvement because it moves.

## Remove the work

- **Remove work before speeding it up:** fewer passes, queries, syscalls, copies, and serializations, and no parse-stringify-parse cycles. Batch across expensive boundaries only while latency, memory, and failure semantics stay acceptable.
- **Fit the structure to the operations.** A lookup inside a loop over the same data is a quadratic scan: index it, sort once at the ownership boundary, use a set for membership. A derived index is derived state with an owner and an invalidation. Bound recursion and traversal against cycles and adversarial input. Keep clear code until a measured N says otherwise.
- **Ownership before cleverness.** Know who owns, who borrows, and why anything is shared (`Rc`, `Arc`). Remove a clone only if the lifetime stays simple, prefer slices and views for read-only access, and pool buffers only where measured. Never reach for `unsafe` to save an allocation.
- **Large input flows through, it does not pile up.** Classify each input as small, large, or unbounded; stream the last two with bounded buffers and a chosen backpressure policy (block, reject, spill, drop). Never assume a chunk is a record, and bound decompression that external input controls. Test at awkward boundaries: one byte at a time, at a delimiter, inside a multibyte character.
- **A cache needs a measured cost, a named authority, and an invalidation.** Add caches, parallelism, pooling, or dependencies only when evidence supports their costs.

## Verify

- **Preserve behavior.** Keep observable behavior, failure semantics, and resource bounds, and surface any proposed contract change before relying on it for gains. Check the changed behavior with focused correctness tests, then rerun the original workflow and the cases likely to regress. Compare outputs or invariants, not exit status.
- **Shrink the loop, not the claim.** Use the smallest workload that retains the mechanism. A microbenchmark can separate hypotheses after profiling but cannot replace representative validation.
- **Compare fairly.** Vet every number with [benchmark-checklist](../benchmark-checklist/SKILL.md) before acting on or reporting it. Report elapsed time for waiting and CPU time for compute cost.
- **Account for tradeoffs.** Check the other costs chosen above, including memory and artifact size. Reject changes whose representative benefit is within noise or whose costs outweigh it. An isolated win with no demonstrated workflow benefit remains an experiment.

## Run a sustained optimization loop

Make one attributable change at a time and compare it with the unchanged baseline, same workload and measurement method; keep or reject it before testing the next hypothesis. If the baseline or measurement is invalid, repair it separately, remeasure both sides, and discard every affected comparison. Never change the workload or acceptance rule to manufacture a win. Keep a change when correctness holds, the benefit is reproducible, and tradeoffs meet the project's constraints. Stop when the outcome is met or remaining hypotheses do not justify their cost. If measurement is blocked, report what is known and what is missing; do not invent a speedup.

**The test:** name the user outcome improved, the work removed or limiter relieved, and the representative evidence connecting them. If you can name neither the work nor the measurement, you have not optimized anything.

**Report:** what changed; baseline and candidate results with units, workload, configuration, run count, and spread; the limiting mechanism and tradeoffs; what was verified, deferred, or left unmeasured. Distinguish observed gains from predictions.
