---
name: isolate-effects
description: Use when domain logic is mixed with filesystem, process, network, database, clock, randomness, environment, or terminal effects, or when tests are forced to use real time, processes, or services.
disable-model-invocation: true
---

# Isolate Effects

Make effects happen at visible edges while decisions stay visible in the core. Apply this to the scope the user names. Do not widen into a repository-wide audit unless asked; if effects are already isolated, report the evidence and change nothing.

Read repository and scoped `AGENTS.md` first. Inventory direct filesystem, process, network, database, environment, clock, randomness, and terminal calls in the scope, plus global mutable state and the modules that mix them with domain decisions. Run the narrowest baseline check before editing.

## Rules

- Shape the flow as parse and validate, then domain decision, then effectful execution. Decide which files change, then apply them; compute retry timing from policy, then ask a clock to wait. Do not hide policy inside low-level I/O helpers.
- Read process-global inputs (environment, current directory, arguments, locale) once at startup or an explicit boundary, convert them to typed values, and pass down only what is needed.
- Make time and randomness explicit inputs where behavior depends on them: acquire "now" at the boundary, keep wall-clock and monotonic time distinct, and pass a seed or RNG. Cryptographic randomness keeps its own dedicated boundary.
- Abstract an effect only when tests need deterministic control, multiple implementations exist, the mechanism is volatile, or the boundary carries real policy or failure semantics. A function parameter often beats a trait. No dependency-injection framework, and no `Manager`, `Context`, or `Provider` that bundles unrelated effects.
- Process execution: build arguments separately from running, pass opaque arguments without shell reinterpretation, make environment inheritance and stdio explicit, and define cancellation and child cleanup.
- Translate mechanism errors only where meaning changes, and keep the source. State who creates, owns, and releases each effectful resource, including on early return.
- Do not change behavior while moving boundaries.

## Verify

Show that decision logic can now be tested without real time, processes, filesystems, or network, and that real adapters still have integration tests. Search for remaining raw effect APIs and classify each. Distinguish pre-existing failures from regressions.

Load `reference.md` for the full inspection checklist, anti-patterns, and acceptance criteria when doing a broad audit. Where it says "this codebase" or "repository-wide", read it as the requested scope.

## Handoff

Report the boundaries you established, effect abstractions added and why each is justified, checks actually run, and decisions the user must make.
