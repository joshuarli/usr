---
name: make-it-fast
description: "Apply when asked to improve a project's performance across user workflows, investigate where time or resources go, or prioritize performance work. Skip isolated benchmark reviews and changes unrelated to performance."
---

# Make It Fast

Optimize the work users experience. A faster inner loop matters only if it improves a relevant workflow or resource constraint.

## Establish what matters

- **Choose outcomes before counters.** Read the relevant entry points, architecture, existing performance checks, and local instructions. Identify the workflows users wait for and the constraints that matter: completion time, startup, responsiveness, tail latency, throughput, memory, I/O, build time, or artifact size. Choose a primary outcome and the few other costs an optimization could worsen; do not benchmark every dimension by default.
- **Use representative work.** Prefer existing real workloads or fixtures with realistic size, distribution, skew, and concurrency. Include a common case and a materially different demanding case when they exercise different behavior. Generated inputs are useful only with an explanation of what they represent and omit. If real data is unavailable, use a bounded representative fixture and qualify conclusions; ask only when the missing workload changes which outcome to optimize.
- **Define successful completion.** Name the start and finish of the measured workflow, input, expected output, production configuration, and relevant warm or cold state. Count completed useful work and failures. Include startup, queueing, persistence, or asynchronous completion when users pay those costs. A fast rejection, partial result, or omitted durability step is not a speedup.

## Find and rank the limiting work

- **Baseline before editing.** Reuse the project's harness and production build settings. Keep workload and environment comparable. Honor local performance gates and host-readiness checks; a deferred gate is not a pass. Avoid privileged or disruptive cache flushing. Prefer a short reproducible command over a new benchmark framework.
- **Use the standard Rust setup.** For Rust projects, use the user's standard [rustybench](https://github.com/laputa-systems/rustybench) harness. Inspect `~/d/ish/Cargo.toml`, `~/d/ish/benches/bench.rs`, `~/d/ish/benches/undo.rs`, and `~/d/ish/Makefile` as examples: a dev dependency, `harness = false` targets, `#[rustybench::bench]`, `rustybench::main()`, allocation profiling where relevant, and baseline comparison or syscall inspection through the CLI. Reuse existing project targets and adapt only what the measured workflow needs. Check the available version, CLI arguments, and measurement boundaries; do not assume ish's sibling checkout path exists or copy its baseline. Fixtures, sample counts, and timed regions still need representative validation.
- **Profile separately from timing.** Trace the representative workflow far enough to distinguish CPU work, storage or network waits, allocations, synchronization, queueing, and scheduling. Observe competing processes and load-generator limits. Use attribution and work counts to explain elapsed time; do not assume a CPU hotspot explains an I/O-bound workflow. Profiling overhead belongs outside reported timings.
- **Prioritize by attainable impact.** Name each candidate's mechanism, share of the relevant critical path or limiting resource, expected benefit, and correctness or maintenance cost. Removing 10% of elapsed time cannot reduce total time by more than 10%. Rank a few supported opportunities and pursue the strongest within scope; do not turn an investigation into a repository-wide rewrite. Re-profile after an improvement because the limiter can move.

## Change and verify

- **Remove work first.** Apply [performance-by-mechanism](../performance-by-mechanism/SKILL.md) for implementation choices: fewer passes and boundary crossings, better data structures, and ownership before cleverness. Add caches, parallelism, pooling, or dependencies only when evidence supports their costs. Preserve observable behavior, failure semantics, and resource bounds; surface proposed contract changes before relying on them for gains.
- **Shrink the iteration loop, not the claim.** Use the smallest workload that retains the observed mechanism. A microbenchmark can distinguish hypotheses after profiling, but cannot substitute for representative validation. Check the changed behavior with focused correctness tests, then rerun the original workflow and the cases likely to regress. Compare outputs or invariants, not merely exit status.
- **Compare fairly.** Apply [benchmark-checklist](../benchmark-checklist/SKILL.md) before acting on or reporting numbers, subject to the project's measurement policy. Interleave baseline and candidate runs with equivalent cache state and enough repetitions to expose variation. Report the statistic appropriate to the outcome: elapsed time for waiting, CPU time for compute cost, and adequate samples for tail latency. Do not select only the fastest run to claim better typical or tail behavior.
- **Account for tradeoffs.** Check the other relevant costs selected above, including memory and artifact size when changed. Explain any latency-throughput, CPU-I/O, or speed-memory tradeoff. Reject changes whose representative benefit is within measurement noise or whose costs outweigh the gain. An isolated win with no demonstrated workflow or resource benefit remains an experiment.

## Stop with evidence

Keep a change when correctness holds, the relevant benefit is reproducible, and tradeoffs meet the project's constraints. Stop when the requested outcome is met or the remaining candidates lack meaningful attainable benefit. If measurement is blocked, report what is known and the missing evidence without inventing a speedup or calling an unverified change done. Keep only fixtures and measurement commands needed to reproduce useful results; avoid a permanent benchmark suite for every experiment.

**The test:** identify the user outcome improved, the work removed or limiter relieved, and the representative evidence connecting them.

**Reply:** what changed; baseline and candidate results with units, workload, configuration, run count, and spread; the limiting mechanism and tradeoffs; what was verified, deferred, or left unmeasured. Distinguish observed gains from predictions.
