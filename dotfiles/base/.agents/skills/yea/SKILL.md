---
name: yea
description: "Use for /yea: accept every recommendation from your last reply and carry all of them out, in full, instead of the smallest change you proposed."
disable-model-invocation: true
metadata:
  opencode/autoinvoke: "false"
---

# Yea

The owner has read your recommendations and accepted all of them. Do the full recommended set, not the smallest subset you offered as a fallback.

## Rules

- **The scope is your last reply.** Take every recommendation in it, and for a choice between options, the one you marked recommended. If the reply had none, say so and stop. Do not invent work the reply did not propose.
- **Do the whole of each one,** including the larger parts you described as optional follow-through, such as the docs, the test, and the ticket cleanup. Where you named a minimal and a fuller version, do the fuller.
- **Acceptance covers the recommendations and no more.** Commit as the global contract directs. Push, publish, or update a PR only when a recommendation named it. Explicit user limits on commits or pushes still apply. A bug gets a failing test first, a contract change is surfaced, and no formatter runs. Other outward-facing or irreversible steps the reply did not name still need their own ask.
- **Push back when the check disagrees.** A recommendation that proves wrong or unsafe once you look at the code is skipped and reported with the evidence, not carried out.
- **Verify each change** with the narrowest check that covers it, and report any wider check before running it.

Number the recommendations from your last reply, carry them out in dependency order with one logical change each, and close any `TODO.md` ticket a change finishes, per the `todo` skill.

**The test:** every recommendation in the last reply is done, skipped with a stated reason, or flagged as needing a separate ask, and nothing outside that list changed.

**Report:** each recommendation as done, skipped, or needs-ask; the checks and results; what was committed and pushed; anything left unpublished.
