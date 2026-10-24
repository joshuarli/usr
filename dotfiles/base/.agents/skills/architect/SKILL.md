---
name: architect
description: "Use for consequential, genuinely uncertain design or boundary changes, including design-only requests; compare structurally different options against existing caller and invariant constraints. Skip routine edits and clear local repairs."
metadata:
  opencode/slash: "true"
  opencode/autoinvoke: "true"
---

# Architect

Ground the decision in current callers, existing contracts, tests, and constraints. A second design earns its cost only when the choice is consequential and the evidence leaves meaningful uncertainty.

## Steps

1. **Ground.** Read the code the change touches, its callers, tests, and constraints. Use `git log` or other relevant records when the question includes why it acquired this shape. Naming a file is not grounding. Skip only for greenfield work with nothing to integrate.
2. **Usage first when it clarifies.** Write the caller's code as you want it to read and derive the types from that. Skip it when the callers are already clear.
3. **Sketch when it settles the decision:** types, signatures, and the module map, no logic. Use `make-invalid-states-unrepresentable` for the types and `api-surface-and-module-boundaries` for the edges. Do not write stubs or files only to satisfy this step.
4. **Set criteria before comparing.** Name the requirements, compatibility obligations, invariants, operational constraints, and costs that decide the shape. For a consequential and genuinely uncertain decision, compare at least two structurally different whole designs. A point fix inside one design is not another candidate.
5. **Compare the designs yourself.** Separate candidate agents only when independence is the point, for example when your own preferred shape would bias the comparison. Then give each the same task, constraints, and source context without revealing a preferred design, and follow [orchestrate](../orchestrate/SKILL.md) for model, effort, ownership, and worktree rules. Sequential attempts by one model are alternatives, not independent confirmation.
6. **Choose one coherent base.** Explain how it meets the criteria and why a competing design loses. Integrate another candidate's idea only when it improves the selected design without weakening its invariants. Do not average incompatible designs. Surface API, type, schema, or invariant changes to the owner.
7. **Respect request mode.** A design-only or plan-only request ends with the requested analysis. Otherwise implement against the selected design. If the code needs a shape it did not foresee, decide whether the design, requirement, or implementation is wrong.
8. **Redesign when evidence shows a pattern:** repeated workarounds across unrelated code, unrelated special-case branches, escape hatches in types, a lock where no sharing was expected, or callers that need internal abstraction rules. Reassess against the same criteria. Complexity in the data is not complexity in the design.

Keep a useful sketch in the reply. Write no design file unless asked. Do not produce competing designs for routine changes or clear local repairs.

**The test:** the selected design fits observed callers and invariants, and every compared design was judged against criteria set before the comparison.

**Report:** the usage sketch when one was needed, criteria, compared shapes when warranted, contract changes, and any implementation deviation.
