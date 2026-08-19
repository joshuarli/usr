# Enforce Architectural Dependency Direction

You are improving an existing codebase so dependencies flow in deliberate directions instead of forming cycles, layer leaks, and arbitrary cross-module reach.

The goal is not textbook layering. The goal is to make ownership and dependency direction obvious enough that local changes stay local.

Preserve runtime behavior and public contracts unless this request explicitly changes them.

## First inspect the repository

Before editing:

- inventory modules/packages/crates and their import/dependency relationships
- identify cycles
- identify low-level modules importing high-level application modules
- identify domain modules depending directly on UI/CLI/HTTP/storage details
- identify "common", "shared", "utils", or "context" modules depended on by nearly everything
- identify internal modules reaching through another module's boundary
- identify dependency inversion interfaces and whether they correspond to real boundaries
- inspect feature flags and build dependencies that create hidden directionality
- run narrow baseline checks

## 1. Define the actual architectural units

Identify coherent units such as:

```text
domain
application/use-cases
adapters
persistence
CLI/UI
platform
```

or whatever matches the repository.

Do not impose a generic architecture template when the codebase has simpler natural boundaries.

## 2. State allowed dependency directions

For example:

```text
CLI -> application -> domain
persistence adapter -> domain contracts
platform adapter -> application boundary
```

The exact graph should follow project needs.

A reader should be able to explain why each dependency direction exists.

## 3. Break cycles at ownership boundaries

When two modules depend on each other, determine which concept owns the shared contract.

Possible fixes:

- move the shared type to the true owner
- extract a narrow boundary contract
- invert one dependency
- merge modules that are actually one cohesive unit

Do not create an "interfaces" package as a dumping ground merely to break cycles.

## 4. Keep policy above mechanism

Low-level mechanism code should not import high-level workflow policy.

Examples:

- filesystem adapter should not decide product workflow
- database layer should not know CLI argument semantics
- serializer should not decide retry policy

## 5. Prevent lateral reach-through

If module A owns concept X, other modules should use A's intentional API rather than reaching into A's internal submodules or representation.

## 6. Treat shared modules skeptically

A module depended on by nearly everything can become an architectural gravity well.

Split shared code by actual ownership where possible.

Keep truly cross-cutting primitives small.

## 7. Avoid dependency inversion theater

Do not add traits/interfaces just to satisfy a diagram.

Invert a dependency when it protects a real stable boundary or testable effect.

## 8. Keep data types with their semantic owner

Do not place all DTOs/models/types into one global package if that obscures who owns their meaning.

## 9. Make architecture visible in the tree

File/module layout should reinforce dependency direction.

Important domain boundaries should be apparent from names and paths.

## 10. Enforce important direction mechanically

Where the ecosystem supports it, use:

- crate/package boundaries
- visibility rules
- dependency linting
- build graph tests
- architectural tests

Do not add heavy tooling if ordinary package boundaries already enforce the rule.

## Explicit anti-patterns

Do not:

- impose clean/hexagonal architecture mechanically
- create an `interfaces` or `shared` junk drawer
- split a cohesive module only to satisfy layering
- add indirection solely to reverse an arrow on a diagram
- let mechanism code own product policy
- permit arbitrary reach-through into internal modules
- centralize all types away from their semantic owners

## Verification

After editing:

- inspect dependency/import graph
- search for forbidden reverse dependencies
- verify removed cycles stay removed
- verify domain/application code is not importing mechanism-specific implementation details
- run focused and broader tests

## Acceptance criteria

The work is complete only when:

- major modules have clear semantic ownership
- dependency directions are explainable
- avoidable cycles are removed
- high-level policy does not leak into low-level mechanism code
- internal module representations are not reached through casually
- shared/common gravity wells are reduced
- dependency inversion exists only at meaningful boundaries
- important directions are mechanically enforceable where practical
- existing behavior remains stable

The architectural principle is: **dependencies should point toward the code that owns meaning, not toward whichever file was easiest to import.**
