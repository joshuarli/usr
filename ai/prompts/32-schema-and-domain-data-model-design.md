# Schema and Domain Data Model Design

You are improving an existing codebase so persisted/domain data models represent real entities, relationships, cardinality, ownership, and invariants instead of accidental implementation shapes.

The goal is not normalization for its own sake. The goal is a model that makes important facts easy to state, query, constrain, and evolve.

Preserve persisted compatibility unless explicitly changing schema semantics.

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

## 1. Model entities by stable identity

Determine which concepts have independent identity and lifecycle.

Do not create entities for transient implementation details.

## 2. Make cardinality explicit

Represent:

- one-to-one
- one-to-many
- many-to-many

with schema structures that enforce intended cardinality.

## 3. Use null only for real absence

A nullable field should mean something specific.

Avoid null as a generic placeholder for "not initialized yet", "wrong state", or "legacy".

## 4. Avoid opaque blobs for queryable domain facts

JSON/blob columns are appropriate for:

- truly opaque payloads
- schemaless extension data
- rarely queried metadata

Do not hide core relational/domain facts in blobs merely to avoid schema work.

## 5. Avoid duplicate authoritative fields

If the same fact is stored in multiple places, define ownership and synchronization or eliminate duplication.

## 6. Encode uniqueness and ownership

Use schema constraints for identities such as:

```text
unique per account
unique per project
one active lease per job
```

where the datastore can enforce them.

## 7. Model state transitions deliberately

If fields are only valid in particular states, consider whether schema constraints or separate tables/variants better express the lifecycle.

Do not overcomplicate simple status models.

## 8. Keep timestamps semantically named

Prefer:

```text
created_at
leased_at
completed_at
expires_at
```

over generic `timestamp`.

Distinguish event time from update bookkeeping.

## 9. Design from real queries

A model should support important access patterns without pathological joins/scans or duplicated truth.

Do not denormalize preemptively without workload evidence.

## 10. Keep tenant/security boundaries visible

For multi-tenant data, ownership should be explicit enough that queries cannot casually omit tenant scope.

## 11. Evolve schema coherently

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
