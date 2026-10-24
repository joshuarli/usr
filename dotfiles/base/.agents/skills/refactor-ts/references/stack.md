# Chosen stack and migration

This carries the existing stack decisions into the refactoring workflow. Apply only layers needed by the product. Tool facts were checked on 2026-10-24; resolve exact releases, peer compatibility, and version-specific APIs again when changing dependencies. Stable language rules do not require a package upgrade on every invocation.

## Package and runtime ownership

- Use pnpm exclusively. Keep `package.json` as the manifest and `pnpm-lock.yaml` as the only lockfile. Use `pnpm add`, `pnpm remove`, `pnpm update`, and `pnpm install`; use neither npm/npx, Yarn, Bun, nor Deno commands.
- Pin the verified pnpm version in project metadata. Declare dependencies in the package that imports them; repair phantom dependencies rather than enabling hoisting. Add workspace structure only when needed.
- Follow current [pnpm configuration](https://pnpm.io/configuring): non-auth settings belong in `pnpm-workspace.yaml` where applicable, including in a single-package project. Do not retain obsolete `package.json#pnpm` or non-auth `.npmrc` settings. Keep credentials outside committed configuration.
- Use latest non-prerelease [Node.js](https://nodejs.org/en/about/previous-releases) for an in-scope runtime migration; do not silently substitute the LTS channel. Pin the runtime reproducibly with the project's mechanism.
- Node owns execution; package scripts own tasks. Invoke tasks with `pnpm run <script>` and local binaries with `pnpm exec`. Keep `dev`, `build`, `lint`, `typecheck`, `test`, `test:browser`, and `check` only where they serve the project. Make `check` a fast local gate.
- Use native ESM, explicit package boundaries, and Web/Node built-ins where they fit. Preserve actual deployment/browser requirements during migrations. Native Node type stripping is not a build pipeline for Solid TSX or published libraries.

## Compiler, lint, and build

| Owner | Direction |
| --- | --- |
| TypeScript 7 | Stable TS7 ships as [`typescript` with native `tsc`](https://devblogs.microsoft.com/typescript/announcing-typescript-7-0/); do not install preview-era `@typescript/native-preview`/`tsgo` by habit. Keep strict, environment-correct configs and fix removed TS6/7 options instead of suppressing them. |
| Oxlint | Use Oxlint plus `oxlint-tsgolint` and the existing JSON-config preference. Enable [type-aware linting](https://oxc.rs/docs/guide/usage/linter/type-aware.html); confirm supported rules and framework coverage before retiring ESLint. |
| Typecheck gate | Keep a separate compiler check such as `pnpm exec tsc --noEmit -p tsconfig.json`, adapted for project references/declaration builds. This is a deliberate project policy: Oxlint also offers a combined type-check mode, but its lint discovery/configuration must not define the only compiler gate. |
| Vite 8 | Use [Vite directly](https://vite.dev/blog/announcing-vite8) with Rolldown/Oxc and the Solid 2 plugin. Remove parallel Webpack/Rollup/esbuild/Babel plumbing after mapping each responsibility. No Vite+/`vp`. |
| Formatting | Do not install, configure, or run Prettier, Oxfmt, or another formatter, including check-only and indirect runs. Inspect aggregate scripts/hooks and run only permitted checks. Remove obsolete formatter configuration in an in-scope stack migration. |

Select correctness-focused lint rules for unsafe value propagation, floating/misused promises, unjustified assertions, and exhaustive state handling. Check actual installed rule/plugin support; do not equate a similarly named rule with identical semantics or enable every rule for strictness. Avoid blanket pedantic/style groups, formatting/import-order rules, mandatory documentation, and rules that force redundant annotations, wrappers, or verbosity. Review selected lint fixes rather than running blanket autofixes. Where coverage cannot be preserved, repair the pattern or report the specific migration blocker instead of silently dropping a correctness check.

Follow [Vite's migration guide](https://vite.dev/guide/migration) for dependency optimization, transforms, plugin APIs, and targets. Vite compiles TypeScript without type-checking. A development server passing does not prove production output, server externalization, or library declarations are correct.

## Libraries and platform facilities

Use Effect for effectful services, failures, Schema, resource scope, concurrency, retries, config, and substantial HTTP/RPC boundaries. Use Solid for reactivity and UI. Prefer their existing capabilities to an extra validation library, state manager, fetch wrapper, or retry layer with the same responsibility.

Prefer fetch, URL, Streams, AbortSignal, structuredClone, Web Crypto, and platform ESM where they satisfy the real contract. Replace a utility package only after accounting for behavior it supplies, such as cancellation, streaming, encoding, or retries. Pure helpers need neither a library nor an Effect wrapper.

Prefer native CSS and progressive enhancement: nesting, layers, container queries, anchor positioning, View Transitions, dialog, and popover as supported by the product's targets. Do not add CSS-in-JS; keep Tailwind only when it provides a concrete benefit. Preserve accessibility and browser compatibility while simplifying.

## Tests

Use [Vitest 5](https://vitest.dev/guide/migration/) for existing pure logic, Node server, and CLI tests. Migrate Jest/ts-jest/Babel-Jest in scope, preserving assertions and test isolation. Check changed mock defaults and inherited project configuration; duplicate setup/plugins can change behavior.

Use [Vitest Browser Mode](https://vitest.dev/guide/browser/) with `@vitest/browser-playwright`, its `playwright()` provider, and configured browser instances for DOM, layout, focus, forms, and navigation. Current browser APIs come from `vitest/browser`; await interactions and retrying element assertions. Keep the Solid 2 plugin even when a testing example still shows `vite-plugin-solid`.

Keep Playwright directly for existing full journeys. Use Effect test Layers and compatible `@effect/vitest` for Effect behavior. Avoid global patching, duplicated test layers, or replacing real-browser coverage with a DOM emulator. Prefer deterministic, isolated behavior checks, following the project's test policy. Add tests only when the user asks to verify behavior; do not create tests solely because code moved.

## Migration sequence and retirement

Inspect entrypoints, packages, routes, network/persistence, existing tests, deployment, and CI before changing their owners. In an in-scope full migration:

1. Establish pnpm and Node ownership, metadata pins, and canonical local scripts.
2. Move to strict TypeScript 7 and environment-correct ESM; repair all diagnostics.
3. Establish Oxlint and Vite 8 with confirmed rule/plugin coverage.
4. Port applicable UI to Solid 2, then use Start mode for applications; enable SSR only where useful.
5. Put meaningful I/O/failure/resource boundaries under Effect 4 without wrapping pure code.
6. Replace redundant utility layers and migrate existing tests.
7. Remove dead code, packages, configs, imports, commands, and extra lockfiles; verify the real changed paths.

Remove obsolete React/Next and their state/router/data layers unless a published integration requires them; remove duplicated Axios/Express/validation machinery after its responsibilities are covered. Retire Webpack, hand-kept Rollup/esbuild/Babel configuration, Jest, ESLint, and formatter remnants once their replacements are proven. A transitive implementation dependency is not an obsolete user-owned tool: do not try to purge every lockfile occurrence.

Remove old Deno configs, lockfiles, tasks, imports, and `Deno.*` calls in a runtime migration, along with obsolete CommonJS glue, Node bootstraps, and tsconfig workarounds. Do not leave two frameworks or runtimes configured just as an escape hatch. Keep genuine consumer compatibility explicit.

If no agent instructions exist, add a terse `AGENTS.md` describing these owners and the actual canonical commands. Do not overwrite existing policy or add a generic manifesto. Avoid reintroducing discarded stacks through copied examples.

Do not edit CI unless asked. When CI is in scope, mirror local commands with `pnpm install --frozen-lockfile`; never regenerate the lockfile there or rely on a warm cache. Verify metadata changes with a frozen install, browser-facing changes in a real browser, SSR through production serving/nested navigation, and changed build output for old frameworks or server-only code.
