# Do playbooks

Choose the route from the user's request and the evidence in the repository. Each route names its entry condition, proof obligations, optional stages, and exit condition. Read only the selected route and leaf skills.

## Small change

**Entry:** the behavior is understood, the scope is narrow, and a focused check exists.

Inspect the source, callers, and nearest convention. Make the focused edit and run the narrow check. Add documentation only when the change alters documented use.

**Exit:** the requested behavior is demonstrated by the focused check.

## Defect repair

**Entry:** the user reports behavior that is wrong.

Reproduce the failure and keep a short feedback loop. Use [root-cause](../../root-cause/SKILL.md) when the cause is uncertain. Repair the origin, keep a regression check, and rerun the original reproduction and relevant focused tests. Use [architect](../../architect/SKILL.md) only when the repair creates a consequential boundary or invariant.

**Exit:** the reproduction fails before the change and passes after it. If the original symptom cannot be reproduced, report that gap and do not claim it is fixed.

## Feature

**Entry:** the request adds an observable capability.

Inspect existing behavior and define observable acceptance. Use [architect](../../architect/SKILL.md) for a consequential new boundary, invariant, or structure. Implement a complete vertical slice, exercise its public surface, handle applicable errors, and update affected docs.

**Proof:** user-facing behavior or the public API, plus focused tests for required outcomes and errors.

**Exit:** the requested capability and its acceptance evidence are complete.

## Refactor or migration

**Entry:** the request changes structure or replaces an existing implementation while preserving agreed behavior.

Name the contracts that must remain unchanged. Use [reference-parity](../../reference-parity/SKILL.md) when a runnable implementation or spec is the oracle. Migrate coherent units, verify callers, and remove obsolete paths after the replacement is proven.

**Proof:** focused parity checks cover the agreed behavior, with any intentional differences named.

**Exit:** the authorized structure change is complete and no obsolete path remains without a proven consumer.

## Performance

**Entry:** the request aims to reduce time, memory, allocations, or artifact size.

Use [make-it-fast](../../make-it-fast/SKILL.md) and [benchmark-checklist](../../benchmark-checklist/SKILL.md). Establish correctness and a comparable baseline, test a grounded hypothesis, and keep a change only when measured gains justify its costs. Follow the repository's host-readiness rules.

**Proof:** representative before-and-after evidence, correctness checks, and relevant resource limits.

**Exit:** the performance goal is met. Deferred timing evidence is not a pass.

## Investigation or review

**Entry:** the user asks to explain, compare, diagnose, or review without implementation.

Read the relevant sources and run only authorized read-only experiments. Report evidence and uncertainty. A negative finding can complete the task. For a narrow read-only review, do not invoke [ultrareview](../../ultrareview/SKILL.md), whose full workflow changes documentation and tickets.

**Proof:** every conclusion points to an observed source, output, or experiment.

**Exit:** the requested explanation or findings are delivered without tracked edits or ticket changes.

## Ticket or backlog

**Entry:** the user names a ticket or requests backlog work.

Read the selected ticket, linked decisions, and current code. Route one ticket through the matching work type. Close it only after its acceptance is met and its mutation is authorized. Use [burn-down-the-backlog](../../burn-down-the-backlog/SKILL.md) only when the user requests the backlog workflow. A single ticket does not invoke the entire backlog.

**Proof:** the ticket's own acceptance and the narrowest relevant check.

**Exit:** the requested ticket scope is complete, or a concrete owner decision blocks it.

## Campaign or custom work

**Entry:** the user names a campaign or the task has real dependency and integration risk.

For a new campaign-sized implementation, use [campaign-plan](../../campaign-plan/SKILL.md), which runs [campaign-preflight](../../campaign-preflight/SKILL.md). Continue from a ready plan only under the owner's actual implementation and commit authority.

For an existing campaign, inspect its changes, prerequisites, and acceptance before resuming. Use `campaign-preflight` only when the plan is stale or incomplete, then resume the existing work.

Use [orchestrate](../../orchestrate/SKILL.md) and its [campaign mechanics](../../orchestrate/references/campaigns.md) when delegation fits the grant. If commits are forbidden, use serial work or patch handoffs; do not use commit-dependent closeout as written.

Compose unusual work from a few evidence-based stages. A blocked portion does not prevent independent useful work.

**Proof:** integrated changes pass their named acceptance checks. The parent reviews the actual result and owns the final verdict.

**Exit:** requested deliverables and applicable proof obligations are complete, or remaining work has a named concrete blocker.
