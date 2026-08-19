# Minimize and Harden the Public API Surface

You are improving an existing codebase so its public API exposes only intentional, stable contracts and keeps implementation details private.

The goal is not to hide everything. The goal is to make the externally usable surface small, coherent, documented, and difficult to misuse.

Preserve existing public behavior unless this request explicitly permits breaking changes.

## First inspect the repository

Before editing:

- inventory public/exported modules, types, functions, methods, constants, traits/interfaces, constructors, feature-gated APIs, package exports, and re-exports
- identify exports that exist only because implementation structure leaked outward
- identify multiple public entry points for the same operation
- identify public fields that allow invalid mutation
- identify APIs that expose dependency-specific types unnecessarily
- identify deprecated APIs and compatibility shims
- inspect tests and downstream examples that rely on the current surface
- run narrow baseline checks

## 1. Treat every public symbol as a compatibility commitment

For each public symbol, ask:

- who needs this?
- what contract does it promise?
- can callers misuse it?
- does it expose an implementation choice?
- does a smaller primitive suffice?

Prefer the narrowest surface that supports real use cases.

## 2. Hide implementation details

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

## 3. Prefer cohesive operations over public field mutation

Avoid public structures whose callers must mutate fields into a valid combination.

Prefer constructors and methods that preserve invariants.

If fields are intentionally data-only, keep that choice explicit.

## 4. Avoid leaking dependency types

A library should not expose arbitrary third-party types through its public API unless interoperability requires it.

Prefer domain-owned wrappers or standard-library types when they keep the contract more stable.

Do not wrap mature standard ecosystem types merely for aesthetic purity.

## 5. Remove duplicate entry points

If several APIs perform the same conceptual operation, choose one canonical path.

Keep aliases only when compatibility requires them, and mark them clearly as deprecated or transitional.

## 6. Make error and result types deliberate

Public functions should expose failure semantics that callers can actually reason about.

Avoid leaking giant internal error enums or unstructured strings.

## 7. Keep feature-gated API coherent

If features alter public surface:

- document the relationship
- avoid surprising combinations
- test representative feature sets
- avoid exporting half-initialized abstractions when a feature is disabled

## 8. Audit constructors

Identify public constructors that bypass validation or permit inconsistent state.

Prefer one clear construction path for invariant-bearing types.

## 9. Make compatibility policy visible

If a public symbol cannot yet be removed:

- deprecate it
- name the replacement
- route it through the canonical implementation
- prevent new internal code and examples from using it

## 10. Test the public surface as a contract

Where practical, test:

- intended construction
- invalid use
- stable serialization or ABI behavior when relevant
- feature combinations
- deprecation forwarding
- documented examples

## Explicit anti-patterns

Do not:

- export implementation details for convenience
- create public getters/setters for every field
- expose raw dependency types without a reason
- keep multiple equally canonical APIs
- add wrapper types that provide no stability or semantic value
- make breaking changes without explicit permission
- retain deprecated APIs as independent implementations

## Acceptance criteria

The work is complete only when:

- every public symbol has a clear purpose
- implementation details remain private
- invariant-bearing types cannot be casually corrupted by public mutation
- dependency details do not leak unnecessarily
- there is one canonical API per operation
- compatibility shims visibly forward to canonical implementations
- public error/result contracts are understandable
- representative public-surface tests pass
- no unrelated API expansion was introduced

The architectural principle is: **a public API should expose capabilities, not implementation structure.**
