Migrate this TypeScript codebase comprehensively to the October 2026 frontier TypeScript/web stack described below.

The stack decisions are already made. Do not spend time comparing frameworks, researching alternative stacks, or preserving obsolete tooling merely because it is already present. Inspect the repository, understand its behavior and constraints, establish the existing test/build baseline, then perform the migration to completion.

Preserve externally observable behavior and public APIs unless changing them is necessary for the migration or clearly fixes an existing defect. Prefer deleting obsolete layers over wrapping them in compatibility abstractions.

## Target architecture

Use this stack where applicable:

- **Deno, latest stable** — canonical runtime, task runner, script runner, and execution environment.
- **pnpm, latest stable** — canonical package manager, dependency resolver, global content-addressed package store, and lockfile owner.
- **`package.json`** — canonical dependency manifest for npm/JSR ecosystem dependencies.
- **`pnpm-lock.yaml`** — canonical dependency lockfile.
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

## Deno runs the project; pnpm owns dependencies

Do **not** introduce Bun.

Do **not** introduce Vite+ / `vp`.

The division of responsibility is deliberate:

```text
pnpm
  dependency resolution
  package installation
  package.json
  pnpm-lock.yaml
  global content-addressed store
  node_modules materialization

Deno
  runtime
  task execution
  script execution
  application/server execution
  permissions
  Deno-native tests where appropriate
```

Do not make Deno and pnpm competing package managers.

For a repository using Vite or the npm ecosystem, **pnpm is the sole package-management authority**. Deno consumes the resulting dependency tree but does not own or recreate it.

The normal fresh-checkout developer interface should be:

```sh
pnpm install
deno task dev
deno task build
deno task test
deno task check
```

Dependency changes should likewise go through pnpm:

```sh
pnpm add <package>
pnpm add -D <package>
pnpm remove <package>
pnpm update
```

Do not use `deno add`, `deno remove`, or `deno install` to mutate the project dependency graph in a pnpm-owned repository.

### Canonical configuration

Use `package.json` as the dependency manifest.

Commit:

```text
package.json
pnpm-lock.yaml
deno.json / deno.jsonc
```

For workspaces, use `pnpm-workspace.yaml` when actually needed.

Pin the expected pnpm release through the appropriate project metadata where practical so developers and CI use the same major/toolchain generation.

Use `deno.json` / `deno.jsonc` for canonical tasks and Deno runtime configuration.

For normal Vite/npm projects, configure Deno explicitly along these lines:

```json
{
  "nodeModulesDir": "manual",
  "lock": false
}
```

`nodeModulesDir: "manual"` is intentional: **pnpm creates and owns `node_modules`; Deno only consumes it.**

Do not use Deno's automatic npm installer or its `.deno` node_modules layout in a pnpm-owned project.

Do not configure Deno's node-modules linker merely to reproduce what pnpm already manages.

With this arrangement:

```text
pnpm global CAS
      │
      ▼
project/node_modules/.pnpm
      │
      ▼
project/node_modules
      │
      ├── vite
      ├── vitest
      ├── oxlint
      ├── tsc
      └── application dependencies
             │
             ▼
        deno task ...
```

Deno tasks should invoke the installed package binaries normally:

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

Do not route these through `pnpm exec` merely because pnpm installed them. `deno task` can execute the binaries exposed in `node_modules/.bin`, keeping Deno as the developer-facing task runner.

### One dependency graph, one lockfile

For a normal application repository:

```text
package.json
    ↓
pnpm
    ↓
pnpm-lock.yaml
    ↓
node_modules
    ↓
Deno / Vite / application
```

There should **not** simultaneously be:

```text
pnpm-lock.yaml
deno.lock
package-lock.json
yarn.lock
bun.lock
bun.lockb
```

Choose one dependency authority.

For this stack, that authority is pnpm.

Set Deno locking off for the pnpm-managed graph rather than maintaining a redundant `deno.lock`.

Delete obsolete:

```text
deno.lock
package-lock.json
yarn.lock
bun.lock
bun.lockb
```

once pnpm owns the complete dependency graph.

Keep `pnpm-lock.yaml`.

Do not run both `pnpm install` and `deno install` in CI.

### JSR dependencies

pnpm has first-class JSR support. Prefer keeping JSR dependencies inside the same package-management graph rather than creating a second Deno-specific graph.

Use:

```sh
pnpm add jsr:@scope/package
```

and import through the dependency name recorded in `package.json`.

This keeps:

```text
npm packages
JSR packages
workspace packages
```

under one resolver and one `pnpm-lock.yaml`.

Avoid direct versioned `jsr:` or remote HTTP imports in an otherwise pnpm-owned application when the same dependency can cleanly be represented in `package.json`.

Do not introduce a second lockfile merely for a handful of Deno-native imports.

If the repository is genuinely a Deno-native program whose architecture intentionally depends on direct Deno/JSR/URL module resolution and has no meaningful npm/Vite dependency graph, it may remain Deno-managed instead. Do not add pnpm merely for ideological uniformity to a repository that has nothing for pnpm to manage.

But once a repository substantially depends on Vite/npm tooling, prefer the pnpm-owned model consistently.

### Node is not the application runtime

Do not add Node as the required application runtime merely because npm packages historically assume Node.

Deno's Node/npm compatibility should remain the execution environment wherever it works correctly.

The fact that pnpm manages dependencies does **not** imply:

```text
pnpm -> Node runtime -> application
```

The intended architecture remains:

```text
pnpm -> dependencies

Deno -> application/tool execution
```

If a specific tool has a genuine Deno incompatibility and actually requires Node execution, isolate and document that exception rather than silently converting the repository back into a Node-first project.

For production Deno programs, use explicit permissions rather than blanket `-A` when practical.

## TypeScript 7

Move the project fully onto TypeScript 7 semantics.

Use strict typing. Remove configuration and syntax deprecated or removed by TypeScript 6/7 instead of suppressing diagnostics.

For normal Vite/browser/library TypeScript, use the stable TypeScript 7 compiler as the authoritative static checker.

Because TypeScript is installed through pnpm, the normal task can simply invoke the local compiler:

```text
tsc --noEmit
```

through `deno task typecheck`.

For source that specifically relies on Deno module resolution, Deno globals, or other Deno-only semantics, also use `deno check`.

A mixed full-stack repository may therefore legitimately have both checks:

```text
TypeScript 7 -> browser/shared/package graph
deno check   -> genuinely Deno-specific source
```

Do not duplicate checking without a reason.

Do not make Deno's unstable compiler integrations a CI or release requirement when the standalone TypeScript 7 compiler is already the authoritative production compiler.

Prefer clean ESM throughout. Remove CommonJS glue unless compatibility absolutely requires it.

Use modern strict compiler options and fix the code instead of weakening the compiler. In particular, preserve or adopt strict null checking, unchecked-index safety, exact optional-property semantics, side-effect import checking, and explicit module semantics where compatible with the repository.

Avoid adding `any`, broad assertions, `@ts-ignore`, or unnecessary `@ts-expect-error` merely to get the migration through the compiler.

## Tooling

Use **Vite 8 directly**, not a compatibility distribution.

Vite 8 already uses Rolldown as its unified bundler and Oxc throughout its native compilation pipeline. Remove obsolete explicit Webpack/Rollup/esbuild/Babel plumbing when Vite 8 replaces it.

Do not add Babel for Solid. Solid 2's `@solidjs/vite-plugin` uses its native Oxc-based compiler by default.

Install frontend/build tooling through pnpm and run it through Deno tasks.

For example:

```sh
pnpm add -D vite vitest oxlint typescript
```

with the appropriate Solid packages added to the proper dependency sections.

Replace ESLint with **Oxlint** unless a small, concrete rule/plugin requirement cannot yet be represented. Enable type-aware linting through `oxlint-tsgolint`.

Prefer JSON/JSONC Oxlint configuration.

Do not set up, install, or configure Oxfmt; formatting is a waste of time.

Remove obsolete ESLint configuration, adapters, dependencies, ignores, and duplicated editor settings after parity is achieved.

Provide simple canonical Deno tasks along the lines of:

```text
dev
build
lint
typecheck
test
test:browser       # when applicable
check
```

`check` should be the single fast repository-quality gate: linting, authoritative type checks, and the normal test suite.

CI may additionally perform production builds and broader browser/E2E suites.

Do not rely on Oxlint's experimental combined type-check mode as the sole type checker. Use TypeScript 7 and/or `deno check` as appropriate.

Do not put ordinary developer commands primarily in `package.json` scripts simply because pnpm is present. `package.json` owns dependencies; `deno.json` owns the canonical task interface.

Avoid parallel interfaces such as:

```text
pnpm dev
npm run dev
deno task dev
```

unless compatibility with external tooling genuinely requires a package script.

The preferred human/agent interface after dependency installation is:

```text
deno task <name>
```

## Solid 2

If this repository contains a frontend, migrate it to **Solid 2**, not Solid 1 compatibility patterns and not React-compatible abstractions.

Use the current Solid 2 release-candidate package family and lock the resolved compatible versions in `pnpm-lock.yaml`.

Use:

```text
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

Keep the deployment boundary based on standard:

```text
Request
Response
fetch
Headers
URL
AbortSignal
ReadableStream
WritableStream
```

Deno should remain the actual application runtime.

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

For browser-dependent UI/component behavior, prefer **Vitest Browser Mode backed by Playwright** rather than jsdom/happy-dom simulation.

We want tests to exercise the real platform when DOM, layout, events, forms, navigation, focus, browser APIs, or rendering semantics matter.

Use standalone Playwright tests for broader end-to-end user journeys when appropriate.

For genuinely Deno-native server/CLI/runtime behavior, `deno test` is acceptable and often preferable. Do not contort Deno-specific code into a Node-oriented test harness solely to have one test runner.

Do not duplicate the same tests under both runners.

Prefer integration/behavior tests over large piles of implementation-detail unit tests.

Avoid excessive mocking. Effect services/Layers should make deterministic dependency substitution straightforward without monkey-patching globals.

Exercise important API boundaries with real schema decoding and encoding.

Preserve accessibility behavior and test important keyboard/focus/form semantics in a real browser.

## Dependencies

Treat this migration as an opportunity to simplify the dependency graph aggressively.

All dependencies should be declared through `package.json` and resolved by pnpm in a pnpm-owned repository.

Prefer:

```sh
pnpm add ...
pnpm add -D ...
pnpm add jsr:...
```

rather than mixing package-management commands.

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

### pnpm discipline

Preserve pnpm's strict dependency boundaries.

Do not work around undeclared-dependency failures by hoisting the world or flattening `node_modules` unless a concrete incompatible tool forces it.

Fix phantom dependencies by declaring them.

Avoid broad hoisting configuration unless required.

Do not switch to npm's traditional flat `node_modules` model merely because an old package accidentally depended on undeclared siblings.

Use pnpm overrides, patches, workspace protocols, catalog/configuration facilities, or other package-manager mechanisms where they provide a clean solution to dependency-graph problems.

Do not manually edit generated `node_modules` contents.

`node_modules` remains generated state and must not be committed.

The fact that it exists is a Vite/npm ecosystem compatibility boundary, not evidence that Node should become the runtime.

## Migration procedure

First inspect the repository thoroughly. Understand its runtime targets, build system, application entrypoints, routes, persistence/network boundaries, existing tests, CI, deployment assumptions, dependency-management state, and public APIs.

Before invasive changes, establish whatever existing build/test baseline is possible. If something is already broken, distinguish that clearly from migration regressions.

Then migrate the system coherently rather than accumulating compatibility layers.

A sensible order is:

1. Establish **pnpm as the sole package/dependency authority** and `pnpm-lock.yaml` as the sole dependency lockfile.
2. Establish **Deno as the canonical runtime and task runner**, consuming pnpm's `node_modules` with `nodeModulesDir: "manual"`.
3. Move to TypeScript 7 and resolve all new compiler diagnostics properly.
4. Replace the old lint/build tooling with Oxlint and Vite 8.
5. If there is a frontend, port it completely to Solid 2 and the new `@solidjs/vite-plugin`.
6. For an application, move serving/routing/SSR needs onto the plugin's Start mode rather than the old SolidStart architecture.
7. Introduce Effect 4 at meaningful I/O/domain boundaries and replace duplicated runtime validation with Schema.
8. Replace obsolete Node/browser utility packages with Deno or Web Platform facilities where this genuinely simplifies things.
9. Port the tests to the appropriate Vitest 5 Browser Mode / Vitest / Deno test layers.
10. Delete obsolete compatibility code, packages, configs, scripts, entrypoints, generated artifacts, duplicate lockfiles, and documentation.
11. Run the complete final verification suite and inspect the production artifact.

Do not stop halfway with both old and new stacks operational unless an external compatibility requirement makes that unavoidable.

In particular, do not leave both:

```text
deno install
pnpm install
```

as competing supported installation workflows.

For a Vite/npm repository, the answer is:

```text
pnpm install
```

followed by Deno tasks.

## Agent-friendly repository ergonomics

Optimize the result not just for human editing but for coding agents.

Compiler/linter/test diagnostics should be precise and easy to consume.

Keep canonical commands few and obvious.

Prefer deterministic configuration and explicit types/contracts over magic.

Do not disable Vite's useful agent-facing diagnostics or browser-console forwarding.

A coding agent should be able to infer the repository model immediately:

```text
dependencies -> package.json + pnpm-lock.yaml + pnpm
tasks       -> deno.json
runtime     -> Deno
frontend    -> Vite + Solid
effects     -> Effect
```

If the repository does not already have clear agent instructions, add a concise `AGENTS.md` explaining:

```text
runtime: Deno
task runner: Deno
package manager: pnpm
dependency manifest: package.json
dependency lockfile: pnpm-lock.yaml
node_modules owner: pnpm
Deno node_modules mode: manual
frontend: Solid 2
app serving: @solidjs/vite-plugin Start mode
effects/domain I/O: Effect 4
build: Vite 8
lint: Oxlint
tests: Vitest 5 / Browser Mode, plus deno test where runtime-specific
install: pnpm install
canonical verification command: deno task check
```

Keep that document terse.

It should prevent a future agent from accidentally reintroducing:

```text
React
Node-first execution
SolidStart
Vite+
Jest
ESLint
npm
Yarn
Bun
Deno-owned npm installation
a second dependency lockfile
```

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
yarn commands
bun commands
deno install used as project dependency installation
deno add used for package.json-managed dependencies
Node-only bootstrap code
CommonJS require/module.exports
package-lock.json
yarn.lock
bun.lock
bun.lockb
deno.lock in a pnpm-owned repository
obsolete tsconfig workarounds
legacy polyfills
```

Remove them when they are no longer required.

Do **not** remove:

```text
package.json
pnpm-lock.yaml
pnpm configuration that serves a real purpose
```

merely because Deno is the runtime.

Do not remove a dependency merely because its name appears in this list if the repository has a legitimate compatibility surface that still requires it. The goal is architectural cleanliness, not blind search-and-delete.

## CI

CI should reproduce the same ownership model as local development.

For a pnpm-owned repository, dependency installation begins with:

```sh
pnpm install --frozen-lockfile
```

Do not run `deno install` afterward.

Then execute repository operations through Deno:

```sh
deno task lint
deno task typecheck
deno task test
deno task build
deno task check
```

Include Browser Mode/E2E tasks where applicable.

The conceptual CI pipeline is:

```text
checkout
   │
   ▼
pnpm install --frozen-lockfile
   │
   ▼
node_modules backed by pnpm CAS
   │
   ▼
deno task check
   │
   ├── oxlint
   ├── tsc / deno check
   ├── vitest
   └── other fast checks
   │
   ▼
deno task build
   │
   ▼
browser / E2E verification
```

Do not regenerate the lockfile in CI.

Do not permit a dirty dependency graph to succeed by silently updating `pnpm-lock.yaml`.

Cache pnpm's store where the CI environment makes that worthwhile, but correctness must not depend on a warm cache.

## Verification

The finished repository must have a clean fresh-checkout workflow with **pnpm installing dependencies and Deno driving the repository afterward**.

At minimum, verify all applicable cases:

```sh
pnpm install --frozen-lockfile
deno task lint
deno task typecheck
deno task test
deno task test:browser
deno task build
deno task check
```

Do not include `deno install --frozen` in this workflow.

Verify that deleting `node_modules` and reinstalling solely through pnpm recreates a functioning repository.

Verify that running the normal development/build/test commands does not cause Deno to rewrite or independently repopulate the dependency tree.

Verify that no unexpected `deno.lock`, `package-lock.json`, `yarn.lock`, or Bun lockfile appears.

Start the actual application under Deno and exercise representative functionality, not merely static compilation.

For frontend applications, open the app in a real browser and verify representative navigation, forms, error states, asynchronous states, and hydration/SSR behavior where applicable.

For SSR/full-stack applications, verify direct navigation to nested routes and production serving, not just client-side navigation from `/`.

Inspect browser and server consoles for warnings/errors.

Inspect the production bundle for accidental retention of the old framework/runtime.

Ensure server-only dependencies and secrets do not leak into client chunks.

Ensure the final dependency graph has one coherent Solid 2 package family rather than accidentally mixing Solid 1 and Solid 2.

Run tests from a clean pnpm install, not from stale local dependency state.

Verify dependency ownership explicitly:

```text
package.json          exists
pnpm-lock.yaml        exists
node_modules          generated by pnpm
deno.json             owns tasks/runtime configuration

deno.lock             absent in ordinary pnpm-owned app
package-lock.json     absent
yarn.lock             absent
bun.lock              absent
bun.lockb             absent
```

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
                    executed by Deno
                              │
             runtime / tasks / permissions


 package.json
      │
      ▼
    pnpm ───────────────► pnpm global CAS
      │
      ▼
 pnpm-lock.yaml
      │
      ▼
 node_modules
      │
      └──────────────► consumed by Deno / Vite
```

The resulting system should feel intentionally designed around this division:

```text
pnpm owns packages.
Deno owns execution.
Vite owns frontend compilation/dev.
Solid owns UI reactivity.
Effect owns meaningful effects/domain I/O.
TypeScript owns static types.
Oxlint owns linting.
```

Do not blur those ownership boundaries without a concrete technical reason.

The presence of `node_modules` is accepted as a compatibility layer for the Vite/npm ecosystem. pnpm's shared content-addressed store should provide the centralized package storage and disk efficiency; do not contort Deno into simultaneously managing the same packages.

The goal is not a superficially "Deno-only" repository.

The goal is the cleanest current architecture:

```text
pnpm for the part Vite still expects to look like Node package management,
Deno for everything that actually needs to execute.
```

Favor deletion, directness, native platform primitives, strong contracts, fine-grained reactivity, typed effects, strict package ownership, and fast machine-verifiable feedback loops.

Complete the migration, fix all resulting failures, update documentation and CI, and leave the repository in a clean state where:

```sh
pnpm install --frozen-lockfile
deno task check
```

are green from a fresh checkout.