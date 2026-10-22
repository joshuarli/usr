---
name: test-heirarchy
description: "Use for /test-heirarchy: explicitly audit a repository's correctness, performance and memory verification costs, then use campaign-plan to design a change-selected, tiered campaign with manual-only full gates. Planning only."
disable-model-invocation: true
metadata:
  opencode/slash: "true"
  opencode/autoinvoke: "false"
---

# Test Heirarchy

An **explicit, repo-agnostic planning workflow**. Audit what each existing verification path proves, costs, and can accidentally invoke. Then apply [campaign-plan](../campaign-plan/SKILL.md), including its [campaign-preflight](../campaign-preflight/SKILL.md), to write **one executable campaign plan** for the target. Do not build another campaign format, test runner, or management framework.

## Authority

- Explicit-only: an audit request authorizes **investigation and a campaign document**, not implementation, commits, pushes, scheduling, dependency installation or expensive tests. Follow the target's AGENTS.md and existing correctness/release policy.
- **Full is manual-only** by default: global suites, exhaustive simulations, fresh world/release builds and qualification. No automatic launch through alias, dependency, fallback or escalation. Do not run Full as a baseline; owner-approved exceptions must name their target.
- Inspect commands' effects on HOME, network, shared stores, databases and outputs. Time only the cheapest safe authorized baseline, or mark it unmeasured and plan its authorized capture. Never invent measurements or treat not-run as pass.
- Reuse existing runners/builds. Assume no PR, CI, daemon or new build system; trial alternatives only after measured overhead.

## Audit

1. **Inventory.** Read AGENTS.md and actual commands; map build dependencies, entrypoints, test selectors, fixtures, imports/generated inputs, slow suites, perf/memory budgets and user workflows. Separate correctness, replay, reference parity, statistical qualification, timing, memory and release approval. Read [test-audit](../test-audit/SKILL.md) for weak or redundant oracles.
2. **Measure.** For representative edit classes separate compilation, setup, execution, teardown and reporting. Record actual costs, current failures, profile churn, reused builds, excluded/flaky tests, shared fixtures and host conditions. Time only safe authorized checks. Use [make-it-fast](../make-it-fast/SKILL.md) and [benchmark-checklist](../benchmark-checklist/SKILL.md).
3. **Select by contract.** Distinguish artifact dependencies (**what rebuilds**) from verification ownership (**what executes**). Map source/test/content/config changes to exact checks; changed tests select themselves. Shared low-level edits need bounded cross-boundary checks, not every downstream workload. Unknown impact remains incomplete; it never passes silently or selects Full.
4. **Record gates.** Stable ID, owner, exact command/selector, independent output oracle, products/fixtures, tier, profile/platform, resource bounds, baseline and evidence invalidation. Prefer runner discovery over thousands of duplicated IDs. Test positive/negative change selection and missing-selector errors.
5. **Inspect results.** Identify existing logs, raw timings, samples, source/product identities and false-pass paths: stale products, empty selections, skips, incomplete work, contaminated host, incomplete replay, or invalid cache hits.

## Prescribe the hierarchy

| Tier | Purpose | Authority |
| --- | --- | --- |
| **Edit** | Exact regression, negatives, cheap deterministic work/invariant counters | Normal authorized agent iteration |
| **Change** | Full affected component contract, bounded boundary checks, selected memory/perf | Coherent change completion |
| **Scenario** | Named substantial E2E, simulation, stress or benchmark workload | Explicit scenario scope and budget |
| **Full** | Global/release/multi-platform tests, exhaustive experiments and qualification | **Manual invocation only** |

These are ceilings, **not a ladder**: no automatic escalation to Scenario or Full because a smaller gate fails, is noisy, or lacks mapping. A scoped pass is not a global pass. Preserve repo-specific names and stricter owner gates.

For stochastic products, keep deterministic smoke, paired pilots, screening and *fresh locked confirmation* distinct. Never treat selection seeds as qualification seeds, drop failures from a denominator, or conflate balance/quality results with correctness and speed. Pin binary, content, seed and input identity.

## Performance, memory and host

- Pin baseline/candidate work, completed output, code/content/seed/config, optimized profile, cache state and errors. Faster incomplete work is not a win. Use deterministic counters in Edit and controlled timing only when relevant.
- Distinguish allocation traffic, retained data, process RSS, tree/cgroup peak, disk and cache. Existing hard limits remain. Allocation bounds are not RSS; summed child peaks are not simultaneous peak.
- Plan host resource reservations across agents/worktrees and isolated products. Observe CPU/runnable load, quotas, swap/memory/I/O pressure, throttling and available frequency/thermal readings before/during/after. External contention makes timing inconclusive; candidate-induced pressure may be a regression. Busy hosts defer timing, never grant a pass.
- Short timings use predeclared interleaved paired baseline/candidate samples with bounded count/uncertainty: **within budget / regression / inconclusive**. Long manual scenarios may be observational. Keep accepted reference distinct from nearby comparison baseline. Profile separately from speed claims.

## Hand off to campaign-plan

After auditing, **apply [campaign-plan](../campaign-plan/SKILL.md) in planning mode**, including campaign-preflight, using actual contracts, costs and authority as the goal. It writes one `docs/CAMPAIGN-<NAME>.md` in the target repo. Do not start it or invent a second plan. Its usual full-scope milestone advice cannot override manual-only Full.

Require the campaign to contain:

- A smallest **real pilot** before expanding infrastructure: one relevant edit selects an independent correctness oracle and cheap resource check, an irrelevant edit excludes them, missing selectors fail, and automatic Full is refused.
- Exact reusable runner commands, minimal product builds, immutable baseline/candidate products, cost ceilings, host/memory validity, test accounting, and source-qualified evidence reuse/invalidation.
- Strict manual-only Full with dependency/alias/wildcard/fallback rejection tests; no assumed PR/CI or scheduled qualification.
- An ~8-line machine-derived result: scoped verdict, tests, perf delta/budget, memory, host validity, manual/unrun scope and smallest reproduce command. Preserve raw evidence by run ID; no agent-generated smoothing.
- campaign-plan's workstreams, prerequisites, owner files, acceptance proofs, bounded steering and a substantive pilot before catalogue expansion.

**The test:** a fresh execution agent, reading only the campaign and repo, can deliver a working narrow selector that catches one real defect, measures the affected resource without making false speed/memory claims, refuses Full unless manually authorized, and prints a concise reproducible verdict. This skill **plans** that implementation; it does not launch it.

**Report:** target revision and existing verification structure; cheapest observed loop and unmeasured costs; harmful broad or automatic paths; the proposed tiers and first pilot; manual-only restrictions; campaign-plan/preflight readiness verdict and document path; decisions requiring the owner and evidence not obtained. Do not claim implementation or full-suite acceptance.
