---
name: refactor-ts
description: "Refactor TypeScript for the chosen Node.js, pnpm, TypeScript, Solid, Effect, Vite, Oxlint, and Vitest stack. Use only when explicitly requested by name or for this stack's refactoring or migration workflow."
disable-model-invocation: true
metadata:
  opencode/slash: "true"
  opencode/autoinvoke: "false"
---

# Refactor TypeScript

Refactor code and applicable tooling for the chosen stack. Improve domain modeling, boundaries, reactivity, failures, and resource ownership; upgrades or lint alone do not finish actionable work. Preserve behavior and public contracts unless their change is authorized. A justified no-op is valid; make no edits to look busy.

Use the requested paths/packages; an unqualified invocation covers the current repository's first-party TypeScript. A whole-codebase invocation includes migration of applicable stack layers. A narrow code refactor does not authorize an unrelated framework or runtime migration. Exclude vendored code and generated outputs; change their source only if in scope.

## Chosen stack and source of truth

Keep these decisions: pnpm owns packages; Node.js owns execution; TypeScript owns static checking; Oxlint owns linting; Vite owns frontend compilation; Solid owns UI reactivity; Effect owns I/O and typed failures; Vitest and Playwright own tests. Pure computation stays ordinary TypeScript. Apply only relevant layers: a server needs no Solid, a library no application server.

Target these majors: TypeScript 7, Vite 8, Solid 2, Effect 4, and Vitest 5. Use latest stable Node.js and pnpm when migrating, and resolve exact versions from the registry, not from memory. Solid 2's release-candidate channel is an intentional choice while it remains prerelease. Do not silently downgrade the stack, switch to other prereleases, or reinterpret latest stable as latest LTS.

Read the relevant references before editing:

- [TypeScript design](references/typescript.md): always; type contracts, inference, modules, boundaries, and async correctness.
- [Stack and migration](references/stack.md): package, runtime, build, lint, or test-tooling changes.
- [Effect](references/effect.md): effectful code, services, failures, resources, and runtime integration.
- [Solid](references/solid.md): components, reactive state, async UI, SSR, and the Solid/Effect boundary.

For version-sensitive work, use installed declarations/exports and official versioned guidance. Check releases before changing pins; unversioned examples may target another major. If upstream is unavailable, use installed evidence and identify uncertainty. Do not invent APIs or upgrade blindly.

## Inspect and decide

Read active instructions, working changes, package manifests/lockfile, runtime targets, tsconfigs, entrypoints, exports, callers, schemas, routes, tests, build/deploy configuration, and available verification. Preserve unrelated edits.

Identify application versus published-library boundaries and browser, server, worker, and test environments. Trace actual data and resource flows: unknown input to decoded value, service to runner, reactive source to UI, acquisition to release. Establish focused baseline results or record unavailable checks.

For each batch, identify its concrete benefit, preserved invariant, and smallest regression check. Preserve wire formats, property presence, public imports and types, failures and status, initialization, SSR, cancellation, and performance. Stronger validation, changed defaults, and new failure cases are contract changes. Fix incidental bugs only within authorized behavior; otherwise report them and continue.

## Refactor in coherent passes

1. Fix the model: remove unjustified `any` and broad assertions, decode external values once, represent correlated states with discriminated unions, and make inference and public contracts deliberate.
2. Simplify implementation: remove duplicate state/validation, needless generics, wrappers, inheritance, and allocations where the real callers permit it. Use direct functions, precise names, small cohesive modules, and explicit runtime/type dependencies.
3. Make effects owned: typed expected failures, scoped resources, bounded concurrency, cancellation propagation, and one composed runtime at the appropriate application lifetime. Avoid hidden runners or work that outlives its owner.
4. Write native Solid: tracked props and derivations, two-phase effects, native async boundaries, teardown, and isolated request state. Keep the Solid/Effect seam explicit.
5. When in scope, migrate packages and commands using the stack reference. Replace each old responsibility with its new owner before deleting the old implementation. Do not retain duplicate frameworks, validators, or orchestration without an actual compatibility need.
6. Update affected callers, public documentation, and existing tests together. Complete the requested scope, not only the first easy file.

Do not add abstractions without a responsibility or mechanically rewrite interfaces, classes, or enums. Do not install, configure, or run formatters, including check-only, editor, hook, or aggregate runs; run the permitted constituent checks instead. Do not stand in for a formatter with import-sorting lints or manual reflow. Keep local layout and correctness lints; avoid blanket pedantic or style groups and forced verbosity. A refactor instruction does not authorize deploying.

## Verify and finish

Use `pnpm run` for scripts and `pnpm exec` for binaries. Keep an independent compiler check for the intended configs, plus applicable Oxlint checks and tests; Node stripping and Vite compilation do not prove type safety. Verify actual file and config discovery, and separate baseline failures from regressions.

Check the risks touched: boundary/omission semantics, exhaustive states, failures, cancellation/finalizers, reactivity, request isolation, and exports/declarations. Do not make checks green with weaker types or schemas, fabricated guards, broad suppressions, or excluded code; a specific false positive may justify a narrow exception.

For UI changes, exercise affected behavior in a real browser. For changed SSR/routes, cover production serving and nested navigation. For dependency changes, verify a frozen install; for build changes, inspect output for obsolete frameworks and server-only imports/secrets. Use relevant existing performance/size gates; measure performance claims.

Review the final diff and rescan for obsolete code, duplicated ownership, accidental contracts, and churn. Stale checks, empty test selections, and excluded code are not passes. State any missing proof as a specific gap.

**The test:** the compiler, Oxlint, and tests pass on the final diff, no obsolete layer or duplicated ownership remains, and behavior and public contracts are preserved unless a change was authorized.

**Report:** code and stack changes with representative symbols; removed dependencies/layers; contracts preserved or intentionally changed; justified exceptions and remaining blockers; source/version uncertainty; checks run, results, preexisting failures, and checks not run.
