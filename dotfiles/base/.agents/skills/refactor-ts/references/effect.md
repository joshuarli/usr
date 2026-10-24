# Effect 4

Use the installed package's declarations and bundled agent/API documentation, then its version-matched [writing guidance](https://github.com/Effect-TS/effect/blob/main/LLMS.md) and [migration index](https://github.com/Effect-TS/effect/blob/main/MIGRATION.md). Links to `main` are discovery points, not proof that an installed version supports an API. The following API names were checked against Effect 4 on 2026-10-24; recheck before migrating.

## Program shape

- Keep pure functions outside Effect. Use `Effect.gen` for inline effectful sequencing. For reusable effectful functions, prefer `Effect.fn("name")` when a tracing boundary helps and `Effect.fnUntraced` when it does not; avoid wrappers whose sole purpose is returning an `Effect.gen`.
- Keep requirements and expected failures visible in the program's type. Do not return a Promise from deep domain helpers just to run an Effect early. Interpret programs at process, request, UI, or other actual application boundaries.
- Use `Context.Service` for a meaningful dependency with behavior and Layers for implementations/composition. Do not create a service for every pure helper. Keep identifiers unambiguous and dependent layers explicit.
- Compose shared services once per appropriate application lifetime. A shared runtime can own pools and infrastructure while request identity, tenant data, transactions, and cancellation remain request-scoped. Do not put request state in a process-global singleton.
- Use `NodeRuntime.runMain` for a suitable CLI/process entrypoint and [`ManagedRuntime`](https://github.com/Effect-TS/effect/blob/main/ai-docs/src/04_integration/10_managed-runtime.ts) for integration with a non-Effect host. Dispose owned runtimes during shutdown/unmount according to their actual owner; a child must not dispose a runtime shared by the application.

## Failures and boundaries

Use the installed [error APIs](https://github.com/Effect-TS/effect/blob/main/migration/error-handling.md). Current v4 uses `Effect.catch`, not `catchAll`; targeted `catchTag`/`catchTags` makes intended recovery visible. Current tagged schema errors use `Schema.TaggedError`. Do not copy earlier beta names or rewrite them from memory.

Represent anticipated failure with the typed error channel and discriminated errors when callers need to branch. Keep original causes useful. Distinguish ordinary failure, defects, and interruption; blanket recovery or `orDie` is not a replacement for deciding who handles each failure. A fallback must be part of the product contract.

Use [Schema](https://github.com/Effect-TS/effect/blob/main/packages/effect/SCHEMA.md) as the canonical definition at untrusted/serialized boundaries. Decode incoming values and encode outbound values; wire and domain representations may differ. Do not hand-maintain parallel interfaces, validators, and DTO conversions for one contract. Avoid repeatedly decoding trusted values within one domain.

Use `Effect.tryPromise` or the matching adapter for a genuinely fallible Promise API, mapping rejection into the intended error type. Pass the adapter's AbortSignal to operations that support cancellation. Do not pretend a Promise-returning library has no failure path because its TS signature omits errors.

## Resources and concurrency

- Pair acquisition/release with Scope and finalizers, including exceptional and interrupted paths; see [resource examples](https://github.com/Effect-TS/effect/blob/main/ai-docs/src/01_effect/05_resources/10_acquire-release.ts).
- Give child/background work a lifetime. Read the [forking migration](https://github.com/Effect-TS/effect/blob/main/migration/forking.md) before replacing old helpers: v4 distinguishes child, scoped, and detached work. Detachment requires an independent owner and shutdown/error handling; it is not a fix for an inconvenient scope.
- Bound concurrency to the actual downstream capacity. Keep stream backpressure and ordering deliberate. Retry only failures that can safely be retried, with a bounded policy; avoid multiplying retries in both client and service layers.
- Cancellation must reach the external operation. Interrupting a fiber does not magically cancel an adapter that ignores its signal. Ensure observers are disposed and finalizers run; do not leak a listener, timer, connection, or fiber after its owner ends.
- Use the selected stack's Config, Clock/DateTime, Schedule, and Stream facilities when their capabilities are needed. Do not add parallel configuration, time, retry, or stream libraries merely for convenience.

## HTTP, RPC, and packages

Choose a web-standard Request/Response handler for a small boundary. For a substantive typed HTTP surface use HttpApi with Schema; use RPC where procedure semantics fit. Do not stack HTTP and RPC abstractions around every trivial endpoint. Reuse domain services between entrypoints.

Effect 4 consolidated several packages. Current imports use `effect/http`, `effect/http-api`, `effect/rpc`, and related exports; earlier `effect/unstable/*` paths were removed. Consult the installed exports and migration guide instead of guessing paths.

Ecosystem packages share a version and must be compatible as a family. Platform and SQL-driver packages remain separate where appropriate; do not add unused platform packages. A clean import path does not imply stability: inspect `@stability` declarations before depending on unstable/experimental modules or widening update ranges.

## Test the contract

Use compatible [`@effect/vitest`](https://github.com/Effect-TS/effect/blob/main/ai-docs/src/09_testing/10_effect-tests.ts), test Layers, and test clocks where useful. Substitute service implementations instead of global monkey-patching. Scope runtimes and resources to the test/fixture owner.

Cover failures, interruption, finalization, and request isolation when changed. Test domain outcomes, not the internal combinator chain. Do not bypass a package peer-dependency conflict or declare Vitest compatibility from matching names alone.
