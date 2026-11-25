+++
name = "typescript"
summary = "TypeScript decodes untrusted values once, models correlated states with unions, keeps deliberate inference and module boundaries, owns every Promise, and runs on the chosen pnpm, Node, tsrs, Oxlint, Vite, and Vitest stack."

[[trigger]]
paths = ["*.ts", "*.tsx", "*.mts", "*.cts", "tsconfig*.json", "package.json", "pnpm-workspace.yaml", ".oxlintrc.json", "vite.config.*", "vitest.config.*"]

[examples]
match = ["src/app.ts", "web/App.tsx", "tsconfig.build.json", "package.json", "vite.config.mts"]
skip = ["src/app.js", "README.md", "tools/x.py"]
+++

# TypeScript

Use the [Handbook](https://www.typescriptlang.org/docs/handbook/), [TSConfig reference](https://www.typescriptlang.org/tsconfig/), and documentation matching the installed compiler for language semantics. Use [Effective TypeScript, second edition](https://effectivetypescript.com/2024/05/21/second-edition/) for design judgment, not release-specific APIs. [typescript-eslint rule explanations](https://typescript-eslint.io/rules/) are useful bug-pattern references; implement applicable checks with Oxlint, not a second linter.

The [Google guide](https://google.github.io/styleguide/tsguide.html) is a selective secondary source: its internal environment, TSLint examples, and blanket private-field prohibition do not govern this stack. [Microsoft's coding guidelines](https://github.com/microsoft/TypeScript/wiki/Coding-guidelines) describe the compiler repository, not the whole ecosystem. Follow current semantics and concrete project constraints rather than importing either guide wholesale.

## Code

### Contracts to preserve

Identify application versus published-library boundaries and browser, server, worker, and test environments. Trace actual data and resource flows: unknown input to decoded value, service to runner, reactive source to UI, acquisition to release. Establish focused baseline results or record unavailable checks.

For each batch, identify its concrete benefit, preserved invariant, and smallest regression check. Preserve wire formats, property presence, public imports and types, failures and status, initialization, SSR, cancellation, and performance. Stronger validation, changed defaults, and new failure cases are contract changes. Fix incidental bugs only within authorized behavior; otherwise report them and continue.

### Values, trust, and states

- Treat untrusted JSON, configuration, request parameters, persisted data, and third-party output as `unknown`. Decode with the canonical Effect Schema at the real trust/serialization boundary; derive domain types instead of maintaining a validator and interface independently. Keep encoded and decoded representations distinct.
- Preserve accepted encodings/coercions, defaults, unknown-key handling, omission/null semantics, and validation error shape when replacing a decoder. Rejecting formerly valid input or silently dropping fields is a contract change, even when the new schema looks stricter.
- Do not invent `parseJson<T>(): T` or fetch helpers that promise a caller-selected type without a decoder. [Assertions](https://www.typescriptlang.org/docs/handbook/2/everyday-types.html#type-assertions), non-null assertions, and `satisfies` perform no runtime validation. Isolate a genuinely unavoidable assertion at the boundary with evidence; fix the contract instead of spreading `as unknown as`, `any`, or `!`.
- Use [discriminated unions](https://www.typescriptlang.org/docs/handbook/2/narrowing.html#discriminated-unions) for correlated states. Avoid independent loading/success/error booleans and optional payloads that permit impossible combinations. Use exhaustive handling where every variant matters, with a `never` check or the stack's exhaustive match facility. Do not duplicate state already represented by Solid's async primitives.
- Preserve absence, present `undefined`, and `null` as distinct when the contract distinguishes them. Do not replace checks with truthiness when `0`, `false`, or an empty string is valid. Use `??` for missing-value defaults only when both null and undefined should default.
- Use a total `Record<K, V>` for a closed, fully populated key set. For dynamic lookup, represent absence and handle it; a type annotation does not populate a dictionary.
- Introduce brands/refinements only for concrete domain mix-ups or constraints, constructed through validation. Do not brand every string or identifier.
- Review handwritten type predicates and assertion functions as trusted code: their annotations do not prove their bodies. Establish both predicate branches and the assertion's throw path. A positive-number predicate cannot claim membership in all `number` values. Prefer ordinary narrowing or the canonical decoder when sufficient; never invent a guard merely to silence an error.

### Inference and API shape

- Infer obvious locals. Give published APIs and service boundaries intentional input/output contracts when they prevent accidental widening or implementation leakage. Keep useful inference inside the implementation.
- Use [`satisfies`](https://www.typescriptlang.org/docs/handbook/release-notes/typescript-4-9.html#the-satisfies-operator) for checked literals/configuration tables when their specific inferred shape matters. Use an annotation when the declared abstraction should be the exposed contract. Inspect contextual inference instead of assuming either form is interchangeable.
- Use `as const` for intentional literals/readonly tuples. [`readonly`](https://www.typescriptlang.org/docs/handbook/2/objects.html#readonly-properties) expresses a static access contract; it neither freezes objects nor eliminates mutable aliases. Accept readonly inputs when mutation is unnecessary, without introducing generic deep-readonly machinery.
- Recheck facts invalidated by mutation, callbacks, or `await`; TypeScript's [soundness limits](https://www.typescriptlang.org/docs/handbook/type-compatibility.html#a-note-on-soundness) do not disappear under `strict`. Capture the required stable value when appropriate; retaining an alias to a mutable object is not a snapshot.
- Prefer concrete domain types and small unions. A [generic parameter](https://www.typescriptlang.org/docs/handbook/2/functions.html#guidelines-for-writing-good-generic-functions) must express a useful relationship between values/types. Avoid speculative overloads, return-only generics, and recursive conditional types that make inference or compiler performance worse.
- Preserve valid explicit generic callers and excess-property behavior when simplifying APIs. Type-aware lint findings are leads; a superficially redundant parameter can still affect compatibility.
- Choose [interfaces versus aliases](https://www.typescriptlang.org/docs/handbook/2/everyday-types.html#differences-between-type-aliases-and-interfaces) by the contract: interfaces for object extension/reopening where wanted, aliases for unions and other type expressions. Keep consistent existing choices when either works.
- Prefer literal unions or constant objects for new application tags when sufficient. Before replacing an [enum](https://www.typescriptlang.org/docs/handbook/enums.html#objects-vs-enums), account for runtime values, reverse mappings, serialization, public imports, and consumers. Native Node type stripping imposes additional syntax restrictions.
- Use classes for actual identity, encapsulation, or framework contracts, including Effect services/schema classes. Prefer functions and data otherwise. Native `#private` and TypeScript `private` have different runtime semantics; do not exchange them merely for style.

### Compiler and module boundaries

Use explicit `strict: true`. When tightening a project, adopt these checks with proper repairs, not broad suppressions:

| Check | Repair the model |
| --- | --- |
| [`noUncheckedIndexedAccess`](https://www.typescriptlang.org/tsconfig/noUncheckedIndexedAccess.html) | Handle missing indexed values; prefer iteration or a real invariant to repeated `!`. |
| [`exactOptionalPropertyTypes`](https://www.typescriptlang.org/tsconfig/exactOptionalPropertyTypes.html) | Preserve property-presence semantics; add `undefined` only if actually part of the API. |
| [`noImplicitOverride`](https://www.typescriptlang.org/tsconfig/noImplicitOverride.html) | Make intentional inheritance relationships explicit. |
| [`noUncheckedSideEffectImports`](https://www.typescriptlang.org/tsconfig/noUncheckedSideEffectImports.html) | Use the real asset integration/declarations; do not hide arbitrary missing modules. |
| [`verbatimModuleSyntax`](https://www.typescriptlang.org/tsconfig/verbatimModuleSyntax.html) | Use `import type`/`export type`, retaining deliberate side-effect imports. |

Match [module configuration](https://www.typescriptlang.org/docs/handbook/modules/guides/choosing-compiler-options.html) to execution: bundler-compatible resolution for Vite, NodeNext-compatible resolution for Node, and consumer-compatible emitted code/declarations for libraries. Separate materially different browser, Node, worker, and test environments so one does not accidentally grant another's globals.

Type-only import cleanup can change initialization if the removed import carried a side effect; preserve that side effect explicitly when required. A TypeScript `paths` mapping does not configure the runtime. Check real package exports, aliases, relative extensions, and production entrypoints rather than trusting the development bundler. For affected published APIs, check representative consumer type calls and emitted declarations/export conditions, not only internal compilation. Do not add `skipLibCheck`, broad ambient modules, or exclusions to hide a broken migration.

For [native Node TypeScript](https://nodejs.org/api/typescript.html), use compatible erasable syntax, explicit type imports, and runtime-resolvable extensions. Node ignores tsconfig and does not type-check, downlevel JavaScript, resolve TS paths, or run TSX. Do not use the removed `--experimental-transform-types` escape hatch. Vite/Solid handles TSX; published libraries still need their promised distribution format.

### Implementation and asynchronous work

- Use precise domain names, cohesive modules, and direct control flow. Do not add an index/barrel at every directory or create cycles to shorten imports. Keep server-only implementations out of shared/client modules.
- Keep pure helpers ordinary functions. Do not build a service or Effect wrapper merely to compute a deterministic value; move into Effect when failures, dependencies, resources, or execution policy require it.
- Preserve callback receivers, object identity, getter evaluation, and own-property/prototype semantics when extracting methods or rewriting objects. An arbitrary-key dictionary needs deliberate ownership checks or a suitable `Map`; a structural object type does not establish runtime key safety.
- Every Promise needs an observer and an owner. [`void promise`](https://typescript-eslint.io/rules/no-floating-promises/#ignorevoid) does not handle rejection. Avoid async `forEach`, Promise-valued conditions, and callbacks whose caller ignores their result.
- Choose sequential execution when order matters and bounded concurrency when independent work can fan out. Preserve ordering, backpressure, timeouts, and cancellation rather than replacing loops with unbounded `Promise.all`.
- `Promise.race` does not cancel losing work, and `Promise.all` rejection does not cancel siblings. Connect cancellation to the underlying operation and observe every outcome; never substitute a timeout wrapper for cleanup/ownership.
- In Effect-owned code, use its concurrency/error/resource model. At an external callback boundary, route failures to an explicit outcome or handler; do not use empty catches, successful defaults, or detached work to silence diagnostics.
- Avoid type puzzles, blanket immutability copies, unnecessary abstraction, and style-only renames. Protect observable behavior, runtime size, and compiler responsiveness.

### Tool policy

- Use pnpm exclusively. Keep `package.json` as the manifest and `pnpm-lock.yaml` as the only lockfile. Use `pnpm add`, `pnpm remove`, `pnpm update`, and `pnpm install`; use neither npm/npx, Yarn, Bun, nor Deno commands.
- Node owns execution; package scripts own tasks. Invoke tasks with `pnpm run <script>` and local binaries with `pnpm exec`. Keep `dev`, `build`, `lint`, `typecheck`, `test`, `test:browser`, and `check` only where they serve the project. Make `check` a fast local gate.

Do not add abstractions without a responsibility or mechanically rewrite interfaces, classes, or enums. Do not install, configure, or run formatters, including check-only, editor, hook, or aggregate runs; run the permitted constituent checks instead. Do not stand in for a formatter with import-sorting lints or manual reflow. Keep local layout and correctness lints; avoid blanket pedantic or style groups and forced verbosity. A refactor instruction does not authorize deploying.

Select correctness-focused lint rules for unsafe value propagation, floating/misused promises, unjustified assertions, and exhaustive state handling. Check actual installed rule/plugin support; do not equate a similarly named rule with identical semantics or enable every rule for strictness. Avoid blanket pedantic/style groups, formatting/import-order rules, mandatory documentation, and rules that force redundant annotations, wrappers, or verbosity. Review selected lint fixes rather than running blanket autofixes. Where coverage cannot be preserved, repair the pattern or report the specific migration blocker instead of silently dropping a correctness check.

### Libraries and platform facilities

Use Effect for effectful services, failures, Schema, resource scope, concurrency, retries, config, and substantial HTTP/RPC boundaries. Use Solid for reactivity and UI. Prefer their existing capabilities to an extra validation library, state manager, fetch wrapper, or retry layer with the same responsibility.

Prefer fetch, URL, Streams, AbortSignal, structuredClone, Web Crypto, and platform ESM where they satisfy the real contract. Replace a utility package only after accounting for behavior it supplies, such as cancellation, streaming, encoding, or retries. Pure helpers need neither a library nor an Effect wrapper.

Prefer native CSS and progressive enhancement: nesting, layers, container queries, anchor positioning, View Transitions, dialog, and popover as supported by the product's targets. Do not add CSS-in-JS; keep Tailwind only when it provides a concrete benefit. Preserve accessibility and browser compatibility while simplifying.

### Tests

Use [Vitest 5](https://vitest.dev/guide/migration/) for existing pure logic, Node server, and CLI tests. Migrate Jest/ts-jest/Babel-Jest in scope, preserving assertions and test isolation. Check changed mock defaults and inherited project configuration; duplicate setup/plugins can change behavior.

For shared-toolchain alignment, preserve existing Node test suites and project-specific build/test configuration. Align Vitest and its browser provider together, and Playwright with `@playwright/test` wherever both are used. Keep Cloudflare SDK, Miniflare, and workerd as a separately validated compatibility group. Do not add a shared tooling package merely to distribute version pins, or introduce Solid/Effect into a project solely to align tools.

Use [Vitest Browser Mode](https://vitest.dev/guide/browser/) with `@vitest/browser-playwright`, its `playwright()` provider, and configured browser instances for DOM, layout, focus, forms, and navigation. Current browser APIs come from `vitest/browser`; await interactions and retrying element assertions. Keep the Solid 2 plugin even when a testing example still shows `vite-plugin-solid`.

Keep Playwright directly for existing full journeys. Use Effect test Layers and compatible `@effect/vitest` for Effect behavior. Avoid global patching, duplicated test layers, or replacing real-browser coverage with a DOM emulator. Run focused existing checks by default unless explicitly opted out; follow the project's test policy. Add tests only for uncovered observable contracts or invariants, not merely because code moved. An authorized bug fix needs a failing reproducer followed by a passing result.

### Verify

Use `pnpm run` for scripts and `pnpm exec` for binaries. Keep an independent `tsrs --noEmit` check for the intended configs, plus applicable Oxlint checks and tests; Node stripping and Vite compilation do not prove type safety. Verify actual file and config discovery, and separate baseline failures from regressions.

Check the risks touched: boundary/omission semantics, exhaustive states, failures, cancellation/finalizers, reactivity, request isolation, and exports/declarations. Do not make checks green with weaker types or schemas, fabricated guards, broad suppressions, or excluded code; a specific false positive may justify a narrow exception.

For UI changes, exercise affected behavior in a real browser. For changed SSR/routes, cover production serving and nested navigation. For dependency changes, verify a frozen install; for build changes, inspect output for obsolete frameworks and server-only imports/secrets. Use relevant existing performance/size gates; measure performance claims.

## Adoption

Apply these only when bringing a whole repository up to this standard with `/standardize`, not at the completion gate.

### Chosen stack

Keep these decisions: pnpm owns packages; Node.js owns execution; tsrs owns type checking; Oxlint owns linting and uses tsrs-lint from that same `tsrs` package for type-aware rules; Vite owns frontend compilation; Solid owns UI reactivity; Effect owns I/O and typed failures; Vitest and Playwright own tests. Pure computation stays ordinary TypeScript. Apply only relevant layers: a server needs no Solid, a library no application server.

Target these majors: TypeScript 7, Vite 8, Solid 2, Effect 4, and Vitest 5. For participating fleet repositories, use Stuff's `fleet/policy/typescript-tools.toml` for Node/pnpm and `fleet/policy/frontend-toolchain.toml` for shared frontend package pins. Resolve proposed upgrades from registries and validate the coupled set before updating that authority and its consumers. Outside that baseline, use latest stable Node.js and pnpm when migrating. Solid 2's release-candidate channel and tsrs's prerelease channel are intentional choices while they remain prerelease. Do not silently downgrade the stack, switch to other prereleases, or reinterpret latest stable as latest LTS.

For version-sensitive work, use installed declarations/exports and official versioned guidance. Check releases before changing pins; unversioned examples may target another major. If upstream is unavailable, use installed evidence and identify uncertainty. Do not invent APIs or upgrade blindly.

This carries the existing stack decisions into the refactoring workflow. Apply only layers needed by the product. Tool facts were checked on 2026-11-11; resolve exact releases, peer compatibility, and version-specific APIs again when changing dependencies. Stable language rules do not require a package upgrade on every invocation.

### Migration passes

When in scope, migrate packages and commands using the stack reference. Replace each old responsibility with its new owner before deleting the old implementation. Do not retain duplicate frameworks, validators, or orchestration without an actual compatibility need.

### Package and runtime ownership

- Pin the verified pnpm version in project metadata. Declare dependencies in the package that imports them; repair phantom dependencies rather than enabling hoisting. Add workspace structure only when needed.
- Follow current [pnpm configuration](https://pnpm.io/configuring): non-auth settings belong in `pnpm-workspace.yaml` where applicable, including in a single-package project. Do not retain obsolete `package.json#pnpm` or non-auth `.npmrc` settings. Keep credentials outside committed configuration.
- For participating fleet repositories, pin Node.js and pnpm from Stuff's `fleet/policy/typescript-tools.toml`; pin shared frontend dependencies from `fleet/policy/frontend-toolchain.toml`. These files own versions; this standard owns responsibilities and migration guidance. Outside the baseline, use latest non-prerelease [Node.js](https://nodejs.org/en/about/previous-releases) for an in-scope runtime migration. Pin the runtime reproducibly with the project's mechanism.
- Use native ESM, explicit package boundaries, and Web/Node built-ins where they fit. Preserve actual deployment/browser requirements during migrations. Native Node type stripping is not a build pipeline for Solid TSX or published libraries.

### Compiler, lint, and build

| Owner | Direction |
| --- | --- |
| TypeScript 7 | [`tsrs`](https://github.com/oxc-project/tsrs) is the type checker, a Rust port of TypeScript 7. Run `pnpm exec tsrs --noEmit --fast`. Keep strict, environment-correct configs and fix removed TS6/7 options instead of suppressing them. |
| Oxlint and tsrs-lint | Oxlint owns lint configuration and invocation; `tsrs-lint` from the same `tsrs` package owns type-aware analysis. Use Oxlint 1.92 or newer and tsrs 0.23 or newer, with the existing JSON-config preference. Remove direct `oxlint-tsgolint` dependencies. Verify an enabled type-aware rule actually reports a violation through [`tsrs-lint`](https://github.com/oxc-project/tsrs#lint-and-type-check-in-one-run). Confirm supported rules and framework coverage before retiring ESLint. |
| Typecheck gate | Keep a separate `pnpm exec tsrs --noEmit --fast`, adapted for project references and declaration builds. Oxlint can report type errors with `--type-check`, but that run must not be the only compiler gate. |
| Vite 8 | Use [Vite directly](https://vite.dev/blog/announcing-vite8) with Rolldown/Oxc and the Solid 2 plugin. Remove parallel Webpack/Rollup/esbuild/Babel plumbing after mapping each responsibility. No Vite+/`vp`. |
| Formatting | Do not install, configure, or run Prettier, Oxfmt, or another formatter, including check-only and indirect runs. Inspect aggregate scripts/hooks and run only permitted checks. Remove obsolete formatter configuration in an in-scope stack migration. |

Follow [Vite's migration guide](https://vite.dev/guide/migration) for dependency optimization, transforms, plugin APIs, and targets. Vite compiles TypeScript without type-checking. A development server passing does not prove production output, server externalization, or library declarations are correct.

### Migration sequence and retirement

Inspect entrypoints, packages, routes, network/persistence, existing tests, deployment, and CI before changing their owners. In an in-scope full migration:

1. Establish pnpm and Node ownership, metadata pins, and canonical local scripts.
2. Move to strict tsrs (TypeScript 7) and environment-correct ESM; repair all diagnostics.
3. Establish Oxlint with tsrs-lint and Vite 8 with confirmed rule/plugin coverage.
4. When a UI migration is authorized, port applicable UI to Solid 2; select application routing and SSR only from actual product requirements. Toolchain alignment alone preserves the existing UI framework and rendering model.
5. Put meaningful I/O/failure/resource boundaries under Effect 4 without wrapping pure code.
6. Replace redundant utility layers and migrate existing tests.
7. Remove dead code, packages, configs, imports, commands, and extra lockfiles; verify the real changed paths.

Remove obsolete React/Next and their state/router/data layers unless a supported integration requires them; remove duplicated Axios/Express/validation machinery after its responsibilities are covered. Trace routes, cookies/auth, middleware, caching, streaming, build/deployment adapters, and public consumers before retiring a framework: matching rendered output alone does not establish parity. Retire obsolete build/test/lint plumbing once replacements are proven; remove formatter remnants without running them. A transitive implementation dependency is not an obsolete user-owned tool: do not purge every lockfile occurrence.

Remove old Deno configs, lockfiles, tasks, imports, and `Deno.*` calls in a runtime migration, along with obsolete CommonJS glue, Node bootstraps, and tsconfig workarounds. Do not leave two frameworks or runtimes configured just as an escape hatch. Keep genuine consumer compatibility explicit.

If no agent instructions exist, add a terse `AGENTS.md` describing these owners and the actual canonical commands. Do not overwrite existing policy or add a generic manifesto. Avoid reintroducing discarded stacks through copied examples.

Do not edit CI unless asked. When CI is in scope, mirror local commands with `pnpm install --frozen-lockfile`; never regenerate the lockfile there or rely on a warm cache. Verify metadata changes with a frozen install, browser-facing changes in a real browser, SSR through production serving/nested navigation, and changed build output for old frameworks or server-only code.

### Inspect

Read active instructions, working changes, package manifests/lockfile, runtime targets, tsconfigs, entrypoints, exports, callers, schemas, routes, tests, build/deploy configuration, and available verification. Preserve unrelated edits.

### Passes

1. Fix the model: remove unjustified `any` and broad assertions, decode external values once, represent correlated states with discriminated unions, and make inference and public contracts deliberate.
2. Simplify implementation: remove duplicate state/validation, needless generics, wrappers, inheritance, and allocations where the real callers permit it. Use direct functions, precise names, small cohesive modules, and explicit runtime/type dependencies.
3. Make effects owned: typed expected failures, scoped resources, bounded concurrency, cancellation propagation, and one composed runtime at the appropriate application lifetime. Avoid hidden runners or work that outlives its owner.
4. Write native Solid: tracked props and derivations, two-phase effects, native async boundaries, teardown, and isolated request state. Keep the Solid/Effect seam explicit.
5. Update affected callers, public documentation, and existing tests together. Complete the requested scope, not only the first easy file.

The migration passes above run as step 5 when a stack migration is in scope.

**Report:** stack changes and removed dependencies or layers; source and version uncertainty.
