# Performance and dependency checks

Dependencies are your call. Vet maintenance, transitive weight, license, and whether the standard library or a few lines would do, and say why in your reply. A dependency must stay within the project's performance gates (build time, binary size, startup, runtime); measure when it could move one. If the repo defines no gates, state the build-time and binary-size impact. Remove ones you stop using.

Time-based perf gates (build time, startup, runtime) prefer a quiet host. Check `perf-gate-ready` once; when it exits 0, measure and rerun it with `-1` right after, discarding a run that overlapped load. When it reports busy, do not wait for it: decide the claim with busy-host evidence instead. Memory and binary-size gates always run. Prefer CPU time for compute cost, use a statistic suited to the claim (median for typical latency, a tail percentile for tail behavior, minimum only for best-case behavior), and interleave baseline and candidate runs. Fail only on a regression larger than the observed spread.

## Busy-host evidence

Contention slows the baseline and candidate together when you run them in the same session. So ratios and work counts still decide many claims on a loaded host.

- **Scaling ratio.** For an asymptotic claim, such as quadratic to linear, time each side at 1x and kx input, interleaved, and compare the kx/1x ratios. Load changes the absolute times, not the shape. For example, a ratio of 12x for the baseline against 1.9x for the candidate at 4x input decides the claim.
- **Paired A/B.** Interleave at least 5 baseline/candidate pairs in one session, using CPU time (user plus system) rather than wall time. Judge the per-pair ratio. Accept an improvement, or reject a regression, only when the effect exceeds both the observed spread and 10%.
- **Load-independent measures.** These are valid on any host: work counters (operations, nodes, bytes, calls), allocation counts, peak RSS, syscall counts, instruction counts where available, and artifact size.
- **Test-suite cost budgets.** Compare the durations the test runner reports for the affected suite before and after, measured in the same session.

Busy-host evidence counts as a pass, labelled "busy host: paired ratio" or "busy host: scaling ratio" in the reply. The gate stays deferred only for claims those measures cannot decide: an absolute latency or throughput number, a tail percentile, or an effect smaller than 10% or within the spread. That deferral blocks a release that depends on the number, but not merging or completing other work. Say "perf gate deferred: host busy" and name the claim left undecided.
