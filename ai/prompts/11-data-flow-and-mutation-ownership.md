# Make Data Flow and Mutation Ownership Obvious

You are improving an existing codebase so readers can tell where data originates, who owns it, who may mutate it, and when state changes.

The goal is to reduce hidden mutation, aliasing, action-at-a-distance, and context objects whose fields are modified by unrelated code.

Preserve behavior and public contracts unless explicitly changing them.

## First inspect the repository

Inventory:

- mutable globals
- shared mutable objects
- large context/state structures
- interior mutability
- setters
- in-place mutation
- caches
- registries
- callbacks that mutate captured state
- event handlers
- database-backed mutable state
- state passed through many layers

Trace important data from creation to final use.

## 1. Give important state an owner

For each mutable resource, identify one conceptual owner.

It should be possible to answer:

- who creates it?
- who may mutate it?
- who observes it?
- when is mutation allowed?
- when does ownership end?

## 2. Prefer transformation over ambient mutation

When practical, prefer:

```text
input -> validated value -> transformed value -> result
```

over unrelated functions mutating shared state.

Do not force immutable copies when mutation is clearly simpler and more efficient.

## 3. Narrow mutation APIs

Expose operations that express intent.

Prefer:

```text
job.complete(result)
```

over:

```text
job.status = "done"
job.result = result
job.finished_at = now
```

when those fields form one invariant-bearing transition.

## 4. Break apart giant context objects

A function should receive what it actually needs.

Avoid passing a universal `Context`, `State`, or `App` object everywhere when it obscures dependencies.

Do not explode signatures mechanically; group values that genuinely form one concept.

## 5. Keep caches subordinate

A cache is derived state.

Make its relationship to authoritative state explicit.

Avoid code paths where a cache silently becomes a second source of truth.

## 6. Make mutation phases visible

If an operation has stages such as:

```text
load -> plan -> mutate -> persist -> publish
```

keep them conceptually distinct.

Avoid partially mutating externally visible state before validation completes unless semantics require it.

## 7. Make transactional boundaries explicit

If multiple mutations must succeed or fail together, enforce that boundary with the mechanism appropriate to the domain.

Do not rely on callers to perform rollback manually.

## 8. Avoid hidden side effects in getters/helpers

Functions that look observational should not unexpectedly mutate durable state, perform network I/O, or trigger major side effects unless clearly named and documented.

## 9. Audit shared mutable concurrency

For state shared across threads/tasks, define:

- synchronization mechanism
- ownership
- lock scope
- update atomicity
- visibility guarantees

## Explicit anti-patterns

Do not:

- ban mutation categorically
- replace clear mutation with allocation-heavy functional ceremony
- pass giant state/context objects everywhere
- expose invariant-bearing state as public mutable fields
- let caches become authoritative accidentally
- hide writes behind innocent-looking accessors
- scatter multi-step mutation across callers

## Acceptance criteria

The work is complete only when:

- important mutable state has obvious ownership
- mutation APIs express domain intent
- giant ambient context dependencies are reduced
- derived caches remain subordinate to authoritative state
- multi-step atomic mutations have explicit boundaries
- hidden writes are eliminated or clearly named
- shared mutable concurrency has explicit synchronization semantics
- existing behavior is preserved

The architectural principle is: **state changes should have an owner, a reason, and a visible boundary.**
