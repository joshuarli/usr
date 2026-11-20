---
name: refactor-benchmarks
description: "Apply when benchmarks are synthetic, overly micro, disconnected from real-world usage, or measuring trivial loop overhead instead of user-facing workflows. Restructure benchmarks around representative workloads, realistic fixtures, macro user journeys, and allocation tracking. Skip non-benchmark tests and isolated timing runs."
---

# Refactor Benchmarks

A benchmark is a claim about how real software performs under real use. Micro or synthetic benchmarks mislead: they measure loop unrolling, early-exit guards, mock closures, or cache hits that never occur in production, and they miss the allocation churn, I/O, and data complexity users actually feel. Reshape the suite around the workflows users wait on and the inputs they actually send.

## Principles

1. **User workflows over micro-loops.** Measure what users wait on or systems pay for, end to end through the production path. An editor opens a file, types with live highlighting, scrolls, and searches. A service handles a realistic request mix at realistic concurrency. A CLI runs its common commands on a real tree. A library runs the call sequence its main consumers make. Never benchmark an isolated getter, a boolean check, or a single-branch return.
2. **Representative fixtures over synthetic generators.** Replace generators that repeat a few canned lines or records with real or realistically varied data: real source, configs, payloads, or datasets, with natural sizes, nesting, encodings, and edge content such as UTF-8 or wide rows.
3. **Several realistic scales.** Cover the small, typical, and heavy inputs the project actually sees, with sizes taken from real usage, not round numbers.
4. **Track allocations as well as time** on hot steady-state paths such as a render frame, a request, or a keystroke: allocation count and bytes. Ask whether that steady state should allocate at all.
5. **No mock seams.** A benchmark that passes mock closures returning constants, or runs on an empty shell, measures the mock. Exercise the production pipeline.

## Method

1. **Audit.** Classify each benchmark as workflow-driven, a realistic micro-benchmark of a measured hot spot, or synthetic triviality. Flag sub-50 ns results, canned-line generators, and fake callbacks.
2. **Prune.** Delete benchmarks of trivial branches, constant-time reads, or mocks. Fold narrow micro-benchmarks into the workflow benchmark that exercises the same path, unless a profile shows that spot dominates a workflow.
3. **Assemble fixtures** from real or realistically varied data, committed or generated deterministically with a fixed seed.
4. **Write the workflow benchmarks** for the project's main user journeys, timing wall time and, on hot paths, allocations.
5. **Calibrate.** Keep setup and fixture generation outside the timed region. Prevent dead-code elimination (`black_box` or the language's equivalent) and confirm the work happened. Run through the project's existing harness.

Report any before-and-after numbers by [benchmark-checklist](../benchmark-checklist/SKILL.md).

**The test:** every remaining benchmark maps to a named user workflow or a profiled hot spot, runs on realistic data at a realistic scale, and fails to compile away.

**Report:** benchmarks pruned, added, or refactored, each with its workflow; fixture changes; timing and allocation deltas on representative workflows; and limiters found.
