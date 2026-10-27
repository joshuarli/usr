---
name: accelerate
description: "Apply when a running multi-lane or subagent campaign lands accepted slices too slowly, or the user says accelerate or asks for more lanes: measure where wall time went and fix that one cause. Skip code or build performance (use make-it-fast) and work not delegated across lanes."
metadata:
  opencode/slash: "true"
---

# Accelerate

Change the method, not the goal or the acceptance floor. Slow accepted slices are rarely fixed by more agents. Use [orchestrate](../orchestrate/SKILL.md) and its [steering checkpoint](../orchestrate/references/campaigns.md#parent-steering-checkpoint).

1. **Measure where the wall time went.** Use the session's own evidence: turn count, time per turn, tool and test durations, idle waits on children, and doc or tooling commits versus product commits. Do not guess, and do not build a measurement platform.
2. **Apply the matching response** from the checkpoint's signal table. Fix the one dominant cause.
3. **Land something.** The next action is a product change, not a note about one. If nothing lands by the next checkpoint, narrow the slice.

Do not commit a steering record for an acceleration. Never weaken a check or suppress a failure to gain speed.

**The test:** the next accepted slice lands sooner than the last one, with the same checks.

**Report:** where the time went (with numbers), the one change you made, and the next slice it should land.
