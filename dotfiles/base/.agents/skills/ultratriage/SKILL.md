---
name: ultratriage
description: "Use for /ultratriage: act as the repository owner to settle every open RFC and unresolved ticket, record evidence-backed decisions in docs and tickets, then offer feedback or burn-down-the-backlog."
disable-model-invocation: true
metadata:
  opencode/autoinvoke: "false"
---

# Ultratriage

Turn an undecided backlog into work an implementer can take cold. Make the owner's technical calls, record why, and account for every item. This is the decision pass between `ultrareview` and `burn-down-the-backlog`; neither neighboring workflow runs implicitly.

## Rules

- **Choose as the delegated owner.** Settle technical choices using the project's purpose, users, contracts, and maintenance cost. Prefer the smallest coherent design that removes the cause. Do not return a menu or leave ordinary engineering decisions for sign-off. Missing credentials, external facts, contractual commitments, and authority cannot be invented.
- **Docs and tickets only.** Leave implementation, tests, dependencies, configuration, and CI untouched. Use engineering skills for analysis and bounded, safe experiments only. A narrower user request still governs.
- **Cover one repository.** Default to every open RFC and unresolved ticket in the named repo or current checkout. A user-named subset narrows the scope. This is not another whole-repo audit or permission to expand into dependencies.
- **Preserve authority and settled contracts.** Carry forward the active request's commit and publication authority; this skill adds neither. Acceptance selects a design, not its implementation. Reaffirm accepted decisions unless evidence or feedback changes a premise; then follow the repo's supersession procedure.
- **Keep one source of truth.** Follow repo conventions, using [todo](../todo/SKILL.md) when it owns them or none exist. Preserve IDs and canonical records. Keep the coverage inventory in working context, not another tracker or permanent done list.
- **Delegate research, own the decisions.** Use [orchestrate](../orchestrate/SKILL.md) for independent groups when it pays. Lanes stay read-only and return evidence and recommendations. One integrator reconciles shared constraints and writes the records.

## Steps

1. **Inventory before deciding.** Read the instructions, overview, backlog, RFCs, and linked decisions. Identify authoritative sources, revision, and working changes. Include drafts, accepted but unimplemented and orphan RFCs, blocked and already-actionable tickets. Paginate accessible external trackers used by the repo; distinguish issues from pull requests. Record every original ID or path, reconcile mirrors, and note inaccessible sources. Never call a partial inventory exhaustive.

2. **Check the premises.** Read relevant code, callers, tests, and constraints; consult history when intent matters. Verify inherited claims, correct stale descriptions, retain sound recommendations, and check whether apparently completed work meets its acceptance. Use the cheapest observation that settles material uncertainty. An unproven defect stays `unproven`, with a precise proof step; selecting a design does not prove it. Do not run broad suites just to change docs.

3. **Resolve related decisions together.** Find shared causes, incompatible proposals, and prerequisites. Use [architect](../architect/SKILL.md) for consequential choices between different designs; keep routine decisions short. Choose one approach, explain why its strongest alternative loses, and name contract, migration, compatibility, and failure-handling consequences. Resolve upstream choices first, then revisit every dependent ticket. Clearing a design blocker does not finish dependent implementation.

4. **Record decisions where they belong.** Give each item a concrete decision or reaffirmed recommendation, source evidence (`file:line`, command result, or authoritative link), and next action. Specify intended behavior, affected boundaries, observable acceptance, and prerequisites without leaving "A or B" to the implementer. Keep small decisions in tickets; use RFCs for substantial contracts. Complete a draft's Decision, settle Open questions, and update Status, preserving rationale and alternatives. Describe future behavior as a target until implemented; refresh only related docs.

   Give each ticket one honest disposition, using the repo's vocabulary:

   | Disposition | Meaning and required follow-through |
   | --- | --- |
   | Ready | The decision is settled and the implementation can start. Keep the ticket and any accepted specification open. |
   | Waiting on a prerequisite | Name the prerequisite IDs and what must land first. Decision dependencies and implementation dependencies are distinct. |
   | Blocked | Name the missing fact, access, or authority; give a recommended default where useful and an exact unblock condition. Continue independent work. |
   | Deferred | Explicitly choose not to spend on it now, explain the tradeoff, and give a concrete revisit trigger. Do not defer merely because a choice is difficult. |
   | Closed | Evidence shows it is already complete, a duplicate points to its surviving item, or the owner decision rejects the work. State which; never describe a rejected proposal as a fixed defect. |

   Keep unimplemented fixes open. Follow the repo's RFC cleanup rules, moving durable facts to owning docs before removal. Removed IDs still appear in the report. File new tickets only for distinct gaps or missing implementation prerequisites, following existing ID rules.

5. **Reconcile and check.** Account for the starting inventory and new items: no omissions, lost IDs, contradictory statuses, broken links, or dangling dependencies. Closed duplicates lead to surviving work. Resolve dependency cycles and incompatible decisions, or name the external constraint preventing resolution. Order work by prerequisites, then priority and ID among ready items; do not inflate priorities to force order. Review the diff for scope and run narrow documented docs checks. Report missing evidence without claiming future implementation checks passed.

6. **Close with the complete report below.** Invite feedback and revise affected decisions and dependents through the repo's normal lifecycle. Offer [burn-down-the-backlog](../burn-down-the-backlog/SKILL.md) for implementation. If both phases were already requested, report the decision checkpoint and continue without asking again.

   Load the actual backlog skill for that handoff; pass decisions, acceptance, prerequisite order, eligible work, and blockers. It consumes `TODO.md`; for another tracker, resolve how execution will read and close canonical tickets before switching. Do not silently create a competing backlog. Preserve its branch, per-ticket commit, verification, and publication rules. A triage-only request stops here; offering the next skill does not invoke it.

**The test:** every inventoried RFC and ticket has an evidence-backed disposition, every runnable ticket has one implementable recommendation, and no design acceptance is mistaken for a completed fix.

**Report:** scope and coverage limits; consequential decisions and their tradeoffs; then a complete table with `Item | Decision and reason | Disposition | Prerequisite or next action`. Include every original RFC and unresolved ticket, even those removed during triage, plus new items; related rows may share a decision but must name every ID. Counts or selected highlights do not replace this table. Finish with the implementation order, genuine blockers, files changed, checks and limits, commit/publication state, and an invitation to give feedback or proceed with `burn-down-the-backlog`. If both phases were already authorized, state that you are proceeding instead.
