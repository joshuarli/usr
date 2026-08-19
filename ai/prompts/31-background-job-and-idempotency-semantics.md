# Background Job, Retry, and Idempotency Semantics

You are improving this codebase so queued/background work has explicit claim, retry, deduplication, idempotency, lease, completion, and failure semantics.

The goal is to prevent duplicate side effects, lost work, zombie leases, retry storms, and jobs whose lifecycle is implicit.

Scope: queues, workers, schedulers, retries, leases, heartbeats, dedupe, acknowledgements, results, and dead-letter behavior.

Applicability: Apply this prompt only when the repository has background/queued work that may be retried, duplicated, leased, cancelled, or recovered after crashes. If the condition is materially absent, report that evidence and make no speculative changes.

Preserve: Existing valid behavior, public contracts, persisted data and formats, output, side effects, permissions, state transitions, and supported-platform semantics unless this request explicitly changes them.

Intentional changes: Only changes explicitly authorized by the invoking request; otherwise none.

If inspection shows that the relevant contract already holds, do not manufacture
changes. Verify it, correct only concrete gaps, and report the evidence.

## First inspect the repository

Before editing:

- inventory job queues, workers, schedulers, cron loops, retries, leases, locks, status fields, heartbeats, dedupe keys, dead-letter behavior, and job result persistence
- identify when jobs become visible
- identify acknowledgement/completion semantics
- identify crash windows
- identify side effects performed before/after acknowledgement
- identify duplicate-delivery behavior
- identify stuck-job recovery
- inspect tests around retry and crash behavior
- run baseline checks

- Record failures that predate the work.

## Non-negotiable design

Each numbered requirement defines an invariant or observable behavior, its
authoritative owner or boundary, the shortcut or ambiguous state it prohibits,
and the evidence that proves it. Do not prescribe incidental implementation
structure unless that structure is itself part of the contract.

### 1. Define delivery, job state, and lease ownership semantics

#### Define delivery semantics


State whether the system provides:

- at-most-once
- at-least-once
- effectively-once through idempotency

Avoid claiming true exactly-once unless the transactional boundary actually provides it.

#### Make job state explicit


Typical states may include:

```text
queued
leased/running
succeeded
failed
retry_wait
dead
cancelled
```

Use the states that match the real system.

#### Define claim/lease semantics


For leases, specify:

- owner identity
- lease duration
- renewal
- expiration
- takeover
- completion authority

A worker should not complete a job it no longer owns.

### 2. Make retryable side effects duplicate-safe across crash windows

#### Make side effects idempotent where retries can duplicate execution


Use:

- idempotency keys
- transactional outbox/inbox patterns
- compare-and-set state
- durable dedupe

as appropriate.

Do not rely on in-memory "already did this" flags for durable guarantees.

#### Define crash windows


For each durable transition, reason about crashes:

```text
after side effect but before acknowledgement
after claim but before execution
after result persisted but before status update
```

Make recovery behavior explicit.

### 3. Bound retries and prevent synchronized retry storms

#### Bound retries


Define:

- retryable errors
- maximum attempts/deadline
- backoff
- jitter
- dead-letter/final failure

#### Avoid synchronized retry storms


Spread retries where appropriate and integrate with global backpressure.

### 4. Define cancellation and deduplication scope

#### Make cancellation semantics explicit


Decide whether cancellation affects:

- queued jobs
- leased jobs
- external side effects already started
- retries

#### Define deduplication scope


A dedupe key must state:

- what operation it represents
- time/lifetime scope
- tenant/account scope
- payload identity

### 5. Test the dangerous failure windows


Use focused tests for:

- worker crash
- lease expiry
- duplicate delivery
- retry
- stale owner completion
- dedupe
- cancellation
- dead-letter transition

### Migration and compatibility policy

Do not create parallel legacy and canonical implementations as part of this work.
If a rename, move, replacement, or contract change becomes necessary, inventory all
references first, keep one canonical path, and retain compatibility only when the
invoking request or an existing external contract requires it.

## Explicit anti-patterns

Do not:

- claim exactly-once loosely
- acknowledge work before durable side effects without reasoning about loss
- retry arbitrary failures forever
- let expired workers complete jobs
- use process-local dedupe for durable guarantees
- hide job lifecycle in booleans
- ignore crash windows


## Verification

After editing:

- Run the nearest hard judge for queues, workers, schedulers, retries, leases, heartbeats, dedupe, acknowledgements, results, and dead-letter behavior: the compiler, type checker, schema/build check, or focused tests that can reject an invalid change.
- Test the observable success behavior, failure behavior, edge cases, and invariants established by the numbered requirements.
- Audit delivery semantics, job states, lease ownership, idempotency, crash windows, bounded retries, dedupe, cancellation, and failure-window tests; classify every remaining exception rather than assuming it is harmless.
- Broaden checks only when the changed boundary warrants it, and distinguish pre-existing failures from regressions introduced by this work.

## Acceptance criteria

The work is complete only when:

- delivery semantics are named accurately
- job states and transitions are explicit
- lease ownership is enforceable
- retryable work is idempotent or otherwise duplicate-safe
- crash windows have defined recovery
- retries are bounded
- dedupe semantics are scoped explicitly
- cancellation behavior is defined
- failure-window tests exist

The architectural principle is: **background work is a distributed state machine; model it as one.**
