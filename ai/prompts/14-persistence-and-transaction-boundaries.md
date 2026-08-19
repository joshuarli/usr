# Persistence and Transaction Boundary Audit

You are improving this codebase so durable state has clear ownership, transactional semantics, schema invariants, and failure behavior.

The goal is to prevent partial updates, inconsistent read-modify-write sequences, hidden N+1 behavior, and persistence logic leaking across the codebase.

Scope: database/durable-file access, transactions, constraints, migrations, read-modify-write paths, query shape, and cache interaction.

Applicability: Apply this prompt only when the codebase has durable state whose atomicity, consistency, concurrency, or query behavior needs an explicit contract. If the condition is materially absent, report that evidence and make no speculative changes.

Preserve: Existing valid behavior, public contracts, persisted data and formats, output, side effects, permissions, state transitions, and supported-platform semantics unless this request explicitly changes them.

Intentional changes: Only changes explicitly authorized by the invoking request; otherwise none.

If inspection shows that the relevant contract already holds, do not manufacture
changes. Verify it, correct only concrete gaps, and report the evidence.

## First inspect the repository

Before editing:

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

- Record failures that predate the work.

## Non-negotiable design

Each numbered requirement defines an invariant or observable behavior, its
authoritative owner or boundary, the shortcut or ambiguous state it prohibits,
and the evidence that proves it. Do not prescribe incidental implementation
structure unless that structure is itself part of the contract.

### 1. Align transactions and persistence boundaries with durable invariants

#### Define transaction boundaries by invariant


A transaction should correspond to a set of changes that must succeed or fail together.

Do not wrap arbitrary layers in transactions merely because they touch the database.

#### Keep persistence mechanics at a boundary


Domain logic may decide what should change.

Persistence code should translate that decision into durable operations.

Avoid SQL/ORM calls scattered through unrelated business logic.

### 2. Protect durable truth against invalid and concurrent writes

#### Protect durable invariants in the datastore


Use appropriate constraints for facts that must remain true regardless of application code path.

#### Avoid read-modify-write races


Where concurrent writers matter, use:

- atomic update statements
- version checks
- locks
- transactions

rather than hoping a prior read remains current.

### 3. State consistency and query-shape expectations explicitly

#### Make consistency assumptions explicit


Document whether reads require:

- strong consistency
- snapshot consistency
- eventual consistency
- stale-cache tolerance

#### Audit query shape


Look for:

- N+1 queries
- repeated point lookups
- fetching broad rows then filtering in application code
- unnecessary round trips
- accidental full-table scans

Measure before broad optimization.

### 4. Keep schema evolution, durable formats, and caches coherent

#### Keep migrations coherent


Migrations should:

- have one direction of schema evolution
- handle existing data safely
- preserve compatibility policy
- avoid relying on application code that may not run atomically with deployment

#### Make serialization/versioning explicit


For durable files/blobs:

- define format version
- define compatibility policy
- validate before mutation
- write atomically where required

#### Keep cache authority subordinate


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


## Verification

After editing:

- Run the nearest hard judge for database/durable-file access, transactions, constraints, migrations, read-modify-write paths, query shape, and cache interaction: the compiler, type checker, schema/build check, or focused tests that can reject an invalid change.
- Test the observable success behavior, failure behavior, edge cases, and invariants established by the numbered requirements.
- Audit transaction boundaries, durable constraints, races, consistency assumptions, N+1/round trips, migrations, formats, and cache authority; classify every remaining exception rather than assuming it is harmless.
- Broaden checks only when the changed boundary warrants it, and distinguish pre-existing failures from regressions introduced by this work.

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
