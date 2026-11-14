---
name: typing-audit
description: "Apply when asked to audit or tighten types, remove typing escape hatches, or make type contracts match runtime behavior. Keep the review within the requested scope. Skip routine type errors unrelated to an audit."
---

# Typing Audit

A type contract is true when every value the code can accept or produce at runtime fits it. A green checker reached through escape hatches is not success. Tighten contracts; never loosen one to make a patch fit. Audit the requested scope; a local request is not a repository sweep. Review-only requests do not authorize edits.

Model work is probabilistic; a type that rejects bad programs keeps working after the session ends. Each change should leave more that the checker proves and less that a reader must trust.

## Evidence the checker can use

A change counts only if it does at least one of these:

- **Rejects a program:** something the checker accepts today, such as a forbidden construction, an unvalidated value reaching a decision, or a missing variant, becomes a type error. Write that program down as the witness.
- **Deletes trust:** a cast, an unchecked assertion, a suppression, `any`, a "should never happen" check, or a repeated guard becomes unnecessary. Delete it in the same change.

Readability, symmetry, or resemblance to a state machine is not evidence. A rename or restructure that rejects nothing new and deletes nothing is churn.

## Classify each finding

- **False contract:** the annotation promises values the code never produces or rejects values it does produce. Examples: `cast(Item, None)`, a dict advertised as a sequence of rows, a serializer that deletes required keys and then claims the full type.
- **Lost inference:** a precise type already exists and an escape hatch drops it, for example an `Any` receiver that erases a typed return. A plain annotation fed by `Any` is as false as a cast, so removing the word `cast` is not enough.
- **Behavior regression:** an earlier typing change altered runtime behavior, for example an added `assert` that turns a supported `None` into a crash.
- **Latent bug:** a truthful type exposes a defect that predates the audit.
- **Stub stronger than the dependency:** a vendored or owned stub promises more than the pinned version returns. Check it against the installed version.
- **Test hides a supported state:** a test casts away a state the code supports, such as `cast(str, None)` standing in for "no release".
- **Not a bug:** examined, and the runtime is fine. Change only the type, or nothing. Earlier validation often already constrains a suspicious fallthrough, and some assertions state real internal invariants. Read the producer before calling either a bug.

## Pick the most critical, then stop

Rank leads by how much unchecked trust reaches decisions. Untrusted or persisted data reaching control flow comes first. Escape hatches on values that select behavior (authority, routing, lifecycle, money, paths) come next, then option soups and loose closed sets guarded by hand, then imprecise internal types. Fix one contract per change: the producer, its consumers, and their tests. A reviewer should see in a minute why the new type is truer than the old one. If a contract cannot be split, say why. Leave the rest as a ranked list.

## Escape hatches

- **Cast:** effectively banned. Restructure with stable local bindings, early returns, branch-local variables, typed accumulators, `isinstance`, or typed constructors. Keep one only for an invariant that is true, cannot be expressed, and no restructuring preserves, and state it. A helper that returns a caller-chosen type is a cast.
- **Generics that reshape:** `f(x: T) -> T` is false when `f` renames keys or changes shape. A `default: T` fallback that picks the claimed type of `Any` data is also false.
- **`Any`:** never for first-party data shapes: payloads, responses, validated data, known `**kwargs`, our own return types. Allow it only where a dependency's types fix it as `Any` and we cannot reshape it, or where a test double is the value. Use `object` for unknown data and parse it.
- **Ignore comments:** only for a wrong third-party stub we do not own, scoped to the error code, with a one-line reason. Fix owned stubs instead.
- **Non-null assertions:** only for an internal invariant already established, never on a value the model, field, or API allows to be null.
- **Banned:** fixed-name `getattr`/`setattr` around a known attribute, blanket stub `__getattr__`, disabling checks for a function, and weaker checker settings.

## Follow the values

1. Read the producer, its callers and consumers, the tests, and dependency implementations or stubs when their behavior matters. Compare the declared types with the actual branches, mutations, and exceptions. Check receivers as well as results.
2. Parse, don't validate. At HTTP, RPC, JSON, config, queue, database-JSON, and untyped-dependency boundaries, parse `object` into a precise record or discriminated union and pass the parsed value on. Validators return what they established. Keep raw input, validated data, in-memory values, and wire JSON as separate types. Keep missing vs null, create vs partial update, empty vs absent, and unsaved vs complete distinct.
3. Fix the producer, not the consumer. Don't reparse a value that already has a precise type. Known keyword arguments become explicit parameters or a typed options record.
4. Preserve runtime behavior: coercions, error types, mutation, and aliasing. Never turn `None` into `""`, `0`, `{}`, `"None"`, or a fake timestamp to satisfy a type. Copying a mapping is a behavior change. A runtime change that a truthful type needs ships separately when possible, called out, with a test that fails before it.
5. When `None` vs `[]` or a similar question decides the type, read the consumers and test it. If the values behave differently, keep both states. If you cannot settle it cheaply, keep the runtime value, type it honestly, and record the question.
6. Keep overrides substitutable. Redesign an incompatible relationship rather than suppressing the error.

Then read [the language notes](references/languages.md) for the checker in use.

## Verify and report

Run the project's type checker on the affected contract and consumers. The checker run is the proof of a typing change. Tests are proportional to regression risk:

- **Witnesses:** keep each one as a negative type test that asserts the intended diagnostic. Use an expected-error marker the checker reports once the error disappears, or the project's checker harness. Keep it minimal so no other error can satisfy it.
- **Runtime tests only when needed:** add one when behavior changes (it must fail before the fix), when you add a parser or type predicate (test the false branch and one malformed input), or when safety depends on a runtime fact the types don't show. Search existing coverage first, in every spelling of the input.
- **Mutation check:** break the guarded line and confirm the test fails, then revert. Delete a test that still passes.
- **`assert_type`:** only where a precise type could decay to `Any` unnoticed.
- **Don't add:** tests of dependency behavior, smoke tests, or a type assertion for every annotation.

**Report:** each finding with its class, the old claim and actual behavior, the corrected contract, the witnesses now rejected and the trust deleted, each escape hatch kept with its justification, any runtime or public API change, the deferred leads in rank order, and the checks run or not run. For review-only work, give each finding a witness and separate uncertainty from demonstrated defects.
