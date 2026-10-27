---
name: rust-hash
description: Migrate Rust map and set usage to hashbrown with a deliberately chosen hasher, auditing every BTreeMap and BTreeSet and benchmarking changes.
disable-model-invocation: true
metadata:
  opencode/autoinvoke: "false"
---

# Rust Hash Migration

Use `hashbrown` as the default table and pick each collection's representation from its real semantics and workload, not by replacing every `BTreeMap` with `HashMap`. Preserve observable behavior, measure instead of assuming, and add no abstraction layers or exotic dependencies without a measured win.

## Baseline

Declare once in `[workspace.dependencies]` and inherit with `{ workspace = true }`:

```toml
hashbrown = { version = "0.17", default-features = false, features = ["default-hasher", "inline-more"] }
```

`default-hasher` supplies foldhash, which makes `HashMap::new()` compile; `inline-more` trades build time and size for speed. Add `raw-entry`, `equivalent`, or `allocator-api2` only if used.

- Table and hasher are separate choices. `std::collections::HashMap` is a hashbrown fork; its weakness is the SipHash default hasher.
- Use `hashbrown::{HashMap, HashSet}` with plain `HashMap<K, V>`; do not add hasher parameters mechanically. Never use `std` maps in application code, and do not use `foldhash::HashMap` (an alias of the std type).
- Attacker-controlled keys (request data, external strings, remote protocol fields) use `hashbrown::HashMap<K, V, std::hash::RandomState>`. Trusted internal keys may use fast hashers. Never trade a security property for a microbenchmark.
- **rustc-hash:** for trusted keys dominated by small integers, IDs, enums, handles, or small tuples, benchmark `rustc_hash::FxBuildHasher` (2.x) against the default via `HashMap<K, V, FxBuildHasher>`. Fx is fastest on such keys but clusters aligned or strided IDs, so adopt it only if the real workload wins.

## Audit every `BTreeMap` and `BTreeSet`

Find why each exists: search `.range(`, `first_key_value`, `last_key_value`, `pop_first`, `pop_last`, bounds, and sorted-iteration assumptions. Classify:

- **A. Order not needed:** `hashbrown::HashMap`/`HashSet`.
- **B. Deterministic output needed, ordered mutation not:** hash on the hot path, sort at the output boundary (diagnostics, serialization, CLI output, tests).
- **C. Build once, read many, ordered:** sorted `Vec` with `sort_unstable`, `dedup`, binary search.
- **D. Real ordered or range workload:** keep the tree.

Hash iteration is unordered. Find accidental reliance on tree order and sort explicitly where output must be deterministic; do not create flaky tests.

## Specialized representations

Check key domains and cardinality before reaching for a hash table:
- dense integer sets: bitset (a crate only if measured); large sparse sets with set algebra: evaluate Roaring after benchmarking;
- dense integer-key maps (`NodeId`, `FileId`): `Vec<Option<V>>` or indexed storage, which needs no hashing;
- tiny collections: benchmark a linear-scan `Vec<(K, V)>`;
- static read-only data: sorted contiguous storage.

## Table usage

- Replace `contains_key` then `get_mut`, `contains` then `insert`, and repeated lookups with the entry API.
- Remove needless key clones, owned `String`s built only for lookup (use borrowed keys), maps rebuilt in hot loops, and collect-then-transform chains.
- Use `with_capacity`/`reserve` where cardinality is predictable; use `clear()` to keep allocations only where ownership stays clear.
- No `FastMap`/`FastSet` wrappers unless many call sites share one specialized policy; keep any alias trivial.

## Benchmarking and dependencies

Measure representative workloads, not isolated hash functions unless hashing is the bottleneck: wall and CPU time, allocations, peak memory, and instructions or cache misses where relevant. Use the project's infrastructure, else Criterion and `perf stat` on Linux. For hot collections compare the existing code, the hashbrown default, and Fx if plausible; keep no losing variant or feature flag. Vet numbers with `benchmark-checklist`.

Remove `fxhash` (obsolete) and unused hasher and collection crates, and run the dependency checks. Every remaining dependency must match a chosen implementation; add no `ahash`, `foldhash`, `rustc-hash`, or bitmap crate speculatively.

**The test:** every `BTreeMap` and `BTreeSet` is classified, each change or kept tree is justified by its guarantees and measured numbers, and no unused hasher crate remains.

**Report:** each collection representation changed; why each `BTreeMap`/`BTreeSet` changed or stayed, naming those deliberately kept; the hashing strategy; specialized representations adopted; before and after numbers; remaining collection bottlenecks.
