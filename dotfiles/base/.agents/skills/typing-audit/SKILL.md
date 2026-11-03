---
name: typing-audit
description: "Apply when asked to audit or tighten types, remove typing escape hatches, or make type contracts match runtime behavior. Keep the review within the requested scope; skip routine type errors unrelated to an audit."
---

# Typing Audit

A type contract must describe every value the implementation can accept or produce. A green checker or fewer escape hatches is not proof. Audit the requested scope; do not turn a local request into a repository sweep. Review-only requests do not authorize edits.

## Follow the values

1. Read the producer, its callers and consumers, relevant tests, and dependency implementations or stubs when their behavior matters. Compare declared types with actual branches, mutations, exceptions, and supported inputs. Check both the type of a receiver and the result: an unchecked receiver can erase an otherwise precise return type.
2. Investigate casts, unchecked assertions, suppressions, broad types, reflection used for known attributes, and generic helpers that promise a caller-selected result. Also look for false annotations that pass because their source is untyped. These are leads, not automatic defects; establish the runtime invariant before changing one.
3. Repair the producer and carry its real type through consumers. Parse unknown external data at the boundary into a checked representation; preserve required versus absent, null versus empty, raw versus validated, and in-memory versus wire values. Reuse an existing precise type rather than reparsing it. Verify dependency types against the version actually used; fix owned stubs when they are wrong.
4. Preserve runtime behavior by default, including coercion, errors, mutation and aliasing. Do not invent defaults, add a crash, or narrow a supported state to satisfy the checker. If a truthful contract exposes a real behavior bug, identify it and separate its fix where practical. Keep overrides substitutable; redesign an incompatible relationship rather than suppressing the error.
5. Prefer small, coherent changes around a contract and its consumers. Retain an escape hatch only when the invariant is true, cannot reasonably be expressed or preserved by restructuring, and is supported by evidence; explain it in the report. Do not weaken checker settings to make an audit pass.

## Language-specific checks

### Python with ty

Use the project's configured ty command and Python version. Prefer `object` for genuinely unknown values and parse them; use precise `TypedDict`, dataclass, union, or protocol types for known shapes. Model known keyword arguments with explicit parameters or `Unpack[TypedDict]`, and transparent forwarding with `ParamSpec`. Distinguish `NotRequired[T]` from a required `T | None`. Treat `Any`, `cast`, ignores, and annotations fed by `Any` as potential lost checks, including in tests and dependency stubs. Use narrowing and stable local bindings before casts. A `TypeGuard` must check the full promised positive shape; `TypeIs` must classify both branches correctly. A content predicate is not necessarily a type predicate. Retain `Any` where an external API or test double genuinely requires it, with the boundary made clear.

### TypeScript

Trace `any` through receivers, generics, and assertions; an annotation or `as` does not validate runtime data. Prefer `unknown` at untrusted boundaries, validate the full shape, and return a typed value. Use discriminated unions and exhaustive handling for real variants; distinguish optional properties, `undefined`, and `null` according to runtime and compiler settings. Check that type predicates really establish their claimed shape and that assertion functions do not turn supported input into a new throw. Prefer narrowing and correctly typed producers to `as`, non-null assertions, and suppression directives. Treat generated declarations and external types as claims to verify, not runtime validation.

### Rust

Trace `Option`, `Result`, enums, conversions, and ownership through producers and consumers. Use variants and validated constructors for actual domain invariants, but retain valid partial states and preserve wire formats. Examine `unwrap`, `expect`, `unreachable!`, unchecked conversions, and `unsafe` assumptions for invariants that callers actually establish; a panic or an unchecked operation is not type evidence. Prefer exhaustive matches, fallible conversions, and precise types to fabricated values or erased errors. Check trait bounds and public signatures against real callers, and avoid adding allocations or changing borrowing and aliasing merely to satisfy a type.

## Verify and report

Run the project's relevant type checker or compiler on the affected contract and consumers, expanding only when a concrete integration risk requires it. Check existing coverage first. Add focused tests when runtime behavior changes, a parser or type predicate needs malformed and negative cases, or safety depends on an otherwise untested runtime invariant. A behavior-fix test should fail before the fix; type-level regression tests are useful when inference could silently decay to an unchecked type. Do not add tests that merely repeat annotations or cover unchanged dependency behavior.

Report the old claim and actual behavior, the corrected contract, any runtime or public API change, remaining escape hatches and their justification, and checks run or not run. For review-only work, report supported findings with evidence and distinguish uncertainty from a demonstrated defect.
