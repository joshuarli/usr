---
name: ts-tools
description: Migrate a TypeScript codebase to the Node.js, pnpm, TypeScript 7, Vite 8, Solid 2, Effect 4, Oxlint, and Vitest 5 stack.
disable-model-invocation: true
---

# TypeScript Stack Migration

Migrate this codebase to the stack below, which was current in October 2026; after that, check versions against upstream first. The decisions are made: do not compare alternatives or keep obsolete tooling because it is present. Inspect the repo and use existing test and build results to identify current behavior and preexisting failures. Preserve observable behavior and public APIs unless the migration requires otherwise. Delete obsolete layers instead of wrapping them. Apply only the layers that fit: a server-only service needs no Solid or Vite, a library no app server.

## Division of responsibility

pnpm owns packages, and Node.js owns execution. Vite handles frontend build and dev. Solid owns UI reactivity. Effect handles I/O and typed failures. TypeScript owns types, and Oxlint owns linting. Prefer Web Platform APIs where they fit. Use the latest stable Node.js release. Do not use the npm CLI, Bun, or Vite+/`vp`.

- **pnpm (latest):** Use pnpm as the sole package manager. `package.json` is the manifest, and `pnpm-lock.yaml` is the only lockfile. Delete `package-lock.json`, `yarn.lock`, and `bun.lock*`. Use `pnpm add`, `pnpm remove`, and `pnpm update` to change dependencies. Declare phantom dependencies and do not hoist. Pin the pnpm release in project metadata. Add `pnpm-workspace.yaml` only if needed.
- **Node.js (latest stable):** Use Node.js as the runtime and task runner. Keep project tasks in `package.json` scripts and invoke them through pnpm. Use ESM and Node's built-in APIs where they fit.
- **Commands:** Use `pnpm install` to install packages. Define project tasks in `package.json` scripts and invoke them with `pnpm run <script>`. Common scripts include `dev`, `build`, `lint`, `typecheck`, `test`, `test:browser`, and `check`. Make `check` the fast gate for lint, type checking, and tests. Do not use npm commands.

## Tooling

- **TypeScript 7:** Use strict mode. Remove config and syntax removed in TypeScript 6 or 7 instead of suppressing diagnostics. Avoid `any`, broad assertions, and `@ts-ignore`. Treat `tsc --noEmit` as authoritative. Use ESM and no CommonJS glue.
- **Vite 8** directly (native Rolldown/Oxc); drop Webpack, Rollup, esbuild, Babel plumbing. No Babel for Solid.
- **Oxlint + `oxlint-tsgolint`** replaces ESLint (JSON config; remove ESLint config and deps after parity). Do not install or configure any formatter. Do not rely on Oxlint's combined type-check mode as the only type check.
- **Solid 2 RC:** `solid-js`, `@solidjs/web`, `@solidjs/vite-plugin`, `@solidjs/router` if needed. Applications use `solid({ start: true })` (add `ssr: true` only if it genuinely helps); Start mode replaces hand-kept `index.html`, bootstraps, adapters. No `@solidjs/start`, no `vite-plugin-solid`. Server boundary is a web-standard `Request -> Response` handler.
- Write Solid, not translated React: signals, derived computations, stores only where structure helps; no destructured reactive values, early accessor reads, memo/callback wrappers, global state managers. Port `createResource`, `batch`, `startTransition`, `useTransition`, `createComputed`, `createMutable` to Solid 2 equivalents. Remove React, Next.js, and their state/router/data libraries unless the repo publishes a React integration.
- **Effect 4** owns I/O, typed failures, services/Layers, scoped resources, concurrency, retries, config, and HTTP/RPC; run effects at app boundaries. Pure helpers stay plain functions. Use `Schema` at untrusted or serialized boundaries (one canonical definition, no revalidating trusted values). For a real typed API surface prefer `HttpApi` + Schema + RPC; do not force it on trivial endpoints.
- **Web platform:** drop libraries that only paper over fetch, URL, Streams, AbortSignal, `structuredClone`, Web Crypto, native ESM. Prefer native CSS (nesting, layers, container queries, anchor positioning, View Transitions, `dialog`, popover) with progressive enhancement; no CSS-in-JS; keep Tailwind only if the app clearly benefits.

## Tests

Move Jest tests to **Vitest 5** and remove Jest, ts-jest, and Babel-Jest. Keep existing pure logic tests in Vitest. Use Vitest Browser Mode with Playwright for DOM, layout, focus, forms, and navigation tests. Use Playwright directly for existing full journeys. Keep Node server and CLI tests in Vitest's Node environment. Do not duplicate coverage or add tests unless the user asks to verify behavior. Prefer wide, deterministic, isolated tests (see `renovate-tests`). Substitute dependencies with Effect Layers, not global patching.

## Procedure

Inspect runtime targets, entrypoints, routes, network and persistence boundaries, tests, CI, and deployment. Use existing test and build results to identify preexisting failures. Then, in order: (1) pnpm as sole package authority; (2) Node.js as runtime and task runner; (3) TypeScript 7, fixing every diagnostic properly; (4) Oxlint and Vite 8; (5) Solid 2 port; (6) serving and routing on Start mode; (7) Effect 4 at meaningful boundaries; (8) replace obsolete utility packages with platform facilities; (9) migrate existing tests; (10) delete remnants; (11) verify changed behavior with the narrowest applicable check when requested.

Remove legacy Deno configuration, tasks, imports, and runtime calls, including `deno.json`, `deno.jsonc`, `deno.lock`, and `Deno.*` APIs.

Remnants to delete unless a real compatibility surface remains: react, next, redux, mobx, zustand, react-query, axios, express, webpack, babel, rollup and esbuild configs, jest, eslint, prettier, npm/yarn/bun commands, obsolete Node bootstraps, `require`/`module.exports`, extra lockfiles, obsolete tsconfig workarounds, and polyfills. Do not leave old and new frameworks configured together.

If the repo has no agent instructions, add a terse `AGENTS.md` naming the ownership above and the canonical commands (`pnpm install`, `pnpm run check`). Forbid a return to Deno, React, SolidStart, Vite+, Jest, ESLint, the npm CLI, Yarn, Bun, or a second lockfile.

Touch CI only when asked. When asked, mirror local: `pnpm install --frozen-lockfile` (never regenerate the lockfile), then the pnpm tasks and browser and end-to-end suites where applicable. Correctness must not depend on a warm cache.

## Verification

Follow the repository's verification instructions. When the user asks for verification, run the narrowest check that covers each changed behavior. Widen only for a specific integration risk or an explicit request for broader checks. State the reason before starting a broader check.

- When package metadata or a lockfile changes, verify installation with `pnpm install --frozen-lockfile`.
- For browser-facing changes, verify the affected paths in a real browser.
- For SSR changes, verify nested-route navigation and the production server.
- Confirm there is one lockfile and one coherent Solid 2 package family when package configuration changes.
- Inspect the production bundle for old frameworks, server-only code, and secrets when build output changes.

**Report:** what was migrated and deleted, the verification run and not run, preexisting failures, and any dependency kept with its reason.
