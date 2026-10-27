---
name: campaign-plan
description: "Use for /campaign-plan <goal>: plan a new campaign from a goal. Survey the repo, measure the baseline, settle decisions, split the work into workstreams and phases, make every deliverable provable by a command, and write the campaign doc in campaign-preflight's final shape."
disable-model-invocation: true
metadata:
  opencode/autoinvoke: "false"
---

# Campaign Plan

Planning only: it turns a goal into a draft campaign doc worth preflighting, then preflights it, and starts nothing. `campaign-preflight` owns the doc's shape, bar, sequencing, phase order, and the one question round; campaign mechanics are in `orchestrate`. This skill adds how to get from a goal to the draft.

## Rules

- **The goal is the owner's.** With no goal in the invocation, ask for it in one line. Everything else comes from the code, the evidence, and the repo's docs.
- **Measure before planning.** Run, capture, or time the thing the goal changes, and put the numbers in the doc. A plan about speed, size, or looks that starts from a belief is a guess.
- **An approved artifact is the spec.** If earlier work left owner-approved output (reviewed mocks, a frozen baseline, a reference), the campaign reproduces it. It does not reinterpret it.
- **Every deliverable has runnable proof** with an explicit threshold. Build the minimum missing gate for the first edit class and schedule one real end-to-end pilot before expanding the harness. Give each infrastructure item an exit test and the delivery it must unblock.
- **Read the prior campaigns** in `docs/CAMPAIGN-*.md` and `DECISIONS.md`. Reuse their house style, and design out why the weak ones fell short (a goal judged by words, not artifacts).
- **Settle what the evidence settles.** Technical blockers go in the plan as parent work. Do not ask the owner about them; preflight asks the one batch of owner decisions, so do not run a second round.
- **No code and no formatters.** Write the doc and the files it needs to be executable, nothing else. Commit only the doc.

## Steps

1. **Read** the goal, the repo's AGENTS.md, the docs and code the goal touches, and the prior campaign docs.
2. **Survey.** Map what exists with `path:line`, each part marked reuse, change, or new. Record the baseline: known red, loop timings, the numbers the goal moves.
3. **Name the deliverables.** Numbered, each an outcome, each with its proof command and threshold.
4. **Pick the proof for the kind of target:**
   - *Speed, size:* `make-it-fast` and `benchmark-checklist`; a baseline, a noisy-host rule (counts and CPU, medians of interleaved runs), a target.
   - *Looks, layout:* approved images as the spec; browser screenshots diffed against them with `odiff` and a threshold per surface, plus a structural check that no text or datum was lost.
   - *Behavior parity:* `reference-parity`. *Storage, wire formats:* `durable-state`.
5. **Decompose and phase** per preflight's Sequence rules. Build foundations that every lane needs (shared stylesheet, harness, types) first, by the coordinator or one lane, never in parallel. Name each slice's acceptance command and the milestones that run the full suite.
6. **Execution authority.** State which effects execution needs the owner to authorize and forbid the rest. Proof that needs unavailable hardware or hosts goes on **Needs environment**.
7. **Write** `docs/CAMPAIGN-<NAME>.md` in preflight's shape and commit it.
8. **Preflight it.** Apply `campaign-preflight` to the draft, including the `blast-radius` proof of the foundation. Do not stop at a draft.

**The test:** the draft names a measured baseline and a runnable proof for every deliverable, and preflight can take it to a verdict without redoing the survey.

**Report:** the verdict (`ready`, `ready after the owner answers <list>`, `not ready`); the baseline numbers; the deliverables with their proofs; the first slice and which slices may run in parallel; the decisions the owner made and the ones you prescribed, so they can overrule; what you could not verify; the doc path; and the one-line prompt that launches the executor.
