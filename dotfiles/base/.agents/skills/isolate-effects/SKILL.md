---
name: isolate-effects
description: "Use when domain logic is mixed with filesystem, process, network, database, clock, randomness, environment, or terminal effects, or when tests need real time, processes, or services. Effects at visible edges, decisions in the core."
disable-model-invocation: true
---

# Isolate Effects

Effects happen at visible edges; policy stays visible in the core. Work on the scope named; audit the whole repo only when asked.

- **Parse, decide, execute.** Decide which files change, then apply them. Compute retry timing from policy, then ask a clock to wait. Low-level I/O helpers hold no policy.
- **Read process globals once** (environment, current directory, arguments, locale) at startup or an explicit boundary. Convert to typed values and pass down only what a callee needs.
- **Time and randomness are inputs** wherever behavior depends on them. Acquire "now" at the edge, keep wall-clock and monotonic time distinct, and pass a seed or an RNG. Cryptographic randomness keeps its own boundary.
- **Abstract an effect only when** tests need to control it, several implementations exist, the mechanism is volatile, or the boundary carries real policy or failure semantics. A function parameter often beats a trait. No dependency-injection framework, and no `Manager`, `Context`, or `Provider` that bundles unrelated effects.
- **Spawn processes structurally:** build arguments apart from running them, no shell reinterpretation, explicit environment and stdio, defined cancellation and child cleanup.
- **Translate a mechanism's error only where its meaning changes,** and keep the source. Each effectful resource has a creator, an owner, and a release on every exit path.
- **Moving a boundary never changes behavior.**

**The test:** can the decision logic run in a unit test with no clock, filesystem, process, or network?

Keep integration tests for the real adapters. Search for remaining raw effect calls in scope and classify each.

**Reply:** the boundaries you set, each abstraction you added and why it earns its place.
