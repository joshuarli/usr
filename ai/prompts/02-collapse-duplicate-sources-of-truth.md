# Collapse Duplicate Sources of Truth

You are improving an existing codebase by finding concepts that are represented, maintained, or validated independently in more than one place and replacing accidental duplication with one authoritative representation.

The goal is not maximal code reuse. The goal is **semantic singularity**: one fact should have one source of truth, with other representations derived from it or mechanically checked against it.

Preserve runtime behavior and public contracts unless this request explicitly changes them.

## First inspect the repository

Before editing:

- inventory registries, enums, lookup tables, parsers, validators, serializers, defaults, schemas, documentation tables, command lists, feature lists, MIME/extension maps, protocol identifiers, routes, state lists, error-code mappings, database metadata, and generated artifacts
- search for repeated strings, names, defaults, discriminants, field lists, and manually synchronized tables
- identify comments such as "keep in sync", "must match", "update both", or equivalent
- identify parallel `match`/`switch` blocks that encode the same closed set
- identify tests whose primary purpose is catching drift between duplicate declarations
- run the narrowest useful baseline checks before editing

## 1. Inventory semantic duplication

Distinguish ordinary repeated code from duplicated knowledge.

High-value targets include:

- an enum plus a separately maintained string parser
- a command registry plus a separate help list
- a database schema plus hand-maintained field metadata
- configuration defaults repeated in CLI/config/docs
- a list of supported formats repeated in parsing, validation, and rendering
- route definitions repeated in dispatch and documentation
- feature definitions repeated in registries and validation
- state definitions repeated across multiple `match` blocks
- one protocol table represented separately for encoding and decoding

Do not merge code merely because it looks similar. Merge **facts that must evolve together**.

## 2. Choose the authoritative representation

For each duplicated concept, explicitly decide which representation owns the truth.

Good authoritative sources are usually:

- the type definition
- a declarative schema
- a registry
- protocol metadata
- the database schema
- generated bindings from an upstream specification

Avoid choosing generated output as the source when a more fundamental declaration exists.

## 3. Derive consumers mechanically

Where practical, make all secondary representations consume or derive from the authoritative declaration.

Examples:

```text
CommandSpec
  ├── parser recognition
  ├── validation
  ├── help rendering
  └── documentation tests
```

```text
enum FileKind
  ├── parse()
  ├── display()
  ├── supported_extensions()
  └── serialization
```

Prefer straightforward iteration, explicit metadata, code generation, macros, derives, or compile-time tables according to the language and project.

Do not introduce a sophisticated generator merely to remove three harmless lines of duplication.

## 4. Keep transformations one-way

Avoid circular authority.

Bad:

```text
A partially derives from B
B partially derives from A
tests reconcile both
```

Good:

```text
A is authoritative
B = f(A)
C = g(A)
```

The direction of truth should be obvious to a reader.

## 5. Remove synchronization comments by removing synchronization work

Comments such as:

```text
// Keep this in sync with ...
```

are architectural alarms.

Whenever feasible, restructure the code so synchronization is impossible to forget.

If duplication is unavoidable because of an external boundary, document why and add a targeted invariant test.

## 6. Use invariant tests for irreducible duplication

Some representations cannot directly share a source because they live across:

- language boundaries
- generated code
- external schemas
- public protocols
- migration snapshots
- documentation
- build systems

When duplication is intentional:

- name the authoritative side
- explain why the secondary copy exists
- add a mechanical drift check if feasible
- fail loudly when the copies diverge

Do not leave intentional duplication indistinguishable from accidental duplication.

## 7. Prefer explicit schemas over clever metaprogramming

A declarative source of truth should be easier to inspect than the duplication it replaces.

Avoid:

- opaque procedural macros
- complex build scripts
- reflection solely to avoid a small table
- generated code with no obvious source
- overly generic registries

The authoritative declaration must remain readable and searchable.

## 8. Preserve boundary-specific representations when useful

A domain model and wire model may intentionally differ.

A database record and application type may intentionally differ.

Do not collapse representations that encode different contracts merely because their fields overlap.

Instead, centralize the mapping and make the distinction explicit.

## 9. Audit all consumers after consolidation

For each canonical source:

- find every parser
- find every renderer
- find every validator
- find every serializer/deserializer
- find every help/documentation surface
- find every test and fixture
- find every generated artifact

Remove obsolete independent copies.

Search for retired spellings and values after the migration.

## Explicit anti-patterns

Do not:

- create a "universal schema" that absorbs unrelated domains
- replace simple duplication with unreadable metaprogramming
- treat two similar but semantically distinct contracts as one
- leave old independent tables beside the new source of truth
- preserve "keep in sync" comments when synchronization can be eliminated
- make generated files authoritative when their input is the true source
- change behavior while consolidating metadata
- create bidirectional derivation between representations
- silently choose one duplicate when existing copies disagree; investigate the discrepancy

## Verification

After editing:

- search for each former duplicate declaration
- confirm one authoritative definition remains
- confirm all relevant consumers derive from it
- confirm intentional external copies have drift tests or explicit documentation
- run focused tests and broader checks when the source crosses module/public boundaries

## Acceptance criteria

The work is complete only when:

- important facts have one authoritative representation
- parser/rendering/validation/documentation surfaces do not independently restate the same closed set where derivation is practical
- "keep in sync" obligations are eliminated or mechanically enforced
- ownership and derivation direction are obvious
- generated outputs clearly identify their source
- intentional boundary-specific models remain distinct
- no obsolete duplicate implementation remains canonical
- tests protect any irreducible duplicated contract
- existing behavior and public contracts are preserved

The architectural principle is: **facts may have many consumers, but they should have one owner.**
