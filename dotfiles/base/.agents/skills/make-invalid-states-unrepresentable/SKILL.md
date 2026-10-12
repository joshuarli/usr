---
name: make-invalid-states-unrepresentable
description: Redesign types so they encode domain constraints, using enums for exclusive states, validated constructors, and unit-bearing values.
disable-model-invocation: true
---

# Make Invalid States Unrepresentable

Make each important type represent the smallest deliberate set of states its contract allows, ideally exactly the valid ones, so valid code is natural and whole classes of bugs cannot be constructed. Move correctness from caller discipline into the representation.

Apply only where invalid states can currently be built from primitives, option soups, magic strings, boolean combinations, or caller discipline. If that is absent, report the evidence and change nothing. Preserve behavior, public contracts, persisted formats, and wire representation unless the request says otherwise.

## Count the states

A struct has the product of its fields' states. An enum has the sum of its variants. Three booleans admit 8 states; a domain with Open, Held, Sold, and OutOfOrder has 4:

```rust
struct FlagState { held: bool, sold: bool, out_of_order: bool } // 8 combinations
enum State { Open, Held, Sold, OutOfOrder }                      // 4 named states
```

For each state-bearing type, write down the intended states and what the current representation permits. Separate independent dimensions (`is_dirty`, `is_cached`: every combination is meaningful, so keep a product) from one hidden state machine (`started`, `finished`, `failed`, `cancelled`: use an enum). A type that began with one boolean is a checkpoint: do not append `failed` or `paused` as another flag when they are alternatives in the same lifecycle. An enum does not validate its payload, so give variant fields precise types too. Keep any unavoidable superset at a boundary and name its owner.

## Rules

- **Option soups become variants.** `status`, `result?`, `error?`, `started_at?`, `finished_at?` permits Completed with no result and Pending with a finish time. One enum with variant-specific fields removes both. A comment explaining which field combinations are valid is the signal to split.
- **Build types from the values you want,** not by carving them out of a looser type with checks. A non-empty list is a head plus a rest. A time range is a start plus a duration.
- **Distinct meanings get distinct types.** `UserId`, `OrganizationId`, and `ProjectId` are not interchangeable strings when swapping them is plausible. Wrap only where it adds safety. Other candidates: validated paths, addresses, quantities, timestamps with different meanings, opaque tokens.
- **Closed sets are enums,** matched exhaustively with no wildcard on an internal enum, so a new variant is a compile error where it matters. Convert to wire strings at the boundary.
- **Validate once, in construction.** Constructors and parsers return a type downstream code can trust (non-empty name, bounded percentage, min <= max, non-zero capacity). Do not re-check afterward. In Rust keep invariant fields private and check `Default`, deserialization, conversions, and struct-update syntax for ways around the constructor.
- **Units live in types or names:** `Duration`, byte counts, validated percentages, timestamps over raw epochs; at minimum a unit suffix.
- **Recover latent state machines.** Find start, stop, finish, cancel, retry, commit, abort, open, close, connect. List legal sources and destinations, terminal and retryable states, idempotent transitions, and transitions that need data. Illegal transitions are errors or impossible, decided in one place and not re-checked by every caller.
- **Give stages their own types only when it removes real checks:** `RawConfig` to `ValidatedConfig`, `UninitializedSession` to `AuthenticatedSession`. No typestate ceremony for trivial flows.
- **Strengthen a type where partiality appears.** An assertion, null check, or "should never happen" throw marks a type that is too weak. Push it into the type, then stop. Prefer total functions.
- **Loose wire and input types stay at the boundary** and convert after validation. A loose external format never weakens the interior.

## Avoid

Newtypes with no concrete failure mode. Type-level machinery harder to read than the bug. Forcing every lifecycle into typestate. Replacing independent booleans with an enum. Public constructors, `Default`, or deserialization that reopen excluded states. Raw strings for finite states. Changed wire formats.

## Verify

Test invalid construction, invalid transitions, boundary rejection of malformed input, and unchanged serialization. Check that matches are exhaustive, search for checks the types made redundant, and run the compiler and focused tests. Separate preexisting failures from regressions.

Done when each important type has an intended state set, any remaining superset is bounded and owned by a boundary, and the result is simpler to reason about, not merely fancier.

**Reply:** each type's state set before and after, and any remaining superset with its owner.
