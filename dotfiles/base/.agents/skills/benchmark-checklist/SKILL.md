---
name: benchmark-checklist
description: "Apply before you report or act on a measured speedup, regression, throughput, latency, or benchmark result, including choosing a library or config from one. Vet the number against seven questions first. Skip results you are not reporting or acting on."
---

# Benchmark Checklist

A number is a claim about work. Answer each question with evidence from a run, not a guess about the code.

A ballpark the user asked for needs one run: still answer questions 4 and 7, and say it was one run. Choosing between options is never a ballpark.

## Before running

- Write the sentence you expect to ship ("export is 30% faster at p50 on the 60k-row set"). The questions test that sentence.
- Read the measurement script. Note what it times, counts, and ignores.
- Check machine load (`uptime`) and core count (`sysctl -n hw.ncpu` or `nproc`). If the machine is busy, find the cause. If you cannot stop it, interleave the sides and say so.

## The questions

1. **Why not double?** Name the limiter. Profile in a run you do not report, since profilers slow the work. Use per-process CPU (`top`), a profiler (`perf`, `samply`, `cargo flamegraph`, `py-spy`, `node --cpu-prof`), I/O wait, and syscall counts. If the load generator saturates first, you measured the load generator.
2. **Was it tuned?** Run every side the way production runs it: release builds, production flags and environment, pooling, batching, warm or cold caches as in production, same versions and data. A side on defaults means you compared configurations, not implementations. Tune it and measure again before naming a winner.
3. **Did it break limits?** Do the arithmetic against disk and network bandwidth, core count, and the share of the run the changed piece takes. Removing a piece that takes 10% of the run makes it at most about 11% faster. A result past a limit measured something else: a cache, a no-op, a bug.
4. **Did it error?** Count failures and non-success responses, and check that outputs are correct, not just present. Rejections are fast; timeouts and retries are slow.
5. **Does it reproduce?** Run each side at least 5 times, alternating A, B, A, B so warmup and drift favor neither. Report the median and range. A gap inside the run-to-run variation is no measurable difference.
6. **Does it matter?** Put the micro result beside the end-to-end path a user waits on, with realistic sizes and concurrency, and report it as a share of the whole.
7. **Did the work happen?** Confirm it ran inside the timed region: the rows were written, the bytes were read, the result was used. Lazy iterators, unawaited futures, and discarded results produce numbers for work that never ran.

## Report

Lead with the verdict: faster, slower, no measurable difference, or inconclusive. Give the number with unit, run count, range, and limiter ("p50 41 ms to 33 ms, median of 7 runs per side, range 32 to 35 ms, bound by JSON parsing on one core"). Call it inconclusive when you cannot name the limiter, a side ran untuned, or you could not answer 4 and 7, and name the gap.
