---
name: api-surface-and-module-boundaries
description: "Use when shrinking or hardening a public API, fixing ambiguous call sites, or untangling module dependency direction, cycles, and reach-through. A capability goes out, implementation structure stays in."
disable-model-invocation: true
---

# API Surface and Module Boundaries

A public API exposes capabilities, not structure, and makes the correct call look natural. Work on the scope named; audit the whole repo only when asked.

**The surface**
- **Every public symbol is a commitment.** For each, ask who needs it and what it promises. Storage, parser internals, cache structures, raw configuration, and dependency adapters stay private. Do not export something because a sibling module needs it.
- **Invariant-bearing types cannot be corrupted from outside.** No public fields that must be mutated into a valid combination. Check what bypasses the constructor: `Default`, deserialization, struct-update syntax, unchecked conversions.
- **Do not leak dependency types** unless interop needs them. Do not wrap mature standard types for taste.
- **One canonical entry point per operation.** A compatibility shim is deprecated, names its replacement, and forwards to the canonical path. New code and examples never use it.
- **Feature-gated surface stays coherent.** No half-initialized abstractions when a feature is off.

**The call site**
- **Replace ambiguous parameters.** `copy(src, dst, true, false, 30, 3)` becomes an enum, a domain type, or a named request type. A boolean often hides two operations (`WriteMode::Create` and `Replace` beat `overwrite: bool`). No builder for two arguments.
- **Absorb what every caller repeats** (normalize, validate, look up, construct) unless it is caller-specific policy. Repeated identical arguments are a missing default.
- **Return outcomes a caller can act on** (`Created`, `Updated`, `Unchanged`, `NotFound`, `Conflict`), not a `bool`.
- **Side effects show in the name.** `get` does not write. A constructor does not start background work.

**The modules**
- Name the real units and the allowed direction between them. Do not impose a layered template the code does not have.
- Break a cycle at the owner of the shared contract: move the type, extract a narrow contract, or merge modules that are really one. No `interfaces` or `shared` junk drawer.
- Policy sits above mechanism: a storage layer does not know CLI semantics. Other modules use a module's intentional API, never its internals. A module everything imports is a gravity well, so split it by ownership.
- Invert a dependency only for a real stable boundary or a testable effect. Enforce a direction mechanically (crate boundaries, visibility, a dependency lint) when that is cheap.

**The test:** could a caller who reads only the signature misuse it without the compiler noticing?

Test intended construction, invalid use, feature combinations, and deprecation forwarding. Breaking a public contract needs the user's permission.

**Reply:** symbols removed or narrowed, call sites clarified, directions fixed, and any contract change.
