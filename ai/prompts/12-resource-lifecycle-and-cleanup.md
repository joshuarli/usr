# Resource Lifecycle and Cleanup Audit

You are improving this codebase so every resource has clear acquisition, ownership, cleanup, cancellation, and shutdown semantics.

The goal is to prevent leaked processes, descriptors, temporary files, locks, sockets, transactions, tasks, and partially initialized resources.

Scope: files, sockets, transactions, locks, temp artifacts, child processes, tasks, watchers, terminal modes, mappings, and leases.

Applicability: Apply this prompt only when the subsystem acquires resources whose partial initialization, cancellation, cleanup, or shutdown semantics matter. If the condition is materially absent, report that evidence and make no speculative changes.

Preserve: Existing valid behavior, public contracts, persisted data and formats, output, side effects, permissions, state transitions, and supported-platform semantics unless this request explicitly changes them.

Intentional changes: Only changes explicitly authorized by the invoking request; otherwise none.

If inspection shows that the relevant contract already holds, do not manufacture
changes. Verify it, correct only concrete gaps, and report the evidence.

## First inspect the repository

Before editing:

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

- Record failures that predate the work.

## Non-negotiable design

Each numbered requirement defines an invariant or observable behavior, its
authoritative owner or boundary, the shortcut or ambiguous state it prohibits,
and the evidence that proves it. Do not prescribe incidental implementation
structure unless that structure is itself part of the contract.

### 1. Pair acquisition with ownership through partial initialization and early failure

#### Pair acquisition with ownership


A resource should have an obvious owner responsible for release.

Prefer structured ownership and RAII where the language supports it.

#### Handle partial initialization


If initialization has multiple steps, ensure failure at step N cleans up steps 1..N-1.

Avoid objects that are externally visible before they are valid.

#### Define cleanup on early return


Audit every error path between acquisition and normal completion.

Cleanup must not depend on reaching the happy-path epilogue.

### 2. Define cancellation and shutdown as lifecycle contracts

#### Define cancellation semantics


For long-running work, decide what cancellation does to:

- child processes
- temp files
- transactions
- locks
- queued work
- externally visible state

Cancellation should not leave ambiguous ownership.

#### Define shutdown order


If components depend on one another, make shutdown ordering deliberate.

Examples:

```text
stop accepting work
drain/abort workers
flush state
close persistence
release external resources
```

### 3. Handle cleanup failure and temporary mutation deliberately

#### Treat cleanup failures deliberately


Do not silently discard cleanup errors.

Also do not overwrite the primary failure casually.

Define precedence and logging/reporting semantics.

#### Make temporary artifacts atomic where needed


For file generation/update workflows, consider:

```text
create temp
write
flush
fsync if durability requires it
rename/replace atomically
cleanup temp on failure
```

### 4. Prevent detached work and oversized lock lifetimes

#### Avoid detached work without ownership


Background tasks and child processes should not outlive the component that conceptually owns them unless explicitly designed to.

#### Keep lock lifetime narrow


Do not hold locks across blocking I/O, callbacks, or unrelated work unless required and justified.

### Migration and compatibility policy

Do not create parallel legacy and canonical implementations as part of this work.
If a rename, move, replacement, or contract change becomes necessary, inventory all
references first, keep one canonical path, and retain compatibility only when the
invoking request or an existing external contract requires it.

## Explicit anti-patterns

Do not:

- rely on process exit for cleanup
- duplicate manual cleanup in many branches when structured ownership can encode it
- ignore child-process lifecycle
- detach tasks casually
- leak temp files on error
- overwrite primary errors with cleanup errors
- hold broad locks for convenience


## Verification

After editing:

- Run the nearest hard judge for files, sockets, transactions, locks, temp artifacts, child processes, tasks, watchers, terminal modes, mappings, and leases: the compiler, type checker, schema/build check, or focused tests that can reject an invalid change.
- Test the observable success behavior, failure behavior, edge cases, and invariants established by the numbered requirements.
- Audit acquisition/release pairs, partial init, early returns, cancellation, shutdown order, cleanup errors, detached work, and lock lifetime; classify every remaining exception rather than assuming it is harmless.
- Broaden checks only when the changed boundary warrants it, and distinguish pre-existing failures from regressions introduced by this work.

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
