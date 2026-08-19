# Background Job, Retry, and Idempotency Semantics

You are improving an existing codebase so queued/background work has explicit claim, retry, deduplication, idempotency, lease, completion, and failure semantics.

The goal is to prevent duplicate side effects, lost work, zombie leases, retry storms, and jobs whose lifecycle is implicit.

Preserve intended processing semantics unless explicitly changing them.

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

## 1. Define delivery semantics

State whether the system provides:

- at-most-once
- at-least-once
- effectively-once through idempotency

Avoid claiming true exactly-once unless the transactional boundary actually provides it.

## 2. Make job state explicit

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

## 3. Define claim/lease semantics

For leases, specify:

- owner identity
- lease duration
- renewal
- expiration
- takeover
- completion authority

A worker should not complete a job it no longer owns.

## 4. Make side effects idempotent where retries can duplicate execution

Use:

- idempotency keys
- transactional outbox/inbox patterns
- compare-and-set state
- durable dedupe

as appropriate.

Do not rely on in-memory "already did this" flags for durable guarantees.

## 5. Define crash windows

For each durable transition, reason about crashes:

```text
after side effect but before acknowledgement
after claim but before execution
after result persisted but before status update
```

Make recovery behavior explicit.

## 6. Bound retries

Define:

- retryable errors
- maximum attempts/deadline
- backoff
- jitter
- dead-letter/final failure

## 7. Avoid synchronized retry storms

Spread retries where appropriate and integrate with global backpressure.

## 8. Make cancellation semantics explicit

Decide whether cancellation affects:

- queued jobs
- leased jobs
- external side effects already started
- retries

## 9. Define deduplication scope

A dedupe key must state:

- what operation it represents
- time/lifetime scope
- tenant/account scope
- payload identity

## 10. Test failure windows

Use focused tests for:

- worker crash
- lease expiry
- duplicate delivery
- retry
- stale owner completion
- dedupe
- cancellation
- dead-letter transition

## Explicit anti-patterns

Do not:

- claim exactly-once loosely
- acknowledge work before durable side effects without reasoning about loss
- retry arbitrary failures forever
- let expired workers complete jobs
- use process-local dedupe for durable guarantees
- hide job lifecycle in booleans
- ignore crash windows

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
