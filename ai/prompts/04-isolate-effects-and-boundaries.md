# Isolate Effects and Make Boundaries Explicit

You are improving an existing codebase so filesystem, network, database, process, clock, randomness, environment, terminal, and other external effects enter the program through deliberate boundaries instead of leaking throughout domain logic.

The goal is not dependency-injection ceremony. The goal is to make side effects visible, ownership clear, and core logic easy to test and reason about.

Preserve runtime behavior and public contracts unless this request explicitly changes them.

## First inspect the repository

Before editing:

- inventory direct filesystem calls
- inventory process spawning
- inventory network/HTTP calls
- inventory database access
- inventory reads of environment variables
- inventory clock/time calls
- inventory randomness
- inventory terminal/stdin/stdout interaction
- inventory global mutable state and singleton access
- identify modules that mix domain decisions with external effects
- identify tests forced to use real time, real processes, real filesystems, or network services unnecessarily
- run narrow baseline checks

## 1. Identify the true effect boundaries

Classify operations such as:

```text
filesystem
process
network
database
clock
randomness
environment
terminal
OS/platform discovery
```

For each, determine which layer should own it.

The codebase should make it easy to answer:

- where does this effect happen?
- what domain decision caused it?
- what failures can cross the boundary?
- who owns cleanup and lifecycle?

## 2. Separate decision logic from execution

Prefer this shape:

```text
parse/validate
      ↓
domain decision
      ↓
effectful execution
```

Examples:

- determine which files should change, then apply filesystem operations
- determine which command should run, then spawn it
- compute retry timing from policy, then ask a clock/scheduler to wait
- build a query/request, then execute it through the boundary

Do not hide domain policy inside low-level I/O helpers.

## 3. Read process-global inputs once

Environment variables, current directory, process arguments, locale, platform state, and similar process-global inputs should be acquired near startup or at an explicit boundary.

Do not let arbitrary deep modules call global APIs when the value is really configuration.

Convert raw inputs into typed values and pass only what downstream code needs.

## 4. Keep adapters thin

Effect adapters should translate between the domain and an external mechanism.

They should not become giant "service" objects containing unrelated policy.

Good:

```text
FilesystemStore
Clock
ProcessRunner
Repository
HttpClient
```

when each represents a real replaceable boundary.

Bad:

```text
AppManager
UtilityService
Context
EverythingProvider
```

## 5. Avoid fake abstraction

Do not introduce a trait/interface solely because "everything should be injectable."

Abstract an effect when at least one is true:

- tests need deterministic control
- multiple implementations genuinely exist
- the external mechanism is volatile
- the boundary carries important policy or failure semantics
- ownership becomes substantially clearer

A small function parameter or explicit helper may be better than a trait hierarchy.

## 6. Make time explicit

Avoid hidden calls to "now" in domain logic.

If behavior depends on time:

- acquire the current time at a boundary
- pass the timestamp or a small clock abstraction where useful
- make durations and deadlines explicit
- keep wall-clock and monotonic time semantics distinct

This should enable deterministic tests without sleeps.

## 7. Make randomness explicit

If randomness affects observable behavior or testing:

- isolate RNG acquisition
- pass an RNG/seed/value at the appropriate boundary
- avoid global nondeterministic behavior deep inside domain code

Cryptographic randomness may require a stricter dedicated boundary.

## 8. Make process execution explicit

For spawned processes:

- keep argument construction separate from execution when useful
- preserve opaque arguments without shell reinterpretation
- make environment inheritance explicit
- make stdin/stdout/stderr behavior explicit
- define cancellation and child cleanup
- preserve exit-status semantics

Avoid shell invocation unless shell syntax is intentionally required.

## 9. Make filesystem effects explicit

Separate path/operation planning from mutation where practical.

Define semantics for:

- symlinks
- replacement
- atomicity
- partial writes
- permissions
- cleanup
- interruption

Do not scatter filesystem mutation through unrelated domain code.

## 10. Define error translation at boundaries

External libraries and OS APIs expose mechanism-specific errors.

Translate them into application/domain errors only where the abstraction boundary actually changes meaning.

Preserve the underlying source/context.

Avoid turning every error into an opaque string.

## 11. Keep lifecycle ownership obvious

For every effectful resource, make clear:

- who creates it
- who owns it
- when it is released
- what happens on early return
- what happens on cancellation
- what happens during shutdown

Prefer language-native structured ownership and RAII where available.

## Explicit anti-patterns

Do not:

- introduce a dependency-injection framework
- create interfaces for every function
- hide effects inside generic "manager" or "context" objects
- let business logic repeatedly read environment variables
- use real sleeps in tests when time can be controlled
- shell out when a direct API exists and shell semantics are not required
- erase useful external error context
- mix planning and mutation when the distinction is important
- add abstraction layers that merely forward calls
- change behavior while moving boundaries

## Verification

After editing:

- search for raw effect APIs and confirm remaining uses are intentional
- verify environment/process-global reads occur at clear boundaries
- verify deterministic logic can be tested without unnecessary external systems
- verify resource cleanup on errors/cancellation
- verify error sources remain inspectable
- run focused tests and integration tests for real adapters

## Acceptance criteria

The work is complete only when:

- important external effects have obvious ownership
- core decision logic is not needlessly entangled with I/O
- raw process-global configuration is not read throughout the codebase
- time/randomness-dependent behavior can be deterministic where useful
- effect abstractions are narrow and justified
- resource lifecycle and cleanup are explicit
- boundary-specific errors preserve useful context
- tests can exercise core logic without unnecessary real external dependencies
- no DI framework or abstraction-for-abstraction's-sake was introduced
- existing behavior and public contracts are preserved

The architectural principle is: **effects should occur at visible edges; policy should remain visible in the core.**
