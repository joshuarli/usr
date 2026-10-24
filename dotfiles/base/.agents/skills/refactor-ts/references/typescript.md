# TypeScript design

Use the [Handbook](https://www.typescriptlang.org/docs/handbook/), [TSConfig reference](https://www.typescriptlang.org/tsconfig/), and documentation matching the installed compiler for language semantics. Use [Effective TypeScript, second edition](https://effectivetypescript.com/2024/05/21/second-edition/) for design judgment, not release-specific APIs. [typescript-eslint rule explanations](https://typescript-eslint.io/rules/) are useful bug-pattern references; implement applicable checks with Oxlint, not a second linter.

The [Google guide](https://google.github.io/styleguide/tsguide.html) is a selective secondary source: its internal environment, TSLint examples, and blanket private-field prohibition do not govern this stack. [Microsoft's coding guidelines](https://github.com/microsoft/TypeScript/wiki/Coding-guidelines) describe the compiler repository, not the whole ecosystem. Follow current semantics and concrete project constraints rather than importing either guide wholesale.

## Values, trust, and states

- Treat untrusted JSON, configuration, request parameters, persisted data, and third-party output as `unknown`. Decode with the canonical Effect Schema at the real trust/serialization boundary; derive domain types instead of maintaining a validator and interface independently. Keep encoded and decoded representations distinct.
- Do not invent `parseJson<T>(): T` or fetch helpers that promise a caller-selected type without a decoder. [Assertions](https://www.typescriptlang.org/docs/handbook/2/everyday-types.html#type-assertions), non-null assertions, and `satisfies` perform no runtime validation. Isolate a genuinely unavoidable assertion at the boundary with evidence; fix the contract instead of spreading `as unknown as`, `any`, or `!`.
- Use [discriminated unions](https://www.typescriptlang.org/docs/handbook/2/narrowing.html#discriminated-unions) for correlated states. Avoid independent loading/success/error booleans and optional payloads that permit impossible combinations. Use exhaustive handling where every variant matters, with a `never` check or the stack's exhaustive match facility. Do not duplicate state already represented by Solid's async primitives.
- Preserve absence, present `undefined`, and `null` as distinct when the contract distinguishes them. Do not replace checks with truthiness when `0`, `false`, or an empty string is valid. Use `??` for missing-value defaults only when both null and undefined should default.
- Use a total `Record<K, V>` for a closed, fully populated key set. For dynamic lookup, represent absence and handle it; a type annotation does not populate a dictionary.
- Introduce brands/refinements only for concrete domain mix-ups or constraints, constructed through validation. Do not brand every string or identifier.

## Inference and API shape

- Infer obvious locals. Give published APIs and service boundaries intentional input/output contracts when they prevent accidental widening or implementation leakage. Keep useful inference inside the implementation.
- Use [`satisfies`](https://www.typescriptlang.org/docs/handbook/release-notes/typescript-4-9.html#the-satisfies-operator) for checked literals/configuration tables when their specific inferred shape matters. Use an annotation when the declared abstraction should be the exposed contract. Inspect contextual inference instead of assuming either form is interchangeable.
- Use `as const` for intentional literals/readonly tuples. [`readonly`](https://www.typescriptlang.org/docs/handbook/2/objects.html#readonly-properties) expresses a static access contract; it neither freezes objects nor eliminates mutable aliases. Accept readonly inputs when mutation is unnecessary, without introducing generic deep-readonly machinery.
- Prefer concrete domain types and small unions. A [generic parameter](https://www.typescriptlang.org/docs/handbook/2/functions.html#guidelines-for-writing-good-generic-functions) must express a useful relationship between values/types. Avoid speculative overloads, return-only generics, and recursive conditional types that make inference or compiler performance worse.
- Preserve valid explicit generic callers and excess-property behavior when simplifying APIs. Type-aware lint findings are leads; a superficially redundant parameter can still affect compatibility.
- Choose [interfaces versus aliases](https://www.typescriptlang.org/docs/handbook/2/everyday-types.html#differences-between-type-aliases-and-interfaces) by the contract: interfaces for object extension/reopening where wanted, aliases for unions and other type expressions. Keep consistent existing choices when either works.
- Prefer literal unions or constant objects for new application tags when sufficient. Before replacing an [enum](https://www.typescriptlang.org/docs/handbook/enums.html#objects-vs-enums), account for runtime values, reverse mappings, serialization, public imports, and consumers. Native Node type stripping imposes additional syntax restrictions.
- Use classes for actual identity, encapsulation, or framework contracts, including Effect services/schema classes. Prefer functions and data otherwise. Native `#private` and TypeScript `private` have different runtime semantics; do not exchange them merely for style.

## Compiler and module boundaries

Use explicit `strict: true`. When tightening a project, adopt these checks with proper repairs, not broad suppressions:

| Check | Repair the model |
| --- | --- |
| [`noUncheckedIndexedAccess`](https://www.typescriptlang.org/tsconfig/noUncheckedIndexedAccess.html) | Handle missing indexed values; prefer iteration or a real invariant to repeated `!`. |
| [`exactOptionalPropertyTypes`](https://www.typescriptlang.org/tsconfig/exactOptionalPropertyTypes.html) | Preserve property-presence semantics; add `undefined` only if actually part of the API. |
| [`noImplicitOverride`](https://www.typescriptlang.org/tsconfig/noImplicitOverride.html) | Make intentional inheritance relationships explicit. |
| [`noUncheckedSideEffectImports`](https://www.typescriptlang.org/tsconfig/noUncheckedSideEffectImports.html) | Use the real asset integration/declarations; do not hide arbitrary missing modules. |
| [`verbatimModuleSyntax`](https://www.typescriptlang.org/tsconfig/verbatimModuleSyntax.html) | Use `import type`/`export type`, retaining deliberate side-effect imports. |

Match [module configuration](https://www.typescriptlang.org/docs/handbook/modules/guides/choosing-compiler-options.html) to execution: bundler-compatible resolution for Vite, NodeNext-compatible resolution for Node, and consumer-compatible emitted code/declarations for libraries. Separate materially different browser, Node, worker, and test environments so one does not accidentally grant another's globals.

Type-only import cleanup can change initialization if the removed import carried a side effect; preserve that side effect explicitly when required. A TypeScript `paths` mapping does not configure the runtime. Check real package exports, aliases, relative extensions, and production entrypoints rather than trusting the development bundler.

For [native Node TypeScript](https://nodejs.org/api/typescript.html), use compatible erasable syntax, explicit type imports, and runtime-resolvable extensions. Node ignores tsconfig and does not type-check, downlevel JavaScript, resolve TS paths, or run TSX. Do not use the removed `--experimental-transform-types` escape hatch. Vite/Solid handles TSX; published libraries still need their promised distribution format.

## Implementation and asynchronous work

- Use precise domain names, cohesive modules, and direct control flow. Do not add an index/barrel at every directory or create cycles to shorten imports. Keep server-only implementations out of shared/client modules.
- Keep pure helpers ordinary functions. Do not build a service or Effect wrapper merely to compute a deterministic value; move into Effect when failures, dependencies, resources, or execution policy require it.
- Every Promise needs an observer and an owner. [`void promise`](https://typescript-eslint.io/rules/no-floating-promises/#ignorevoid) does not handle rejection. Avoid async `forEach`, Promise-valued conditions, and callbacks whose caller ignores their result.
- Choose sequential execution when order matters and bounded concurrency when independent work can fan out. Preserve ordering, backpressure, timeouts, and cancellation rather than replacing loops with unbounded `Promise.all`.
- In Effect-owned code, use its concurrency/error/resource model. At an external callback boundary, route failures to an explicit outcome or handler; do not use empty catches, successful defaults, or detached work to silence diagnostics.
- Avoid type puzzles, blanket immutability copies, unnecessary abstraction, and style-only renames. Protect observable behavior, runtime size, and compiler responsiveness.
