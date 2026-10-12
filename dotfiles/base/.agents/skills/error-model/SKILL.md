---
name: error-model
description: Use when adding or changing error types, error propagation and context, panics or unwrap, retry or cancellation handling, ignored cleanup errors, or exit-code and status mapping.
---

# Error Model

Give failures deliberate semantics: what kind of failure it is, what context survives, who may retry, and who presents it. Apply this to the code being changed or the scope the user names. Do not widen into a repository-wide audit unless asked; if nothing here applies, say so and change nothing.

Read repository and scoped `AGENTS.md` first. Search the affected code for `unwrap`, `expect`, panics, string errors, `map_err`, catch-all handling, ignored errors, and exit conversion, and run the narrowest baseline check before editing.

## Rules

- Classify only the failures that matter in this project (invalid input, invalid configuration, missing resource, permission, external dependency, transient, timeout, cancellation, conflict, corrupt persisted state, internal invariant violation). Do not create categories for symmetry.
- User and environment failures return errors and never panic. A violated internal invariant stays distinguishable; do not disguise it as a recoverable error, and do not turn programmer bugs into vague runtime errors.
- Keep structured causes: category, source, relevant path or resource, status. Render text only at the presentation boundary.
- Add context once, where a low-level mechanism gains domain meaning, and do not repeat the same wording at every layer. Translate dependency errors at the boundary while preserving the source.
- Decide retryability structurally; never parse message text. Keep retry policy out of error presentation.
- Cancellation is distinguishable from failure so callers skip noisy diagnostics and wrongful retries.
- For batch or multi-step work, choose the contract (all-or-nothing, partial result plus errors, first failure stops, best effort) and represent it in the type; do not silently drop successes or failures.
- Convert errors to stderr, exit codes, HTTP statuses, or telemetry at one narrow boundary. Deep code does not call `exit()` or format final diagnostics.
- Every intentionally ignored error (cleanup, flush, close, rollback, logging) has a stated reason.

## Verify

Test error category, relevant context, retryability, exit or status mapping, cleanup, and partial completion. Avoid full-string assertions unless the text is a compatibility contract. Classify each remaining `unwrap`, `expect`, or panic. Distinguish pre-existing failures from regressions, and preserve observable exit behavior unless the request changes it.

Load `reference.md` for the full inspection checklist, anti-patterns, and acceptance criteria when the change is a broad audit or the design is non-trivial. Where it says "this codebase" or "repository-wide", read it as the requested scope.

## Handoff

Report the failure categories and boundaries you established, any change to exit or status behavior, checks actually run, and decisions the user must make.
