# Resource Lifecycle and Cleanup Audit

You are improving an existing codebase so every resource has clear acquisition, ownership, cleanup, cancellation, and shutdown semantics.

The goal is to prevent leaked processes, descriptors, temporary files, locks, sockets, transactions, tasks, and partially initialized resources.

Preserve behavior unless correcting a lifecycle bug.

## First inspect the repository

Inventory resources such as:

- files and file descriptors
- sockets
- database connections and transactions
- locks
- temporary files/directories
- child processes
- threads/tasks
- subscriptions/watchers
- terminal modes
- memory mappings
- external leases
- mounted resources

For each, identify creation and cleanup paths, including errors and cancellation.

## 1. Pair acquisition with ownership

A resource should have an obvious owner responsible for release.

Prefer structured ownership and RAII where the language supports it.

## 2. Handle partial initialization

If initialization has multiple steps, ensure failure at step N cleans up steps 1..N-1.

Avoid objects that are externally visible before they are valid.

## 3. Define cleanup on early return

Audit every error path between acquisition and normal completion.

Cleanup must not depend on reaching the happy-path epilogue.

## 4. Define cancellation semantics

For long-running work, decide what cancellation does to:

- child processes
- temp files
- transactions
- locks
- queued work
- externally visible state

Cancellation should not leave ambiguous ownership.

## 5. Define shutdown order

If components depend on one another, make shutdown ordering deliberate.

Examples:

```text
stop accepting work
drain/abort workers
flush state
close persistence
release external resources
```

## 6. Treat cleanup failures deliberately

Do not silently discard cleanup errors.

Also do not overwrite the primary failure casually.

Define precedence and logging/reporting semantics.

## 7. Make temporary artifacts atomic where needed

For file generation/update workflows, consider:

```text
create temp
write
flush
fsync if durability requires it
rename/replace atomically
cleanup temp on failure
```

## 8. Avoid detached work without ownership

Background tasks and child processes should not outlive the component that conceptually owns them unless explicitly designed to.

## 9. Keep lock lifetime narrow

Do not hold locks across blocking I/O, callbacks, or unrelated work unless required and justified.

## Explicit anti-patterns

Do not:

- rely on process exit for cleanup
- duplicate manual cleanup in many branches when structured ownership can encode it
- ignore child-process lifecycle
- detach tasks casually
- leak temp files on error
- overwrite primary errors with cleanup errors
- hold broad locks for convenience

## Acceptance criteria

The work is complete only when:

- each resource has a clear owner
- partial initialization cleans up correctly
- early returns and cancellation release owned resources
- shutdown ordering is explicit
- cleanup failures have deliberate semantics
- background work cannot silently leak
- lock lifetimes are justified and narrow
- temporary mutation is atomic where required
- lifecycle tests cover meaningful failure paths

The architectural principle is: **if code acquires something, ownership of its end-of-life must be just as explicit.**
