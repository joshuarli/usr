---
name: deslop
description: "Use when asked to deslop, simplify, or clean up code, or for a focused cleanup pass after implementation. Skip behavior changes and new features."
---

# Deslop

Make code easier to maintain without changing its behavior. Prefer a small, justified diff over a comprehensive rewrite.

## Scope

Read applicable repository instructions and nearby code. Use the requested scope; otherwise review the current task's changes, including staged, unstaged, and new files. Keep edits local and preserve unrelated work.

## Cleanup

- Delete comments that merely narrate code. Keep rationale, constraints, and non-obvious invariants.
- Remove needless indirection, speculative generality, and redundant code. Reuse existing helpers when they genuinely fit; do not force unrelated logic into one abstraction.
- Simplify convoluted control flow and unclear names. Favor straightforward code over clever compression.
- Fix the underlying typing issue instead of hiding it with casts or suppressions.
- Remove code, guards, fallbacks, or metadata only after checking their contracts and implicit or external consumers. No local references and passing tests are not proof of redundancy.

Preserve interfaces, error semantics, and safety guarantees. Do not add dependencies, redesign architecture, weaken tests, or make unrelated style changes. Leave uncertain changes alone and flag them; separate behavioral fixes from cleanup.

## Verify

Run the narrowest check that covers the diff and inspect the final diff for accidental behavior changes. A no-change result is valid.

**Reply:** the substantive edits, checks actually run, and unresolved concerns.
