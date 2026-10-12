---
name: rust-hash
description: Migrate Rust map and set usage to hashbrown with a deliberately chosen hasher, auditing every BTreeMap and BTreeSet and benchmarking changes.
disable-model-invocation: true
---

You are working in an existing Rust codebase. Modernize its map and set usage for performance, with `hashbrown` as the default hash table, choosing each collection from its actual semantics and workload.

This is not "replace every `BTreeMap` with `HashMap`." Audit every important map and set, determine what guarantees it needs, and use the cheapest representation that provides them. Implement the changes rather than just reporting. Preserve observable semantics, measure instead of assuming, and keep the result simple: no abstraction layers or exotic dependencies without measured justification.

Goals: port ordinary hash maps and sets to current `hashbrown`; remove dead fast-hash crates such as `fxhash`; eliminate trees where order and range semantics are not needed; choose hashers deliberately; use a specialized representation where a generic hash table is not the best fit.

## Baseline policy

Declare `hashbrown` once in `[workspace.dependencies]` and inherit it with `{ workspace = true }`:

```toml
hashbrown = { version = "0.17", default-features = false, features = ["default-hasher", "inline-more"] }
```

- `default-hasher` supplies foldhash as the default `S`, which is what makes `HashMap::new()` and `HashSet::from([..])` compile. `inline-more` trades compile time and binary size for speed. `default-features = false` drops what we do not use. Add `raw-entry`, `equivalent`, or `allocator-api2` only if the code needs them.
- Table and hasher are separate choices. The table is hashbrown's SwissTable; `std::collections::HashMap` is a hashbrown fork, so the table itself is about as fast. Std's problem is its default hasher, SipHash-1-3 (`RandomState`), which is slow on small keys. The hasher is foldhash by default, with `rustc_hash::FxBuildHasher` as the candidate for trusted small integer keys.
- Do not use `foldhash::HashMap` or `foldhash::HashSet`; they are aliases of the std types with a foldhash hasher. Use hashbrown's types, which also give the full hashbrown API.
- Never use `std::collections::{HashMap, HashSet}` in application code, even with a custom hasher. For attacker-controlled keys, use `hashbrown::HashMap<K, V, std::hash::RandomState>` (SipHash) instead of the default hasher.
- Prefer `use hashbrown::{HashMap, HashSet};` for ordinary internal maps and sets, and do not mechanically add hasher parameters. The starting point is plain `HashMap<K, V>` and `HashSet<K>`.

## rustc-hash

For trusted, non-adversarial keys dominated by integer IDs, enums, interned symbols, handles, indexes, inode and device IDs, or other small fixed-size keys, benchmark `rustc-hash` 2.x against the default:

```rust
use hashbrown::HashMap;
use rustc_hash::FxBuildHasher;

type FxHashMap<K, V> = HashMap<K, V, FxBuildHasher>;
```

(and likewise for `HashSet`). Fx is one multiply-rotate per word, so it is usually fastest on `u32`/`u64`/ID-like keys and small tuples. foldhash distributes better, handles strings and longer keys well, and is the safer default. Fx's weak low-bit mixing can cluster aligned or strided IDs, so a microbenchmark win can reverse on real data. Adopt Fx only for trusted keys and only if the real workload wins. Do not reintroduce the obsolete `fxhash` crate.

## Security boundary

Trusted internal keys (compiler IR IDs, locally collected filesystem metadata, internal indexes, generated symbols, enum and integer keys, trusted configuration) may use fast hashers. Attacker-controlled keys (network request data, externally supplied strings, remote protocol fields, public endpoints) keep a DoS-resistant hashing strategy. Do not give up a security property for a microbenchmark.

## Audit every `BTreeMap` and `BTreeSet`

Find out why each tree exists. Search for `.range(...)`, `.first_key_value()`, `.last_key_value()`, `.pop_first()`, `.pop_last()`, lower and upper bound usage, and assumptions about sorted iteration. Classify each:

- **A. Ordering not required.** Use `hashbrown::HashMap` or `HashSet`. This is the common case when a tree was just a convenient map.
- **B. Deterministic output required, ordered mutation not.** Keep a hash table on the hot path and sort only at the output boundary (`items.sort_unstable_by_key(...)`): diagnostics, serialization, reports, CLI output, tests.
- **C. Build once, read many, ordered.** Use a sorted `Vec<K>` or `Vec<(K, V)>`: `sort_unstable()`, `dedup()`, binary search. Better locality; only where mutation patterns permit.
- **D. Genuine ordered or range workload** (ordered iteration, predecessor and successor queries, arbitrary ranges, min and max extraction, incremental sorted insertion). Keep the tree. Correct semantics outweigh theoretical hash speed.

Hash iteration is unsorted. Find code that relied accidentally on `BTreeMap` order, sort explicitly where deterministic output is required, and do not let tests become flaky.

## Specialized representations

Inspect key domains and cardinalities before reaching for a hash table.

- **Dense integer sets:** a bitset, with a bitset crate only for a clear, measured benefit.
- **Large sparse integer sets** with unions, intersections, differences, repeated membership, or serialization: evaluate Roaring bitmaps, after benchmarking.
- **Dense integer-key maps** (`NodeId(usize)`, `FileId(u32)`, `SlotId(usize)`): `Vec<Option<V>>` or other indexed storage. Densely allocated IDs need no hashing, which can beat any hasher change.
- **Tiny collections:** benchmark a `Vec<(K, V)>` linear scan. It avoids allocation and table metadata and has excellent locality. Build no small-map abstraction without profiling.
- **Static or read-only data** built once and queried heavily: sorted contiguous storage over a mutable table. Optimize for lifecycle, not just asymptotics.

## Table usage quality

- Replace `contains_key` followed by `get_mut`, `contains` followed by `insert`, and repeated lookups of one key with the entry API (`match map.entry(key) { Entry::Occupied(..) .. Entry::Vacant(..) .. }`), which avoids repeated hashing and probing.
- Look for needless key clones and temporary allocations, owned `String`s built only for lookup (use borrowed-key lookup), maps recreated in hot loops, and collecting into one map only to transform it into another.
- Use `with_capacity` or `reserve` where cardinality is predictable (parsers, directory walkers, graph construction, symbol tables, bulk indexing, known-length iterators) without grossly over-reserving.
- For create, fill, drop, repeat loops, `clear()` retains the allocation. Do it only where ownership stays clear; do not turn local data into long-lived mutable state to save an allocation unless a benchmark justifies it.

## No abstraction for its own sake

Do not create `FastMap` or `FastSet` wrappers unless many call sites share one specialized hasher policy or you intend to switch implementations centrally, and then keep the alias trivial. Direct `hashbrown::HashMap` and `HashSet` are usually clearer.

## Benchmarking

Measure representative application workloads, not isolated hash functions unless hashing is the bottleneck. Measure what is relevant: wall time, CPU time, allocations, peak and steady-state memory, instructions, cycles, cache misses, branch misses. Use the project's existing infrastructure; otherwise Criterion for stable microbenchmarks and `perf stat` and `perf record` on Linux. For particularly hot collections compare (1) the existing implementation, (2) the `hashbrown` default, (3) `hashbrown` plus `rustc_hash::FxBuildHasher` when the keys make Fx plausible. Keep no losing implementation or feature flag afterward.

## Dependencies

Remove `fxhash`, unused hasher crates, and now-unused collection dependencies, and run the dependency checks. Every remaining dependency must correspond to a selected implementation: do not add `ahash`, `foldhash`, `rustc-hash`, or bitmap libraries speculatively. `hashbrown` already supplies its default hasher, so depend on the underlying hasher only if the code needs its API directly. Beyond `hashbrown` and, if it wins its benchmark, `rustc-hash`, add no other dependency without the measured justification above.

## Deliverable

Implement the changes, then summarize concisely: every important collection representation changed; why each major `BTreeMap` or `BTreeSet` was changed or retained, calling out the trees reviewed and intentionally kept; the hashing strategy now in use; any specialized representations adopted; before and after benchmark results; and remaining collection-related bottlenecks.

## Decision tree

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

The governing objective is cache-efficient, simple data structures chosen from actual access patterns. Be aggressive about removing accidental tree usage and conservative about cleverness: a straightforward `hashbrown::HashMap` beats an elaborate custom structure unless profiling clearly shows otherwise.
