---
name: audit-metrics
description: "Use for /audit-metrics: audit whether every quality users perceive (smoothness, responsiveness, reliability over time, throughput, efficiency) has a metric in user units, measured where the user perceives it, with a gate that can actually fail. Honors audit-only requests. Skip benchmark suite structure (use bench-pyramid) and vetting one number (use benchmark-checklist)."
disable-model-invocation: true
metadata:
  opencode/slash: "true"
  opencode/autoinvoke: "false"
---

# Audit Metrics

Find the user-perceptible qualities a product can lose without any check noticing. A regression users can feel but no metric reports is found late, by the owner, as "it feels laggy". Benchmarks that exist but measure the wrong place, in the wrong units, or behind a gate that never produces a verdict count as missing. [bench-pyramid](../bench-pyramid/SKILL.md) owns suite structure and the entrypoint; [benchmark-checklist](../benchmark-checklist/SKILL.md) owns vetting one number; [make-it-fast](../make-it-fast/SKILL.md) owns fixing what this finds.

## Scope and authority

- Default to **audit**: findings, then stop for selection. Implement only the items the owner picks, or all of them when the request says so.
- Run only cheap, existing measurements or a short probe that settles a suspicion. Full or manual-only suites stay manual-only.
- Extend the project's harnesses and result formats. No new framework, dashboard or results database.

## 1. List what users perceive

Start from the product's real journeys, not from the existing benchmarks. For each journey, name the qualities a person notices:

- **Smoothness:** how often visible state updates during continuous input or motion (positions or frames per second, the worst gap between updates).
- **Responsiveness:** input to the first visible effect, and to completion (p50 and p95, plus the tail a person remembers).
- **Reliability over time:** whether long sessions, runs or soaks keep working (time to first failure, completed runs per hour). Many defects only appear after tens of minutes.
- **Throughput:** useful work per unit time under realistic limits (pages, items or requests per minute), plus the wasted work per unit (retries, backoffs, rework) that explains a poor rate.
- **Efficiency:** CPU, memory, bandwidth or money per completed unit of work.
- **Correctness of output:** the fraction of results that pass an independent check (replay, verify, diff), not "the command exited 0".

Also read the owner's and users' recent complaints. Every complaint names a perceived quality; one with no metric is the first finding.

## 2. Check each quality's metric

For every quality from step 1, find the metric that covers it and check, with evidence from the code or a recorded result:

1. **User units.** It reports what the person perceives (positions per second, ms to visible effect), not a proxy (bytes sent, internal frames, CPU idle). A proxy can stay green while the perception degrades.
2. **Measured where perceived.** It spans the full path to what the user sees: the real client, transport and renderer. Where a stage is excluded (a test client instead of the real viewer, a direct path instead of the gateway), the exclusion is stated and the excluded stage is a gap. Per-stage counters exist so a regression can be located; an end-to-end number alone says only that something is slow.
3. **Realistic stimulus.** The input resembles real use: continuous pointer motion at device rate rather than one click, real pages rather than a solid fill, long runs rather than one minute. A stimulus that cannot trigger the defect class proves nothing about it.
4. **A gate that can fail.** A budget exists, and the gate has produced a pass or fail verdict on a recent revision. Look for gates that never fire: always `inconclusive` because the host is never quiet enough, budgets tied to one host so others cannot fail, tiers nobody runs, results that print a failing number while the run reports success. A gate with no verdict for weeks is a missing gate.
5. **Someone reads it.** A failing number reaches a person: a nonzero exit, a release block, a ticket. A number that is only written to a file is unread.

Run a short probe only when the code cannot settle a point. For example, a reported lag with no measurement needs the metric written first; the measurement then locates the cause.

## 3. Report and stop

Give each gap a number, the quality and journey it affects, the evidence (file and line, or the recorded result that shows the gate never fired), what a regression would look like to a user, and the smallest metric or gate change that closes it: the stimulus, the unit, where it is measured, the budget, and how it fails. Rank by how badly users would feel the regression and how likely it is to land unnoticed. Merge gaps with one root cause, such as a gate mechanism that never yields verdicts.

**The test:** another agent can name, for each quality users perceive, the metric that would turn red if it regressed, and show that the metric has actually turned red or green recently.

**Report:** the journeys and qualities audited; a table of quality, metric, units, measured path, budget and last verdict; the numbered gaps from most to least harmful with evidence and the proposed fix; what you observed versus inferred; and what you did not inspect or run. End by asking which gap numbers to fix. Do not start fixes in the same turn unless the request authorized them.
