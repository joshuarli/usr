# Do playbooks

Choose the route from the user's request and repository evidence. Each route names its entry condition, proof obligations, optional stages, and exit condition. Read only the selected route and leaf skills.

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

Inspect existing behavior and define observable acceptance. Use [architect](../../architect/SKILL.md) for a consequential new boundary, invariant, or structure. For consequential changes whose uncertainty and impact justify independent scrutiny, use [review](../../review/SKILL.md) for a focused completion review; routine changes do not need an extra review lane. Implement a complete vertical slice, exercise its public surface, handle applicable errors, and update affected docs.

**Proof:** user-facing behavior or the public API, plus focused tests for required outcomes and errors.

**Exit:** the requested capability and its acceptance evidence are complete.

## Consequential design

**Entry:** the request chooses a significant structure, boundary, or invariant with multiple plausible shapes and material tradeoffs, including a design-only request. Skip routine changes and clear local choices.

Use [architect](../../architect/SKILL.md) to ground the decision in callers and existing contracts, set criteria before comparing structurally different options, and choose one coherent base. Respect request mode: design-only and plan-only requests end with the requested analysis; implementation continues only when requested.

**Exit:** the requested recommendation or implementation is complete, with the compared choices and acceptance evidence that matter to the decision.

## Removal

**Entry:** the user directs complete removal of a live capability or supported surface, including its old behavior.

Use [delete](../../delete/SKILL.md) to trace and remove the retired path without compatibility support. Identify breaking contracts and any existing data that needs an authorized one-time conversion.

**Proof:** no live execution path or supported surface retains the removed behavior, and every remaining reference is unrelated or historical.

**Exit:** the requested removal is complete, with breaking contracts and any unperformed data conversion reported.

## Refactor or migration

**Entry:** the request changes structure or replaces an existing implementation while preserving agreed behavior.

Name the contracts that must remain unchanged. Use [reference-parity](../../reference-parity/SKILL.md) when a runnable implementation or spec is the oracle. Migrate coherent units, verify callers, and remove obsolete paths after the replacement is proven.

**Proof:** focused parity checks cover the agreed behavior, with any intentional differences named.

**Exit:** the authorized structure change is complete and no obsolete path remains without a proven consumer.

## Performance

**Entry:** the request aims to reduce time, memory, allocations, or artifact size.

Use [make-it-fast](../../make-it-fast/SKILL.md) and [benchmark-checklist](../../benchmark-checklist/SKILL.md). Establish correctness and a comparable baseline, test a mechanism-based hypothesis, and keep a change only when measured gains justify its costs. Confirm useful work completed, use a statistic suited to the claim, and follow host-readiness rules.

**Proof:** representative before-and-after evidence, correctness checks, and relevant resource limits.

**Exit:** the performance goal is met. Deferred timing evidence is not a pass.

## Investigation or review

**Entry:** the user asks to explain, compare, diagnose, or review without implementation.

For a focused read-only review, use [review](../../review/SKILL.md) to assess correctness, safety, and completeness while keeping the requested scope. For explanations and diagnoses, use source and execution evidence to establish current behavior. When the question is why the implementation acquired its shape, consult relevant history, PR discussions, issues, design records, or operational evidence if available and useful. Do not infer historical intent from code alone. Label inferred rationale, and check whether an odd-looking mechanism still protects a contract before removing it. Keep research proportional to the question.

Run only authorized read-only experiments. Apply [bounded experiments](#bounded-experiments) when an observable fact would change the answer. Report evidence and uncertainty. A negative finding can complete the task. A review stays read-only, including docs and tickets. Do not invoke [ultrareview](../../ultrareview/SKILL.md), whose broader workflow can change documentation and tickets.

**Proof:** every conclusion points to source, output, relevant history, or an experiment, with inference identified.

**Exit:** the requested explanation or findings are delivered without tracked edits or ticket changes.

## Bounded experiments

**Entry:** a decision depends on an observable fact that source inspection alone cannot settle.

Before running anything, state internally the question, alternatives, observation that distinguishes them, and result that would change the recommendation. Use the smallest safe experiment and an isolated artifact under `.work/tmp` or the task's disposable fixture. An experiment is evidence for a decision, not a production implementation. Promote a chosen approach only through the normal implementation and verification route.

Respect the task's effect boundary. A read-only request permits experiments on isolated local fixtures, not live hot-patching or external writes. Do not change production code or the user's working tree just to experiment. If the needed observation is unavailable, qualify the answer. Ask only about intent, preference, authority, or a consequential tradeoff that evidence cannot settle.

**Proof:** the observation distinguishes the stated alternatives and was gathered within the authorized effect boundary.

**Exit:** the decision is evidence-based, or its unresolved uncertainty is explicit.

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
