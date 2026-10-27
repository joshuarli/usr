---
name: error-model
description: "Apply when introducing or changing an error type, how errors propagate or are presented, retry or cancellation handling, or exit-code and status mapping. Skip incidental error handling in unrelated code."
---

# Error Model

An error is part of the program's contract, not a string on the unhappy path.

- **Classify only the failures that matter here** (invalid input, invalid configuration, missing resource, permission, dependency failure, transient, timeout, cancellation, conflict, corrupt state, invariant violation). A category no caller distinguishes does not earn a variant.
- **User and environment failures return errors; they never panic.** A violated internal invariant stays distinguishable (assert or panic); strengthen the type first (`make-invalid-states-unrepresentable`), and assert only what the type cannot express. Do not disguise it as a recoverable error, and do not turn a bug into a vague runtime error.
- **Keep the structured cause:** category, source, path or resource, status. Render text once, at the presentation boundary.
- **Add context once, where meaning changes.** Do not repeat the same wording at every layer. Translate a dependency's error at the boundary and keep its source.
- **Retryability is structure, never message text.** Retry policy lives apart from presentation.
- **Cancellation is not failure.** Callers can skip noisy diagnostics and wrongful retries.
- **Batch work has a stated contract** in its type: all-or-nothing, partial result plus errors, stop at first, or best effort. Never silently drop a success or a failure.
- **One boundary converts errors** to stderr, exit codes, HTTP statuses, or telemetry. Deep code never calls `exit()` or formats the final diagnostic.
- **Deaths have a status contract.** A signal-terminated process reports signal death (128+signal to a shell); handler and exit rules live in `lifecycle-concurrency`. State which signals terminate gracefully and prove it by killing the process mid-operation.
- **Every ignored error has a reason** (cleanup, flush, close, rollback, logging).

**The test:** can a caller decide between retry, report, and abort from the error's type alone, without reading its text?

Test category, context, retryability, exit or status mapping, cleanup, and partial completion. Do not assert full message strings unless the text is a compatibility contract. Keep observable exit behavior unless the request changes it.

**Report:** the failure categories and boundaries you set, and any change to exit or status behavior.
