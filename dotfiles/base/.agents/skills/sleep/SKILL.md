---
name: sleep
description: "Use for /sleep before the owner goes to sleep: proceed unattended without stopping: decide within authority and park only owner-blocked work."
disable-model-invocation: true
metadata:
  opencode/autoinvoke: "false"
  opencode/slash: "true"
---

# Sleep

`/sleep` grants run-until-done authority for the current task; the global contract's run-until-done rule governs it. Keep working until the bounded objective is complete or no authorized useful step remains.

- Park only work blocked by a missing fact, authority, or irreversible effect you lack. Name the blocker and unblock condition, then continue every independent step.
- Treat later messages as steering within the same task.

**The test:** work continues without stopping for routine choices, and blocked work names its blocker. No turn ends on a known next step with nothing needed from the owner, on a wait for a running job, or on a question you already had a recommendation for.

**Report:** the result, decisions made, blocked work with unblock conditions, and checks.
