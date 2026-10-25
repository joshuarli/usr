# Gate design

Read when changing ownership, selectors, execution, evidence reuse or reporting. Reuse the target's vocabulary and formats. This is a design checklist, not a required manifest schema.

## Choose layers by failure mode

A cheap pure test suits a domain invariant; a component test suits a public module contract; a boundary test needs the actual serialization, process, storage or network behavior at risk. Keep a few representative user journeys where the assembled system adds failure modes. Move redundant setup out of inner loops without replacing the only real boundary oracle with a mock.

For every proposed addition or deletion, answer: what observable wrong behavior would this detect, why would the assertion fail, and where is that contract otherwise covered? Use negative controls, properties, metamorphic relations or a trusted reference when appropriate. Validate reference semantics before treating it as an oracle. Snapshot volume and coverage percentage do not establish oracle strength.

Treat correctness, resource bounds, compatibility, statistical quality and release approval as different claims. A quality benchmark cannot substitute for error handling; a replay cannot establish fresh qualification.

## Minimal ownership model

Keep only fields consumed by selection, execution or reporting. Existing task definitions, test tags and build metadata may already provide them.

| Concern | Information the consumer needs |
| --- | --- |
| Identity | Stable component/workload identity and owned contracts |
| Selection | Relevant source/test/config/fixture/generated-input changes and bounded boundary witnesses |
| Execution | Exact native command/filter, required products, setup/cleanup and output oracle |
| Cost | Tier, time/resource ceiling, concurrency and platform/profile requirements |
| Measurement | Required metrics, scope, cache regime and applicable baseline/budget |
| Evidence | Selected/completed accounting, code/product/input identity and invalidation conditions |
| Authority | Whether the workload is manual-only and which invocation can request it |

Do not enumerate every discovered test in a parallel catalogue. Use the smallest maintainable component-level map and native test discovery. Add stronger machinery only after a real failure demonstrates the need.

Build graph reachability answers what to rebuild. Verification ownership answers which contracts need evidence. Neither a path heuristic nor historical coverage alone proves that an excluded test is irrelevant. Coverage can enrich mappings and expose missing edges. Reflection, runtime imports, plugins, generated files, shared fixtures and configuration need explicit treatment where they exist.

## Selection algorithm and failure behavior

1. Take the actual change set: working-tree edits, additions, deletions, renames and relevant staged changes, or the user-named revision range. A commit is not required for each iteration.
2. Resolve changed tests, owning contracts, shared dependencies and required bounded boundary witnesses. Record why each component/workload was selected.
3. Apply the permitted tier and resource ceiling **before execution**, including setup, transitive prerequisites and aliases. Explicitly show blocked required work.
4. Ask the native runner to discover exact cases. Freeze the intended selection for accounting; validate selectors before timing. Report discovery-time filters and intentional exclusions separately.
5. Build the smallest necessary products once, then execute compatible groups with the intended profile and environment.
6. Reconcile selected, started and completed cases and their outcomes. Report unresolved ownership, zero matches, missing cases, required skips, cancellation and timeout as incomplete or failing according to policy.

An optional unsupported-platform case can be legitimately excluded if that policy was declared up front. A newly skipped required case is a gap. A successfully reused correctness result must be labeled as reused, with its validity established. Never fabricate fresh runs.

For a shared low-level change, choose representative witnesses for its actual contracts and disclose remaining coverage. If the minimum sufficient set exceeds the budget, report the additional named work needed. Do not silently drop required checks to meet the budget.

## Manual Full must survive composition

The normal change selector must be unable to reach comprehensive workloads through an umbrella target, wildcard, dependency, fixture preparation or baseline command. Keep automatic and manual entrypoints distinct enough to inspect and enforce. A `--full` option may expose an explicit manual entrypoint; the planner must never supply it as a fallback.

Check nested scripts and task graphs, not just target names. Reclassifying a whole-workspace sweep as “Change” does not make it bounded. A manual run still needs exact workload, inputs, resource budget, cleanup and result scope. It does not authorize unrelated exhaustive work.

A focused boundary proof can use a fake full workload that writes a sentinel or fails if invoked. Exercise the automatic path and prove the sentinel is untouched or the plan is rejected. Do not use a real expensive run as a guard test.

## Reuse without stale evidence

Reuse compilation and fixtures when their actual inputs are unchanged. Prefer the build tool's dependency tracking; do not invent a universal content-addressed build system. Distinguish an artifact cache hit from a test result reuse and from a measurement.

Evidence validity depends on relevant code, transitive/generated inputs, fixture content, toolchain/profile/configuration, oracle and environment. Record enough provenance to establish these identities using existing mechanisms. Invalidate when a relevant dependency changes or validity is unknown. Dirty-tree evidence is acceptable if tied to the tested content; a revision name alone cannot identify it.

Keep baseline/candidate products immutable while they are compared. Ensure imports, shared libraries, scripts and fixtures do not drift through another agent's mutable checkout. Fresh measurements must execute; cached successes are not benchmark samples. Report build and fixture reuse separately from runtime.

Inspect stateful workload cache keys. If an executor changes but output reuse hides all execution, the run measures reuse, not rebuild performance. Use a disposable controlled store or explicit fixture invalidation to exercise the desired work. Never clear a user's real store just to force a benchmark.

## Examples of useful witnesses

These are choices, not mandatory suites.

| Change | Cheap relevant evidence | Explicit larger scenario |
| --- | --- | --- |
| Parser, evaluator or shared library | Exact regression, invalid inputs, representative consumer contract, allocation/work counter | Selected large real programs |
| Build/task scheduler | Deterministic small graph: dependency order, failure propagation, no-op and controlled incremental work, completed/reused counts | A named large build with pinned parallelism and inputs |
| CLI, filesystem or core utilities | Output/exit/error contract on empty, small, streaming and adverse fixtures; bounded memory growth | Large datasets or platform matrix |
| API, UI or service boundary | Domain test plus actual changed wire/storage/UI boundary and isolated state | A named real end-to-end journey or load profile |
| Reference-tool implementation | Normalized correctness on a shared supported subset; candidate versus accepted candidate resource checks | Upstream comparison on matched semantics and data |
| Stochastic model or simulation | Deterministic smoke/invariants, paired seeds for screening, explicit error accounting | Fresh locked confirmation or qualification |

A preview/dry-run graph and a real execution prove different things. No-op reuse, incremental change and clean build are different workloads. For probabilistic work, keep screening seeds/data separate from fresh confirmation, pin artifacts and preserve failures in denominators. Do not claim qualification from the data used to select a candidate.

## Concise results

Prefer a short native summary plus existing raw artifacts. Add a structured result file only when an actual caller needs it. Keep correctness, performance, memory, host validity and scope independently visible; aggregate status must preserve required incomplete evidence. Do not average away a regressing required metric.

Illustrative output; all numbers below are placeholders, not default budgets:

```text
SCOPE: Change / scheduler — INCOMPLETE; 43s total
TESTS: 18/18 required passed; 0 skips; build 12s, execution 27s
TIME: deferred — host I/O contention; no accepted comparison
MEMORY: workload-tree peak 82 MiB / 96 MiB budget — within budget
WORK: 24 tasks completed, 6 reused; expected outputs verified
HOST: CPU reservation held; external I/O pressure invalidated timing
NOT RUN: manual large-build and Full; no global acceptance claimed
NEXT: rerun scheduler timing when ready; exact command + evidence location
```

Lead with failures or incomplete required work, actual delta/budget and the smallest next action. Hide passing-case detail behind a result pointer. Preserve raw samples and diagnostics when they support a claim; avoid a mandatory telemetry service or permanent ledger.
