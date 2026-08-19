# API Ergonomics and Misuse Resistance

You are improving an existing codebase so its internal and public APIs guide callers toward correct use, make common operations obvious, and make incorrect use difficult.

The goal is not to make APIs "cute" or maximally terse. The goal is to reduce caller-side ceremony, ambiguity, parameter mistakes, invalid sequencing, and repeated glue.

Preserve behavior and compatibility unless this request explicitly permits API changes.

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

## 1. Optimize for correct obvious usage

A caller should be able to infer:

- what operation does
- what inputs mean
- what must happen first
- what can fail
- who owns the result
- what side effects occur

without reading implementation details.

## 2. Avoid ambiguous positional parameters

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

## 3. Replace boolean mode switches

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

## 4. Prefer one canonical entry point

If callers can accomplish the same operation through several APIs, choose the clearest canonical path.

Compatibility wrappers may remain but should not look equally preferred.

## 5. Move repeated caller obligations inward

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

## 6. Make optionality meaningful

Avoid APIs with large numbers of optional parameters whose combinations are unclear.

Use distinct request/configuration types or variants when optional fields imply modes.

## 7. Return useful domain results

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

## 8. Make side effects visible in naming and ownership

A function named `get` should not unexpectedly mutate durable state.

A constructor should not start background work unless that is obvious from the API.

## 9. Keep defaults canonical

If callers repeatedly pass the same arguments, determine whether they represent true defaults.

Do not encode policy as copy-pasted call-site parameters.

## 10. Audit fluent/builders for hidden state

Builders should accumulate configuration clearly and validate at final construction.

Avoid builders with order-dependent setters or hidden side effects.

## 11. Keep convenience layers honest

Convenience APIs are useful when they reduce repetitive boilerplate while preserving the same semantics.

Do not create wrappers that obscure failure, ownership, or performance cost.

## 12. Test API misuse paths

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
