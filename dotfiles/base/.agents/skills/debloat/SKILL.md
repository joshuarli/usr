---
name: debloat
description: "Use for /debloat: a deep review of a repo, path, or change that weighs each mechanism's cost against what it buys, and finds what to delete, inline, merge, or walk back (dead code, speculative layers, config, dependencies, tests, tooling, docs, CI steps). Reports ranked findings, then applies the ones the owner confirms. The restrained sibling of ultrareview. Skip performance work, hardening, new features, and bug hunting."
disable-model-invocation: true
metadata:
  opencode/autoinvoke: "false"
---

# Debloat

Review the requested path or change, or the repository when none is named, for live mechanisms whose upkeep costs more than their benefit. Dead code is easy; over-engineering is the goal. Name what was outside scope, rank findings first, and edit only after the owner confirms them.

## Rules

- **Subtract only.** Findings remove, inline, merge, or narrow. Do not add tests, checks, abstractions, config, dependencies, CI, or hardening; do not propose a split, rename, or reorganization. Do not optimize; use `make-it-fast` only when asked. Speed gains from a deletion are a footnote.
- **Weigh both sides.** Name concrete costs and the behavior, invariant, gate, or current second case a mechanism buys. Live, tested, documented code can still be bloat; file size alone proves nothing.
- **Keep tiers separate.** A `cut` preserves behavior, errors, and public contracts and fits one diff. A `walk-back` removes live behavior or machinery; name who loses what and what replaces it, often nothing. The owner decides walk-backs separately.
- **Respect declared work.** Repo instructions, invariants, and gates stand. Open TODOs and RFCs are not findings; remove stale ones already done. Note unrelated correctness bugs in one line, with no ticket unless a simplification depends on them.
- **Prove each finding.** Cite a read `file:line`. Prove dead-code removals with `dead-code-archaeology`; trace callers, tests, docs, and loss for other changes with `blast-radius`. Mark unproven claims or drop them.
- **Wait for confirmation.** Steps 1–5 are read-only. Apply only findings the owner confirms; findings discovered later wait for approval.
- **Follow repo rules.** Read `AGENTS.md` and run the cheapest baseline check. No formatters, commits, or pushes. Apply one change at a time, run its narrowest check, and revert a removal that breaks it. An unapproved contract change returns to the owner.

## Steps

1. **Orient.** Read `AGENTS.md`, README, manifests, open TODOs and RFCs, entry points, tests, and recent churn (`git log --stat`; date a path with `git log -1 --format=%cs -- PATH`). Run a baseline check. Use line counts, reachable references, and code-to-test/docs/tooling ratios to direct the sweep, never as findings by themselves.
2. **Map mechanisms.** For each subsystem, name its layers, modules, registries, adapters, state machines, queues, caches, options, protocols, recovery paths, tests, and procedures. State in one line what each buys and who uses it today.
3. **Sweep every lens below.** Read code, not only search results. Dead-code checks go first; always cover the structural lenses. For a scope too broad to hold, use `orchestrate` with one read-only worker per subsystem and give it all lenses, the mechanism map, and the finding format. Use `expert` for cross-cutting design.
4. **Prove and rank.** Prove no supported caller depends on a proposed cut. For a walk-back, trace affected callers, tests, and docs, state the loss, and judge whether it costs less than what goes. Use `blast-radius`. Rank by reader load removed times confidence, not effort; merge common causes and cap each tier at ten. Include the strongest structural findings. An empty structural list requires a complete sweep.
5. **Confirm.** Present the findings and stop. The owner can accept all, select some, or reject them. File only deferred work to TODO.
6. **Apply.** Change only confirmed items, one logical change at a time. Run narrow checks; revert failures. Stop for any contract change the owner did not approve.

## Lenses

For every structural lens, ask what it buys, who needs it now, and what simpler design would do.

| Aspect | Skill | Ask |
| --- | --- | --- |
| Dead code | `dead-code-archaeology` | Which paths have no consumer? Prove it before deletion. |
| Duplicated facts | `single-source-of-truth` | Which defaults, limits, or closed sets can have one owner? |
| **Layers** (structural) | `api-surface-and-module-boundaries` | Follow a user action; count wrappers, forwarding modules, and state hops that add no behavior. |
| **Speculation** (structural) | none | Which knobs, hooks, flags, interfaces, or generic designs serve only one case? |
| **Machinery** (structural) | none | Which caches, queues, recovery systems, state machines, protocols, or derived pipelines cost more than the failures they prevent? Would inline work, recomputing, or failing loudly suffice? |
| **Features** (structural) | none | Which behavior has no user, product-doc, test, or recent-history evidence? |
| Dependencies | none | Can a small standard-library or local implementation replace a dependency? What transitive cost disappears? |
| **Tests** (structural) | `test-audit`, `renovate-tests` | Which tests are redundant, trivia, smoke tests, or coupled to implementation? Can tests or test-only seams be removed? |
| **Tooling and process** (structural) | none | Which tools, records, docs, and gates are unreachable, duplicated, or costlier than the failure they catch? Declared gates stay. |
| CI | none | Which jobs repeat local checks or guard nothing? Report candidates; do not edit CI. |
| Comments | `comment-cleanup` | Which comments excuse code that should be fixed or removed? |
| Docs | `technical-writing` | Which docs repeat code or each other, describe removed machinery, or track completed work? |

Skip `error-model`, `lifecycle-concurrency`, `durable-state`, `os-boundaries`, and `make-it-fast`; they address changes this review must not add. Read them only to understand the benefit of existing mechanisms.

## Findings

Use the `todo` ticket shape with these fields:

- **Tier:** `cut` or `walk-back`.
- **Cost:** the lines, files, concepts, dependencies, or steps removed.
- **Benefit lost:** `none` for a cut; for a walk-back, state what behavior or guarantee goes and who notices.
- **Fix with:** the skill that owns the removal.
- **Safe because:** the evidence that makes a cut safe or the reason a walk-back is acceptable.

**The test:** the owner can judge a smaller design from evidence, and each walk-back names its loss. No finding asks for more code, tests, or CI.

**Report:** before confirmation, give the scope, baseline, ranked findings with cost and lost benefit, covered and skipped lenses with reasons, mechanisms judged worth keeping, and open questions. If there are only cuts, explain which structural lenses were empty. After applying, report removals, checks run or skipped, reverted or deferred findings, and open decisions.
