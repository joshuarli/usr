# Performance, memory and host validity

Read when adding or changing resource checks. Apply only metrics that matter to the target contract; do not bolt microbenchmarks onto every component.

## Define the claim before measuring

Pin the workload, required completed work and correctness oracle, candidate/reference artifacts, inputs, toolchain/profile, concurrency, cache regime, metric scope and existing budget. Validate output, exit/error behavior and completed/reused counts before interpreting speed. Faster incomplete work is a failure.

Separate compile/setup time from runtime unless end-to-end iteration is the intended metric. Preserve debug, checked and optimized profiles where their behavior matters. Keep diagnostic instrumentation separate from accepted uninstrumented timing. A profiler's overhead is not a candidate regression.

Choose cheap deterministic evidence for Edit where possible: operations, allocations/bytes, graph visits, syscall counts or growth across controlled input sizes. Use counters only if they track a real resource contract; they do not prove elapsed-time performance. Selected Change gates can add controlled timing and memory. Expensive realism belongs to explicitly named scenarios or manual Full.

Reference comparisons have two purposes. Candidate versus an accepted version detects the project's regressions. Candidate versus another implementation describes comparative performance, only on matched semantics and completed work. Record unsupported behavior and output differences instead of rewarding doing less.

## Timing and budgets

- Preserve existing hard limits. Where no limit exists, measure representative variance and establish a provisional proposal; do not present a generic percentage as an established project requirement.
- Define practical relative tolerance and, where appropriate, an absolute floor for small timings. State how those combine. Keep strict resource caps distinct from a noisy timing comparison.
- For short workloads, use a predeclared bounded sequence of interleaved baseline/candidate pairs, consistent warmup and cache treatment. Balance or randomize order to reduce drift; record the order. Choose the sampling/stopping rule before seeing the result.
- Compare the paired observations with an uncertainty method appropriate to the data and sample size. Report **within budget**, **regression**, or **inconclusive**. An estimate near a threshold with unresolved uncertainty is not a pass. A tiny sample cannot support a tail-percentile claim.
- Bound retries and total cost. If noise remains, defer or request the specifically needed scenario; never rerun until green, cherry-pick favorable samples or widen to Full.
- Expensive manual runs may provide observational evidence with explicit uncertainty rather than a statistically decisive gate. Keep that limitation visible.
- Retain a nearby comparison baseline for attribution and an accepted longer-lived anchor for cumulative drift. Promote baselines/budgets only through the project's explicit acceptance process; the candidate cannot silently bless itself.

For cache-sensitive workloads, name the layer: process state, OS page cache, build outputs, package/object store or remote cache. “Cold” without that definition is not reproducible. Do not drop system caches or alter machine policy as a routine measurement step. Use isolated fixtures or disclose the uncontrolled layer.

For parallel jobs, wall time minus summed child durations is not orchestration overhead: children overlap. Use an appropriate no-op/planning witness, critical-path analysis or direct measurements. Record configured and effective parallelism, completed work and reuse.

## Host readiness and contention

Use the repository's existing host gate or resource reservation first. If it specifies `perf-gate-ready`, follow its pre/post-run protocol. Else use available platform telemetry; do not require Linux, containers, systemd, privileged controls or a new daemon.

1. **Coordinate owned work.** Use an existing lock/reservation or the smallest equivalent across agents/worktrees sharing the machine. Reserve relevant CPU, memory and I/O capacity; avoid overlapping compilation, indexing and timed work. A cooperative lock does not exclude unrelated host processes.
2. **Check before and during.** Record effective CPU set/quota and topology, runnable/CPU load, memory and swap pressure, I/O pressure, throttling/OOM events and frequency/thermal state where available. Capture a useful summary before/during/after, plus the resource allocation and missing telemetry. Raw load average alone does not establish readiness.
3. **Bound waiting.** If unavailable or busy, defer timing and continue useful correctness or applicable resource work. Report timing incomplete; do not claim release readiness when required evidence is missing.
4. **Attribute pressure.** External contention may invalidate timing. Pressure, oversubscription or OOM caused by the candidate can be the regression itself; do not throw it away as “host noise.” Retain the sample, work counters and diagnostics.
5. **Keep validity explicit.** Do not divide timing by host load or compare unmatched machines as if normalized. Compare like environments or report distinct tracks. Noisy-host observations may guide investigation without becoming accepted gate evidence.

Readiness tolerances must fit the host and workload. Do not hard-code a universal “load below N” policy. Missing isolation or telemetry lowers the strength of the claim and may leave a strict gate inconclusive.

## Memory requires a named scope

| Metric | What it establishes | Important limitation |
| --- | --- | --- |
| Allocation count/bytes | Allocation traffic or churn | Not retained memory or resident peak |
| Live/retained heap | State retained at a defined point | May omit allocator, runtime, mappings and children |
| Process RSS/peak | Residency of the measured process | Does not establish a concurrent workload-tree peak |
| Workload-tree or container/cgroup peak | Simultaneous memory charged to that scope | May include cache/kernel/shared charges; define what is included |
| Cache, disk or artifact size | Storage growth for that layer | A separate budget from RAM |

Do not sum child lifetime peaks or use the largest child peak as simultaneous tree memory. Do not report the container client process as the container workload. A batch peak is not a per-test peak.

Where available, use a fresh per-case workload scope, such as a suitable OS job/container or delegated Linux cgroup, and record the metric's accounting semantics. Preserve useful anonymous/file-cache breakdowns if the backend exposes them. Sampled process-tree RSS can miss short peaks and double-count shared pages; label it as an estimate and do not silently substitute it for a strict peak gate. If the required metric cannot be measured, say so.

Use small-to-large fixtures to reveal growth where scaling is the contract. Specify input size, concurrency, lifecycle point and whether warm caches are retained. Timeouts, memory limits and cleanup must include child work. An OOM or killed child cannot become a successful partial result.

Continue applicable memory, allocation and artifact-size checks when timing is deferred, but establish their own validity: shared-memory pressure, cache eviction or an uncontrolled measurement scope can affect them too.

## Record only evidence needed by a reader

Reuse native logs/artifacts. A trustworthy result needs the tested content/product/input identity, command and profile, selection and completion, samples with order, cache/concurrency conditions, metric scope, budget/reference and host-validity decision. Keep diagnostics sufficient to reproduce a failure or explain an inconclusive result.

Do not introduce a global ledger, dashboard or elaborate schema just to collect fields. Start with the existing report plus the minimal machine-readable data required by its actual consumer. A concise report must never hide missing measurements or rephrase uncertainty as success.
