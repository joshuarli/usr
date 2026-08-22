# Serialization, Versioning, and Compatibility

You are improving this codebase so persisted and wire formats have explicit compatibility, validation, evolution, and round-trip semantics.

The goal is to prevent accidental protocol changes and long-lived data debt caused by treating serialization as an implementation detail.

Scope: wire and persisted formats, versioning, field semantics, readers/writers, migrations, unknown values, and compatibility fixtures.

Applicability: Apply this prompt only when serialized data crosses a persistence or external compatibility boundary. If the condition is materially absent, report that evidence and make no speculative changes.

Preserve: Existing valid behavior, public contracts, persisted data and formats, output, side effects, permissions, state transitions, and supported-platform semantics unless this request explicitly changes them.

Intentional changes: Only changes explicitly authorized by the invoking request; otherwise none.

If inspection shows that the relevant contract already holds, do not manufacture
changes. Verify it, correct only concrete gaps, and report the evidence.

## First inspect the repository

Before editing:

- inventory JSON/YAML/TOML/binary formats, database blobs, cache files, config files, IPC messages, HTTP/RPC payloads, snapshots, manifests, and exported data
- identify format/version fields
- identify custom serialization hooks
- identify renamed/defaulted/optional fields
- identify unknown-field behavior
- identify old readers/writers and migrations
- identify places where domain models double as wire models
- inspect golden fixtures and compatibility tests
- run narrow baseline checks

- Record failures that predate the work.

## Non-negotiable design

Each numbered requirement defines an invariant or observable behavior, its
authoritative owner or boundary, the shortcut or ambiguous state it prohibits,
and the evidence that proves it. Do not prescribe incidental implementation
structure unless that structure is itself part of the contract.

### 1. Treat serialized formats as contracts distinct from internal representation when needed

#### Treat serialized formats as contracts


Once persisted or consumed externally, field names, discriminants, defaults, omission behavior, and null semantics may be compatibility commitments.

Do not change them casually during internal refactors.

#### Separate wire/persistence models from domain models when contracts diverge


Use distinct types when:

- external fields are legacy-shaped
- compatibility requires optionality the domain does not
- internal types evolve faster than the protocol
- validation is required before trust

Do not create duplicate models when the structures genuinely have the same contract.

### 2. Define version, unknown-field, and absent/null/default semantics

#### Define versioning strategy


For evolving formats, decide whether compatibility uses:

- explicit version field
- additive fields with defaults
- tagged variants
- negotiation
- migration-on-read
- migration-on-write

Avoid ad hoc "try parsing old shape, then new shape" behavior without documented policy.

#### Define unknown-field behavior


Decide intentionally whether unknown fields are:

- rejected
- ignored
- preserved for round-trip compatibility

Forward compatibility may require preserving opaque data.

#### Distinguish absent, null, empty, and default


Do not conflate these unless the format contract explicitly does so.

### 3. Use one canonical writer and validate after parsing

#### Keep canonical writing behavior


If old formats must still be read, new writes should usually emit one canonical current format.

Avoid multiple equally canonical writers.

#### Validate after parsing


Syntactic deserialization does not establish semantic validity.

Convert raw wire/persisted forms into validated internal domain values.

### 4. Define round-trip and deterministic-output expectations

#### Make round-trip expectations explicit


Determine whether the contract requires:

```text
decode(encode(x)) == x
```

or stronger preservation such as unknown fields or formatting.

Do not assume structural round-trip when canonicalization is intended.

#### Stabilize output


Where serialized output is checked into repositories, cached, hashed, diffed, or consumed by humans, use deterministic ordering and formatting when semantics permit.

### 5. Keep compatibility fixtures and migration direction explicit

#### Maintain compatibility fixtures


Keep representative fixtures for:

- oldest supported version
- current version
- unknown/additive fields
- deprecated variants
- malformed input

Golden files should be small enough to review.

#### Make migrations one-way and explicit


Migration logic should identify source and target versions.

Avoid repeatedly re-migrating already current data.

### 6. Exclude sensitive internal data from serialization


Ensure secrets/internal fields are not serialized merely because a domain struct derives serialization.


## Explicit anti-patterns

Do not:

- derive serialization on internal types without considering exposure
- silently rename persisted/wire fields
- use implicit parser fallback as an undocumented version strategy
- keep old and new writers equally canonical
- discard unknown fields when preservation is required
- conflate absent/null/default accidentally
- trust deserialized data without semantic validation
- serialize secrets because they happen to be fields


## Verification

After editing:

- run old-format fixtures
- run current round-trip tests
- verify canonical output is stable
- verify unknown-field behavior
- verify malformed semantic states are rejected
- inspect serialized output for accidental field exposure
- run compatibility tests across supported versions


- Distinguish failures that predate the work from regressions introduced by this change.

## Acceptance criteria

The work is complete only when:

- external/persisted formats are treated as explicit contracts
- version evolution has a documented strategy
- old supported data remains readable
- new writes use one canonical format
- unknown-field behavior is deliberate
- absent/null/default semantics are defined
- parsed data is semantically validated
- round-trip expectations are tested
- output is deterministic where useful
- sensitive/internal fields are not exposed accidentally

The architectural principle is: **serialization freezes decisions into data; make those decisions deliberate before they become compatibility obligations.**
