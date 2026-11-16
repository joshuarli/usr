---
name: audit-skills
description: "Use for /audit-skills: improve the agent system's reliability and cost from evidence. Audit instructions for contradictions, duplicate owners, and bloat; measure from sessions whether skills fire and help; find mistakes agents repeat and guard them, architecture first and instructions last; consolidate; prove each fix. `past 2h` limits it to recent sessions; a repo path targets that repo's repeated failures."
disable-model-invocation: true
metadata:
  opencode/slash: "true"
  opencode/autoinvoke: "false"
---

# Audit Skills

The one entry point for improving how agents work here. Instructions drift, skills fire wrongly or add steps without helping, and agents repeat the same mistakes, which get fixed by hand. Each finding ends in the strongest fix available: a mechanism that makes the mistake impossible, a merged or deleted skill, or one owner for a rule. A new instruction is the last resort, for a judgment call nothing can enforce. A good run often leaves fewer instructions than it found.

## Invocation

- `/audit-skills`: the whole loop over the agent system in `~/usr`.
- `/audit-skills past 2h` (any window): stages 2 and 3 over sessions in that window only, across harnesses and repos, including delegation and qualification tooling friction.
- `/audit-skills <repo>`: stages 3, 4 and 6 for that repository, from its history, reviews and sessions, plus its `AGENTS.md` chain and repo-local skills. A window may be combined with it.

Audit and report first. Apply only what the owner approves, unless the invocation explicitly authorizes an unattended repair run (for example `/audit-skills apply`). Even then, park owner decisions: a behavior choice between conflicting rules, removing a slash command the owner types, and model or effort settings.

## Cost

Start cheap and deepen only where evidence warrants. The first pass is an inventory and a bounded sample: byte and description sizes, the checker's warnings, and up to 5 sessions per question. Follow a lead further only when the sample shows a recurring or costly problem. Do not scan full history, run broad suites, or run paired experiments by default; announce any of them first, and causal comparisons need separate authorization.

## Stages

1. **Instruction audit.** Contradictions, rules without one owner, restated enforcement, procedures that belong in tooling, bloat, misplacement, unclear wording, and imprecise descriptions. Read [instructions](references/instructions.md).
2. **Empirical evaluation.** From existing sessions: does each skill load when it should and stay silent when it should not, and was the work better or cheaper for it. Delegation and qualification tooling are judged the same way, from what sessions did. Read [sessions](references/sessions.md).
3. **Recurring failures.** Group the mistakes agents repeat, from user corrections in sessions, fix and revert commits, review comments, and workaround comments. A class counts once it has happened twice. Read [failures](references/failures.md).
4. **Enforcement.** Fix each class at the highest level that works: architecture, then types, then a lint or check, then a behavior test, then documentation. Read [failures](references/failures.md).
5. **Consolidation.** Merge skills that always load together or share an owner, demote or delete skills sessions never needed, retire rules a new guard made redundant, and delete the old way an agent would copy.
6. **Verification.** Prove each fix: a new check fails on a real past mistake, the text-pinning and structural checks pass, every removed decision is accounted for, and a later run of stage 2 or 3 shows whether the situation moved, or says it is too soon to tell.

## Findings

Check every claim against the files or logs before reporting; lanes misread, and a contradiction or friction may already be resolved. Rank one list by impact, then recurrence, then load cost: contradictions and costly repeated failures first. Each finding gives its evidence (`file:line` with the quoted text, or counts with a dated one-line paraphrase), the proposed fix and its level, and why a stronger level does not work.

Keep transcripts private: counts, dates and one-line paraphrases, never prompts or code pasted from a session into a skill, doc, or ticket.

**The test:** every finding cites evidence that survived verification and ends at the strongest level that works; no two files give conflicting orders; each shared rule has one owner; every applied guard was shown to fail on a real past mistake; and no skill decision treats a higher invocation rate as success.

**Report:** the target, window and session counts; findings ranked with evidence and chosen level; owner decisions listed separately; skills with too little data; after applying, the commits, guards and tools added with the instructions they replaced, bytes before and after for the contract, descriptions and total, removed tokens, checks run, and what to re-measure and when.
