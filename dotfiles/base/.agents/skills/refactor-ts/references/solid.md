# Solid 2 and the Effect boundary

Use [Solid 2 documentation](https://v2.solidjs.com/), the installed package declarations, and the [Solid 1 migration guide](https://v2.solidjs.com/migration/from-solid-1). The rules below were checked on 2026-10-24 while Solid 2 was an RC; match the exact package family rather than mixing Solid 1 documentation, early beta examples, and current APIs.

## Reactivity and components

- Keep props reactive. Read properties in JSX or tracked computations; do not destructure reactive props, copy them into one-time component locals, or read an accessor early and pass its frozen result around. Use current `merge`/`omit` helpers only when needed, not remembered `mergeProps`/`splitProps` recipes.
- Use signals for owned values and stores when structured state earns them. Derive data rather than copying it with effects. A cheap expression can be a derived accessor; a shared result/equality boundary can use `createMemo`. Avoid React-style render memoization and callback-stability wrappers.
- Keep [derivations separate from imperative effects](https://v2.solidjs.com/guides/avoid-unnecessary-effects). `createEffect(compute, apply)` tracks in compute and performs imperative work in untracked apply. Read the needed store fields during compute; passing a proxy into apply does not establish those property dependencies.
- Compute functions remain free of application writes. Return teardown from apply. Use `onSettled` for settled DOM setup and return cleanup; ref callbacks are untracked and have no owner for creating reactive work.
- Respect staged writes: updates commit on a microtask. Remove old `batch` usage without replacing each call with `flush`. Use an explicit flush only for a real immediate imperative requirement.
- Use store draft setter callbacks; do not retain old path setters, `produce` wrappers, or mutable-store patterns without checking the migration. Keep ownership explicit and avoid adding a global state manager.

## Async UI

Use [async memos/derived stores and boundaries](https://v2.solidjs.com/concepts/async-reactivity) instead of recreating resource, transition, loading, error, and result state. Read reactive inputs synchronously before awaiting or constructing lazily executed work.

Distinguish initial loading from a pending update to already displayed data. Use `Loading`, `Errored`, and `isPending` where appropriate. Choose whether old data should remain visible when a subject changes; preserve intended UX rather than accepting an accidental new loading policy.

Superseded results being ignored does not cancel the underlying operation. Register run cleanup and an AbortController before the first await where cancellation is needed. Do not mechanically delete `onCleanup`: async memos still use it. A displayed run can remain live until its replacement commits; do not await that old run's cleanup from inside the replacement.

## Solid owns reactivity; Effect owns execution

This is the skill's integration prescription, combining Solid's ownership model with Effect's runtime model:

1. Read reactive inputs in Solid's tracked computation and capture ordinary values.
2. Pass those values to an Effect program. Do not bury a signal/prop read inside a lazy generator and expect Solid to track it.
3. Bridge once to a Promise through the application's reused ManagedRuntime. Solid owns displayed/loading/error state; Effect owns I/O, typed failures, retry/concurrency policy, and resources.
4. Connect the Solid run/owner's abort signal to the Effect runner, then to fetch/Promise adapters. Observe errors and dispose work at the correct lifetime.
5. Let a replacement result update the UI through Solid. Avoid a second hand-kept loading/result/error state machine, a runtime per computation, or an unowned fiber for each render.

Use a narrow adapter with concrete ownership if this seam repeats. Do not build a second reactive framework or add an atom/state bridge speculatively. Consult [non-Solid integration](https://v2.solidjs.com/guides/integrate-non-solid-code) for subscriptions, DOM libraries, cleanup, and owner restoration.

## Types, packages, and server boundaries

Use [the Solid 2 TypeScript setup](https://v2.solidjs.com/guides/typescript). Reactive/store primitives come from `solid-js`; DOM rendering and DOM JSX/component prop types come from `@solidjs/web`. Keep `jsx: "preserve"` and `jsxImportSource: "@solidjs/web"` where required by this compiler pipeline. Do not import removed `solid-js/web` or `solid-js/store` subpaths.

Use `@solidjs/vite-plugin` with its Oxc default. Use Start mode for Solid applications with `solid({ start: true })`; enable SSR only when useful. Start mode replaces hand-maintained bootstraps and SolidStart adapters. Keep `@solidjs/router` when routing is needed. Verify all peer ranges and exports before deleting old packages; do not reintroduce `@solidjs/start`, `vite-plugin-solid`, or Babel from another tool's outdated example. See the [official RC announcement](https://github.com/solidjs/solid/discussions/2995).

Write [SSR-safe code](https://v2.solidjs.com/guides/ssr-safe-code): component bodies/compute run on server and client, while effect apply and `onSettled` are browser-side. Keep DOM/browser access in the right phase. Never store request/user state in shared module state; preserve hydration consistency and request-specific services.

Treat [server functions](https://v2.solidjs.com/building-apps/server-functions/arguments-and-security) as external entrypoints. Validate arguments and authorize within the actual server-function body, where HTTP dispatch executes them. Get identity from trusted request context. Keep server modules and secrets out of the browser import graph.

## Verification

Exercise changing props, repeated updates, replacement of pending work, failure rendering, unmount, subscription teardown, and any changed stale-data policy. Use a real browser for DOM/layout/focus/forms/navigation, and production serving plus nested routes for SSR. Test request isolation when moving state or runtimes. Preserve existing user-visible behavior; fewer signals or effects alone do not prove correctness.
