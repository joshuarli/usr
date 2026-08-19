# Make the Error Model Explicit

You are improving this codebase so failures have deliberate semantics instead of collapsing into strings, panics, generic catch-all errors, or inconsistent ad hoc handling.

The goal is to make it obvious which failures are user mistakes, environmental failures, external-service failures, transient conditions, cancellation, violated invariants, or partial outcomes—and to preserve useful context across boundaries.

Scope: error types, propagation, context, panic paths, retryability, cancellation, partial success, presentation, and exit/status mapping.

Applicability: Apply this prompt only when failure behavior is fragmented, stringly typed, over-wrapped, panic-prone, or semantically ambiguous. If the condition is materially absent, report that evidence and make no speculative changes.

Preserve: Existing valid behavior, public contracts, persisted data and formats, output, side effects, permissions, state transitions, and supported-platform semantics unless this request explicitly changes them.

Intentional changes: Only changes explicitly authorized by the invoking request; otherwise none.

If inspection shows that the relevant contract already holds, do not manufacture
changes. Verify it, correct only concrete gaps, and report the evidence.

## First inspect the repository

Before editing:

- inventory error types and error aliases
- search for `unwrap`, `expect`, panic paths, generic exceptions, string errors, `map_err`, catch-all handling, ignored errors, retries, and exit-code conversion
- inspect logging and diagnostic presentation
- identify errors converted to strings too early
- identify duplicated context wrapping
- identify external-library errors leaking through public/domain APIs
- identify places where retryability or cancellation is inferred from error text
- inspect cleanup behavior on errors
- run narrow baseline checks

- Record failures that predate the work.

## Non-negotiable design

Each numbered requirement defines an invariant or observable behavior, its
authoritative owner or boundary, the shortcut or ambiguous state it prohibits,
and the evidence that proves it. Do not prescribe incidental implementation
structure unless that structure is itself part of the contract.

### 1. Define failure categories without conflating programmer bugs and runtime errors

#### Define an error taxonomy


Classify meaningful failures into categories such as:

- invalid user input
- invalid configuration
- missing resource
- permission/access failure
- external dependency failure
- transient/retryable failure
- timeout
- cancellation
- conflict/concurrency failure
- corrupted or invalid persisted state
- internal invariant violation

Use the taxonomy that fits the project; do not create categories merely for symmetry.

#### Keep programmer bugs distinct from runtime errors


Malformed user input should not panic.

Ordinary environmental failures should not panic.

Conversely, a violated internal invariant should not always be disguised as an ordinary recoverable error.

Use assertions/panics for genuine programmer-impossible conditions according to project conventions.

### 2. Preserve structured causes and translate only where meaning changes

#### Preserve structured errors


Do not stringify errors prematurely.

Keep:

- error category/type
- causal source
- relevant path/resource/operation
- status/code where meaningful
- retryability information when part of policy

Render human-readable diagnostics only at presentation boundaries.

#### Add context once, where meaning changes


Context should explain what the application was trying to do.

Good:

```text
failed to load project configuration at ...
```

Bad chains repeat the same wording at every layer.

Add context at boundaries where a low-level mechanism gains domain meaning.

#### Keep external mechanism errors behind boundaries


A domain API should not expose an arbitrary HTTP/SQL/filesystem library error when callers care about domain semantics.

Translate at the boundary while preserving the underlying source.

Do not erase useful mechanism details that operators need for diagnosis.

### 3. Represent retryability and cancellation explicitly

#### Make retryability explicit


If behavior retries only certain failures, encode that decision structurally.

Do not parse error strings to decide whether a failure is transient.

Keep retry policy separate from error presentation.

#### Model cancellation separately


Cancellation is often not an error in the same sense as failure.

Where the project has asynchronous/long-running operations, make cancellation distinguishable so callers can avoid noisy diagnostics or inappropriate retries.

### 4. Define partial outcomes and centralize final presentation

#### Define partial-success semantics


For batch or multi-step operations, decide whether failure means:

- all-or-nothing
- partial result plus errors
- first failure stops work
- best effort

Represent that contract explicitly.

Do not silently discard successful work or failed items.

#### Centralize presentation/exit conversion


For CLIs and services, convert structured errors to:

- stderr/stdout diagnostics
- process exit codes
- HTTP/RPC statuses
- telemetry severity

at a narrow boundary.

Avoid arbitrary deep code calling `exit()` or formatting final user-facing diagnostics.

### 5. Handle ignored/cleanup failures deliberately and test failure contracts

#### Audit ignored errors


Every intentionally ignored error should have a reason.

Particularly inspect failures during:

- cleanup
- flush
- close
- remove-temp-file
- child termination
- rollback
- telemetry/logging

Do not overwrite a primary failure with a secondary cleanup failure without deliberate policy.

#### Test failure behavior


For important failure paths, test:

- error category
- relevant context
- retryability
- exit/status mapping
- cleanup
- side effects
- partial completion

Avoid brittle full-string assertions unless exact diagnostics are part of the public contract.

### Migration and compatibility policy

Do not create parallel legacy and canonical implementations as part of this work.
If a rename, move, replacement, or contract change becomes necessary, inventory all
references first, keep one canonical path, and retain compatibility only when the
invoking request or an existing external contract requires it.

## Explicit anti-patterns

Do not:

- replace structured errors with strings
- panic on user/environment input
- wrap the same context repeatedly
- expose arbitrary dependency errors through domain boundaries without reason
- infer retryability from message text
- conflate cancellation with failure
- silently ignore cleanup errors
- make every error variant unique when callers do not need the distinction
- create a giant catch-all error enum containing implementation trivia
- change observable exit/status behavior accidentally


## Verification

After editing:

- search for premature stringification
- search for `unwrap`/`expect`/panic and classify each remaining use
- verify retry decisions use structure
- verify cancellation and partial-success semantics
- verify external error sources remain inspectable
- verify final presentation happens at clear boundaries
- run focused failure-path tests and broader checks


- Distinguish failures that predate the work from regressions introduced by this change.

## Acceptance criteria

The work is complete only when:

- meaningful failure categories are explicit
- user/environment failures do not panic
- internal invariant violations remain distinguishable
- structured causal context survives until presentation
- external mechanism errors are translated at appropriate boundaries
- retryability and cancellation are explicit where relevant
- partial-success behavior is defined
- final diagnostics/status conversion is centralized
- intentionally ignored errors are justified
- important error paths have contract-focused tests
- existing observable error/exit behavior is preserved unless intentionally changed

The architectural principle is: **errors are part of the program's contract, not incidental strings emitted on the unhappy path.**
