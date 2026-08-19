# Algorithmic Complexity and Data Structure Fit

You are improving an existing codebase so algorithms and data structures match the actual operations, scale characteristics, and invariants of the workload.

The goal is not clever algorithms. The goal is to eliminate accidental quadratic work, repeated scans, inappropriate collections, and complexity hidden behind convenient APIs.

Preserve observable behavior unless explicitly changing semantics.

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

## 1. State the operation profile

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

## 2. Find accidental quadratic behavior

Look for patterns such as:

```text
for x in items:
    items.find(...)
```

or repeated list membership inside loops.

Replace with indexed/set/map structures when input size makes it material.

## 3. Avoid repeated sorting

If data is sorted repeatedly with unchanged ordering semantics, consider:

- sorting once at the ownership boundary
- maintaining order incrementally
- selecting min/max without full sort
- using a heap when appropriate

Do not maintain sorted structures when writes dominate and ordering is rarely needed.

## 4. Avoid repeated whole-collection passes

Combine passes only when it improves cost without making logic opaque.

Do not fuse unrelated loops into unreadable mega-loops solely to reduce iteration count.

## 5. Cache derived indexes, not truth

When repeated queries justify an index, make its ownership and invalidation explicit.

Do not introduce hidden duplicate sources of truth.

## 6. Use sets for set semantics

If code conceptually performs membership/deduplication/intersection, use a set-like representation when appropriate.

Do not preserve accidental duplicates merely because a vector/list was the original container.

## 7. Make ordering requirements explicit

Distinguish:

- insertion order
- sorted order
- stable deterministic order
- arbitrary order

Do not pay for ordering that no consumer requires.

## 8. Bound recursion and traversal

For graphs/trees/filesystems, consider:

- cycles
- maximum depth
- stack usage
- visited sets
- adversarial input

## 9. Be explicit about asymptotic tradeoffs

When choosing a non-obvious structure, document the operation pattern that justifies it.

Do not explain standard obvious choices.

## 10. Measure before large rewrites

If complexity only matters at large N, reproduce representative N before replacing clear code with sophisticated structures.

## Explicit anti-patterns

Do not:

- replace every vector/list with a hash map
- optimize tiny bounded collections for asymptotics
- introduce sophisticated trees/indexes without workload evidence
- hide duplicate truth in derived indexes
- fuse loops until control flow becomes obscure
- assume hash structures are always faster
- optimize complexity while worsening determinism or memory dramatically without reason

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
