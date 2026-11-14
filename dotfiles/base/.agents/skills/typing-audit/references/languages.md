# Typing audit: language notes

Read the section for the language you are auditing. The rules in [the skill](../SKILL.md) apply in every language; these notes add each checker's specifics.

## Python with ty

Use the project's configured ty command and Python version. Prefer `object` for genuinely unknown values and parse them; use precise `TypedDict`, dataclass, union, or protocol types for known shapes. Model known keyword arguments with explicit parameters or `Unpack[TypedDict]`, and transparent forwarding with `ParamSpec`. Distinguish `NotRequired[T]` from a required `T | None`. Treat `Any`, `cast`, ignores, and annotations fed by `Any` as potential lost checks, including in tests and dependency stubs. Use narrowing and stable local bindings before casts. A `TypeGuard` must check the full promised positive shape; `TypeIs` must classify both branches correctly. A content predicate is not necessarily a type predicate. Retain `Any` where an external API or test double genuinely requires it, with the boundary made clear. Write witnesses as `# ty: ignore[<code>]` on the offending line; the repository sets `unused-ignore-comment` to error, so the test fails once the error disappears.

## TypeScript

Trace `any` through receivers, generics, and assertions; an annotation or `as` does not validate runtime data. Prefer `unknown` at untrusted boundaries, validate the full shape, and return a typed value. Use discriminated unions and exhaustive handling for real variants; distinguish optional properties, `undefined`, and `null` according to runtime and compiler settings. Check that type predicates really establish their claimed shape and that assertion functions do not turn supported input into a new throw. Prefer narrowing and correctly typed producers to `as`, non-null assertions, and suppression directives. Treat generated declarations and external types as claims to verify, not runtime validation. `// @ts-expect-error` accepts any error on the next line, so keep each witness to one expression whose only possible error is the intended one.

## Rust

Trace `Option`, `Result`, enums, conversions, and ownership through producers and consumers. Use variants and validated constructors for actual domain invariants, but retain valid partial states and preserve wire formats. Examine `unwrap`, `expect`, `unreachable!`, unchecked conversions, and `unsafe` assumptions for invariants that callers actually establish; a panic or an unchecked operation is not type evidence. Prefer exhaustive matches, fallible conversions, and precise types to fabricated values or erased errors. Check trait bounds and public signatures against real callers, and avoid adding allocations or changing borrowing and aliasing merely to satisfy a type. Write witnesses as `compile_fail` doctests; stable rustdoc does not check the error code, so keep each one minimal.
