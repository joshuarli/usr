---
name: ts-tools
description: Migrate a TypeScript codebase to the Deno, pnpm, TypeScript 7, Vite 8, Solid 2, Effect 4, Oxlint, and Vitest 5 stack.
disable-model-invocation: true
---

Migrate this TypeScript codebase comprehensively to the October 2026 frontier TypeScript/web stack below.

The stack decisions are made. Do not compare frameworks, research alternatives, or preserve obsolete tooling because it is already present. Inspect the repository, understand its behavior and constraints, establish the existing test and build baseline, then migrate to completion. Preserve externally observable behavior and public APIs unless the migration requires otherwise or it fixes an existing defect. Delete obsolete layers instead of wrapping them in compatibility abstractions.

## Target stack

Apply only the layers that fit the repository. A server-only service needs no Solid or Vite, a library needs no application server, and a frontend gets the full relevant stack.

- **Deno, latest stable:** runtime, task runner, script runner.
- **pnpm, latest stable:** package manager, dependency resolver, global content-addressed store, lockfile owner. `package.json` is the dependency manifest (npm and JSR) and `pnpm-lock.yaml` the lockfile.
- **TypeScript 7 stable:** strict, native compiler.
- **Vite 8:** frontend dev and build, on its native Rolldown/Oxc pipeline.
- **Solid 2 RC:** `solid-js`, `@solidjs/web`, `@solidjs/vite-plugin`, and `@solidjs/router` where routing is needed. Its Start mode is the application serving layer, not the old separate SolidStart.
- **Effect 4 stable:** effects, typed failures, services, resource lifetimes, concurrency, schemas, configuration, HTTP and RPC.
- **Oxlint + `oxlint-tsgolint`:** linting, including type-aware rules.
- **Vitest 5**, with **Vitest Browser Mode + Playwright provider** for behavior that depends on browser semantics, and Playwright directly only for true end-to-end flows.
- **Modern native CSS and browser APIs** instead of JavaScript abstractions for what the browser now provides.

## pnpm owns packages, Deno owns execution

No Bun. No Vite+ / `vp`. pnpm handles resolution, installation, `package.json`, `pnpm-lock.yaml`, the global store, and `node_modules`. Deno handles the runtime, tasks, scripts, application and server execution, permissions, and Deno-native tests. They are not competing package managers: for a Vite/npm repository pnpm is the sole package authority and Deno only consumes its tree.

The developer interface is `pnpm install`, then `deno task dev`, `build`, `test`, `check`. Dependencies change through `pnpm add`, `pnpm add -D`, `pnpm remove`, `pnpm update`, never `deno add`, `deno remove`, or `deno install` in a pnpm-owned repository. Pin the expected pnpm release through project metadata where practical, and add `pnpm-workspace.yaml` only when actually needed.

`deno.json` / `deno.jsonc` owns tasks and Deno runtime configuration:

```json
{
  "nodeModulesDir": "manual",
  "lock": false,
  "tasks": {
    "dev": "vite",
    "build": "vite build",
    "lint": "oxlint .",
    "typecheck": "tsc --noEmit",
    "test": "vitest run"
  }
}
```

`nodeModulesDir: "manual"` is intentional: pnpm creates and owns `node_modules`, and Deno only consumes it. Do not use Deno's automatic npm installer or `.deno` layout, and do not configure Deno's linker to reproduce what pnpm manages. Tasks call the installed binaries in `node_modules/.bin` directly; do not route them through `pnpm exec`.

**One graph, one lockfile.** `package.json` → pnpm → `pnpm-lock.yaml` → `node_modules` → Deno/Vite/application. Delete `deno.lock`, `package-lock.json`, `yarn.lock`, `bun.lock`, and `bun.lockb` once pnpm owns the graph, keep `pnpm-lock.yaml`, and keep Deno locking off (`"lock": false`). Never run both `pnpm install` and `deno install` in CI.

**JSR** dependencies go through pnpm too: `pnpm add jsr:@scope/package`, imported by the name recorded in `package.json`, so npm, JSR, and workspace packages share one resolver and one lockfile. Avoid direct versioned `jsr:` or remote HTTP imports in an otherwise pnpm-owned application. A genuinely Deno-native program with no meaningful npm/Vite graph may stay Deno-managed; do not add pnpm for uniformity.

**Node is not the application runtime.** Dependencies being managed by pnpm does not mean Node runs the app. Keep Deno's Node/npm compatibility as the execution environment wherever it works. If a specific tool truly needs Node, isolate and document that exception. Production Deno programs use explicit permissions rather than blanket `-A` where practical.

## TypeScript 7

Move fully onto TypeScript 7 semantics, strictly. Remove configuration and syntax deprecated or removed by TypeScript 6/7 instead of suppressing diagnostics. `tsc --noEmit` through `deno task typecheck` is the authoritative check for browser, shared, and package code; add `deno check` for source that depends on Deno module resolution or Deno globals. Do not duplicate checks without a reason, and do not make Deno's unstable compiler integrations a CI or release requirement.

Prefer clean ESM and remove CommonJS glue unless compatibility demands it. Preserve or adopt strict null checking, unchecked-index safety, exact optional property semantics, side-effect import checking, and explicit module semantics. Fix the code rather than weaken the compiler: no `any`, broad assertions, `@ts-ignore`, or needless `@ts-expect-error` to get through.

## Tooling

Use Vite 8 directly, not a compatibility distribution, and remove explicit Webpack, Rollup, esbuild, and Babel plumbing it replaces. Do not add Babel for Solid: `@solidjs/vite-plugin` uses its native Oxc-based compiler. Install through pnpm and run through Deno tasks, e.g. `pnpm add -D vite vitest oxlint typescript`.

Replace ESLint with Oxlint, type-aware through `oxlint-tsgolint`, unless a small concrete rule or plugin cannot yet be represented. Prefer JSON/JSONC config. Do not set up, install, or configure Oxfmt or any formatter. Remove ESLint config, adapters, dependencies, ignores, and duplicated editor settings after parity.

Provide canonical Deno tasks: `dev`, `build`, `lint`, `typecheck`, `test`, `test:browser` (when applicable), and `check`. `check` is the single fast quality gate (lint, authoritative type checks, normal tests); CI may add production builds and broader browser and end-to-end suites. Do not rely on Oxlint's experimental combined type-check mode as the sole type checker. `package.json` owns dependencies and `deno.json` owns the task interface, so no parallel `pnpm dev` or `npm run dev` unless external tooling needs a package script. Do not disable Vite's agent-facing diagnostics or browser-console forwarding.

## Solid 2

Port any frontend fully to Solid 2: the current RC package family, locked in `pnpm-lock.yaml`. Not Solid 1 compatibility patterns, not React-shaped abstractions, and not the old `vite-plugin-solid` package name.

Applications use Start mode in `@solidjs/vite-plugin`:

```ts
import { defineConfig } from "vite";
import solid from "@solidjs/vite-plugin";

export default defineConfig({
  plugins: [
    solid({
      start: true,
    }),
  ],
});
```

`start: true` owns application entries, development serving, and build integration. Client-only apps keep its default SPA/static output. Enable SSR explicitly (`solid({ start: true, ssr: true })`) only if the application genuinely benefits, and keep a static or client-rendered architecture when that is simpler and correct. Remove hand-maintained `index.html`, client and server bootstraps, framework adapters, and metaframework boilerplate that Start mode takes over. Use its filesystem routing, API routes and server functions, middleware, per-request setup, and environment handling. The server boundary stays web-standard, a `Request -> Response` handler such as `handleRequest(request)`, not Node HTTP objects. Do not introduce `@solidjs/start`.

Write Solid, not React translated line by line. Model fine-grained reactive dependencies: local signals for local state, derived computations for derived values, stores only where structured state benefits. Avoid component-wide invalidation, global state managers, memoization and callback wrappers, React-shaped hook abstractions, destructuring reactive values, and reading accessors early. Use Solid 2's async-aware reactive model and its loading, error, and reveal control flow. Do not reintroduce `createResource`, `batch`, `startTransition`, `useTransition`, `createComputed`, or `createMutable`; port them to their Solid 2 equivalents and simplify the surrounding code. Do not add React Query, Redux, MobX, Zustand, or similar without first checking whether Solid's reactive graph plus Effect already covers the need. Remove React, ReactDOM, React-specific state, router, and data libraries, Next.js, JSX runtime configuration, and compatibility code unless the repository publishes a React-facing integration.

## Effect 4

Use Effect 4, not Effect 3 APIs. Solid owns UI state, DOM, fine-grained reactivity, and presentation. Effect owns I/O, typed failures, services, concurrency, cancellation, retries, timeouts, resource lifetime, configuration, schemas, networking, persistence, and workflows.

Pure helpers stay ordinary functions; do not wrap them in `Effect`. Avoid raw Promise, try/catch, and singleton-service spaghetti in the domain layer. `Effect<A, E, R>` makes success, expected failure, and required capabilities visible; represent expected domain and infrastructure failures explicitly instead of throwing arbitrary `Error`s across boundaries. Use Services and Layers for capabilities and managed infrastructure (no ambient service locators), scoped acquisition and release for resource lifetimes, Effect concurrency instead of detached Promises, and run Effects at application boundaries rather than escaping to Promises mid-domain.

Use Effect 4 `Schema` at untrusted or serialized boundaries: HTTP input and output, configuration, persistence, local storage, external APIs, messages and events, and URL or query data where validation matters. Keep one canonical definition instead of an interface plus hand-written validation, and do not revalidate trusted internal values.

Where the application has a real typed API surface, strongly prefer Effect 4's `HttpApi`, Schema, and RPC so one endpoint declaration drives the request, response, and error schemas, the server handler contract, the typed client, URL construction, and OpenAPI. Do not force a heavyweight abstraction onto trivial one-off endpoints. Keep the deployment boundary on web standards (Request, Response, fetch, Headers, URL, AbortSignal, ReadableStream, WritableStream), with Deno as the runtime.

## Web platform and CSS

Remove libraries that exist only to paper over capabilities the platform now has: fetch, Request/Response, URL/URLSearchParams, Headers, FormData, Blob/File, Web Streams, AbortController/AbortSignal, `structuredClone`, Web Crypto, native ESM. For frontend behavior consider platform features before adding a dependency: Navigation API, View Transitions, Popover, `dialog`, `inert`, container queries, CSS nesting, cascade layers, `@scope`, anchor positioning, scroll and view timelines, logical properties, custom properties. Use progressive enhancement per the app's browser support policy, and do not replace reliable functionality just to use a new API.

Use modern native CSS. No CSS-in-JS. No Tailwind merely because it is common (keep it if the app substantially benefits). Prefer the cascade and layout system over JavaScript layout calculation, and preserve the existing visual design unless redesign is in scope.

## Testing

Migrate Jest to Vitest 5 and remove Jest, ts-jest, Babel-Jest, and duplicate configuration. Pure logic gets ordinary fast Vitest tests. Browser-dependent behavior (DOM, layout, events, forms, navigation, focus, browser APIs, rendering) uses Vitest Browser Mode with Playwright, not jsdom or happy-dom. Broader user journeys use standalone Playwright. Genuinely Deno-native server, CLI, or runtime behavior uses `deno test` instead of being contorted into a Node harness. Do not duplicate tests across runners. Prefer integration and behavior tests, avoid excessive mocking (Effect Layers substitute dependencies without monkey-patching globals), exercise API boundaries with real schema decoding and encoding, and preserve and test accessibility, keyboard, focus, and form semantics in a real browser.

## Dependencies

Simplify the graph aggressively. Everything is declared in `package.json` and resolved by pnpm (`pnpm add`, `pnpm add -D`, `pnpm add jsr:...`). Remove dependencies superseded by Deno, TypeScript 7, Vite 8, Solid 2, Effect 4, browser APIs, modern CSS, Vitest 5, and Oxlint. Do not keep old ones to minimize the diff, but keep mature specialist libraries with real domain value. Prefer direct imports to barrel files, and avoid code generation that ordinary inference or Effect Schema can replace.

Keep pnpm's strict boundaries. Fix phantom dependencies by declaring them; do not hoist the world, flatten `node_modules`, or switch to npm's flat layout unless a concrete tool forces it. Use overrides, patches, the workspace protocol, and catalogs where they solve a graph problem. Never hand-edit `node_modules` or commit it: it exists as a Vite/npm compatibility boundary, not as evidence that Node should be the runtime.

## Procedure

Inspect first: runtime targets, build system, entrypoints, routes, persistence and network boundaries, tests, CI, deployment assumptions, dependency-management state, and public APIs. Establish whatever baseline is possible and separate preexisting breakage from migration regressions. Then migrate coherently, in this order:

1. Make pnpm the sole package authority, with `pnpm-lock.yaml` the sole lockfile.
2. Make Deno the runtime and task runner, consuming pnpm's `node_modules` with `nodeModulesDir: "manual"`.
3. Move to TypeScript 7 and resolve every new diagnostic properly.
4. Replace the old lint and build tooling with Oxlint and Vite 8.
5. Port any frontend completely to Solid 2 and the new `@solidjs/vite-plugin`.
6. Move serving, routing, and SSR onto Start mode.
7. Introduce Effect 4 at meaningful I/O and domain boundaries; Schema replaces duplicated runtime validation.
8. Replace obsolete Node and browser utility packages with Deno or Web Platform facilities where that simplifies.
9. Port tests to Vitest 5 (Browser Mode where needed) and `deno test` where runtime-specific.
10. Delete obsolete compatibility code, packages, configs, scripts, entrypoints, generated artifacts, duplicate lockfiles, and documentation.
11. Run the complete final verification and inspect the production artifact.

Do not stop with both stacks operational, and never leave `deno install` and `pnpm install` as competing supported workflows.

## Agent ergonomics

If the repository has no clear agent instructions, add a terse `AGENTS.md` stating: runtime and task runner Deno; package manager pnpm; manifest `package.json`; lockfile `pnpm-lock.yaml`; `node_modules` owner pnpm; Deno `nodeModulesDir` manual; frontend Solid 2; app serving `@solidjs/vite-plugin` Start mode; effects and domain I/O Effect 4; build Vite 8; lint Oxlint; tests Vitest 5 / Browser Mode plus `deno test` where runtime-specific; install `pnpm install`; canonical verification `deno task check`. It must prevent a future agent from reintroducing React, Node-first execution, SolidStart, Vite+, Jest, ESLint, npm, Yarn, Bun, Deno-owned npm installation, or a second lockfile. Prefer deterministic configuration and explicit types and contracts over magic, so compiler, linter, and test diagnostics stay precise.

## Cleanup

When the migration works, search for remnants of the old stack and remove them if no longer required: react, react-dom, next, redux, mobx, zustand, @tanstack/react-query, axios, express, webpack, babel, rollup and esbuild configs, vite-plugin-solid, @solidjs/start, jest, ts-jest, eslint, prettier, npm/yarn/bun commands, `deno install` or `deno add` used for project dependencies, Node-only bootstrap code, CommonJS `require`/`module.exports`, `package-lock.json`, `yarn.lock`, `bun.lock`, `bun.lockb`, `deno.lock` in a pnpm-owned repo, obsolete tsconfig workarounds, and legacy polyfills. Keep a dependency with a legitimate compatibility surface; the goal is architectural cleanliness, not blind search-and-delete. Never remove `package.json`, `pnpm-lock.yaml`, or pnpm configuration that serves a real purpose merely because Deno is the runtime.

## CI

CI reproduces the same ownership model as local development: `pnpm install --frozen-lockfile` (never `deno install` afterward), then `deno task lint`, `typecheck`, `test`, `build`, and `check`, plus browser and end-to-end tasks where applicable. Do not regenerate the lockfile in CI, and do not let a dirty graph succeed by silently updating `pnpm-lock.yaml`. Cache pnpm's store where worthwhile, but correctness must not depend on a warm cache.

## Verification

From a fresh checkout, with pnpm installing and Deno driving afterward, verify all applicable of: `pnpm install --frozen-lockfile`, `deno task lint`, `typecheck`, `test`, `test:browser`, `build`, `check`. Do not include `deno install --frozen`. Also verify:

- deleting `node_modules` and reinstalling solely through pnpm recreates a functioning repository, and tests pass from that clean install
- normal dev, build, and test commands do not make Deno rewrite or repopulate the dependency tree
- no unexpected `deno.lock`, `package-lock.json`, `yarn.lock`, or Bun lockfile appears, and `package.json`, `pnpm-lock.yaml`, and `deno.json` exist
- the dependency graph holds one coherent Solid 2 package family, with no Solid 1 mixed in
- the real application runs under Deno and representative functionality works; in a real browser, check navigation, forms, error states, asynchronous states, and hydration or SSR; for SSR, check direct navigation to nested routes and production serving, not just client navigation from `/`
- browser and server consoles are free of warnings and errors
- the production bundle retains no old framework or runtime, and server-only dependencies and secrets do not leak into client chunks

## Definition of done

The repository behaves as before, on this division of responsibility: pnpm owns packages, Deno owns execution, Vite owns frontend compilation and dev, Solid owns UI reactivity, Effect owns meaningful effects and domain I/O, TypeScript owns static types, Oxlint owns linting, and Web Platform APIs sit underneath. Favor deletion, directness, native primitives, strong contracts, fine-grained reactivity, typed effects, strict package ownership, and fast machine-verifiable feedback. Update documentation and CI, and leave `pnpm install --frozen-lockfile && deno task check` green from a fresh checkout.
