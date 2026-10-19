---
name: ts-tools
description: Migrate a TypeScript codebase to the Deno, pnpm, TypeScript 7, Vite 8, Solid 2, Effect 4, Oxlint, and Vitest 5 stack.
disable-model-invocation: true
---

# TypeScript Stack Migration

Migrate this codebase to the stack below, which was current in October 2026; after that, check versions against upstream first. The decisions are made: do not compare alternatives or keep obsolete tooling because it is present. Inspect the repo, baseline its tests and build, then migrate to completion. Preserve observable behavior and public APIs unless the migration requires otherwise. Delete obsolete layers instead of wrapping them. Apply only the layers that fit: a server-only service needs no Solid or Vite, a library no app server.

## Division of responsibility

pnpm owns packages, Deno owns execution, Vite owns frontend build and dev, Solid owns UI reactivity, Effect owns I/O and typed failures, TypeScript owns types, Oxlint owns linting, Web Platform APIs sit underneath. No Bun, no Vite+/`vp`.

- **pnpm (latest):** sole package authority. `package.json` is the manifest (npm and JSR via `pnpm add jsr:@scope/pkg`), `pnpm-lock.yaml` the only lockfile; delete `deno.lock`, `package-lock.json`, `yarn.lock`, `bun.lock*`. Change dependencies only through `pnpm add/remove/update`, never `deno add/install`. Keep pnpm's strict layout: declare phantom dependencies, do not hoist. Pin the pnpm release in project metadata; add `pnpm-workspace.yaml` only if needed.
- **Deno (latest):** runtime, tasks, scripts, permissions (explicit, not blanket `-A`), Deno-native tests. `deno.json` sets `"nodeModulesDir": "manual"` and `"lock": false` so Deno consumes pnpm's `node_modules`. Tasks call `node_modules/.bin` binaries directly. Node is not the app runtime; isolate and document any tool that truly needs it. A purely Deno-native program with no npm/Vite graph stays Deno-managed.
- **Interface:** `pnpm install`, then `deno task dev|build|lint|typecheck|test|test:browser|check`. `check` is the fast gate (lint, type check, tests). No parallel `pnpm dev`/`npm run` scripts. Never run `pnpm install` and `deno install` together.

## Tooling

- **TypeScript 7**, strict. Remove config and syntax removed in 6/7 instead of suppressing; no `any`, broad assertions, or `@ts-ignore`. `tsc --noEmit` is authoritative; add `deno check` only for Deno-resolved source. Clean ESM, no CommonJS glue.
- **Vite 8** directly (native Rolldown/Oxc); drop Webpack, Rollup, esbuild, Babel plumbing. No Babel for Solid.
- **Oxlint + `oxlint-tsgolint`** replaces ESLint (JSON config; remove ESLint config and deps after parity). Do not install or configure any formatter. Do not rely on Oxlint's combined type-check mode as the only type check.
- **Solid 2 RC:** `solid-js`, `@solidjs/web`, `@solidjs/vite-plugin`, `@solidjs/router` if needed. Applications use `solid({ start: true })` (add `ssr: true` only if it genuinely helps); Start mode replaces hand-kept `index.html`, bootstraps, adapters. No `@solidjs/start`, no `vite-plugin-solid`. Server boundary is a web-standard `Request -> Response` handler.
- Write Solid, not translated React: signals, derived computations, stores only where structure helps; no destructured reactive values, early accessor reads, memo/callback wrappers, global state managers. Port `createResource`, `batch`, `startTransition`, `useTransition`, `createComputed`, `createMutable` to Solid 2 equivalents. Remove React, Next.js, and their state/router/data libraries unless the repo publishes a React integration.
- **Effect 4** owns I/O, typed failures, services/Layers, scoped resources, concurrency, retries, config, and HTTP/RPC; run effects at app boundaries. Pure helpers stay plain functions. Use `Schema` at untrusted or serialized boundaries (one canonical definition, no revalidating trusted values). For a real typed API surface prefer `HttpApi` + Schema + RPC; do not force it on trivial endpoints.
- **Web platform:** drop libraries that only paper over fetch, URL, Streams, AbortSignal, `structuredClone`, Web Crypto, native ESM. Prefer native CSS (nesting, layers, container queries, anchor positioning, View Transitions, `dialog`, popover) with progressive enhancement; no CSS-in-JS; keep Tailwind only if the app clearly benefits.

## Tests

Jest becomes **Vitest 5** (remove Jest, ts-jest, Babel-Jest). Pure logic gets fast Vitest tests; DOM, layout, focus, forms, and navigation use Vitest Browser Mode with Playwright, not jsdom or happy-dom; full journeys use Playwright directly; Deno-native server or CLI behavior uses `deno test`. No duplicate coverage across runners. Prefer wide, deterministic, isolated tests (see `renovate-tests`); substitute dependencies with Effect Layers, not global patching.

## Procedure

Inspect runtime targets, entrypoints, routes, network and persistence boundaries, tests, CI, and deployment. Baseline and separate preexisting breakage. Then, in order: (1) pnpm as sole package authority; (2) Deno as runtime and task runner; (3) TypeScript 7, fixing every diagnostic properly; (4) Oxlint and Vite 8; (5) Solid 2 port; (6) serving and routing on Start mode; (7) Effect 4 at meaningful boundaries; (8) replace obsolete utility packages with platform facilities; (9) port tests; (10) delete remnants; (11) full verification.

Remnants to delete unless a real compatibility surface remains: react, next, redux, mobx, zustand, react-query, axios, express, webpack, babel, rollup and esbuild configs, jest, eslint, prettier, npm/yarn/bun commands, `deno install/add` for project deps, Node-only bootstrap, `require`/`module.exports`, extra lockfiles, obsolete tsconfig workarounds, polyfills. Never stop with both stacks supported.

If the repo has no agent instructions, add a terse `AGENTS.md` naming the ownership above and the canonical commands (`pnpm install`, `deno task check`), and forbidding a return to React, Node-first execution, SolidStart, Vite+, Jest, ESLint, npm/Yarn/Bun, or a second lockfile.

Touch CI only when asked. When asked, mirror local: `pnpm install --frozen-lockfile` (never regenerate the lockfile), then the Deno tasks, plus browser and end-to-end suites where applicable. Correctness must not depend on a warm cache.

## Verification

From a fresh checkout: `pnpm install --frozen-lockfile`, then each applicable `deno task`. Also confirm:
- deleting `node_modules` and reinstalling through pnpm alone restores a passing repo, and Deno never rewrites the tree;
- no stray lockfile; one coherent Solid 2 package family;
- the app runs under Deno; in a real browser check navigation, forms, error and async states, hydration; for SSR, direct navigation to nested routes and the production server;
- browser and server consoles are clean;
- the production bundle holds no old framework and no server-only code or secrets.

**Report:** what was migrated and deleted, the verification run and not run, preexisting failures, and any dependency kept with its reason.
