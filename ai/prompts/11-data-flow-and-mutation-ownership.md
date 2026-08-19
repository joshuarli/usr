# Make Data Flow and Mutation Ownership Obvious

You are improving this codebase so readers can tell where data originates, who owns it, who may mutate it, and when state changes.

The goal is to reduce hidden mutation, aliasing, action-at-a-distance, and context objects whose fields are modified by unrelated code.

Scope: important mutable state, context objects, caches, transactional mutation, setters, shared state, and hidden side effects.

Applicability: Apply this prompt only when ownership or mutation authority is unclear enough to permit action-at-a-distance or invalid partial state. If the condition is materially absent, report that evidence and make no speculative changes.

Preserve: Existing valid behavior, public contracts, persisted data and formats, output, side effects, permissions, state transitions, and supported-platform semantics unless this request explicitly changes them.

Intentional changes: Only changes explicitly authorized by the invoking request; otherwise none.

If inspection shows that the relevant contract already holds, do not manufacture
changes. Verify it, correct only concrete gaps, and report the evidence.

## First inspect the repository

Before editing:

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

- Record failures that predate the work.

## Non-negotiable design

Each numbered requirement defines an invariant or observable behavior, its
authoritative owner or boundary, the shortcut or ambiguous state it prohibits,
and the evidence that proves it. Do not prescribe incidental implementation
structure unless that structure is itself part of the contract.

### 1. Give important mutable data one conceptual owner

#### Give important state an owner


For each mutable resource, identify one conceptual owner.

It should be possible to answer:

- who creates it?
- who may mutate it?
- who observes it?
- when is mutation allowed?
- when does ownership end?

#### Prefer transformation over ambient mutation


When practical, prefer:

```text
input -> validated value -> transformed value -> result
```

over unrelated functions mutating shared state.

Do not force immutable copies when mutation is clearly simpler and more efficient.

### 2. Expose domain mutation instead of ambient state editing

#### Narrow mutation APIs


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

#### Break apart giant context objects


A function should receive what it actually needs.

Avoid passing a universal `Context`, `State`, or `App` object everywhere when it obscures dependencies.

Do not explode signatures mechanically; group values that genuinely form one concept.

### 3. Keep derived state and multi-step mutation subordinate to authoritative state

#### Keep caches subordinate


A cache is derived state.

Make its relationship to authoritative state explicit.

Avoid code paths where a cache silently becomes a second source of truth.

#### Make mutation phases visible


If an operation has stages such as:

```text
load -> plan -> mutate -> persist -> publish
```

keep them conceptually distinct.

Avoid partially mutating externally visible state before validation completes unless semantics require it.

#### Make transactional boundaries explicit


If multiple mutations must succeed or fail together, enforce that boundary with the mechanism appropriate to the domain.

Do not rely on callers to perform rollback manually.

### 4. Make hidden writes and shared-mutation synchronization explicit

#### Avoid hidden side effects in getters/helpers


Functions that look observational should not unexpectedly mutate durable state, perform network I/O, or trigger major side effects unless clearly named and documented.

#### Audit shared mutable concurrency


For state shared across threads/tasks, define:

- synchronization mechanism
- ownership
- lock scope
- update atomicity
- visibility guarantees

### Migration and compatibility policy

Do not create parallel legacy and canonical implementations as part of this work.
If a rename, move, replacement, or contract change becomes necessary, inventory all
references first, keep one canonical path, and retain compatibility only when the
invoking request or an existing external contract requires it.

## Explicit anti-patterns

Do not:

- ban mutation categorically
- replace clear mutation with allocation-heavy functional ceremony
- pass giant state/context objects everywhere
- expose invariant-bearing state as public mutable fields
- let caches become authoritative accidentally
- hide writes behind innocent-looking accessors
- scatter multi-step mutation across callers


## Verification

After editing:

- Run the nearest hard judge for important mutable state, context objects, caches, transactional mutation, setters, shared state, and hidden side effects: the compiler, type checker, schema/build check, or focused tests that can reject an invalid change.
- Test the observable success behavior, failure behavior, edge cases, and invariants established by the numbered requirements.
- Audit state creation/mutation/observation, giant contexts, cache authority, transactional phases, hidden writes, and shared synchronization; classify every remaining exception rather than assuming it is harmless.
- Broaden checks only when the changed boundary warrants it, and distinguish pre-existing failures from regressions introduced by this work.

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
