# Enforce Architectural Dependency Direction

You are improving this codebase so dependencies flow in deliberate directions instead of forming cycles, layer leaks, and arbitrary cross-module reach.

The goal is to make ownership and dependency direction obvious enough that local changes stay local.

Scope: module/package/crate dependency relationships, cycles, shared modules, reach-through imports, and policy/mechanism layering.

Applicability: Apply this prompt only when the repository has multiple architectural units whose dependency direction or ownership can drift. If the condition is materially absent, report that evidence and make no speculative changes.

Preserve: Existing valid behavior, public contracts, persisted data and formats, output, side effects, permissions, state transitions, and supported-platform semantics unless this request explicitly changes them.

Intentional changes: Only changes explicitly authorized by the invoking request; otherwise none.

If inspection shows that the relevant contract already holds, do not manufacture
changes. Verify it, correct only concrete gaps, and report the evidence.

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

- Record failures that predate the work.

## Non-negotiable design

Each numbered requirement defines an invariant or observable behavior, its
authoritative owner or boundary, the shortcut or ambiguous state it prohibits,
and the evidence that proves it. Do not prescribe incidental implementation
structure unless that structure is itself part of the contract.

### 1. Define architectural units and allowed dependency directions

#### Define the actual architectural units


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

#### State allowed dependency directions


For example:

```text
CLI -> application -> domain
persistence adapter -> domain contracts
platform adapter -> application boundary
```

The exact graph should follow project needs.

A reader should be able to explain why each dependency direction exists.

### 2. Break cycles without letting mechanism own policy

#### Break cycles at ownership boundaries


When two modules depend on each other, determine which concept owns the shared contract.

Possible fixes:

- move the shared type to the true owner
- extract a narrow boundary contract
- invert one dependency
- merge modules that are actually one cohesive unit

Do not create an "interfaces" package as a dumping ground merely to break cycles.

#### Keep policy above mechanism


Low-level mechanism code should not import high-level workflow policy.

Examples:

- filesystem adapter should not decide product workflow
- database layer should not know CLI argument semantics
- serializer should not decide retry policy

### 3. Prevent reach-through and shared-module gravity wells

#### Prevent lateral reach-through


If module A owns concept X, other modules should use A's intentional API rather than reaching into A's internal submodules or representation.

#### Treat shared modules skeptically


A module depended on by nearly everything can become an architectural gravity well.

Split shared code by actual ownership where possible.

Keep truly cross-cutting primitives small.

### 4. Keep inversion and types with their semantic owners

#### Avoid dependency inversion theater


Do not add traits/interfaces just to satisfy a diagram.

Invert a dependency when it protects a real stable boundary or testable effect.

#### Keep data types with their semantic owner


Do not place all DTOs/models/types into one global package if that obscures who owns their meaning.

### 5. Make dependency direction visible and enforceable

#### Make architecture visible in the tree


File/module layout should reinforce dependency direction.

Important domain boundaries should be apparent from names and paths.

#### Enforce important direction mechanically


Where the ecosystem supports it, use:

- crate/package boundaries
- visibility rules
- dependency linting
- build graph tests
- architectural tests

Do not add heavy tooling if ordinary package boundaries already enforce the rule.

### Migration and compatibility policy

Do not create parallel legacy and canonical implementations as part of this work.
If a rename, move, replacement, or contract change becomes necessary, inventory all
references first, keep one canonical path, and retain compatibility only when the
invoking request or an existing external contract requires it.

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


- Distinguish failures that predate the work from regressions introduced by this change.

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
