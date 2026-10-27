---
name: deduplicate
description: "Apply when the same logic, envelope, or structural pattern repeats across modules and one owner could serve all callers, or when adding a helper others must adopt. Skip single-use code, speculative generality, and facts that must evolve together; use single-source-of-truth."
---

# Deduplicate

Copies multiply every future fix. One owner, many callers.

- **Merge only what must evolve together, not code that looks alike.** Facts, defaults, and limits belong to `single-source-of-truth`; paths with no consumer belong to `dead-code-archaeology`.
- **Survey before centralizing.** Group repeats with `file:line` evidence: what repeats, how many sites, lines saved. Rank by sites times churn risk. A justified no-op is valid; do not manufacture edits.
- **Batch coherently.** Each batch names its concrete benefit, the invariant it preserves, and its smallest regression check. One batch is one owner module plus all its callers plus existing tests. Complete the batch; never leave half-migrated callers.
- **Name one owner.** The helper lives where its responsibility lives: I/O with I/O, retry with the transport, rendering with the presenter. Never a `utils`, `shared`, or `common` drawer, and never a new layer for a single caller. Respect owning-module rules in repo instructions.
- **Preserve the contract.** Signatures and keyword names, error messages, omission-versus-null semantics, ordering and duplicates, resource and lock lifetimes, cancellation, and performance stay identical unless the owner authorized a change. A copy that swallows errors stays swallowing.
- **Absorb only what every caller repeats** (`api-surface-and-module-boundaries`). Caller-specific policy (prefixes, envelopes, retry counts, sort orders) stays with the caller or becomes an explicit parameter, never a hidden default. No config knobs, flags, or speculative generality for one case.
- **Treat a new export as a commitment.** Follow `api-surface-and-module-boundaries` for the shared helper's name, parameters, and placement. Trace affected callers with `blast-radius` before widening scope.
- **Verify each batch** with the narrowest check covering every touched call site, then rescan the diff for accidental contracts, churn, and obsolete code.

**The test:** fix one bug or add one variant. Exactly one owner changes and every caller follows, or a test names the intentional duplicate.

**Report:** each retired group with its new owner and lines removed; intentional duplicates and why they stay; authorized contract changes; checks run and gaps.
