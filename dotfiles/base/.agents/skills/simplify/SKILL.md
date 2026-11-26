---
name: simplify
description: "Use for /simplify: reduce a repo, subsystem, path, or change's conceptual and operational complexity while preserving supported behavior and performance. Implement bounded improvements; honor review-only requests. Skip new features, capability removal, and optimization campaigns."
disable-model-invocation: true
metadata:
  opencode/autoinvoke: "false"
---

# Simplify

Reduce what a maintainer must understand, remember, or coordinate to change the system correctly. Preserve its supported behavior and required performance envelope. A smaller design may need a new type, boundary function, or focused test; each addition must remove a demonstrated burden elsewhere. A justified no-op is a successful outcome.

## Bound and understand

1. **Honor the requested scope and mode.** Read repository instructions and the relevant callers, tests, configuration, and history. For a broad request, inspect each named area before choosing bounded, coherent changes. Review-only means findings without edits. An implementation request authorizes behavior-preserving work within that scope; do not add an approval stop for every cut.
2. **Follow a real operation.** Identify its sources of truth, representations, layers, independently mutable state, resource owners, special cases, and coordination steps. Include tests, generated context, documentation, and procedures when they are part of the burden. Explain what each suspect mechanism buys and who depends on it. File size, unfamiliar code, and repeated-looking syntax are leads, not findings.
3. **Name the preservation contract.** Identify affected outputs, errors, defaults, ordering, supported configurations and platforms, cancellation and cleanup, persisted/wire formats, and resource bounds. For agent instructions, preserve invocation, authority, routing, acceptance, and handoff semantics. Declared requirements and verification gates remain binding. Reuse trustworthy baseline evidence; run the narrowest missing baseline before editing.

## Choose and implement

- **State the reduction before editing:** what no longer needs to be understood or kept consistent, the simplest credible replacement, and why it meets the same requirements. Prefer fewer authorities, states, conversions, layers, or coordination steps. Judge the whole result, including callers, tests, generators, and deployment steps; moving complexity into a helper or dependency does not remove it.
- **Use a focused method only when it earns its context:**

  | Mechanism | Skill |
  | --- | --- |
  | Unused paths and their consumers | [dead-code-archaeology](../dead-code-archaeology/SKILL.md) |
  | Repeated logic that must evolve together | [deduplicate](../deduplicate/SKILL.md) |
  | Repeated facts, defaults, or closed sets | [single-source-of-truth](../single-source-of-truth/SKILL.md) |
  | Representations admitting forbidden states | [make-invalid-states-unrepresentable](../make-invalid-states-unrepresentable/SKILL.md) |
  | Consequential uncertainty between whole designs | [architect](../architect/SKILL.md) |
  | Redundant or implementation-coupled tests | [test-audit](../test-audit/SKILL.md) |

- **Complete one attributable change at a time.** Include affected callers and remove superseded internal machinery. Keep compatibility only for a supported consumer. Preserve checks at independent execution or trust boundaries even when they share a decision rule. Do not introduce a framework, mutable configuration, generic extension point, or dependency for a hypothetical second case. Skip cosmetic churn and unrelated fixes.
- **Separate capability cuts.** Removing supported behavior or a guarantee requires authorization for that loss. Report such candidates separately and continue with justified in-scope simplifications. Missing usage evidence alone does not prove a feature unused. Do not change permissions, skip validation, weaken tests, or omit durable work to make the implementation look smaller.

## Prove and decide

- **Correctness:** run the focused checks covering the changed contracts and callers. Add a characterization or regression check only for a concrete uncovered risk. When a test follows the old structure, retain its behavioral proof at the appropriate boundary. Never change expected behavior merely to make the candidate pass. For instruction changes, inspect composed procedures and exercise the affected decision or handoff where uncertain.
- **Performance:** retain the project's budgets and production configuration. When runtime or resource costs can change, compare the same representative work on baseline and candidate using the existing [performance guidance](../../instructions/performance.md). Check the cost the removed mechanism controlled, including startup, memory, scaling, or tail behavior where relevant. Verify useful work and output equivalence. Explain why a path is unaffected when measurement is unnecessary; passing correctness tests alone does not prove performance preservation. Keep inconclusive claims explicit and leave a candidate unlanded when an unresolved performance risk is material to acceptance.
- **Keep, revise, or reject:** keep the change only when the complexity reduction is concrete and preservation evidence meets the requirements. Reuse valid checks instead of repeating a campaign. Stop when the requested outcome is met or the remaining mechanisms earn their cost. Do not invent scores, a new audit framework, or a mandatory full-suite ritual.

**The test:** name a future change or investigation that now requires fewer independent facts, states, or steps, and the evidence that the supported outcomes and performance constraints still hold.

**Report:** scope inspected; complexity removed and the resulting ownership; behavior preserved; checks and performance evidence or justified exclusions; changes rejected or deferred; remaining mechanisms worth keeping and unresolved limitations. Keep evidence in the normal reply or commit/PR record, without adding a new report file unless requested.
