# Parse, Validate, and Normalize at Boundaries

You are improving an existing codebase so untrusted or loosely structured input is converted into trusted internal representations exactly once, near the boundary where it enters the system.

The goal is to stop raw strings, wire values, optional blobs, and partially parsed input from leaking deep into business logic.

Preserve external formats and compatibility unless explicitly changing them.

## First inspect the repository

Inventory inputs from:

- CLI
- environment variables
- config files
- JSON/YAML/TOML
- HTTP/RPC
- database rows
- filesystem names/content
- IPC
- subprocess output
- user text

Trace where parsing, validation, defaulting, normalization, and error reporting occur.

## 1. Separate raw and trusted forms

Prefer a pipeline such as:

```text
raw input
  -> parse
  -> validate
  -> normalize
  -> domain type
```

Downstream logic should not repeatedly ask whether raw input is valid.

## 2. Preserve raw boundary semantics

Paths and process arguments may not be UTF-8.

Wire values may distinguish absent from null.

Do not lossy-convert merely for convenience.

## 3. Normalize once

Examples:

- case normalization
- path normalization
- URL canonicalization
- identifier normalization
- whitespace policy

Do not normalize inconsistently at multiple call sites.

## 4. Validate cross-field invariants together

If validity depends on multiple fields, validate them in one authoritative place.

## 5. Keep defaults at the boundary

Do not let downstream code independently reinterpret missing values.

Resolve defaults once into the trusted representation.

## 6. Preserve unknown/opaque values intentionally

When forward compatibility requires unknown fields or tokens to survive round trips, model that explicitly rather than rejecting or stringifying indiscriminately.

## 7. Keep error location useful

Boundary validation errors should identify:

- field/argument/path
- invalid value class
- relevant expected form

without dumping sensitive values unnecessarily.

## 8. Avoid over-normalization

Do not canonicalize values when representation itself is meaningful.

Examples may include:

- case-sensitive identifiers
- opaque tokens
- exact filenames
- cryptographic material

## Explicit anti-patterns

Do not:

- parse the same value repeatedly
- keep raw config/wire strings deep in domain code
- normalize at random call sites
- lossy-convert paths/arguments
- conflate absent, null, empty, and default unless the contract says so
- discard unknown values needed for compatibility
- validate only individual fields when the invariant is cross-field

## Acceptance criteria

The work is complete only when:

- raw inputs have clear entry points
- parsing/validation/defaulting happen once
- internal code consumes trusted domain representations
- normalization rules are centralized
- opaque and non-UTF-8 values are preserved when required
- cross-field validation has one owner
- boundary errors are precise
- external compatibility remains intact

The architectural principle is: **be permissive only at the edge; make the interior precise.**
