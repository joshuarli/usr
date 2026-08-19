# Schema and Domain Data Model Design

You are improving this codebase so persisted/domain data models represent real entities, relationships, cardinality, ownership, and invariants instead of accidental implementation shapes.

The goal is a model that makes important facts easy to state, query, constrain, and evolve.

Scope: domain/persistence entities, keys, relationships, cardinality, nullability, blobs, state fields, timestamps, constraints, tenancy, queries, and migrations.

Applicability: Apply this prompt only when the repository has a persisted schema or durable domain model whose relationships and invariants materially affect correctness. If the condition is materially absent, report that evidence and make no speculative changes.

Preserve: Existing valid behavior, public contracts, persisted data and formats, output, side effects, permissions, state transitions, and supported-platform semantics unless this request explicitly changes them.

Intentional changes: Only changes explicitly authorized by the invoking request; otherwise none.

If inspection shows that the relevant contract already holds, do not manufacture
changes. Verify it, correct only concrete gaps, and report the evidence.

## First inspect the repository

Before editing:

- inventory tables/collections/entities
- identify primary and foreign keys
- identify nullable fields
- identify JSON/blob catch-all columns
- identify polymorphic records
- identify denormalized duplicate fields
- identify status/state columns
- identify timestamps and lifecycle fields
- identify uniqueness constraints
- identify ownership/tenant boundaries
- inspect common queries and mutations
- inspect migrations and old schema versions
- run baseline checks

- Record failures that predate the work.

## Non-negotiable design

Each numbered requirement defines an invariant or observable behavior, its
authoritative owner or boundary, the shortcut or ambiguous state it prohibits,
and the evidence that proves it. Do not prescribe incidental implementation
structure unless that structure is itself part of the contract.

### 1. Model identity, cardinality, and absence explicitly

#### Model entities by stable identity


Determine which concepts have independent identity and lifecycle.

Do not create entities for transient implementation details.

#### Make cardinality explicit


Represent:

- one-to-one
- one-to-many
- many-to-many

with schema structures that enforce intended cardinality.

#### Use null only for real absence


A nullable field should mean something specific.

Avoid null as a generic placeholder for "not initialized yet", "wrong state", or "legacy".

### 2. Keep queryable truth structured, singular, and constrained

#### Avoid opaque blobs for queryable domain facts


JSON/blob columns are appropriate for:

- truly opaque payloads
- schemaless extension data
- rarely queried metadata

Do not hide core relational/domain facts in blobs merely to avoid schema work.

#### Avoid duplicate authoritative fields


If the same fact is stored in multiple places, define ownership and synchronization or eliminate duplication.

#### Encode uniqueness and ownership


Use schema constraints for identities such as:

```text
unique per account
unique per project
one active lease per job
```

where the datastore can enforce them.

### 3. Give lifecycle states and timestamps precise meaning

#### Model state transitions deliberately


If fields are only valid in particular states, consider whether schema constraints or separate tables/variants better express the lifecycle.

Do not overcomplicate simple status models.

#### Keep timestamps semantically named


Prefer:

```text
created_at
leased_at
completed_at
expires_at
```

over generic `timestamp`.

Distinguish event time from update bookkeeping.

### 4. Design for real queries and explicit tenant ownership

#### Design from real queries


A model should support important access patterns without pathological joins/scans or duplicated truth.

Do not denormalize preemptively without workload evidence.

#### Keep tenant/security boundaries visible


For multi-tenant data, ownership should be explicit enough that queries cannot casually omit tenant scope.

### 5. Evolve toward one canonical schema


Migrations should move toward one canonical model.

Avoid permanent half-migrations with multiple equally authoritative representations.


## Explicit anti-patterns

Do not:

- normalize mechanically to theoretical maximum
- put core domain fields in generic JSON blobs
- use nullable columns to encode state-machine confusion
- duplicate authoritative values casually
- rely only on application code for uniqueness/ownership
- denormalize without measured need
- use generic field names that hide semantic time/state


## Verification

After editing:

- Run the nearest hard judge for domain/persistence entities, keys, relationships, cardinality, nullability, blobs, state fields, timestamps, constraints, tenancy, queries, and migrations: the compiler, type checker, schema/build check, or focused tests that can reject an invalid change.
- Test the observable success behavior, failure behavior, edge cases, and invariants established by the numbered requirements.
- Audit identity, cardinality, null semantics, opaque blobs, duplicate fields, uniqueness/ownership, lifecycle fields, query fit, tenancy, and schema evolution; classify every remaining exception rather than assuming it is harmless.
- Broaden checks only when the changed boundary warrants it, and distinguish pre-existing failures from regressions introduced by this work.

## Acceptance criteria

The work is complete only when:

- entities and relationships reflect real domain concepts
- cardinality and uniqueness are enforced where practical
- null has deliberate semantics
- core facts are queryable and constrained
- duplicate authoritative fields are removed or explicitly synchronized
- state/timestamp fields have precise meaning
- important queries fit the model
- tenant/ownership scope is visible
- migrations converge toward one canonical representation

The architectural principle is: **a schema should store facts once, constrain relationships, and make the domain's important questions natural to ask.**
