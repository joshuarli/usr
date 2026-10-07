You are working in an existing Rust codebase. Your task is to modernize its map/set usage for performance, with `hashbrown` as the default hash-table implementation, while choosing collection types intelligently based on actual semantics and workload.

The goal is **not** “replace every `BTreeMap` with `HashMap`.” The goal is to audit every important map/set use, determine what guarantees it actually requires, and use the cheapest/highest-performance representation that satisfies those requirements.

## Primary goals

1. Port ordinary hash maps and hash sets to current `hashbrown`.
2. Remove dependence on old/dead fast-hash crates such as `fxhash`.
3. Audit `BTreeMap` / `BTreeSet` usage and eliminate them where ordering/range semantics are not actually required.
4. Where hashing is appropriate, choose the hasher deliberately.
5. Where a generic hash table is not the best structure, use a more specialized representation.
6. Preserve observable semantics and correctness.
7. Measure performance changes rather than assuming they are improvements.
8. Keep the resulting implementation simple. Do not introduce abstraction layers, generic machinery, or exotic dependencies without measurable justification.

## Baseline hash-table policy

Use current:

```toml
hashbrown = "..."
```

and prefer:

```rust
use hashbrown::{HashMap, HashSet};
```

for ordinary internal maps/sets.

Use `hashbrown`'s current default hasher—currently foldhash—as the baseline fast implementation.

Do **not** mechanically add custom hasher parameters everywhere.

The default starting point should therefore be:

```rust
HashMap<K, V>
HashSet<K>
```

from `hashbrown`.

## Consider `rustc-hash` where appropriate

For compiler-like/internal workloads dominated by:

- integer IDs
- enums
- interned symbols
- handles
- indexes
- inode/device IDs
- small fixed-size keys
- other trusted non-adversarial keys

benchmark `rustc-hash` 2.x against `hashbrown`'s default hasher.

A candidate configuration is:

```rust
use hashbrown::HashMap;
use rustc_hash::FxBuildHasher;

type FxHashMap<K, V> = HashMap<K, V, FxBuildHasher>;
```

and likewise for `HashSet`.

Do not assume Fx hashing wins. Benchmark it.

Do not reintroduce the obsolete `fxhash` crate.

## Security boundary

Fast non-cryptographic hashers must not casually be used where keys can be deliberately controlled by an untrusted attacker and a collision DoS would matter.

During the audit, distinguish:

### Trusted/internal keys

Examples:

- compiler IR IDs
- filesystem metadata collected locally
- internal indexes
- generated symbols
- enum/integer keys
- trusted configuration

Fast hashers are appropriate here.

### Attacker-controlled/untrusted keys

Examples:

- network service request data
- arbitrary externally supplied strings
- remotely supplied protocol fields
- public server endpoints

Retain a DoS-resistant hashing strategy where relevant.

Do not sacrifice a meaningful security property for a microbenchmark.

## Audit every `BTreeMap` and `BTreeSet`

For each call site, determine why a tree is being used.

Search for operations such as:

```rust
.range(...)
.first_key_value()
.last_key_value()
.pop_first()
.pop_last()
lower_bound...
upper_bound...
```

as well as assumptions about sorted iteration.

Classify each tree into one of these groups.

### A. Ordering is not required

Replace with:

```rust
hashbrown::HashMap
hashbrown::HashSet
```

This should be the common case if the tree was merely selected as a convenient map/set.

### B. Deterministic output is required, but ordered mutation is not

Do not necessarily pay `BTreeMap` costs throughout execution.

Prefer keeping the hot-path representation as a hash table and sorting only at the output boundary:

```rust
let mut items: Vec<_> = map.iter().collect();
items.sort_unstable_by_key(...);
```

This is especially attractive for diagnostics, serialization, reports, CLI output, tests, etc.

### C. Build once / read many ordered collection

Consider a sorted `Vec` instead of `BTreeMap` / `BTreeSet`.

Examples:

```rust
Vec<K>
Vec<(K, V)>
```

Build, then:

```rust
sort_unstable()
dedup()
```

and use binary search.

A contiguous representation can substantially improve cache locality compared with a pointer-heavy/tree representation.

Do this only where mutation patterns permit it.

### D. Genuine ordered/range-query workload

Keep `BTreeMap` / `BTreeSet`.

Do not replace a tree when the algorithm genuinely relies on:

- ordered iteration
- predecessor/successor queries
- arbitrary ranges
- min/max extraction
- efficient incremental sorted insertion

Correct semantics outweigh theoretical hash-table speed.

## Specialized representations

Do not treat every set/map problem as a hash-table problem.

Inspect key domains and cardinalities.

### Dense integer sets

For sets over a reasonably bounded integer domain, consider a bitset.

Instead of:

```rust
HashSet<u32>
```

a bitmap may provide drastically cheaper membership, union, intersection, and memory usage.

Only add a bitset dependency if there is a clear use case and measurable benefit.

### Sparse integer sets

For large sparse integer sets with significant set algebra, evaluate Roaring bitmaps.

Especially relevant if the code performs:

- unions
- intersections
- differences
- repeated membership tests
- serialization of large integer sets

Again: benchmark before adopting.

### Dense integer-key maps

If keys are small dense integer IDs such as:

```rust
NodeId(usize)
FileId(u32)
SlotId(usize)
```

consider whether a direct:

```rust
Vec<Option<V>>
```

or equivalent indexed storage is superior to hashing.

If IDs are allocated densely, hashing may be completely unnecessary.

This can be a larger optimization than changing hash functions.

### Small collections

For collections that usually contain only a handful of entries, benchmark whether a small `Vec` beats a hash table.

For example:

```rust
Vec<(K, V)>
```

with a linear scan can outperform hashing at very small cardinalities because it:

- avoids allocation/table metadata
- has excellent locality
- has negligible setup cost

Do not introduce a complicated small-map abstraction unless profiling identifies this as meaningful.

### Static/read-only data

If a collection is constructed once and then queried heavily, consider whether a sorted contiguous representation is better than maintaining a mutable hash table.

Optimize for lifecycle, not just asymptotic complexity.

## Hash table usage quality

While performing the migration, clean up inefficient table usage.

Look for patterns such as:

```rust
if map.contains_key(&key) {
    map.get_mut(&key)...
}
```

Replace double lookups with entry/raw-entry APIs where appropriate.

Prefer:

```rust
match map.entry(key) {
    Entry::Occupied(...)
    Entry::Vacant(...)
}
```

where that prevents repeated hashing/probing.

Likewise inspect:

- redundant `contains` followed by `insert`
- repeated lookup of the same key
- needless cloning of keys
- unnecessary temporary allocations
- constructing owned `String`s merely for lookup
- repeated table growth
- maps recreated in hot loops
- collecting into one map merely to immediately transform it into another

Use borrowed-key lookup where possible.

## Capacity management

Where cardinality is reasonably predictable, use:

```rust
HashMap::with_capacity(...)
HashSet::with_capacity(...)
```

or reserve appropriately.

Do not grossly over-reserve.

Pay particular attention to:

- parsers
- directory walkers
- graph construction
- symbol tables
- bulk indexing
- known-length iterators

Avoid repeated table resizing in obvious bulk-construction paths.

## Allocation/lifecycle analysis

For hot maps, inspect whether the code repeatedly:

1. creates a map
2. fills it
3. drops it
4. repeats

If so, consider whether the table can be reused with:

```rust
clear()
```

while retaining its allocation.

Only do this where ownership/lifetime design remains clear.

Avoid turning straightforward local data into long-lived mutable state just to save an allocation unless benchmarks justify it.

## Iteration

Remember that iteration over a hash table is not sorted.

Any existing code relying accidentally on `BTreeMap`'s deterministic order must be identified.

Tests should not become flaky because an implicit ordering guarantee disappeared.

Where deterministic output is required, sort explicitly at that boundary.

This is preferable to retaining a tree globally merely to make output deterministic.

## Avoid abstraction for abstraction's sake

Do not immediately create project-wide wrappers such as:

```rust
FastMap
FastSet
```

unless there is a concrete benefit.

Direct:

```rust
hashbrown::HashMap
hashbrown::HashSet
```

is often clearer.

A project-level alias is appropriate only if:

- many call sites genuinely share the same specialized hasher policy, or
- we intend to benchmark/switch implementations centrally.

If aliases are introduced, keep them trivial and obvious.

## Benchmarking

Establish meaningful before/after measurements.

Do not benchmark isolated hash functions unless that is actually the bottleneck.

Benchmark representative application workloads.

Measure, where relevant:

- wall-clock runtime
- CPU time
- allocations
- peak/steady-state memory
- instructions
- cycles
- cache misses
- branch misses

For Linux, use the project's existing benchmark/profiling infrastructure where possible; otherwise useful tools include Criterion for stable microbenchmarks and `perf stat` / `perf record` for system-level behavior.

Prefer real representative inputs over synthetic single-operation loops.

For particularly hot collections, compare at least:

1. existing implementation
2. `hashbrown` default
3. `hashbrown + rustc_hash::FxBuildHasher`

when the key workload makes FxHash plausible.

Do not keep multiple implementations or feature flags after determining the winner unless there is a real ongoing reason.

## Dependency cleanup

After migration:

- remove obsolete `fxhash`
- remove unused hasher crates
- remove now-unused collection dependencies
- run dependency checks
- keep the dependency graph minimal

Do not add `ahash`, `foldhash`, `rustc-hash`, bitmap libraries, etc. merely because they might theoretically be useful.

Every additional dependency should correspond to an actual selected implementation.

Note that `hashbrown` already supplies its own current default hashing strategy; do not explicitly depend on its underlying hasher unless the code needs its API directly.

## Deliverables

Implement the improvements rather than merely producing a report.

At the end, provide a concise summary containing:

1. every important collection representation changed
2. why each major `BTreeMap` / `BTreeSet` was changed or retained
3. which hashing strategy is now used
4. any specialized representations adopted
5. benchmark results before vs. after
6. any remaining collection-related bottlenecks worth investigating

Also explicitly call out tree structures that were reviewed and intentionally retained.

## Decision principle

Use this hierarchy:

```text
Need a collection?
│
├─ Dense integer key?
│   ├─ set ───────────────> bitset
│   └─ map ───────────────> indexed Vec/storage
│
├─ Tiny collection? ──────> consider Vec
│
├─ Build once/read many
│  + ordered? ────────────> sorted Vec
│
├─ Need true dynamic
│  ordered/range semantics?
│   └─ yes ───────────────> BTreeMap / BTreeSet
│
└─ Otherwise ─────────────> hashbrown HashMap / HashSet
                              │
                              ├─ general keys → default hasher
                              └─ trusted ID/int-heavy hot path
                                   → benchmark rustc-hash
```

The governing objective is **cache-efficient, simple data structures chosen from actual access patterns**, not merely replacing one Rust collection crate with another.

Be aggressive about removing accidental tree usage, but conservative about adding cleverness. Prefer a straightforward `hashbrown::HashMap` over an elaborate custom structure unless profiling clearly shows the latter matters.
