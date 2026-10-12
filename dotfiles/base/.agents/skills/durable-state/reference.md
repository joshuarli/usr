# Durable State: Data Model, Formats, Transactions, and Background Work

You are improving this codebase so durable state has a data model that represents real entities and invariants, explicit on-disk and on-wire format contracts, clear ownership, transactional semantics, and defined failure and recovery behavior.

The goal is to prevent partial updates, inconsistent read-modify-write sequences, hidden N+1 behavior, persistence logic leaking across the codebase, accidental format changes, lost or duplicated background work, and schemas that store accidental implementation shapes instead of domain facts.

Scope: database/durable-file access, entities, keys, relationships, cardinality, nullability, blobs, state and timestamp fields, tenancy, transactions, constraints, migrations, read-modify-write paths, query shape, cache interaction, persisted and wire formats and their versioning, and queued/background work with leases, retries, and deduplication.

Applicability: Apply this prompt only when the codebase has durable state, a serialized format that crosses a persistence or external compatibility boundary, or retried/leased background work whose data model, atomicity, consistency, concurrency, compatibility, or crash-recovery behavior needs an explicit contract. If the condition is materially absent, report that evidence and make no speculative changes.

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
- tables/collections/entities, primary and foreign keys, and uniqueness constraints
- nullable fields, JSON/blob catch-all columns, polymorphic records, and denormalized duplicate fields
- status/state columns and timestamp/lifecycle fields
- ownership/tenant boundaries
- JSON/YAML/TOML/binary formats, cache files, config files, IPC and HTTP/RPC payloads, manifests, and golden fixtures, including format/version fields, unknown-field behavior, and places where domain models double as wire models
- job queues, workers, schedulers, leases, heartbeats, dedupe keys, acknowledgement points, and stuck-job recovery

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


### 5. Model entities, cardinality, and absence explicitly

#### Model entities by stable identity and make cardinality explicit

Determine which concepts have independent identity and lifecycle; do not create
entities for transient implementation details. Represent one-to-one,
one-to-many, and many-to-many relationships with structures that enforce the
intended cardinality, and encode uniqueness and ownership (unique per account,
one active lease per job) as constraints where the datastore can enforce them.

#### Keep queryable truth structured and singular

JSON/blob columns are for truly opaque payloads, schemaless extension data, or
rarely queried metadata, not for core relational facts. If the same fact is
stored in two places, define ownership and synchronization or eliminate the
duplicate. Do not denormalize without workload evidence.

#### Give null, state, and time precise meaning

A nullable field should mean one specific kind of absence, not "not initialized
yet", "wrong state", or "legacy". If fields are only valid in particular states,
consider whether constraints or separate tables express the lifecycle better.
Name timestamps for what they record (`created_at`, `leased_at`, `completed_at`,
`expires_at`) rather than a generic `timestamp`.

#### Keep tenant ownership visible

For multi-tenant data, ownership should be explicit enough that queries cannot
casually omit tenant scope.

#### Converge on one canonical schema

Migrations should move toward one canonical model, not leave permanent
half-migrations with multiple equally authoritative representations.

### 6. Treat serialized formats as contracts

- Once persisted or consumed externally, field names, discriminants, defaults,
  omission behavior, and null semantics are compatibility commitments. Do not
  change them during internal refactors.
- Use separate wire/persistence types when the external shape is legacy-shaped,
  needs optionality the domain does not, or must be validated before trust. Do
  not duplicate a model whose contract is genuinely the same. Do not derive
  serialization on internal types without considering what it exposes, and keep
  secrets out of serialized output.
- Choose the versioning strategy deliberately (version field, additive fields
  with defaults, tagged variants, migration-on-read or on-write) instead of an
  undocumented "try the old shape, then the new shape" fallback.
- Decide unknown-field behavior (reject, ignore, or preserve for round-trip), and
  keep absent, null, empty, and default distinct unless the format says otherwise.
- Syntactic deserialization is not semantic validity: convert raw forms into
  validated domain values.
- Keep one canonical writer for the current format. Old readers may remain; old
  writers should not.
- Make output deterministic (ordering, formatting) where it is diffed, hashed, or
  checked in. State whether `decode(encode(x)) == x` is required or whether
  canonicalization is intended.
- Keep small fixtures for the oldest supported version, the current version,
  additive/unknown fields, deprecated variants, and malformed input.

### 7. Model background work as a durable state machine

- State the delivery semantics honestly: at-most-once, at-least-once, or
  effectively-once through idempotency. Do not claim exactly-once unless a
  transactional boundary provides it.
- Make job states explicit (for example queued, leased, succeeded, retry-wait,
  dead, cancelled), not a pile of booleans.
- Specify lease owner, duration, renewal, expiration, and takeover. A worker must
  not complete a job it no longer owns (enforce with compare-and-set).
- For each durable transition, walk the crash windows: after the side effect but
  before acknowledgement, after claim but before execution, after the result is
  persisted but before the status update. Make recovery explicit, and use
  idempotency keys, outbox/inbox patterns, or durable dedupe rather than
  in-memory "already done" flags.
- Bound retries (retryable categories, max attempts or deadline, backoff,
  jitter, dead-letter) and state what cancellation does to queued jobs, leased
  jobs, and side effects already started.
- Scope a dedupe key by operation, lifetime, tenant/account, and payload identity.
- Test worker crash, lease expiry, duplicate delivery, stale-owner completion,
  retry, cancellation, and the dead-letter transition.

## Explicit anti-patterns

Do not:

- silently rename persisted or wire fields
- keep old and new writers equally canonical
- discard unknown fields when round-trip preservation is required
- claim exactly-once loosely, or use process-local dedupe for a durable guarantee
- let an expired worker complete a job
- put core domain fields in generic JSON blobs
- use nullable columns to encode state-machine confusion
- normalize mechanically to the theoretical maximum
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
- entities and relationships reflect real domain concepts, with cardinality and uniqueness enforced where practical
- null, state, and timestamp fields have precise meaning, and core facts are queryable and constrained
- persisted and wire formats have a documented version, unknown-field, and absent/null/default policy, one canonical writer, and compatibility fixtures
- background work has named delivery semantics, enforceable lease ownership, bounded retries, defined crash recovery, and failure-window tests
- existing data contracts remain valid

The architectural principle is: **durability is a contract; a schema should store facts once, constrain relationships, and make atomicity and consistency visible.**
