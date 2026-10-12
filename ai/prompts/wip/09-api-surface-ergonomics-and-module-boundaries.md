# API Surface, Ergonomics, and Module Boundaries

You are improving this codebase so its public API exposes only intentional, stable contracts and keeps implementation details private.

The goal is to make the externally usable surface small, coherent, documented, and difficult to misuse.

Scope: public/exported APIs, constructors, fields, feature-gated surface, dependency leakage, compatibility shims, the call-site ergonomics of frequently used internal and public functions, and module/package dependency direction.

Applicability: Apply this prompt only when the codebase exposes an API surface whose intentionality, stability, privacy, or misuse resistance needs audit, or when callers face ambiguous parameters, repeated ceremony, surprising side effects, or invalid sequencing. If the condition is materially absent, report that evidence and make no speculative changes.

Preserve: Existing valid behavior, public contracts, persisted data and formats, output, side effects, permissions, state transitions, and supported-platform semantics unless this request explicitly changes them.

Intentional changes: Only changes explicitly authorized by the invoking request; otherwise none.

If inspection shows that the relevant contract already holds, do not manufacture
changes. Verify it, correct only concrete gaps, and report the evidence.

## First inspect the repository

Before editing:

- inventory public/exported modules, types, functions, methods, constants, traits/interfaces, constructors, feature-gated APIs, package exports, and re-exports
- identify exports that exist only because implementation structure leaked outward
- identify multiple public entry points for the same operation
- identify public fields that allow invalid mutation
- identify APIs that expose dependency-specific types unnecessarily
- identify deprecated APIs and compatibility shims
- identify functions with many positional parameters, boolean mode parameters, or optional parameters whose combinations are unclear
- identify steps every caller repeats before invoking the same API (normalize, validate, look up, construct)
- identify constructors that require post-construction mutation
- inspect tests and downstream examples that rely on the current surface
- run narrow baseline checks

- Record failures that predate the work.

## Non-negotiable design

Each numbered requirement defines an invariant or observable behavior, its
authoritative owner or boundary, the shortcut or ambiguous state it prohibits,
and the evidence that proves it. Do not prescribe incidental implementation
structure unless that structure is itself part of the contract.

### 1. Treat the public surface as an intentional compatibility commitment

#### Treat every public symbol as a compatibility commitment


For each public symbol, ask:

- who needs this?
- what contract does it promise?
- can callers misuse it?
- does it expose an implementation choice?
- does a smaller primitive suffice?

Prefer the narrowest surface that supports real use cases.

#### Hide implementation details


Keep internal:

- helper types
- storage representations
- parser internals
- cache structures
- dependency-specific adapters
- intermediate states
- raw configuration structures

Do not make something public merely because another internal module needs it.

Use crate/package/module visibility appropriately.

### 2. Protect invariants and avoid leaking implementation dependencies

#### Prefer cohesive operations over public field mutation


Avoid public structures whose callers must mutate fields into a valid combination.

Prefer constructors and methods that preserve invariants.

If fields are intentionally data-only, keep that choice explicit.

#### Avoid leaking dependency types


A library should not expose arbitrary third-party types through its public API unless interoperability requires it.

Prefer domain-owned wrappers or standard-library types when they keep the contract more stable.

Do not wrap mature standard ecosystem types merely for aesthetic purity.

### 3. Provide one canonical operation with deliberate result/error types

#### Remove duplicate entry points


If several APIs perform the same conceptual operation, choose one canonical path.

Keep aliases only when compatibility requires them, and mark them clearly as deprecated or transitional.

#### Make error and result types deliberate


Public functions should expose failure semantics that callers can actually reason about.

Avoid leaking giant internal error enums or unstructured strings.

### 4. Keep feature-gated construction coherent

#### Keep feature-gated API coherent


If features alter public surface:

- document the relationship
- avoid surprising combinations
- test representative feature sets
- avoid exporting half-initialized abstractions when a feature is disabled

#### Audit constructors


Identify public constructors that bypass validation or permit inconsistent state.

Prefer one clear construction path for invariant-bearing types.

### 5. Make compatibility secondary and prove the public contract

#### Make compatibility policy visible


If a public symbol cannot yet be removed:

- deprecate it
- name the replacement
- route it through the canonical implementation
- prevent new internal code and examples from using it

#### Test the public surface as a contract


Where practical, test:

- intended construction
- invalid use
- stable serialization or ABI behavior when relevant
- feature combinations
- deprecation forwarding
- documented examples


### 6. Make the correct call obvious at the call site

#### Replace ambiguous parameters

Be skeptical of signatures such as `copy(src, dst, true, false, 30, 3)`.

Prefer enums, domain types, or a named request type. A boolean parameter often
hides two operations: `WriteMode::Create` / `WriteMode::Replace` beats
`overwrite: bool` when the distinction has semantic weight. Do not create a
builder for a two-argument function.

Use distinct request types or variants when optional fields imply modes, rather
than a large set of optionals whose combinations are unclear.

#### Absorb repeated caller obligations

If every caller must normalize, validate, look up, construct, then invoke, the
API should probably own more of that sequence. Do not absorb caller-specific
policy into a generic lower-level API.

If callers repeatedly pass the same arguments, determine whether they are a true
default and make it one authoritative default instead of copy-pasted policy.

#### Return outcomes callers can act on

Prefer result types that distinguish meaningful outcomes (`Created`, `Updated`,
`Unchanged`, `NotFound`, `Conflict`) over a `bool` or a side effect the caller
must reverse-engineer.

#### Make side effects visible

A function named `get` should not mutate durable state. A constructor should not
start background work unless the API makes that obvious. Builders should
validate at final construction and must not have order-dependent setters.

Test misuse paths: invalid parameter combinations, invalid sequencing, duplicate
calls, and missing required configuration.

### 7. Keep module boundaries and dependency direction deliberate

Applies when the repository has several modules, packages, or crates whose
dependency direction can drift.

- Name the actual architectural units and the allowed direction between them
  (for example CLI -> application -> domain; adapters -> domain contracts). Do
  not impose a generic layered template when the codebase has simpler natural
  boundaries.
- Break cycles at the owner of the shared contract: move the type to its true
  owner, extract a narrow boundary contract, invert one dependency, or merge
  modules that are really one unit. Do not create an `interfaces` or `shared`
  junk drawer to break a cycle.
- Keep policy above mechanism: a filesystem adapter should not decide workflow,
  a storage layer should not know CLI argument semantics.
- Other modules use a module's intentional API, not its internal submodules or
  representation. Keep data types with the module that owns their meaning.
- Treat a module nearly everything depends on as a gravity well and split it by
  ownership; keep truly cross-cutting primitives small.
- Invert a dependency only for a real stable boundary or testable effect, not to
  satisfy a diagram. Enforce important directions mechanically where the
  ecosystem makes it cheap (package boundaries, visibility, dependency lints).

## Explicit anti-patterns

Do not:

- impose clean or hexagonal architecture mechanically, or split a cohesive module only to satisfy layering
- optimize for the shortest call syntax
- use boolean flags for semantically distinct modes
- return `bool` when callers need a richer outcome
- introduce builders everywhere
- export implementation details for convenience
- create public getters/setters for every field
- expose raw dependency types without a reason
- keep multiple equally canonical APIs
- add wrapper types that provide no stability or semantic value
- make breaking changes without explicit permission
- retain deprecated APIs as independent implementations


## Verification

After editing:

- Run the nearest hard judge for public/exported APIs, constructors, fields, feature-gated surface, dependency leakage, and compatibility shims: the compiler, type checker, schema/build check, or focused tests that can reject an invalid change.
- Test the observable success behavior, failure behavior, edge cases, and invariants established by the numbered requirements.
- Audit exports, public mutation, dependency-specific types, duplicate entry points, deprecations, and feature-gated contracts; classify every remaining exception rather than assuming it is harmless.
- Broaden checks only when the changed boundary warrants it, and distinguish pre-existing failures from regressions introduced by this work.

## Acceptance criteria

The work is complete only when:

- every public symbol has a clear purpose
- implementation details remain private
- invariant-bearing types cannot be casually corrupted by public mutation
- dependency details do not leak unnecessarily
- there is one canonical API per operation
- compatibility shims visibly forward to canonical implementations
- public error/result contracts are understandable
- parameter meaning is clear at call sites, and semantically distinct modes use explicit types
- repeated caller boilerplate is absorbed where ownership permits
- representative public-surface tests pass
- no unrelated API expansion was introduced

The architectural principle is: **a public API should expose capabilities, not implementation structure, and make the correct call look natural and the incorrect call look awkward or impossible.**
