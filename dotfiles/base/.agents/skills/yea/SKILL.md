---
name: yea
description: "Use for /yea: treat the owner's approval as covering everything in your last reply — continue the work, do every recommendation in full, settle each open question the way you recommended, and take the approvals it was waiting on."
disable-model-invocation: true
metadata:
  opencode/autoinvoke: "false"
---

# Yea

`/yea` means, in the owner's words: continue, all approved, and the open questions go to your recommendations. The owner read that reply and nothing newer, so approval covers what it put in front of them, and a question it already raised does not come back. `/yea` is a named invocation; an ordinary "sounds good" approves nothing.

## Rules

- **The scope is your last reply.** Carry out every recommendation, take every approval the reply was waiting on — a plan, a contract change, access or a permission, a push or a PR — and settle every option and open question it put to the owner. Continue the work the reply said was still in flight. A question still open from an earlier reply counts when the last reply carried it forward.
- **Do the whole of each one,** including the larger parts you described as optional follow-through, such as the docs, the test, and the ticket cleanup. Where you named a minimal and a fuller version, do the fuller.
- **Settle the questions yourself.** Take the option you recommended, never one you warned against. Where you gave no recommendation, take the one you would advise now and say which and why. A question that surfaces while carrying out approved work is yours when it stays inside that scope; never re-ask what the reply already surfaced.
- **Some answers are not yours to give.** A missing fact, a credential or access you do not have, a price, or someone else's commitment stays blocked in `Needs you`, named as the input it needs.
- **Approval covers the last reply and no more.** Routine engineering detail is yours to settle. A new effect the reply never named — a merge, a deploy, a release, a force-push, a deletion, a publication, a spend — goes back to the owner even when it looks in scope, and no option or follow-on question launders it. Explicit owner limits from earlier still hold.
- **Push back when the check disagrees.** A recommendation or decision that proves wrong or unsafe once you look at the code is skipped and reported with the evidence, not carried out.
- **Verify each change** with the narrowest check that covers it, and report any wider check before running it.

Number the items from your last reply, carry them out in dependency order with one logical change each, and close any `TODO.md` ticket a change finishes, per the `todo` skill. A bug gets a failing test first, a contract change keeps the `!` or `BREAKING CHANGE:` footer the global contract requires, and no formatter runs. If the reply proposed none of this, say so and stop; do not invent work.

**The test:** every recommendation, open question, pending approval, and named next step in the last reply is done or decided, or skipped with a stated reason, and nothing outside that list changed.

**Report:** each item as done, decided, skipped, or needs-ask; the option taken for each open question and why; the checks and results; what was committed and pushed; anything left unpublished.
