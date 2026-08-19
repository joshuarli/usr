# Algorithmic Complexity and Data Structure Fit

You are improving this codebase so algorithms and data structures match the actual operations, scale characteristics, and invariants of the workload.

The goal is to eliminate accidental quadratic work, repeated scans, inappropriate collections, and complexity hidden behind convenient APIs.

Scope: important algorithms, collection choices, lookup patterns, sorting, traversal, indexing, and asymptotic behavior.

Applicability: Apply this prompt only when input size or operation frequency makes accidental scans, sorting, recursion, or data-structure mismatch materially relevant. If the condition is materially absent, report that evidence and make no speculative changes.

Preserve: Existing valid behavior, public contracts, persisted data and formats, output, side effects, permissions, state transitions, and supported-platform semantics unless this request explicitly changes them.

Intentional changes: Only changes explicitly authorized by the invoking request; otherwise none.

If inspection shows that the relevant contract already holds, do not manufacture
changes. Verify it, correct only concrete gaps, and report the evidence.

## First inspect the repository

Before editing:

- identify loops nested over collections
- identify repeated scans and repeated sorting
- identify linear lookup in frequently queried collections
- identify repeated parsing/hash/comparison work
- identify collection conversions
- identify use of maps/sets/lists/trees/heaps/queues
- identify recursion and potentially unbounded traversal
- inspect expected input sizes and hot paths
- inspect benchmarks/profiles where available
- run baseline correctness and performance checks

- Record failures that predate the work.

## Non-negotiable design

Each numbered requirement defines an invariant or observable behavior, its
authoritative owner or boundary, the shortcut or ambiguous state it prohibits,
and the evidence that proves it. Do not prescribe incidental implementation
structure unless that structure is itself part of the contract.

### 1. Choose structures from the workload and remove accidental quadratic behavior

#### State the operation profile


For each important collection, identify dominant operations:

- append
- ordered iteration
- membership
- keyed lookup
- min/max
- priority
- deduplication
- range lookup
- stable ordering
- insertion/removal

Choose the structure for those operations rather than habit.

#### Find accidental quadratic behavior


Look for patterns such as:

```text
for x in items:
    items.find(...)
```

or repeated list membership inside loops.

Replace with indexed/set/map structures when input size makes it material.

### 2. Avoid repeated sorting and whole-collection work

#### Avoid repeated sorting


If data is sorted repeatedly with unchanged ordering semantics, consider:

- sorting once at the ownership boundary
- maintaining order incrementally
- selecting min/max without full sort
- using a heap when appropriate

Do not maintain sorted structures when writes dominate and ordering is rarely needed.

#### Avoid repeated whole-collection passes


Combine passes only when it improves cost without making logic opaque.

Do not fuse unrelated loops into unreadable mega-loops solely to reduce iteration count.

### 3. Use derived indexes, set semantics, and ordering deliberately

#### Cache derived indexes, not truth


When repeated queries justify an index, make its ownership and invalidation explicit.

Do not introduce hidden duplicate sources of truth.

#### Use sets for set semantics


If code conceptually performs membership/deduplication/intersection, use a set-like representation when appropriate.

Do not preserve accidental duplicates merely because a vector/list was the original container.

#### Make ordering requirements explicit


Distinguish:

- insertion order
- sorted order
- stable deterministic order
- arbitrary order

Do not pay for ordering that no consumer requires.

### 4. Bound traversal and justify asymptotic tradeoffs

#### Bound recursion and traversal


For graphs/trees/filesystems, consider:

- cycles
- maximum depth
- stack usage
- visited sets
- adversarial input

#### Be explicit about asymptotic tradeoffs


When choosing a non-obvious structure, document the operation pattern that justifies it.

Do not explain standard obvious choices.

### 5. Measure before replacing clear algorithms


If complexity only matters at large N, reproduce representative N before replacing clear code with sophisticated structures.

### Migration and compatibility policy

Do not create parallel legacy and canonical implementations as part of this work.
If a rename, move, replacement, or contract change becomes necessary, inventory all
references first, keep one canonical path, and retain compatibility only when the
invoking request or an existing external contract requires it.

## Explicit anti-patterns

Do not:

- replace every vector/list with a hash map
- optimize tiny bounded collections for asymptotics
- introduce sophisticated trees/indexes without workload evidence
- hide duplicate truth in derived indexes
- fuse loops until control flow becomes obscure
- assume hash structures are always faster
- optimize complexity while worsening determinism or memory dramatically without reason


## Verification

After editing:

- Run the nearest hard judge for important algorithms, collection choices, lookup patterns, sorting, traversal, indexing, and asymptotic behavior: the compiler, type checker, schema/build check, or focused tests that can reject an invalid change.
- Test the observable success behavior, failure behavior, edge cases, and invariants established by the numbered requirements.
- Audit operation profiles, nested/repeated scans, sorting, collection passes, derived indexes, ordering, recursion/cycles, and representative measurements; classify every remaining exception rather than assuming it is harmless.
- Broaden checks only when the changed boundary warrants it, and distinguish pre-existing failures from regressions introduced by this work.

## Acceptance criteria

The work is complete only when:

- important collections match their dominant operations
- accidental quadratic/repeated-scan behavior is removed where material
- ordering requirements are explicit
- repeated sorting and conversion are reduced
- derived indexes have clear ownership
- graph/tree traversal handles cycles/depth appropriately
- non-obvious complexity choices are justified by workload
- representative performance improves or remains stable
- behavior remains correct

The architectural principle is: **choose data structures from the operations the program performs, not from familiarity.**
