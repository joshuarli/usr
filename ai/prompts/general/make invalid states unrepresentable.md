# Make Invalid States Unrepresentable

You are improving this codebase so its types encode the real domain constraints instead of relying on comments, boolean combinations, magic values, nullable-field conventions, or caller discipline.

The goal is for each important type to represent the smallest deliberate set of states allowed by its contract—ideally exactly the valid states, not a larger superset that callers must police. Make valid code naturally express valid states and make common classes of bugs impossible or difficult to construct.

Use the algebraic-data-type (ADT) distinction as a design lens. A product type such as a
struct combines the values of all its fields; for finite fields, its representable
state count is the product of their counts. A sum type such as an enum represents
one of its declared alternatives; its state set is the disjoint union of those
variants. A single boolean can look harmless, but adding more flags grows a
product (often to `2^n` combinations) while a lifecycle usually has a small set
of mutually exclusive states. Choose the representation whose state set matches
the domain, and keep any unavoidable superset confined to a boundary.

Scope: domain types, constructors, state representations, identifiers, units, and lifecycle transitions.

Applicability: Apply this prompt only when invalid domain states can currently be constructed through primitive values, option soups, magic strings, boolean combinations, or caller discipline. If the condition is materially absent, report that evidence and make no speculative changes.

Preserve: Existing valid behavior, public contracts, persisted data and formats, output, side effects, permissions, state transitions, and supported-platform semantics unless this request explicitly changes them.

Intentional changes: Only changes explicitly authorized by the invoking request; otherwise none.

If inspection shows that the relevant contract already holds, do not manufacture
changes. Verify it, correct only concrete gaps, and report the evidence.

## First inspect the repository

Before editing:

- inventory important identifiers, state fields, booleans, nullable/optional fields, strings acting as enums, integer codes, unit-bearing values, request/response structures, lifecycle states, and constructors
- search for comments describing impossible combinations or required call ordering
- search for repeated validation of the same structural invariant
- search for functions with several interchangeable primitive parameters
- identify structs/objects that can be instantiated in states the application later rejects
- for each suspicious state-bearing type, write down the intended states and the combinations its representation currently permits; distinguish independent dimensions from one hidden state machine
- in Rust, inspect public fields and generated construction (`Default`, deserialization, conversion impls, and struct update syntax) that may bypass an invariant-preserving constructor
- identify types that started with one state boolean and accumulated, or are likely to accumulate, more flags as features were added
- identify state transitions encoded indirectly through mutation
- run the narrowest useful baseline checks

- Record failures that predate the work.

## Non-negotiable design

Each numbered requirement defines an invariant or observable behavior, its
authoritative owner or boundary, the shortcut or ambiguous state it prohibits,
and the evidence that proves it. Do not prescribe incidental implementation
structure unless that structure is itself part of the contract.

### 1. Give primitive and finite domain values precise representations

#### Replace primitive obsession where semantics differ


Semantically distinct values should not be interchangeable merely because both are strings or integers.

Prefer:

```rust
struct UserId(String);
struct OrganizationId(String);
struct ProjectId(String);
```

over three raw `String` values when accidental interchange is plausible and meaningful.

Use newtypes/branded types/value objects selectively for:

- identifiers
- units
- validated paths
- addresses
- quantities
- timestamps with different semantics
- opaque tokens

Do not wrap primitives when the wrapper adds no safety, semantics, or discoverability.

#### Replace stringly typed finite sets


If a value has a closed set of states, represent it as an enum/tagged union/algebraic data type rather than arbitrary strings.

Prefer exhaustive matching where it improves correctness.

Keep wire-format conversion at the boundary.

### 2. Model mutually exclusive state explicitly

#### Account for the state set before choosing the shape

Treat the representation as a statement about which states are allowed to exist,
not merely as a convenient collection of fields. A struct/product type can
represent every combination of its fields unless construction is deliberately
constrained. An enum/sum type lists the alternatives that can exist. For example:

```rust
struct FlagState {
    held: bool,
    sold: bool,
    out_of_order: bool,
}
// 2 * 2 * 2 = 8 representable combinations, although the domain may have only
// Open, Held, Sold, and OutOfOrder.

enum State {
    Open,
    Held,
    Sold,
    OutOfOrder,
}
// Four named alternatives; the mutually exclusive states are explicit.
```

When a type begins with one boolean, treat the next requested mode or lifecycle
phase as a design checkpoint. Do not keep appending `failed`, `cancelled`,
`paused`, or similar flags if they are alternatives in the same state machine.
Refactor the representation before the product-shaped state space becomes the
implicit contract. An enum does not validate an invalid payload by itself, so
its variant fields must also use precise types or controlled construction.

#### Replace boolean state combinations with explicit states


Look for structures such as:

```text
started: bool
finished: bool
failed: bool
cancelled: bool
```

Ask whether these are really one state machine.

Prefer:

```text
enum JobState {
    Pending,
    Running,
    Completed,
    Failed,
    Cancelled,
}
```

when that reflects the actual domain.

Do not mechanically replace independent booleans that genuinely represent independent properties.

Independent facts should remain a product when every combination is meaningful.
For example, `is_dirty` and `is_cached` may be separate properties. The test is
whether the domain permits all combinations, not whether a type contains a
boolean.

#### Replace optional-field soups with variants


Look for types where validity depends on which optional fields happen to be populated.

Example:

```text
status
result?
error?
started_at?
finished_at?
```

If combinations correspond to distinct domain states, model them as variants whose fields are present only when meaningful.

The type should not permit:

```text
Completed with no result
Pending with finished_at
Successful with an error
```

unless those combinations are genuinely valid.

`Option<T>` is itself a two-way sum, but several optional fields form another
product and commonly recreate the invalid-combination problem. Prefer a single
enum with variant-specific fields when presence depends on the state.

### 3. Establish validated construction and unit-safe values

#### Make validated construction explicit


If a value has invariants, avoid unrestricted public construction.

Use constructors/parsers/builders that validate once and return a type whose invariants downstream code can trust.

In Rust, keep invariant-bearing fields private and expose only construction and
transition APIs that preserve the chosen state set. Be skeptical of derived or
generic construction such as `Default`, deserialization, unchecked conversions,
or public struct-update paths when they can create combinations the normal
constructor rejects. Generated implementations are acceptable only when they
preserve the same contract.

Examples:

- non-empty names
- normalized paths
- bounded percentages
- valid ranges
- minimum <= maximum
- parsed addresses
- non-zero capacities

Do not repeatedly revalidate trusted domain values after construction.

#### Encode units


Avoid interchangeable scalar values when unit confusion is plausible.

Prefer:

- `Duration`
- byte-count types or explicitly named byte fields
- percentages represented with validated types
- timestamps rather than raw integer epochs
- domain quantity types

At minimum, include units in names when the language lacks better options.

### 4. Recover lifecycle state machines and trusted stages

#### Recover latent state machines


Search for operations such as:

```text
start
stop
finish
cancel
retry
commit
abort
open
close
connect
disconnect
```

Determine:

- legal source states
- legal destination states
- terminal states
- retryable states
- idempotent transitions
- transitions that require data

Make invalid transitions explicit errors or impossible APIs.

Do not scatter lifecycle legality checks across callers.

#### Distinguish parsed, validated, and active forms when useful


Sometimes one type is being asked to represent multiple lifecycle stages.

Consider separate types for stages such as:

```text
RawConfig
ValidatedConfig
ResolvedConfig
```

or:

```text
UninitializedSession
AuthenticatedSession
```

Use this only when the distinction removes real checks or invalid states. Avoid typestate ceremony for trivial workflows.

### 5. Keep boundary compatibility outside the strict domain model

#### Keep boundary compatibility separate


External APIs, JSON, databases, and CLI inputs may require permissive primitive representations.

Keep those wire/input types at the boundary.

Convert them into stricter domain types after validation.

Do not weaken the internal model merely because an external format is loose.

#### Prefer readable type safety


Reject designs that require substantial generic gymnastics to understand ordinary control flow.

The best model is usually the simplest type structure that makes the invalid case difficult to express.


## Explicit anti-patterns

Do not:

- create newtypes for every primitive without a concrete failure mode
- encode business logic in unreadable type-level machinery
- force every lifecycle into typestate
- replace independent booleans with an enum when combinations are legitimately independent
- expose constructors that bypass the validation the type claims to guarantee
- keep raw strings as the internal representation of a finite state
- spread parsing/validation throughout business logic
- change wire/public representations unnecessarily
- use `Option` to represent mutually exclusive variants when an enum is clearer
- add another state boolean to a type that already models a mutually exclusive lifecycle with flags
- treat a struct's field-by-field validity as proof that every field combination is valid together
- use wildcard matches on a closed internal enum when exhaustive matching would make new states visible to the compiler
- let `Default`, deserialization, public fields, or unchecked conversions reopen states that the domain type claims to exclude


## Verification

After editing:

- search for repeated invariant checks that should now be unnecessary
- for each refactored state-bearing type, compare the intended state set with the combinations its representation permits; record any remaining superset and its boundary owner
- test invalid construction
- test invalid state transitions
- ensure exhaustive matches cover newly explicit states
- ensure boundary parsing rejects malformed values
- ensure serialization/wire compatibility remains unchanged where required
- run the nearest compiler/type checker and focused tests


- Distinguish failures that predate the work from regressions introduced by this change.

## Acceptance criteria

The work is complete only when:

- each important state-bearing type has an explicit intended state set, and any
  representable superset is deliberate, bounded, and owned by a boundary
- mutually exclusive alternatives are modeled as a sum (such as a Rust enum),
  while genuinely independent facts remain products
- important semantically distinct values are not accidentally interchangeable where the language can prevent it
- closed state sets are represented explicitly
- impossible optional-field combinations are eliminated where practical
- important validated values have controlled construction
- units are explicit
- lifecycle transitions have a clear legal model
- invalid transitions are impossible or rejected at one authoritative boundary
- permissive wire/input types do not infect the internal domain model
- the resulting types are simpler to reason about, not merely more sophisticated
- existing behavior and external contracts are preserved

The architectural principle is: **move correctness from caller discipline into the representation itself.**
