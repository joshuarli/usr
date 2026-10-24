---
name: refactor-ts
description: "Refactor TypeScript for the chosen Node.js, pnpm, TypeScript, Solid, Effect, Vite, Oxlint, and Vitest stack. Use only when explicitly requested by name or for this stack's refactoring or migration workflow."
disable-model-invocation: true
metadata:
  opencode/slash: "true"
  opencode/autoinvoke: "false"
---

# Refactor TypeScript

Refactor the code and its applicable tooling into a coherent implementation of the chosen stack. Improve domain modeling, boundaries, reactivity, error handling, and resource ownership; a dependency bump or lint-only pass does not finish actionable work. Preserve behavior and public contracts unless their change is already authorized. If the scope already meets the goal, report the evidence without manufacturing edits.

Use the requested paths/packages; an unqualified invocation covers the current repository's first-party TypeScript. A whole-codebase invocation includes migration of applicable stack layers. A narrow code refactor does not authorize an unrelated framework or runtime migration. Exclude vendored code and generated outputs; change their source only if in scope.

## Chosen stack and source of truth

Keep these decisions: pnpm owns packages; Node.js owns execution; TypeScript owns static checking; Oxlint owns linting; Vite owns frontend compilation; Solid owns UI reactivity; Effect owns I/O and typed failures; Vitest and Playwright own tests. Pure computation stays ordinary TypeScript. Apply only relevant layers: a server needs no Solid, a library no application server.

The selected generations are TypeScript 7, Vite 8, Solid 2, Effect 4, and Vitest 5. Use latest stable Node.js and pnpm when migrating; resolve and pin compatible releases instead of copying remembered version numbers. Solid 2's release-candidate channel is an intentional choice while it remains prerelease. Do not silently downgrade the stack, switch to other prereleases, or reinterpret latest stable as latest LTS.

Read the relevant references before editing:

- [TypeScript design](references/typescript.md): always; type contracts, inference, modules, boundaries, and async correctness.
- [Stack and migration](references/stack.md): package, runtime, build, lint, or test-tooling changes.
- [Effect](references/effect.md): effectful code, services, failures, resources, and runtime integration.
- [Solid](references/solid.md): components, reactive state, async UI, SSR, and the Solid/Effect boundary.

These are this stack's prescriptions, synthesized from primary sources, not one vendor's universal style guide. For version-sensitive work, read the installed package's declarations, exports, bundled guidance, and official versioned docs/migration notes. Check current releases before changing pins. Current unversioned examples can still target the wrong major. If upstream access fails, use installed evidence, identify uncertainty, and avoid inventing APIs or upgrading blindly.

## Inspect and decide

Read active instructions, working changes, package manifests/lockfile, runtime targets, tsconfigs, entrypoints, exports, callers, schemas, routes, tests, build/deploy configuration, and available verification. Preserve unrelated edits.

Identify application versus published-library boundaries and browser, server, worker, and test environments. Trace actual data and resource flows: unknown input to decoded value, service to runner, reactive source to UI, acquisition to release. Establish focused baseline results or record unavailable checks.

Keep a lightweight assessment of concrete changes, justified exceptions, and contract conflicts. Preserve wire formats, optional-property presence, public imports/types, error/status behavior, initialization order, route/SSR behavior, cancellation and disposal, and performance constraints. Do not make a published type harder to use merely to satisfy a preference. Honor local policies before generic advice.

## Refactor in coherent passes

1. Fix the model: remove unjustified `any` and broad assertions, decode external values once, represent correlated states with discriminated unions, and make inference and public contracts deliberate.
2. Simplify implementation: remove duplicate state/validation, needless generics, wrappers, inheritance, and allocations where the real callers permit it. Use direct functions, precise names, small cohesive modules, and explicit runtime/type dependencies.
3. Make effects owned: typed expected failures, scoped resources, bounded concurrency, cancellation propagation, and one composed runtime at the appropriate application lifetime. Avoid hidden runners or work that outlives its owner.
4. Write native Solid: tracked props and derivations, two-phase effects, native async boundaries, teardown, and isolated request state. Keep the Solid/Effect seam explicit.
5. When in scope, migrate packages and commands using the stack reference. Replace each old responsibility with its new owner before deleting the old implementation. Do not retain duplicate frameworks, validators, or orchestration without an actual compatibility need.
6. Update affected callers, public documentation, and existing tests together. Complete the requested scope, not only the first easy file.

Do not add abstractions or clever type machinery without a concrete responsibility, or mechanically rewrite interfaces, classes, or enums. Do not install, configure, or run formatters, including check-only runs, editor actions, hooks, and aggregate commands that invoke them. Inspect task definitions and run permitted constituent checks instead. Do not substitute formatting/import-sorting lints or manual reflow. Preserve local layout. Favor correctness lints; avoid blanket pedantic/style groups and rules that force verbosity or redundant annotations.

Keep publication, major contract decisions, and CI edits within existing authorization. Do not edit CI unless asked. An instruction to refactor does not itself authorize committing, pushing, or deploying.

## Verify and finish

Follow active repository verification instructions and reuse existing results. When verification is requested or required by those instructions, use the narrowest existing commands that establish the changed contracts. Run scripts through `pnpm run` and binaries through `pnpm exec`. Keep an independent compiler check for the intended configs, plus applicable Oxlint checks and tests. Node type stripping and Vite compilation do not prove type safety. Separate preexisting failures from regressions.

Check the risks actually touched: boundary/omission semantics, exhaustive states, failures/defects, cancellation/finalizers, reactive updates, SSR/request isolation, and package exports/declarations. Add tests only when the user asks to verify behavior and an observable contract or invariant lacks coverage, never to assert code shape. Respect a verification opt-out and report what it leaves unproven.

For UI changes, exercise affected behavior in a real browser. For SSR, cover production serving and nested navigation. For package/lockfile changes, verify a frozen-lockfile install. For build changes, inspect output for obsolete frameworks, server-only imports, and secrets. Use existing performance/size gates only where the change can affect them.

Review the final diff and rescan for obsolete imports, duplicated ownership, new suppressions, accidental API changes, or unrelated churn. Report a blocked migration precisely; do not hide it behind weakened types, silently lost lint coverage, or compatibility shims.

**Report:** code and stack changes with representative symbols; removed dependencies/layers; contracts preserved or intentionally changed; justified exceptions and remaining blockers; source/version uncertainty; checks run, results, preexisting failures, and checks not run.
