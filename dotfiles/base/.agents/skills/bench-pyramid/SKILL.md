---
name: bench-pyramid
description: "Use for /bench-pyramid: audit a project's benchmarks and profiling for representative workloads, metric coverage and observability, then give it one full-suite entrypoint with a preflight and tiered selective runs. Honors audit-only requests. Full runs stay manual-only."
disable-model-invocation: true
metadata:
  opencode/slash: "true"
  opencode/autoinvoke: "false"
---

# Bench Pyramid

Make a project's benchmarks answer real performance questions. They should run representative work, measure the metrics users and operators pay for, and explain a regression when one appears. One entrypoint should check readiness before spending time, then run the full suite or just the tier a change needs. This skill applies [test-pyramid](../test-pyramid/SKILL.md)'s tiers, manual-only Full and [measurement validity](../test-pyramid/references/measurement.md) to benchmarks. Vet numbers with [benchmark-checklist](../benchmark-checklist/SKILL.md), reshape micro suites with [refactor-benchmarks](../refactor-benchmarks/SKILL.md), and leave optimization to [make-it-fast](../make-it-fast/SKILL.md).

## Scope and authority

- Default to **audit and improvement** of the named project or area. An **audit-only** request stops at findings. Session scope still controls commits, installs, external services and costly runs.
- **Full is manual-only.** Run the full suite only when the user asks for that run. Building or fixing the entrypoint does not authorize running it, and neither does a flag or a TTY.
- Extend the project's existing harnesses, task runner and result formats. Add a small native or standard-library driver, not a framework, dashboard or results database.

## 1. Audit what the suite can tell you

Read the harnesses, their fixtures, the result files and how results are judged. Run only cheap, existing preflight or self-test commands to confirm a suspicion.

1. **Outcomes before benchmarks.** List the outcomes users wait on and the resources the project pays for: named journeys, startup, throughput, tail latency, CPU per completed task, memory footprint, I/O, bandwidth, artifact size. For each, name the benchmark that covers it with a realistic workload, a correctness oracle and a completed-work check. An outcome covered only by microbenchmarks, synthetic fixtures or an unchecked result is a gap. Keep a micro benchmark only where it pins a contract a real workload depends on and the workload is too noisy to resolve it.
2. **Metric quality.** For each metric, check its scope against the measurement reference: what process tree, cgroup or VM it charges, and what it omits. Check the statistic and sample count, interleaving with the reference, host gating, and the anchor a regression is detected against. Gates written for an earlier architecture, runtime or data size are findings: show the regression they would let through.
3. **Observability.** For each primary outcome, ask whether a regression could be attributed with the tools the project has. Cover CPU sampling across every process and guest involved, allocation or footprint attribution, I/O and syscall counts, traces with operation boundaries, and protocol or byte counters. Note each tool's overhead, and keep instrumented runs separate from timed ones. An outcome with no attribution path is a gap. Name the cheapest instrument that would close it.
4. **Operability.** Find where a run fails late: prerequisites discovered minutes in, defaults that do not match a real checkout, stale binaries or images, leftover processes from earlier runs, unpinned fixtures, unavailable external services. Check that each result records its inputs (commit, dirty state, artifact identities, host conditions), that cleanup is verified, and whether anything fails when a number regresses, or only a reader would notice.

Rank findings by the risk of a missed or false regression, then by wasted iteration time. In improvement mode, fix what the entrypoint needs and file the rest through the project's backlog.

## 2. Assign each workload a tier

| Tier | Benchmark evidence | Typical cost |
| --- | --- | --- |
| **Edit** | The harness's own tests: parsing, accounting, gates, cleanup. Deterministic counters where a contract exists | Seconds |
| **Change** | One short round of each real workload a change touches, plus lifecycle and resource checks on production paths | Minutes |
| **Scenario** | Multi-round real workloads with interleaved reference comparison and the project's host gate | Tens of minutes |
| **Full** | Everything: sustained, density, external-target and matrix workloads | Manual request only |

Record each workload's name, tier, area, purpose (the outcome it serves), estimated cost labelled as estimated or observed, requirements, command and output location. Reuse the harnesses' own round, sample and gate options instead of reimplementing them.

## 3. Give the suite one entrypoint

- **Commands.** Use the project's task runner, for example `make bench` for the full suite. Add `bench-check` for the preflight alone, `bench-list` for the registry, and a side-effect-free dry run that prints the commands.
- **Selectors.** Add a tier ceiling, workload names, areas, and skips. Keep names and areas distinct, or say which one a selector takes. An unknown name, or a selection that matches nothing, is an error, never an empty pass.
- **Preflight first.** For the selected workloads only, check the tools and versions, built artifacts fresh against their sources, fixtures at their pinned revisions, external services, free disk, and leftover processes from earlier runs. Report host readiness as information. Each failure names the problem, the fix and the workloads that need it, and nothing runs. Stale inputs that are expensive to rebuild, and may be intentional, become a visible warning that names them, not a silent pass.
- **Run and report.** Give each run its own dated directory with per-workload logs and outputs. Write a summary with each workload's exit status, duration, timing validity (samples the harness discarded, or busy-host runs labelled as such; a busy host still runs the selection and its paired or scaling ratios, see [busy-host evidence](../../instructions/performance.md#busy-host-evidence)) and every exclusion with its reason, including platform-unsupported workloads. Exit nonzero on any failure. Where budgets exist, report each workload as within budget, regression or inconclusive. Where budgets do not exist, say that completion is not a performance verdict.
- **Document it.** Put the exact commands, tiers, selectors, prerequisites, run cost and the manual-only rule in the project's performance doc.

## 4. Prove the entrypoint narrowly

Test the selection rules: the tier ceiling, names against areas, unknown and empty selections, and visible exclusions. Run the preflight with one requirement deliberately unmet and check that nothing runs. Check that the dry run writes nothing. Run the Edit tier, and one Change workload for each kind of harness, end to end, and inspect its output for real measurements. Never run Full to test the guard.

**The test:** another agent can run `bench-check`, pick the smallest tier or workload covering a change, and get a result whose timing validity and coverage gaps are visible. When a number moves, it can find the instrument that explains it. It cannot launch the full suite by accident.

**Report:** the audit verdict (coverage matrix gaps, stale gates, observability and operability findings, ranked) with the tickets filed. List the entrypoint commands, the selection and preflight behavior, and the exact checks run with their observed costs. Name the workloads and tiers not run, and the smallest next action.
