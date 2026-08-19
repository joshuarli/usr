# Make Invalid States Unrepresentable

You are improving an existing codebase so its types encode the real domain constraints instead of relying on comments, boolean combinations, magic values, nullable-field conventions, or caller discipline.

The goal is not type-level cleverness. The goal is to make valid code naturally express valid states and make common classes of bugs impossible or difficult to construct.

Preserve runtime behavior and public contracts unless this request explicitly changes them.

## First inspect the repository

Before editing:

- inventory important identifiers, state fields, booleans, nullable/optional fields, strings acting as enums, integer codes, unit-bearing values, request/response structures, lifecycle states, and constructors
- search for comments describing impossible combinations or required call ordering
- search for repeated validation of the same structural invariant
- search for functions with several interchangeable primitive parameters
- identify structs/objects that can be instantiated in states the application later rejects
- identify state transitions encoded indirectly through mutation
- run the narrowest useful baseline checks

## 1. Replace primitive obsession where semantics differ

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

## 2. Replace stringly typed finite sets

If a value has a closed set of states, represent it as an enum/tagged union/algebraic data type rather than arbitrary strings.

Prefer exhaustive matching where it improves correctness.

Keep wire-format conversion at the boundary.

## 3. Replace boolean state combinations with explicit states

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

## 4. Replace optional-field soups with variants

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

## 5. Make validated construction explicit

If a value has invariants, avoid unrestricted public construction.

Use constructors/parsers/builders that validate once and return a type whose invariants downstream code can trust.

Examples:

- non-empty names
- normalized paths
- bounded percentages
- valid ranges
- minimum <= maximum
- parsed addresses
- non-zero capacities

Do not repeatedly revalidate trusted domain values after construction.

## 6. Encode units

Avoid interchangeable scalar values when unit confusion is plausible.

Prefer:

- `Duration`
- byte-count types or explicitly named byte fields
- percentages represented with validated types
- timestamps rather than raw integer epochs
- domain quantity types

At minimum, include units in names when the language lacks better options.

## 7. Recover latent state machines

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

## 8. Distinguish parsed, validated, and active forms when useful

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

## 9. Keep boundary compatibility separate

External APIs, JSON, databases, and CLI inputs may require permissive primitive representations.

Keep those wire/input types at the boundary.

Convert them into stricter domain types after validation.

Do not weaken the internal model merely because an external format is loose.

## 10. Prefer readable type safety

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

## Verification

After editing:

- search for repeated invariant checks that should now be unnecessary
- test invalid construction
- test invalid state transitions
- ensure exhaustive matches cover newly explicit states
- ensure boundary parsing rejects malformed values
- ensure serialization/wire compatibility remains unchanged where required
- run the nearest compiler/type checker and focused tests

## Acceptance criteria

The work is complete only when:

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
