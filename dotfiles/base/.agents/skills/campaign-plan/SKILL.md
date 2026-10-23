---
name: campaign-plan
description: "Use for /campaign-plan <goal>: plan a new campaign from a goal. Survey the repo, measure the baseline, settle decisions, split the work into workstreams and phases, make every deliverable provable by a command, and write the campaign doc in campaign-preflight's final shape."
disable-model-invocation: true
metadata:
  opencode/autoinvoke: "false"
---

# Campaign Plan

Planning only: it turns a goal into a campaign doc a coordinator can run unattended, and starts nothing. The doc's shape and bar are `campaign-preflight`'s, campaign mechanics are the Campaigns section of `orchestrate`, and each design area's method lives in the skill named for it (preflight's lens table). This skill adds how to get from a goal to a draft worth preflighting, and then preflights it.

## Rules

- **The goal is the owner's.** With no goal in the invocation, ask for it in one line. Everything else comes from the code, the evidence, and the repo's docs.
- **Measure before planning.** Run, capture, or time the thing the goal changes, and put the numbers in the doc. A plan about speed, size, or looks that starts from a belief is a guess.
- **An approved artifact is the spec.** If earlier work left owner-approved output (reviewed mocks, a frozen baseline, a reference), the campaign reproduces it. It does not reinterpret it.
- **Every deliverable has runnable proof**, with an explicit threshold. Build the minimum missing gate for the first edit class and schedule one real end-to-end pilot before expanding the harness. Missing proof blocks affected acceptance, not independently verifiable work. Give each infrastructure item an exit test and the substantive delivery it must unblock.
- **Plan for steering, not just dispatch.** Use the [parent steering checkpoint](../orchestrate/references/campaigns.md#parent-steering-checkpoint). Separate owner requirements from revisable agent tactics, define substantive progress, and name the next milestone, review cadence, and response to stalled progress. Reuse the campaign log; no separate management framework.
- **Read the prior campaigns** in `docs/CAMPAIGN-*.md` and `DECISIONS.md`. Reuse their house style. Find why the weak ones fell short (a goal judged by words, not artifacts) and design that out.
- **Technical blockers are not questions.** Anything the evidence and the code can settle (a type design, a rule the campaign wrote for itself, a cross-file change) goes in the plan as parent work. Ask only what changes the product, the contract, or authorization.
- **Ask once.** Batch the owner's decisions into one question round of at most four. Recommend each answer, and ask only about choices that change the product or contract or carry real risk. Prescribe or delegate the rest with a reason and a bound.
- **No code, no commits, no pushes, no formatters.** Write the doc and the files it needs to be executable, nothing else.

## Steps

1. **Read** the goal, the repo's AGENTS.md, the docs and code the goal touches, and the prior campaign docs.
2. **Survey.** Map what exists with `path:line`, each part marked reuse, change, or new. Record the baseline: known red, loop timings, the numbers the goal moves.
3. **Name the deliverables.** Numbered, each an outcome, each with its proof command and threshold.
4. **Pick the proof for the kind of target:**
   - *Speed, size:* `make-it-fast` and `benchmark-checklist`; a baseline, a noisy-host rule (counts and CPU, medians of interleaved runs), a target.
   - *Looks, layout:* approved images as the spec; browser screenshots diffed against them with `odiff` and a threshold per surface, plus a structural check that no text or datum was lost.
   - *Behavior parity:* `reference-parity`. *Storage, wire formats:* `durable-state`.
5. **Decompose.** Workstreams by shared code, items sized as capabilities, prerequisites written on the item, the files each lane owns and must not touch, initial lane widths and ceilings, a provisional-work cap, and memory and acceptance-capacity budgets. Foundations that every lane builds on (shared stylesheet, harness, types) are built first by the coordinator or one lane, never invented in parallel.
6. **Phase** as preflight orders them: ground (baseline red, a measured loop, the minimum proof), a substantive pilot, parity and completeness, hardening, optimization and polish, close. Specify focused candidate checks and bounded full-scope validation waves separately from commit granularity; retain required final audits and qualified reuse rules.
7. **Execution authority.** State which effects execution needs the owner to authorize and forbid the rest. The plan records that boundary; writing or approving a plan does not authorize execution or commits.
8. **Write** `docs/CAMPAIGN-<NAME>.md` in preflight's shape. Commit nothing.
9. **Preflight it.** Apply `campaign-preflight` to the draft: audit, decide, sequence, make the loop fast, prove the foundation with `blast-radius`. Do not stop at a draft.

**Report:** the verdict (`ready`, `ready after the owner answers <list>`, `not ready`); the baseline numbers; the deliverables with their proofs; the initial lane widths and ceilings, acceptance cadence, and first substantive milestone; the decisions the owner made and the ones you prescribed, so they can overrule; what you could not verify; the doc path; and the one-line prompt that launches the executor.
