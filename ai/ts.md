Migrate this TypeScript codebase comprehensively to the October 2026 frontier TypeScript/web stack described below.

The stack decisions are already made. Do not spend time comparing frameworks, researching alternative stacks, or preserving obsolete tooling merely because it is already present. Inspect the repository, understand its behavior and constraints, establish the existing test/build baseline, then perform the migration to completion.

Preserve externally observable behavior and public APIs unless changing them is necessary for the migration or clearly fixes an existing defect. Prefer deleting obsolete layers over wrapping them in compatibility abstractions.

## Target architecture

Use this stack where applicable:

- **Deno, latest stable** — canonical runtime, package manager, task runner, script runner, and lockfile owner.
- **TypeScript 7 stable** — strict TypeScript and the native compiler.
- **Vite 8** — frontend dev/build system, using its native Rolldown/Oxc pipeline.
- **Solid 2 RC** — UI/reactivity layer for browser applications.
- **`@solidjs/web`** — Solid 2 DOM/SSR runtime.
- **`@solidjs/vite-plugin`** — Solid compiler and application integration.
- **Solid Start mode in `@solidjs/vite-plugin`** — the full application serving layer. Do **not** build the migrated application around the old separate SolidStart architecture.
- **`@solidjs/router`** where routing is needed.
- **Effect 4 stable** — application effects, typed failures, services, resource lifetimes, concurrency, schemas, configuration, HTTP/RPC, etc.
- **Oxlint + `oxlint-tsgolint`** — linting, including type-aware rules.
- **Vitest 5** — Vite-integrated tests.
- **Vitest Browser Mode + Playwright provider** — browser/component behavior that genuinely depends on browser semantics.
- **Playwright** directly only for true end-to-end flows where Browser Mode is not the right abstraction.
- **Modern native CSS and browser APIs** rather than JavaScript abstractions for platform capabilities the browser now provides.

Apply only layers that make sense for the repository. A server-only TypeScript service does not need Solid or Vite. A library does not need an application server. A frontend application should use the complete relevant frontend stack.

## Deno is canonical

Do **not** introduce Bun.

Do **not** introduce Vite+ / `vp`.

Vite+ currently assumes a Node-based tooling environment and one of npm/pnpm/Yarn/Bun as package manager. We want Deno instead.

Run Vite, Vitest, Oxc tooling, TypeScript tooling, and other npm ecosystem packages through Deno's npm compatibility.

The normal developer interface should be:

```sh
deno install
deno task dev
deno task build
deno task test
deno task check
```

Use `deno.json` / `deno.jsonc` for canonical tasks and Deno configuration. Commit `deno.lock` and use frozen-lockfile behavior in CI.

A `package.json` may remain when it is genuinely useful for npm package metadata, publishing, Vite ecosystem compatibility, or dependency metadata. Its existence does not make npm the package manager: dependency installation and task execution still go through Deno.

Delete `package-lock.json`, `pnpm-lock.yaml`, `yarn.lock`, `bun.lock`, `bun.lockb`, Bun configuration, package-manager shims, and package-manager-specific scripts once they are no longer required.

Allow Deno to create `node_modules` when npm/Vite tooling needs it; it is generated state, not the package-management authority.

Do not add Node as a required user-facing runtime merely because an npm package historically assumed Node. Deno's Node/npm compatibility should be the default. Keep a Node dependency only if an actual incompatibility requires it and there is no reasonable Deno-compatible solution.

For production Deno programs, use explicit permissions rather than blanket `-A` when practical.

## TypeScript 7

Move the project fully onto TypeScript 7 semantics.

Use strict typing. Remove configuration and syntax deprecated or removed by TypeScript 6/7 instead of suppressing diagnostics.

For normal Vite/browser/library TypeScript, use the stable TypeScript 7 compiler as the authoritative static checker.

For source that specifically relies on Deno module resolution, `jsr:` imports, Deno globals, or other Deno-only semantics, also use `deno check`.

A mixed full-stack repository may therefore legitimately have both checks:

```text
TypeScript 7 -> browser/shared/package graph
deno check   -> Deno-native graph
```

Do not make Deno's currently unstable `--unstable-tsgo` integration a CI or release requirement. The standalone TypeScript 7 compiler is already the production-ready native compiler.

Prefer clean ESM throughout. Remove CommonJS glue unless compatibility absolutely requires it.

Use modern strict compiler options and fix the code instead of weakening the compiler. In particular, preserve or adopt strict null checking, unchecked-index safety, exact optional-property semantics, side-effect import checking, and explicit module semantics where compatible with the repository.

Avoid adding `any`, broad assertions, `@ts-ignore`, or unnecessary `@ts-expect-error` merely to get the migration through the compiler.

## Tooling

Use **Vite 8 directly**, not a compatibility distribution.

Vite 8 already uses Rolldown as its unified bundler and Oxc throughout its native compilation pipeline. Remove obsolete explicit Webpack/Rollup/esbuild/Babel plumbing when Vite 8 replaces it.

Do not add Babel for Solid. Solid 2's `@solidjs/vite-plugin` uses its native Oxc-based compiler by default.

Replace ESLint with **Oxlint** unless a small, concrete rule/plugin requirement cannot yet be represented. Enable type-aware linting through `oxlint-tsgolint`.

Prefer JSON/JSONC Oxlint configuration so it works cleanly in the Deno environment.

Do not set up, install, or configure Oxfmt; formatting is a waste of time.

Remove obsolete ESLint configuration, adapters, dependencies, ignores, and duplicated editor settings after parity is achieved.

Provide simple canonical tasks along the lines of:

```text
dev
build
lint
typecheck
test
test:browser       # when applicable
check
```

`check` should be the single fast repository-quality gate: linting, authoritative type checks, and the normal test suite. CI may additionally perform production builds and broader browser/E2E suites.

Do not rely on Oxlint's experimental combined type-check mode as the sole type checker. Use TypeScript 7 and/or `deno check` as appropriate.

## Solid 2

If this repository contains a frontend, migrate it to **Solid 2**, not Solid 1 compatibility patterns and not React-compatible abstractions.

Use the current Solid 2 release-candidate package family and lock the resolved compatible versions in `deno.lock`.

Use:

```ts
solid-js
@solidjs/web
@solidjs/vite-plugin
```

and `@solidjs/router` when routing is required.

Do not use the old `vite-plugin-solid` package name.

### Start mode replaces the old SolidStart path

For applications, use **Start mode built directly into `@solidjs/vite-plugin`**.

The baseline Vite configuration is conceptually:

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

`start: true` is the application serving layer. It owns the application entries, development serving, and build integration.

For a client-only application, keep Start mode in its default SPA/static-output configuration.

If the existing application genuinely benefits from SSR, enable it explicitly:

```ts
solid({
  start: true,
  ssr: true,
})
```

Do not enable SSR simply because it exists. Preserve a static/client-rendered architecture when that is the simpler correct architecture.

When Start mode takes ownership of application entrypoints, remove obsolete hand-maintained `index.html`, client bootstrap, server bootstrap, framework-adapter, or metaframework boilerplate rather than retaining a parallel legacy path.

Use Start mode's current facilities for filesystem routing, API routes/server functions, middleware, per-request setup, environment handling, and SSR where appropriate.

The production server boundary should remain web-standard: ultimately expose or compose around a `Request -> Response` handler such as Start mode's `handleRequest(request)` contract rather than binding application logic to Node HTTP objects.

**Do not introduce `@solidjs/start` as the architecture for a newly migrated Solid 2 app.** The new direction is Start mode in `@solidjs/vite-plugin`.

### Write Solid, not React translated mechanically into Solid

Do not port React components line-for-line and reproduce React's programming model.

Model state as fine-grained reactive dependencies.

Avoid component-wide invalidation patterns, unnecessary stores, global state managers, memoization wrappers, callback memoization, and React-shaped "hook" abstractions.

A Solid component is not a React render function. Preserve Solid's fine-grained semantics and avoid accidentally breaking reactivity by destructuring reactive values or prematurely reading accessors.

Prefer local signals for genuinely local state and derived reactive computations for derived values. Use stores only where structured reactive state actually benefits from them.

Solid 2 makes async part of the reactive graph. Use its current async-aware reactive model rather than recreating the resource/transition machinery of older frameworks.

In particular, do not reintroduce obsolete Solid 1-era primitives that Solid 2's model has absorbed, including patterns built around:

```text
createResource
batch
startTransition
useTransition
createComputed
createMutable
```

Port old uses to their proper Solid 2 equivalents and simplify the surrounding code.

Use Solid's current loading/error/reveal control-flow primitives where they naturally model asynchronous UI.

Do not add React Query, Redux, MobX, Zustand, or equivalent state/data libraries merely because the old application used them. First determine whether Solid's reactive graph plus Effect already covers the requirement.

Remove React, ReactDOM, React-specific state libraries, React-specific router/data libraries, Next.js, JSX runtime configuration, and React compatibility code once the migration is complete, unless the repository intentionally publishes or embeds a React-facing integration.

## Effect 4

Use **Effect 4**, not Effect 3 APIs.

Effect should own nontrivial effectful application logic rather than view-local reactive state.

The basic division is:

```text
Solid
  UI state
  DOM
  fine-grained reactivity
  presentation

Effect
  I/O
  typed failures
  dependency/services
  concurrency
  cancellation
  retries
  timeouts
  resource lifetime
  configuration
  schemas
  networking
  persistence
  workflows
```

Do not wrap every pure helper in `Effect`. Pure computations should remain ordinary functions.

Conversely, avoid raw Promise/try/catch/service-singleton spaghetti in the application/domain layer when Effect gives the operation a meaningful typed representation.

Use `Effect<A, E, R>` to make success, expected failure, and required capabilities visible in the program's types.

Represent expected domain and infrastructure failures explicitly rather than throwing arbitrary `Error` values across application boundaries.

Use Effect services and Layers for dependencies that represent capabilities or managed infrastructure. Avoid ambient global service locators.

Use scoped acquisition/release for resources with lifetimes.

Use Effect concurrency rather than unstructured detached Promises when cancellation or lifetime matters.

Run Effects at application boundaries rather than repeatedly escaping to Promises in the middle of the domain model.

### Schema

Use Effect 4 `Schema` at untrusted or serialized boundaries:

- HTTP input/output
- configuration
- persistence
- local storage
- external APIs
- messages/events
- URL/query data where validation matters

Do not define one TypeScript interface for compile time and separately hand-write validation for the same shape when Schema can provide one canonical definition.

Do not validate trusted internal values redundantly.

### HTTP and RPC

Where the application has a meaningful typed API surface, strongly prefer Effect 4's `HttpApi`, Schema, and/or RPC facilities over manually duplicated server routes, request types, response types, validation, and clients.

A single endpoint declaration should be able to drive as much as is reasonable of:

```text
request schema
response schema
error schema
server handler contract
typed client
URL construction
OpenAPI/reflection
```

Do not force a heavyweight API abstraction onto trivial one-off endpoints, but eliminate duplicated contract definitions where the application already has a real API layer.

Keep the deployment boundary based on standard `Request`, `Response`, `fetch`, `Headers`, `URL`, `AbortSignal`, and streams.

Deno should remain the actual runtime.

## Prefer the web platform

Remove libraries that exist solely to paper over browser capabilities now available natively, where migration is straightforward.

Prefer:

```text
fetch
Request / Response
URL / URLSearchParams
Headers
FormData
Blob / File
Web Streams
AbortController / AbortSignal
structuredClone
crypto / Web Crypto
native ESM
```

over package-specific equivalents.

For frontend behavior, consider modern platform facilities before introducing another dependency:

```text
Navigation API
View Transitions
Popover
dialog
inert
container queries
CSS nesting
cascade layers
@scope
anchor positioning
scroll/view timelines
logical properties
custom properties
```

Use progressive enhancement when a feature is not universal enough for the application's browser support policy.

Do not replace reliable existing functionality merely to use a shiny browser API; use platform primitives where they actually simplify the implementation.

## CSS

Prefer modern native CSS.

Do not introduce CSS-in-JS.

Do not introduce Tailwind merely because it is common. Keep it if the existing application substantially benefits from it, or use it when its authoring model is genuinely advantageous, but native CSS should be the default for new styling.

Use the modern cascade and browser layout system instead of JavaScript layout calculations whenever possible.

Preserve the existing visual design during migration unless redesign is explicitly part of the repository's requirements.

## Testing

Preserve useful existing tests, but migrate the testing architecture rather than carrying Jest infrastructure forever.

Use **Vitest 5** for Vite/application tests.

Move Jest tests to Vitest and remove Jest, ts-jest, Babel-Jest, and duplicate Jest configuration once migration is complete.

For pure logic, use fast ordinary Vitest tests.

For browser-dependent UI/component behavior, prefer **Vitest Browser Mode backed by Playwright** rather than jsdom/happy-dom simulation. We want tests to exercise the real platform when DOM, layout, events, forms, navigation, focus, browser APIs, or rendering semantics matter.

Use standalone Playwright tests for broader end-to-end user journeys when appropriate.

For genuinely Deno-native server/CLI/runtime behavior, `deno test` is acceptable and often preferable. Do not contort Deno-specific code into a Node-oriented test harness solely to have one test runner.

Do not duplicate the same tests under both runners.

Prefer integration/behavior tests over large piles of implementation-detail unit tests.

Avoid excessive mocking. Effect services/Layers should make deterministic dependency substitution straightforward without monkey-patching globals.

Exercise important API boundaries with real schema decoding and encoding.

Preserve accessibility behavior and test important keyboard/focus/form semantics in a real browser.

## Dependencies

Treat this migration as an opportunity to simplify the dependency graph aggressively.

Remove dependencies superseded by:

- Deno
- TypeScript 7
- Vite 8 / Rolldown / Oxc
- Solid 2
- Effect 4
- modern browser APIs
- modern CSS
- Vitest 5
- Oxlint

Do not retain old dependencies merely to minimize diff size.

At the same time, do not reinvent mature specialist functionality simply to reduce the package count. Keep dependencies that provide substantial domain-specific value.

Avoid barrel-file-heavy architectures where direct imports produce clearer boundaries and better tooling/tree-shaking behavior.

Avoid unnecessary code generation when ordinary TypeScript inference or Effect Schema can express the same contract.

## Migration procedure

First inspect the repository thoroughly. Understand its runtime targets, build system, application entrypoints, routes, persistence/network boundaries, existing tests, CI, deployment assumptions, and public APIs.

Before invasive changes, establish whatever existing build/test baseline is possible. If something is already broken, distinguish that clearly from migration regressions.

Then migrate the system coherently rather than accumulating compatibility layers.

A sensible order is:

1. Establish Deno as package/task/runtime authority and clean up dependency management.
2. Move to TypeScript 7 and resolve all new compiler diagnostics properly.
3. Replace the old lint/build tooling with Oxlint and Vite 8.
4. If there is a frontend, port it completely to Solid 2 and the new `@solidjs/vite-plugin`.
5. For an application, move serving/routing/SSR needs onto the plugin's Start mode rather than the old SolidStart architecture.
6. Introduce Effect 4 at meaningful I/O/domain boundaries and replace duplicated runtime validation with Schema.
7. Replace obsolete Node/browser utility packages with Deno or Web Platform facilities where this genuinely simplifies things.
8. Port the tests to the appropriate Vitest 5 Browser Mode / Vitest / Deno test layers.
9. Delete obsolete compatibility code, packages, configs, scripts, entrypoints, generated artifacts, and documentation.
10. Run the complete final verification suite and inspect the production artifact.

Do not stop halfway with both old and new stacks operational unless an external compatibility requirement makes that unavoidable.

## Agent-friendly repository ergonomics

Optimize the result not just for human editing but for coding agents.

Compiler/linter/test diagnostics should be precise and easy to consume.

Keep canonical commands few and obvious.

Prefer deterministic configuration and explicit types/contracts over magic.

Do not disable Vite's useful agent-facing diagnostics or browser-console forwarding.

If the repository does not already have clear agent instructions, add a concise `AGENTS.md` explaining:

```text
runtime/package manager: Deno
frontend: Solid 2
app serving: @solidjs/vite-plugin Start mode
effects/domain I/O: Effect 4
build: Vite 8
lint: Oxlint
tests: Vitest 5 / Browser Mode, plus deno test where runtime-specific
canonical verification command: deno task check
```

Keep that document terse. It should prevent a future agent from accidentally reintroducing React, Node-first tooling, SolidStart, Vite+, Jest, ESLint, or another package manager.

## Cleanup expectations

Once the migration is working, search the repository for remnants of the old stack.

Depending on the original project, this may include:

```text
react
react-dom
next
redux
mobx
zustand
@tanstack/react-query
axios
express
webpack
babel
rollup config
esbuild config
vite-plugin-solid
@solidjs/start
jest
ts-jest
eslint
prettier
npm commands
pnpm commands
yarn commands
bun commands
Node-only bootstrap code
CommonJS require/module.exports
old lockfiles
obsolete tsconfig workarounds
legacy polyfills
```

Remove them when they are no longer required.

Do not remove a dependency merely because its name appears in this list if the repository has a legitimate compatibility surface that still requires it. The goal is architectural cleanliness, not blind search-and-delete.

## Verification

The finished repository must have a clean fresh-checkout workflow driven by Deno.

At minimum, verify all applicable cases:

```sh
deno install --frozen
deno task lint
deno task typecheck
deno task test
deno task test:browser
deno task build
deno task check
```

Use the exact supported frozen-lockfile spelling for the installed Deno release.

Start the actual application under Deno and exercise representative functionality, not merely static compilation.

For frontend applications, open the app in a real browser and verify representative navigation, forms, error states, asynchronous states, and hydration/SSR behavior where applicable.

For SSR/full-stack applications, verify direct navigation to nested routes and production serving, not just client-side navigation from `/`.

Inspect browser and server consoles for warnings/errors.

Inspect the production bundle for accidental retention of the old framework/runtime.

Ensure server-only dependencies and secrets do not leak into client chunks.

Ensure the final dependency graph has one coherent Solid 2 package family rather than accidentally mixing Solid 1 and Solid 2.

Run tests from a clean install, not from stale local dependency state.

## Definition of done

This is complete when the repository behaves as before, but its applicable architecture is now:

```text
                         TypeScript 7
                              │
                  ┌───────────┴───────────┐
                  │                       │
              browser/app              domain/I/O
                  │                       │
               Solid 2                 Effect 4
                  │                       │
       @solidjs/vite-plugin          Schema / services
           Start mode               HTTP / RPC / etc.
                  │                       │
                  └───────────┬───────────┘
                              │
                    Web platform APIs
                              │
                         Vite 8
                    Rolldown + Oxc
                              │
                           Deno
                runtime / packages / tasks
```

The resulting system should feel intentionally designed around this stack, not like the previous architecture with new dependencies bolted onto it.

Favor deletion, directness, native platform primitives, strong contracts, fine-grained reactivity, typed effects, and fast machine-verifiable feedback loops.

Complete the migration, fix all resulting failures, update documentation and CI, and leave the repository in a clean state where `deno task check` is green.
