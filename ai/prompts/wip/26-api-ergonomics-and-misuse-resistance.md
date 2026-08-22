# API Ergonomics and Misuse Resistance

You are improving this codebase so its internal and public APIs guide callers toward correct use, make common operations obvious, and make incorrect use difficult.

The goal is to reduce caller-side ceremony, ambiguity, parameter mistakes, invalid sequencing, and repeated glue.

Scope: frequently used internal/public functions, constructors, builders, request types, methods, and caller-side glue.

Applicability: Apply this prompt only when callers face ambiguous parameters, repeated ceremony, surprising side effects, invalid sequencing, or multiple competing entry points. If the condition is materially absent, report that evidence and make no speculative changes.

Preserve: Existing valid behavior, public contracts, persisted data and formats, output, side effects, permissions, state transitions, and supported-platform semantics unless this request explicitly changes them.

Intentional changes: Only changes explicitly authorized by the invoking request; otherwise none.

If inspection shows that the relevant contract already holds, do not manufacture
changes. Verify it, correct only concrete gaps, and report the evidence.

## First inspect the repository

Before editing:

- inventory frequently called functions, methods, constructors, builders, service interfaces, and public APIs
- identify APIs with many positional parameters
- identify boolean parameters
- identify APIs where callers repeatedly perform the same preparation/validation
- identify constructors that require post-construction mutation
- identify APIs whose return values require non-obvious follow-up
- identify operations with multiple equally plausible entry points
- identify repeated caller-side adapter code
- inspect call sites, examples, tests, and docs before changing signatures
- run baseline checks

- Record failures that predate the work.

## Non-negotiable design

Each numbered requirement defines an invariant or observable behavior, its
authoritative owner or boundary, the shortcut or ambiguous state it prohibits,
and the evidence that proves it. Do not prescribe incidental implementation
structure unless that structure is itself part of the contract.

### 1. Make correct calls obvious and parameter modes unambiguous

#### Optimize for correct obvious usage


A caller should be able to infer:

- what operation does
- what inputs mean
- what must happen first
- what can fail
- who owns the result
- what side effects occur

without reading implementation details.

#### Avoid ambiguous positional parameters


Be skeptical of signatures such as:

```text
copy(src, dst, true, false, 30, 3)
```

Prefer:

- named parameter structures
- enums
- domain types
- builders when optional configuration is substantial

Do not create a builder for a two-argument function.

#### Replace boolean mode switches


A boolean parameter often hides two operations.

Prefer:

```text
WriteMode::Create
WriteMode::Replace
```

over:

```text
overwrite: bool
```

when the distinction has semantic weight.

### 2. Provide one canonical entry point and absorb repeated caller obligations

#### Prefer one canonical entry point


If callers can accomplish the same operation through several APIs, choose the clearest canonical path.

Compatibility wrappers may remain but should not look equally preferred.

#### Move repeated caller obligations inward


If every caller must:

```text
normalize
validate
lookup
construct
then invoke
```

consider whether the API should own more of that sequence.

Do not absorb caller-specific policy into a generic lower-level API.

### 3. Represent optional modes and outcomes explicitly

#### Make optionality meaningful


Avoid APIs with large numbers of optional parameters whose combinations are unclear.

Use distinct request/configuration types or variants when optional fields imply modes.

#### Return useful domain results


Avoid forcing callers to reverse-engineer outcome from side effects or generic booleans.

Prefer result types that distinguish meaningful outcomes:

```text
Created
Updated
Unchanged
NotFound
Conflict
```

where callers need that distinction.

### 4. Make side effects visible and defaults authoritative

#### Make side effects visible in naming and ownership


A function named `get` should not unexpectedly mutate durable state.

A constructor should not start background work unless that is obvious from the API.

#### Keep defaults canonical


If callers repeatedly pass the same arguments, determine whether they represent true defaults.

Do not encode policy as copy-pasted call-site parameters.

### 5. Keep builders/convenience layers honest and test misuse

#### Audit fluent/builders for hidden state


Builders should accumulate configuration clearly and validate at final construction.

Avoid builders with order-dependent setters or hidden side effects.

#### Keep convenience layers honest


Convenience APIs are useful when they reduce repetitive boilerplate while preserving the same semantics.

Do not create wrappers that obscure failure, ownership, or performance cost.

#### Test API misuse paths


Where practical, cover:

- invalid parameter combinations
- invalid sequencing
- duplicate calls
- missing required configuration
- ambiguity between modes


## Explicit anti-patterns

Do not:

- optimize for shortest call syntax
- use boolean flags for semantically distinct modes
- introduce builders everywhere
- add convenience wrappers that hide important cost
- keep multiple equally canonical ways to perform one operation
- require callers to repeat identical validation/normalization
- return `bool` when callers need richer outcome semantics
- make side effects surprising


## Verification

After editing:

- Run the nearest hard judge for frequently used internal/public functions, constructors, builders, request types, methods, and caller-side glue: the compiler, type checker, schema/build check, or focused tests that can reject an invalid change.
- Test the observable success behavior, failure behavior, edge cases, and invariants established by the numbered requirements.
- Audit positional/boolean ambiguity, repeated caller obligations, optional modes, outcomes, side-effect naming, defaults, builders, and misuse tests; classify every remaining exception rather than assuming it is harmless.
- Broaden checks only when the changed boundary warrants it, and distinguish pre-existing failures from regressions introduced by this work.

## Acceptance criteria

The work is complete only when:

- common operations have one obvious path
- parameter meaning is clear at call sites
- semantically important modes use explicit types
- repeated caller boilerplate is reduced where ownership permits
- invalid parameter combinations are harder to construct
- side effects and ownership are visible
- outcome types expose meaningful distinctions
- compatibility paths remain secondary
- existing behavior and public contracts are preserved unless intentionally changed

The architectural principle is: **a good API makes the correct call look natural and the incorrect call look awkward or impossible.**
