# Parse, Validate, and Normalize at Boundaries

You are improving this codebase so untrusted or loosely structured input is converted into trusted internal representations exactly once, near the boundary where it enters the system.

The goal is to stop raw strings, wire values, optional blobs, and partially parsed input from leaking deep into business logic.

Scope: CLI, environment, config, wire, database, filesystem, subprocess, IPC, and other untrusted input boundaries.

Applicability: Apply this prompt only when raw or loosely structured input reaches internal logic before parsing, validation, defaulting, or normalization is complete. If the condition is materially absent, report that evidence and make no speculative changes.

Preserve: Existing valid behavior, public contracts, persisted data and formats, output, side effects, permissions, state transitions, and supported-platform semantics unless this request explicitly changes them.

Intentional changes: Only changes explicitly authorized by the invoking request; otherwise none.

If inspection shows that the relevant contract already holds, do not manufacture
changes. Verify it, correct only concrete gaps, and report the evidence.

## First inspect the repository

Before editing:

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

- Record failures that predate the work.

## Non-negotiable design

Each numbered requirement defines an invariant or observable behavior, its
authoritative owner or boundary, the shortcut or ambiguous state it prohibits,
and the evidence that proves it. Do not prescribe incidental implementation
structure unless that structure is itself part of the contract.

### 1. Separate raw boundary values from trusted internal representations

#### Separate raw and trusted forms


Prefer a pipeline such as:

```text
raw input
  -> parse
  -> validate
  -> normalize
  -> domain type
```

Downstream logic should not repeatedly ask whether raw input is valid.

#### Preserve raw boundary semantics


Paths and process arguments may not be UTF-8.

Wire values may distinguish absent from null.

Do not lossy-convert merely for convenience.

### 2. Normalize once and validate cross-field invariants together

#### Normalize once


Examples:

- case normalization
- path normalization
- URL canonicalization
- identifier normalization
- whitespace policy

Do not normalize inconsistently at multiple call sites.

#### Validate cross-field invariants together


If validity depends on multiple fields, validate them in one authoritative place.

### 3. Resolve defaults while preserving opaque compatibility values

#### Keep defaults at the boundary


Do not let downstream code independently reinterpret missing values.

Resolve defaults once into the trusted representation.

#### Preserve unknown/opaque values intentionally


When forward compatibility requires unknown fields or tokens to survive round trips, model that explicitly rather than rejecting or stringifying indiscriminately.

### 4. Report precise boundary errors without over-normalizing meaningful representation

#### Keep error location useful


Boundary validation errors should identify:

- field/argument/path
- invalid value class
- relevant expected form

without dumping sensitive values unnecessarily.

#### Avoid over-normalization


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


## Verification

After editing:

- Run the nearest hard judge for CLI, environment, config, wire, database, filesystem, subprocess, IPC, and other untrusted input boundaries: the compiler, type checker, schema/build check, or focused tests that can reject an invalid change.
- Test the observable success behavior, failure behavior, edge cases, and invariants established by the numbered requirements.
- Audit raw/trusted representations, normalization rules, defaults, opaque values, UTF-8 assumptions, and cross-field validation; classify every remaining exception rather than assuming it is harmless.
- Broaden checks only when the changed boundary warrants it, and distinguish pre-existing failures from regressions introduced by this work.

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
