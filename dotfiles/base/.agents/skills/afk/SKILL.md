---
name: afk
description: "Use when the user asks you to keep working while they are away or unattended; make bounded decisions and defer owner-dependent blockers. Skip ordinary work while the user is available."
disable-model-invocation: true
metadata:
  opencode/slash: "true"
---

# AFK

Keep the agreed work moving while the user is away. AFK changes how you handle uncertainty and progress, not the task's scope or authority.

## Rules

- **Decide and continue.** Resolve ordinary ambiguity from the task, repository rules, and evidence using the smallest reversible assumption. Do not ask or wait for routine answers. Investigate and fix technical blockers, and run the narrowest applicable checks. Do not end a turn while an authorized useful next step remains.
- **Defer only owner-dependent work.** Park a step only when it depends on unavailable facts, authority, or a consequential choice that evidence cannot settle. Keep the missing input and what would unblock it in working context or the existing task artifact. Continue every independent step, and do not retry while conditions are unchanged. Do not create task artifacts solely to maintain AFK status; follow repository rules when a blocker qualifies for durable deferral.
- **Keep existing boundaries.** Follow the user's task, repository instructions, and tool permissions. AFK adds no authorization for broader scope or separate consequential actions. Continue any work that remains within existing authorization.
- **Dismiss AFK on any new user message.** Begin the first reply with `Welcome back —` and give only important updates: completed or active work, consequential decisions or changes, deferred blockers, and decisive checks. Skip routine chronology. Then handle the new message under normal session rules, preserving the active task unless the user changes or cancels it. Do not keep applying AFK unless asked again.

**The test:** authorized work kept moving without routine questions, blocked steps were deferred with a clear unblock condition, and AFK ended on the first new user message.

**Report:** report the result, consequential decisions, deferred blockers, and checks. On the user's return, lead with the required `Welcome back —` brief.
