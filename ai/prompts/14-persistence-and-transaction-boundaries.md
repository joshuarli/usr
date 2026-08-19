# Persistence and Transaction Boundary Audit

You are improving an existing codebase so durable state has clear ownership, transactional semantics, schema invariants, and failure behavior.

The goal is to prevent partial updates, inconsistent read-modify-write sequences, hidden N+1 behavior, and persistence logic leaking across the codebase.

Preserve data compatibility unless explicitly permitted otherwise.

## First inspect the repository

Inventory:

- database access
- repositories/DAOs
- transactions
- migrations
- schema constraints
- read-modify-write paths
- retries
- optimistic/pessimistic locking
- bulk operations
- N+1 query patterns
- serialization to durable files
- cache/persistence interactions

## 1. Define transaction boundaries by invariant

A transaction should correspond to a set of changes that must succeed or fail together.

Do not wrap arbitrary layers in transactions merely because they touch the database.

## 2. Keep persistence mechanics at a boundary

Domain logic may decide what should change.

Persistence code should translate that decision into durable operations.

Avoid SQL/ORM calls scattered through unrelated business logic.

## 3. Protect durable invariants in the datastore

Use appropriate constraints for facts that must remain true regardless of application code path.

## 4. Avoid read-modify-write races

Where concurrent writers matter, use:

- atomic update statements
- version checks
- locks
- transactions

rather than hoping a prior read remains current.

## 5. Make consistency assumptions explicit

Document whether reads require:

- strong consistency
- snapshot consistency
- eventual consistency
- stale-cache tolerance

## 6. Audit query shape

Look for:

- N+1 queries
- repeated point lookups
- fetching broad rows then filtering in application code
- unnecessary round trips
- accidental full-table scans

Measure before broad optimization.

## 7. Keep migrations coherent

Migrations should:

- have one direction of schema evolution
- handle existing data safely
- preserve compatibility policy
- avoid relying on application code that may not run atomically with deployment

## 8. Make serialization/versioning explicit

For durable files/blobs:

- define format version
- define compatibility policy
- validate before mutation
- write atomically where required

## 9. Keep cache authority subordinate

Caches should never silently override durable truth.

Define invalidation and stale-read behavior.

## Explicit anti-patterns

Do not:

- scatter persistence calls everywhere
- rely only on application validation for critical durable invariants
- perform unsafe read-modify-write sequences
- use transactions as generic wrappers
- hide N+1 behavior behind abstractions
- let cache state become authoritative accidentally
- mutate durable files non-atomically when corruption matters

## Acceptance criteria

The work is complete only when:

- transaction boundaries correspond to real invariants
- durable constraints protect important persisted truths
- persistence mechanics are localized
- concurrent updates have defined semantics
- query shape is intentional
- migrations preserve compatibility
- durable formats have explicit version/validation policy where needed
- caches remain subordinate
- existing data contracts remain valid

The architectural principle is: **durability is a contract; persistence code should make atomicity and consistency visible.**
