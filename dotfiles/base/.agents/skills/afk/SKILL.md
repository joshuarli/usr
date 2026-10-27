---
name: afk
description: "Use when a requested workflow needs unattended execution or the user asks you to work while they are away. Make bounded decisions and park owner-dependent blockers. Apply away/return behavior only after an explicit departure."
disable-model-invocation: true
metadata:
  opencode/autoinvoke: "false"
  opencode/slash: "true"
---

# AFK

AFK owns unattended execution and explicit away/return behavior. User presence and workflow persistence are separate.

## Unattended execution

- **Decide and continue.** Resolve ordinary ambiguity from the task, repository rules, and evidence using the smallest reversible assumption. Do not ask or wait for routine answers. Investigate and fix technical blockers, and run the narrowest applicable checks. Continue while an authorized useful step remains.
- **Never close on a question.** While the user is away, no reply ends by asking them to choose, and none carries a "decisions for you" or "needs you" list, whatever another skill's report template says. In the global status block, **Needs you** is always "nothing" and decisions made go under **Done**. Pick the option you would have recommended, apply it within existing authority, and report it as a decision made with how to reverse it. Then continue with the next step.
- **Defer only owner-dependent work.** Park a step only when it depends on unavailable facts or authority you lack, or on an effect that cannot be undone. A preference, tradeoff or earlier stop condition is yours to settle once the user has said to decide, to trust you, or to move that way ("you decide", "make it easier"); the newer instruction replaces the older stop condition. Keep the missing input and what would unblock it in working context or the existing task artifact. Continue every independent step, and do not retry while conditions are unchanged. Do not create task artifacts solely to maintain AFK status; follow repository rules when a blocker qualifies for durable deferral.
- **Keep existing boundaries.** Follow the user's task, repository instructions, and tool permissions. AFK adds no authorization for broader scope or separate consequential actions. Continue any work that remains within existing authorization.
- **Treat messages as steering.** Answer a status request, incorporate a correction, and retain the active workflow. A pause or cancellation stops the affected work. An incompatible new objective replaces it according to the task owner. Stop when the bounded objective is complete or no useful authorized step remains.

## Explicit away/return behavior

Apply presence behavior only when the user actually says they are going away. Their next message clears that away state unless it says they are still away ("still afk", "you decide"); that message is steering, not a return, so do not open with `Welcome back —` and keep every unattended rule above in force. Begin the response to a real return with `Welcome back —` and give only important updates: completed or active work, consequential decisions or changes, deferred blockers, and decisive checks. A return does not cancel or dismiss an active unattended workflow; answer the message as steering and continue within the workflow's scope.

**The test:** bounded authorized work continues without routine questions, owner-dependent steps are parked with a clear unblock condition, and only an explicit away request creates away/return behavior.

**Report:** report the result, consequential decisions, deferred blockers, and checks. On an explicit return, lead with the required `Welcome back —` brief.
