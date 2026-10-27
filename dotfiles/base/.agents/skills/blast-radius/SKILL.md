---
name: blast-radius
description: "Use when a consequential change has a downstream safety question that source search cannot settle; trace and exercise the assumption against relevant callers or runtime. Skip routine changes, clear local repairs, and broad repository audits."
metadata:
  opencode/slash: "true"
  opencode/autoinvoke: "true"
---

# Blast Radius

Listing callers is not the job; grep does that. The job is the breakage grep will not show.

## Prove it

A writeup that sounds right proves nothing. Find the one or two facts the change's safety depends on and prove them by running code.

For each such fact, climb this ladder as far as is cheap and say where you stopped:

1. You said so. Worthless alone.
2. You pointed at a real `file:line`, or the library's own source.
3. You walked the failure step by step and it does not reach.
4. You ran a script or test that calls the real code and fails loudly if you are wrong.
5. You reproduced it in the running app.

Use existing commands first. Keep any focused probe in `.work/tmp` or a disposable fixture, and do not edit the product under review.

## Steps

1. **Read the change:** the symbols it adds, changes, and deletes, and what behaves differently, including what the diff does not spell out.
2. **Find the one fact it is safe because of,** such as "this call only drops entries that are already dead". If it holds, most risky cases clear at once. Spend your time here, not on a long list of maybes.
3. **Look where grep stops:** the source and pinned version of the libraries you call (and any local patch), ordering of teardown and async work, JSON an API returns, database columns, wire formats, another language reading the same bytes, feature flags, code three hops downstream.
4. **Rate each risk honestly** with a real likelihood and a real cost. Cite a real `file:line`. A search that finds nothing is still an answer. Never invent a caller or an API. List what you checked and cleared separately.
5. **Prove the one fact:** write a script or test against the real code, run it, and paste what happened.

For a consequential, uncertain change, an independent review may catch a missed risk: see [review](../review/SKILL.md) and [orchestrate](../orchestrate/SKILL.md).

**The test:** the one fact the change is safe because of is stated, with the ladder rung you reached, or marked `unproven`.

**Report:**

- **What it does,** including the non-obvious part.
- **The one fact it is safe because of,** and the proof. If you could not prove it, write `unproven`.
- **Risks,** each with how it breaks, `file:line`, likelihood, cost, and how to check.
- **Cleared:** what you checked and why it is fine.
- **Before you merge:** the cheapest test or repro that catches the real bug, including your script.
