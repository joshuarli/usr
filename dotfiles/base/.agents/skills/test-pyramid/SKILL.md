---
name: test-pyramid
description: "Use for /test-pyramid: audit and improve a project's test layers, change-selected gates, and performance and memory bounds. Honors audit-only and campaign-planning requests. Full runs stay manual-only."
disable-model-invocation: true
metadata:
  opencode/slash: "true"
  opencode/autoinvoke: "false"
---

# Test Pyramid

Make cheap, relevant verification trustworthy and expensive verification deliberate. Choose layers by what defects they catch, how strong the assertions are, isolation and cost, not unit-test quotas or a prescribed framework. Per-test judgment and the Oracle Test live in `test-audit`; suite shape lives in `renovate-tests`.

## Scope and authority

- Default to **audit and improvement** of the named project/area. **Audit/review-only or plan-only** requests stop at findings or a plan. Session scope still controls commits, publication, installs, external mutations and costly runs.
- Identify effects on shared stores, databases, network, home and outputs before running anything; use disposable fixtures for destructive cases.
- **Full is manual-only:** require the user's explicit request for that named workload. Never launch it through defaults, aliases, wildcards, prerequisites, hooks, schedules, fallback or a baseline run. An agent may execute the request; a TTY or flag alone is not authorization.
- Assume no PR, CI, scheduler, daemon, platform, language or build system. Extend existing tools; migrating builds needs a measured bottleneck and cost.
- Preserve existing budgets and required checks. If outside permitted scope, report them unmet; do not remove them, run them anyway or claim completion.

## 1. Audit the actual verification path

Inspect configuration and representative tests. Capture what drives a decision:

1. **Contracts and layers.** Locate behavior, invariants, failure paths and resource limits, then the independent checks that would fail on a real defect: static checks, unit/property, component/contract, integration and real end-to-end tests. Find gaps, vacuous assertions, excessive mocks, state pollution, flakes and costly duplication. Before deleting a test, name what preserves its contract.
2. **Selection and dependencies.** Map products, discovery/filters, ownership, imports, generated inputs, fixtures, configuration and services. Separate what rebuilds from what executes. Changed tests select themselves; shared changes need a small set of boundary tests.
3. **Costs and conditions.** Separate build, setup, execution, teardown and reporting. Reuse measurements; run only the smallest safe authorized baseline resolving a real uncertainty. Label each cost observed, estimated or unmeasured.
4. **False passes.** Inspect empty filters, stale binaries, required skips, incomplete work, cache hits, ignored errors, timeouts, flaky retries and host contamination. Check that results account for all selected work.

Rank by failure risk and wasted iteration time. Prefer stronger assertions, precise selectors, isolation and build reuse before orchestration. With no setup, start with one real contract and its native runner.

## 2. Define ceilings and ownership

Adapt names and budgets to the project. These are ceilings, not an escalation ladder.

| Tier | Evidence | When to run |
| --- | --- | --- |
| **Edit** | Exact regression, relevant controls, cheap deterministic invariants or resource counters | Normal authorized iteration |
| **Change** | Affected component contracts, bounded boundary checks, relevant performance and memory | Completion of the scoped change |
| **Scenario** | Named substantial integration, stress, simulation or real workload | Explicit scenario scope and cost budget |
| **Full** | Comprehensive suites, exhaustive matrices, world/release builds and qualification | Explicit manual request for that workload only |

Select the smallest set covering changed contracts, including a small set of boundary tests for shared changes. Unknown ownership, unsupported environments or exceeded budgets leave a visible gap; never an empty green result or automatic Full.

Read [gate design](references/gate-design.md) when changing selection/execution and [measurement](references/measurement.md) for resource checks. Register components/workloads only as needed; discover tests natively.

## 3. Improve or plan, as requested

Deliver working changes and focused verification in improvement mode. A report or pilot alone does not complete broader requested work.

- Fix the highest-value problems. Strengthen missing behavior and invariant assertions; preserve useful integration coverage. No tests that echo the implementation or only assert file existence.
- Expose exact native selectors and small product builds. Batch compatible cases to reuse compilation/setup while preserving isolation and accounting. Reject missing selectors and required zero-match selections.
- Make defaults bounded and exclusions legible. Enforce manual Full in the existing command surface, including indirect dependencies and aliases. Retain a documented manual entrypoint.
- Add mappings, result fields or helpers only for actual callers. Prefer existing configuration/output. No compulsory catalogue, dashboard, database, runner rewrite or framework.
- Isolate fixtures and reference/candidate artifacts; preserve relevant profiles and cache semantics. Coordinate competing agents/worktrees before timing. A busy host defers timing while unrelated useful work continues; it never grants a pass.
- Update existing project guidance with exact commands, selection reasons, cost ceilings, manual workloads and evidence validity.

For **campaign planning**, use [campaign-plan](../campaign-plan/SKILL.md) and [campaign-preflight](../campaign-preflight/SKILL.md) to write one executable campaign document with actual contracts/costs/unknowns, prerequisites, a real pilot, ownership, resource validity, manual boundaries and acceptance proofs. Do not execute it. Ordinary audits need findings; small improvements need working changes, not campaigns.

## 4. Prove the changed mechanism, narrowly

Use the smallest real scenario resolving each remaining risk. For selector/gate changes, check related edits select required contracts, unrelated edits exclude them, and missing/empty selectors cannot pass. For oracle changes, temporarily introduce an actual contract violation in a disposable fixture and verify detection.

For manual-boundary changes, inspect the command graph and use a harmless plan/dry-run or fixture to prove automatic Full is rejected; never run Full to test the guard. For reporting changes, prove required skip, timeout, contaminated timing and incomplete work cannot become a pass. Check mechanisms changed or relied on, not a mandatory battery on every invocation.

Keep known failures visible. Do not weaken expectations, silently quarantine failures or retry until green. Stop once the scoped result is adequately verified; broaden only for a named unresolved risk within the current ceiling. Continue past the pilot until the requested scope is covered.

**The test:** another agent can make a relevant edit, run the documented smallest gates, detect a real defect or resource regression, and understand what remains unverified without accidentally launching comprehensive work.

**Report:** a scoped verdict and what changed; exact checks and observed costs; performance and memory verdicts, or why unmeasured; host validity; material gaps and manual work not run; the smallest next action or reproduce command. Never turn a scoped pass into a global claim. In planning mode, report plan readiness and evidence still needed.
