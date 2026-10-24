---
name: refactor-ts
description: "Refactor TypeScript for the chosen Node.js, pnpm, TypeScript, Solid, Effect, Vite, Oxlint, and Vitest stack. Use only when explicitly requested by name or for this stack's refactoring or migration workflow."
disable-model-invocation: true
metadata:
  opencode/slash: "true"
  opencode/autoinvoke: "false"
---

# Refactor TypeScript

Refactor code and applicable tooling for the chosen stack. Improve domain modeling, boundaries, reactivity, failures, and resource ownership; upgrades or lint alone do not finish actionable work. Preserve behavior and public contracts unless their change is authorized. A justified no-op is valid; do not manufacture edits.

Use the requested paths/packages; an unqualified invocation covers the current repository's first-party TypeScript. A whole-codebase invocation includes migration of applicable stack layers. A narrow code refactor does not authorize an unrelated framework or runtime migration. Exclude vendored code and generated outputs; change their source only if in scope.

## Chosen stack and source of truth

Keep these decisions: pnpm owns packages; Node.js owns execution; TypeScript owns static checking; Oxlint owns linting; Vite owns frontend compilation; Solid owns UI reactivity; Effect owns I/O and typed failures; Vitest and Playwright own tests. Pure computation stays ordinary TypeScript. Apply only relevant layers: a server needs no Solid, a library no application server.

The selected generations are TypeScript 7, Vite 8, Solid 2, Effect 4, and Vitest 5. Use latest stable Node.js and pnpm when migrating; resolve and pin compatible releases instead of copying remembered version numbers. Solid 2's release-candidate channel is an intentional choice while it remains prerelease. Do not silently downgrade the stack, switch to other prereleases, or reinterpret latest stable as latest LTS.

Read the relevant references before editing:

- [TypeScript design](references/typescript.md): always; type contracts, inference, modules, boundaries, and async correctness.
- [Stack and migration](references/stack.md): package, runtime, build, lint, or test-tooling changes.
- [Effect](references/effect.md): effectful code, services, failures, resources, and runtime integration.
- [Solid](references/solid.md): components, reactive state, async UI, SSR, and the Solid/Effect boundary.

For version-sensitive work, use installed declarations/exports and official versioned guidance. Check releases before changing pins; unversioned examples may target another major. If upstream is unavailable, use installed evidence and identify uncertainty. Do not invent APIs or upgrade blindly.

## Inspect and decide

Read active instructions, working changes, package manifests/lockfile, runtime targets, tsconfigs, entrypoints, exports, callers, schemas, routes, tests, build/deploy configuration, and available verification. Preserve unrelated edits.

Identify application versus published-library boundaries and browser, server, worker, and test environments. Trace actual data and resource flows: unknown input to decoded value, service to runner, reactive source to UI, acquisition to release. Establish focused baseline results or record unavailable checks.

For each batch, identify its concrete benefit, preserved invariant, and smallest regression check. Preserve wire formats, property presence, public imports/types, failures/status, initialization, SSR, cancellation, and performance. Stronger validation, changed defaults, and new failure cases are contract changes. Fix incidental bugs only within authorized behavior; otherwise report them and continue independent work. Honor local policy.

## Refactor in coherent passes

1. Fix the model: remove unjustified `any` and broad assertions, decode external values once, represent correlated states with discriminated unions, and make inference and public contracts deliberate.
2. Simplify implementation: remove duplicate state/validation, needless generics, wrappers, inheritance, and allocations where the real callers permit it. Use direct functions, precise names, small cohesive modules, and explicit runtime/type dependencies.
3. Make effects owned: typed expected failures, scoped resources, bounded concurrency, cancellation propagation, and one composed runtime at the appropriate application lifetime. Avoid hidden runners or work that outlives its owner.
4. Write native Solid: tracked props and derivations, two-phase effects, native async boundaries, teardown, and isolated request state. Keep the Solid/Effect seam explicit.
5. When in scope, migrate packages and commands using the stack reference. Replace each old responsibility with its new owner before deleting the old implementation. Do not retain duplicate frameworks, validators, or orchestration without an actual compatibility need.
6. Update affected callers, public documentation, and existing tests together. Complete the requested scope, not only the first easy file.

Do not add abstractions without a responsibility or mechanically rewrite interfaces, classes, or enums. Do not install, configure, or run formatters, including check-only, editor, hook, or aggregate runs. Inspect task definitions and run permitted constituent checks. Do not substitute formatting/import-sorting lints or manual reflow. Keep local layout and correctness lints; avoid blanket pedantic/style groups or forced verbosity.

Keep publication, major contract decisions, and CI edits within existing authorization. Do not edit CI unless asked. An instruction to refactor does not itself authorize committing, pushing, or deploying.

## Verify and finish

Run focused verification by default, honoring explicit opt-outs and active instructions. Use `pnpm run` for scripts and `pnpm exec` for binaries. Keep an independent compiler check for the intended configs, plus applicable Oxlint checks and tests; Node stripping and Vite compilation do not prove type safety. Verify actual file/config discovery. Reuse results only while relevant code, dependencies, configuration, and environment remain unchanged; separate baseline failures from regressions.

Check the risks touched: boundary/omission semantics, exhaustive states, failures, cancellation/finalizers, reactivity, request isolation, and exports/declarations. Add tests only for an uncovered observable contract or invariant, never code shape. An authorized bug fix needs a failing reproducer followed by a passing result. Do not make checks green with weaker types/schemas/tests, fabricated guards, broad suppressions, or excluded code; a specific false positive may justify a narrow exception.

For UI changes, exercise affected behavior in a real browser. For changed SSR/routes, cover production serving and nested navigation. For dependency changes, verify a frozen install; for build changes, inspect output for obsolete frameworks and server-only imports/secrets. Use relevant existing performance/size gates; measure performance claims.

Review the final diff and rescan for obsolete code, duplicated ownership, accidental contracts, and churn. Bind evidence to final changes: stale checks, empty test selections, or excluded code are not passes. Missing required proof means unverified/partial, not complete. Report the precise gap without compatibility shims or silently lost coverage.

**Report:** code and stack changes with representative symbols; removed dependencies/layers; contracts preserved or intentionally changed; justified exceptions and remaining blockers; source/version uncertainty; checks run, results, preexisting failures, and checks not run.
