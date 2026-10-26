---
name: accelerate
description: "Speed up a running campaign by measuring where wall time went (model turns, ceremony, integration, checks) and fixing that one cause so the next slice lands sooner. Use when the user says accelerate, speed up, too slow, or asks for more lanes. Skip work that is not delegated across lanes or subagents."
metadata:
  opencode/slash: "true"
---

# Accelerate

Change the method, not the goal or the acceptance floor. Being asked to speed up means accepted slices are landing too slowly. The fix is rarely more agents. Use [orchestrate](../orchestrate/SKILL.md) and its [steering checkpoint](../orchestrate/references/campaigns.md#parent-steering-checkpoint).

1. **Measure where the wall time went.** Use the session's own evidence: turn count, time per turn, tool and test durations, idle waits on children, and doc or tooling commits versus product commits. Do not guess, and do not build a measurement platform.
2. **Apply the remedy that matches the cause:**
   - *Model turns dominate* (many short turns, long time to first token): batch reads, searches, and edits per turn, lower the child's reasoning effort for routine work, and give lanes larger, fully specified briefs.
   - *Ceremony dominates* (audits, checkpoints, handoffs, doc rewrites): stop it. Rewrite **Status** once and deliver.
   - *Integration dominates* (lanes conflict on shared files, red merges): serialize, and fix the integration branch first.
   - *Checks dominate*: run the narrowest acceptance command per slice, reuse evidence whose inputs are unchanged, and group wider suites at milestones.
   - *Implementation is starved* and the ready work owns disjoint files: add one writer within `perf-gate-ready -s` headroom.
3. **Land something.** The next action is a product change, not a note about one. If nothing lands by the next checkpoint, narrow the slice.

Do not commit a steering record for an acceleration. Never weaken a check or suppress a failure to gain speed.

**The test:** the next accepted slice lands sooner than the last one, with the same checks.

**Report:** where the time went (with numbers), the one change you made, and the next slice it should land.
