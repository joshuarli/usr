---
name: accelerate
description: "Apply when a running multi-lane or subagent campaign is slow to finish its features, or the user says accelerate or asks for more lanes: count which deliverables are done, measure where wall time went, cut work that moves no feature toward done, and fix the one dominant cause. Skip code or build performance (use make-it-fast) and work not delegated across lanes."
metadata:
  opencode/slash: "true"
---

# Accelerate

The owner cares about feature completion more than anything else. A feature is done when its deliverable works end to end and its acceptance check passes on the integration branch. Until the features are done, everything else waits: polish, refactors, extra hardening, tooling, doc rewrites, performance work beyond the acceptance threshold, and investigations that unblock no feature. This is [preflight's phase order](../campaign-preflight/SKILL.md) enforced mid-run. Change the method, not the goal or the acceptance floor. Adding agents rarely helps. Use [orchestrate](../orchestrate/SKILL.md) and its [steering checkpoint](../orchestrate/references/campaigns.md#parent-steering-checkpoint).

1. **Count what is done.** Mark each deliverable done, started, or not started. An accepted slice of an unfinished feature counts as progress, not as done.
2. **Measure where the wall time went,** split into feature work and everything else. Use the session's own evidence: turn count, time per turn, tool and test durations, idle waits on children and long jobs, and product commits versus doc and tooling commits. Do not guess, and do not build a measurement platform.
3. **Cut what moves no feature.** Stop or defer it. File a real defect you dropped as a ticket per `todo`; drop everything else.
4. **Fix the one dominant cause** with the matching response from the checkpoint's signal table.
5. **Land the next piece of the started feature closest to done.** Finish a started feature before you start another. The next action is a product change, not a note about one. If nothing lands by the next checkpoint, narrow the slice.
6. **Keep going.** Acceleration does not end the turn. A known next step that the granted authority covers and that needs nothing from the owner is the next action. A running build or remote job is time to work an independent slice.

Do not commit a steering record for an acceleration. Never weaken a check or suppress a failure to gain speed.

**The test:** more deliverables are done at the next checkpoint than at the last, with the same checks, and the action after this skill is a product change.

**Report:** deliverables done and remaining; where the time went, with numbers, split into feature work and the rest; what you cut; the one change you made; and the feature slice it should land next.
