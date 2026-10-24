# Google Rust guide checklist

Adapted and condensed from Google's [Rust Style Guide](https://google.github.io/styleguide/rustguide.html), licensed under [CC BY 3.0](https://creativecommons.org/licenses/by/3.0/); see [upstream licensing](https://github.com/google/styleguide/blob/gh-pages/README.md#licensing). Reviewed 2026-10-24 against [this source revision](https://github.com/google/styleguide/blob/c775c0c2f73c110613243520c001577cdbc0034d/rustguide.md). This adaptation groups rules and exceptions for refactoring; it does not reproduce the guide's examples. Links below identify the original rules. The compatibility and verification workflow in the parent skill is additional refactoring guidance.

## Contents

- [Applicability](#applicability)
- [Modules and imports](#modules-and-imports)
- [Formatting](#formatting)
- [Ownership and function boundaries](#ownership-and-function-boundaries)
- [Errors and control flow](#errors-and-control-flow)
- [Types and traits](#types-and-traits)
- [Names and accessors](#names-and-accessors)
- [Public API contracts](#public-api-contracts)
- [Documentation and unsafe code](#documentation-and-unsafe-code)
- [Concurrency, macros, and initialization](#concurrency-macros-and-initialization)
- [Implementation clarity](#implementation-clarity)

## Applicability

Follow [public Rust style and API guidance](https://google.github.io/styleguide/rustguide.html#public-rules) where Google's guide does not override it. Apply [API design in context](https://google.github.io/styleguide/rustguide.html#api-design-context): reusable libraries need broadly useful contracts; application code should prioritize simplicity and immediate needs. Do not infer a mandatory architecture from a preference.

Keep platform rules scoped:

| Codebase | Rules that belong there |
| --- | --- |
| Chromium | [Small crates](https://google.github.io/styleguide/rustguide.html#small-crates), [flat crate source layout](https://google.github.io/styleguide/rustguide.html#structure), [`chromium::import!`](https://google.github.io/styleguide/rustguide.html#import-macro), [no async/await](https://google.github.io/styleguide/rustguide.html#async-await-chrome), and [sequences instead of standard-library thread creation](https://google.github.io/styleguide/rustguide.html#std-thread). |
| Fuchsia | [`fuchsia_sync::Mutex`](https://google.github.io/styleguide/rustguide.html#fuchsia-mutex). |
| Each platform | Its own [test framework](https://google.github.io/styleguide/rustguide.html#test-framework) and [unstable-feature exceptions](https://google.github.io/styleguide/rustguide.html#unstable-features). Keep an ordinary Cargo project's existing layout, runtime, and test framework. |

## Modules and imports

- Name [leaf modules/files](https://google.github.io/styleguide/rustguide.html#userdefined-item) after their primary user-defined item when they have one. Keep [non-leaf modules](https://google.github.io/styleguide/rustguide.html#non-leaf-modules) mostly declarations and re-exports; a little coordinating implementation is allowed. Inline tests and binding modules do not make an otherwise leaf module non-leaf.
- Avoid [glob imports](https://google.github.io/styleguide/rustguide.html#glob-imports) and defining new preludes. Exceptions: `super::*` in inline modules, enum variants in enum-focused functions, non-leaf public re-exports, and private merging of C++ namespaces. An established third-party prelude may be accepted deliberately.
- Import from [one module per `use`](https://google.github.io/styleguide/rustguide.html#use-statement): group sibling items, not nested paths in braces. Prefer [function-local trait imports](https://google.github.io/styleguide/rustguide.html#prefer-local-trait-imports) unless methods are used throughout the file.
- [Qualify imported free functions](https://google.github.io/styleguide/rustguide.html#toplevel-functions) with their module; exceptions include sufficiently disambiguated names, namespace collisions, and Chromium's small first-party crates. [Import type names directly](https://google.github.io/styleguide/rustguide.html#type-names), allowing qualification/aliases for collisions, large related type groups, macros/generated code, or unwieldy import lists.

## Formatting

- This workflow overrides Google's [formatting-tool recommendation](https://google.github.io/styleguide/rustguide.html#formatting-other): do not install, configure, or run formatters, including `rustfmt`/`cargo fmt`, check-only runs, or indirect invocation through another command. Do not enable formatting lints as a substitute.
- Keep readable local layout while making substantive changes. Do not reflow untouched code, enforce column/hexadecimal preferences mechanically, or add/remove [`rustfmt::skip`](https://google.github.io/styleguide/rustguide.html#formatting-optout) merely for this pass. Preserve meaningful manual alignment and generated code.

## Ownership and function boundaries

- Prefer [unique ownership and borrowing](https://google.github.io/styleguide/rustguide.html#avoid-rc-arc). Keep `Rc`/`Arc` when replacing them makes ownership unreasonably complex. Avoid [needless deep copies](https://google.github.io/styleguide/rustguide.html#prefer-borrows), but retain pragmatic cloning when borrowing becomes too complex. Cloning an `Rc`/`Arc` is not a deep copy.
- Use [flexible immutable borrows](https://google.github.io/styleguide/rustguide.html#flexible-references): `&T` rather than `&Box<T>`, `&[T]` rather than `&Vec<T>`, `&str` rather than `&String`, and `Option<&T>` rather than `&Option<T>`. Keep specialized representations such as ropes when needed.
- Prefer [iterator returns](https://google.github.io/styleguide/rustguide.html#return-iterators) for reusable APIs when useful. Keep vectors when already owned/naturally constructed, required by most callers, needed for indexing, explicitly the product, or simpler for the application.
- Reusable APIs that only iterate should accept [iterators or `IntoIterator`](https://google.github.io/styleguide/rustguide.html#accept-iterators). Application slices are fine. Consider [`impl Into<T>`](https://google.github.io/styleguide/rustguide.html#accepting-into) only when library call-site ergonomics justify generic complexity and code size; application APIs should almost never need it.
- Replace an [ambiguous boolean parameter](https://google.github.io/styleguide/rustguide.html#enum-vs-bool) with an enum. Keep self-explanatory booleans; the guide also permits explanatory argument comments.

## Errors and control flow

- Match the [error contract](https://google.github.io/styleguide/rustguide.html#reporting-errors): `Option` for anticipated absence/simple failure needing no detail, `Result` for recoverable failures needing context, and panic for bugs or violated invariants. Honor stricter panic policies. Tests and developer-facing binaries have exceptions.
- Replace [check-then-unwrap](https://google.github.io/styleguide/rustguide.html#dont-check-then-unwrap) with matching. When an invariant panic remains necessary, prefer [`expect`](https://google.github.io/styleguide/rustguide.html#expect-over-unwrap) with the reason. This does not mean converting recoverable failures into panics.
- In matches on [non-exhaustive enums](https://google.github.io/styleguide/rustguide.html#non-exhaustive-enum-matching), account explicitly for known variants, including ignored ones alongside a wildcard for future variants. Use `if let`/`let else` when interested in only a few variants; a clearer `match` is an allowed exception.
- Add useful [assertion context](https://google.github.io/styleguide/rustguide.html#assertion-context), especially for user-visible failures, relevant values, and distinguishing caller misuse from implementation bugs. Do not merely repeat the assertion condition.

## Types and traits

- Use [newtypes](https://google.github.io/styleguide/rustguide.html#newtypes-vs-type-aliases) for meaningful semantic distinctions, a dedicated API, representation flexibility, or prevention of accidental interchange. Prefer [named fields](https://google.github.io/styleguide/rustguide.html#prefer-named-fields) to ambiguous tuples; newtype tuple structs and clear local tuples are fine.
- Anticipate needs in low-level libraries; add application [trait implementations](https://google.github.io/styleguide/rustguide.html#traits-yagni) as needed. Use [standard traits](https://google.github.io/styleguide/rustguide.html#known-traits) when behavior matches their contracts; a companion inherent method may help discovery.
- Prefer [derives](https://google.github.io/styleguide/rustguide.html#derive) where they express the intended implementation. Check custom semantics and generated bounds before replacing handwritten implementations.
- Prefer [generic parameters to `dyn Trait`](https://google.github.io/styleguide/rustguide.html#generics-vs-dyn-trait) in library inputs, with code-size exceptions. Define [traits](https://google.github.io/styleguide/rustguide.html#trait-vs-inherent-impl) for generic programming, opaque/dynamic dispatch, or extension methods; use inherent implementations otherwise, not organizational traits.
- Name [extension traits](https://google.github.io/styleguide/rustguide.html#extension-traits) with `Ext`. Normally the original type's team should own them; widely useful foundational extensions are an exception. An input trait implemented for foreign types is a different use case.
- Consider [common traits](https://google.github.io/styleguide/rustguide.html#important-traits) supported by public fields. Implement `Copy` when the type can reasonably stay copyable, including error types where possible; consider `Clone` for non-resource types. Provide `Default` for a parameterless `new()` or meaningful default state.
- For comparisons, prefer `PartialEq`/`PartialOrd` unless stronger `Eq`/`Ord` contracts hold. Anticipated map keys need `Hash` and `Eq`; add `Ord` when meaningful. Keep equality, hashing, and ordering laws consistent.
- Give important [`From` construction paths](https://google.github.io/styleguide/rustguide.html#from-impls) discoverable inherent constructors. Public-field [options bags](https://google.github.io/styleguide/rustguide.html#options-should-implement-default) should implement `Default`.

## Names and accessors

- Follow [conversion naming](https://google.github.io/styleguide/rustguide.html#naming-methods) and receiver conventions for `as_`, `to_`, and `into_`. Use [`new`/`new_with_foo`](https://google.github.io/styleguide/rustguide.html#naming-initialization-functions), `try_new` for fallible construction, and `from_foo` with the appropriate `From` implementation for value conversions.
- Give [type lifetimes](https://google.github.io/styleguide/rustguide.html#lifetimes) descriptive names. Anonymous lifetimes, broadly generic abstractions, and one or two local input/output or higher-ranked lifetimes may stay short.
- Use short, meaningful [generic names](https://google.github.io/styleguide/rustguide.html#generic-parameters), often reflecting a trait bound; `T`/`U` are fine for broadly generic types. Avoid obscure [abbreviations](https://google.github.io/styleguide/rustguide.html#avoid-abbreviations), allowing familiar ones.
- Follow [accessor names](https://google.github.io/styleguide/rustguide.html#getters-and-setters): `foo`, `foo_mut`, `take_foo`, `set_foo`, and `replace_foo` according to borrow/move/replace semantics.
- Consider [closure accessors](https://google.github.io/styleguide/rustguide.html#closure-accessors), `with_foo`/`with_mut_foo`, when they hide an interior-mutability guard or allow required post-mutation validation. Preserve lock/borrow scope and forward the closure's return value when useful.

## Public API contracts

- Provide [`is_empty` with `len`](https://google.github.io/styleguide/rustguide.html#expected-api-sets). Treat foreign [`doc(hidden)` items](https://google.github.io/styleguide/rustguide.html#doc-hidden) as private.
- Make a public function [`const`](https://google.github.io/styleguide/rustguide.html#const-functions) only with a durable compatibility commitment or a willingness to migrate clients. Use [operator overloads](https://google.github.io/styleguide/rustguide.html#operator-overloads) for mathematical/logical semantics.
- Use [`non_exhaustive` enums](https://google.github.io/styleguide/rustguide.html#non-exhaustive-enums) and [public-field structs](https://google.github.io/styleguide/rustguide.html#non-exhaustive-structs) for evolving APIs used across team boundaries. Exceptions: fixed models, coordinated caller migration, small/internal usage, and structs intended for functional record update. Adding the attribute to an existing published type can itself break callers; it is not a mechanical fix.
- Use [`must_use` on functions](https://google.github.io/styleguide/rustguide.html#must-use-on-functions) when discarding a pure/critical result misuses the API. Use it on [error-like or lazy types](https://google.github.io/styleguide/rustguide.html#must-use-on-types) when appropriate. Avoid redundant function annotations when the returned type already has it.

## Documentation and unsafe code

- Write useful [public API documentation](https://google.github.io/styleguide/rustguide.html#writing-doc), covering malformed-input panics and unsafe invariants, with enough examples to teach use. Use `///` for items, `//!` for modules/crates, Markdown, capitalization, and punctuation. Keep implementation-only remarks out of rustdoc.
- Omit redundant narration, language tutorials, and self-evident variant descriptions. Prefer directly readable doc comments to generated documentation; honor stricter local comment rules.
- Prefer [safe implementations](https://google.github.io/styleguide/rustguide.html#unsafe). Encapsulate necessary unsafe in a sound abstraction and separate it from business logic. A low-dependency crate is an ideal, not a reason to split every unsafe block into a new crate.
- Explain each unsafe operation's correctness with a `SAFETY:` comment and justify why safe code cannot provide the required functionality. A performance justification requires benchmarks. Never invent a safety argument to make a style pass look complete.

## Concurrency, macros, and initialization

- Do not extract the protected contents of a [poisoned mutex](https://google.github.io/styleguide/rustguide.html#poison). Existing recovery is a behavioral issue to understand before changing.
- Avoid [`panic::catch_unwind`](https://google.github.io/styleguide/rustguide.html#catch-unwind) in first-party code. Its narrow exception is defense in depth in code already avoiding panics, with no correctness property relying on recovery, and where `panic=unwind` is possible. Do not remove an existing boundary without checking its contract.
- Prefer [ordinary Rust facilities](https://google.github.io/styleguide/rustguide.html#macros), then `macro_rules!`, then other generation, then procedural macros. Weigh readability, tooling, and maintenance costs; this is not a ban on useful standard macros or derives.
- Avoid executable [initialization before `main`](https://google.github.io/styleguide/rustguide.html#global-initialization), such as `ctor`. Preserve required initialization order when restructuring.
- Avoid [unstable features](https://google.github.io/styleguide/rustguide.html#unstable-features), subject to the guide's platform-specific exceptions. Existing pinned toolchains and required features need an explicit migration decision rather than silent removal.

## Implementation clarity

- Add enough [type annotations](https://google.github.io/styleguide/rustguide.html#type-inference) to explain generic conversions and complex iterator results. Prefer annotating bindings to unnecessary turbofish syntax; use inference where clear.
- Prefer direct loops over [long/stateful combinator chains](https://google.github.io/styleguide/rustguide.html#combinator-chains) and usually over `for_each`. Bind a combinator chain to a meaningful name before using it in a `for` header. Keep short, expressive combinators such as `any`.
- Prefer [`format!`/`write!`](https://google.github.io/styleguide/rustguide.html#prefer-format-or-write) for combining more than two strings or substituting into a literal template. Do not interpret this as a reason to replace every efficient buffer append.
