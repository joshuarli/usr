+++
name = "python"
summary = "Python keeps honest types at real boundaries, explicit failures and resource ownership, modern typing within the declared floor, and pinned ty and Ruff with targeted strictness."

[[trigger]]
paths = ["*.py", "*.pyi", "!*_pb2.py", "!*_pb2.pyi", "pyproject.toml", "ruff.toml", "ty.toml"]

[[trigger]]
shebang = ['^#!.*\bpython[0-9.]*\b']

[examples]
match = ["tools/sync/main.py", "stubs/x.pyi", "pyproject.toml", { path = "dotfiles/base/.local/bin/todo", text = "#!/usr/bin/env python3\n" }]
skip = ["gen/api_pb2.py", "README.md", { path = "bin/run", text = "#!/bin/sh\n" }]
+++

# Python

Use the [versioned Python documentation](https://docs.python.org/3.13/) for runtime semantics and the living [typing specification](https://typing.python.org/en/latest/spec/index.html) for type contracts. These are design prescriptions for this standard, not blanket PEP 8 enforcement. The declared minimum interpreter remains the target even when the host is newer. Do not run a formatter or perform a cosmetic modernization sweep.

## Code

### Contracts to preserve

Preserve signatures/keyword names, imports/re-exports, key presence, serialization/pickling, exceptions/exit status, order/duplicates, iterator consumption, mutation/aliasing, evaluation timing, resource/lock lifetimes, cancellation, and performance constraints. Internal APIs may change with all callers. Establish a focused baseline or record why it cannot run.

### Types at real boundaries

- Annotate function inputs and meaningful public returns. Give stored state and ambiguous containers enough context to establish their contract; infer obvious locals and safe private synchronous returns. Explicitly annotate async/generator returns where ty cannot infer them. Keep an annotation that prevents an unwanted public API inference change.
- Use `object` for an arbitrary value that must be checked before use. Keep `Any` only at an unavoidable, identified dynamic boundary; do not spread it through the typed core. A `cast`, annotation, or `TypedDict` declaration does not validate runtime data. Decode and validate external values once with the project's existing boundary machinery.
- Preserve accepted coercions, defaults, extra keys, omission/null semantics, and error shape when replacing validation. Check domain constraints explicitly: for example, `bool` is an `int` subclass, so an integer-only domain may need to exclude it. Do not strengthen validation or silently discard data under the name of a behavior-preserving refactor.
- Preserve honest unions. Model correlated states together rather than allowing impossible combinations of optional fields and flags. Use `Literal`, an enum, a record, or a small union when it expresses a real distinction; avoid a hierarchy for every result or a brand for every string.
- Accept the operations actually needed: `Iterable[T]` for one traversal, `Sequence[T]` for indexing/repeated traversal, and `Mapping[K, V]` for read access. Do not promise arbitrary iterable support while consuming input twice. Return the concrete owned collection when that is the useful API. Read-only interfaces do not promise that other aliases cannot mutate the value.
- Use a small [Protocol](https://typing.python.org/en/latest/spec/protocol.html) for a genuine structural capability. Keep direct concrete dependencies when adequate. Runtime-checkable protocols do not check method signatures; they cannot replace boundary validation. Avoid protocols, ABCs, overloads, or dependency injection layers created only to wrap one implementation.

### Modern typing without semantic drift

- Use built-in generics, `X | None`, and `collections.abc` where appropriate. Import [3.13 typing facilities](https://docs.python.org/3.13/library/typing.html), including `TypeIs`, `ReadOnly`, `override`, and type-parameter defaults, from their standard location. Remove `typing_extensions` only after all remaining imports and required features are accounted for.
- Prefer the [`type` statement](https://typing.python.org/en/latest/spec/aliases.html) and [PEP 695 parameter syntax](https://peps.python.org/pep-0695/) for new or substantively changed types. Preserve old syntax when runtime consumers, variance, or checker support require it. A `type` alias is not an interchangeable runtime constructor or class. Inspect calls, bases, `isinstance`, decorators, serialization, and reflection before migrating an assignment alias.
- Use generic parameters only when they preserve a relationship among inputs and outputs. Use `ParamSpec` and `functools.wraps` for a wrapper that must preserve the wrapped call signature and metadata; do not replace every wrapper with type gymnastics. A [type-parameter default](https://peps.python.org/pep-0696/) should represent a meaningful omitted choice, not conceal an untyped API.
- Use [`TypedDict`](https://typing.python.org/en/latest/spec/typeddict.html) for an existing dictionary/wire representation. Distinguish an absent key (`NotRequired`) from a present nullable value (`T | None`). `ReadOnly` restricts writes through the typed view; it neither freezes nor recursively validates the runtime dictionary.
- Prefer ordinary `is None`/`isinstance` guards when sufficient. Use [`TypeIs[T]`](https://typing.python.org/en/latest/guides/type_narrowing.html) only for an exact membership predicate whose narrowed type is compatible with the input; it narrows both branches. Keep `TypeGuard` when positive-only or invariant-container narrowing is required. A predicate accepting only positive integers cannot truthfully claim `TypeIs[int]`. Neither annotation proves the predicate's body correct.
- Mutation through aliases, callbacks, threads, or an `await` can invalidate earlier narrowing. Capture a stable value or re-check at the relevant boundary; do not silence the risk with a cast. Use `@override` on intentional overrides when touching inheritance contracts, without forcing decorators across unrelated code.
- Do not blindly add/remove `from __future__ import annotations`. Ordinary annotations are generally eager in 3.13, deferred by default in 3.14+, and stringified by that future import. Inspect framework/decorator introspection and `get_type_hints()` before changing imports or annotation-only dependencies. [`annotationlib`](https://docs.python.org/3.14/library/annotationlib.html) requires 3.14; keep it out of a 3.13 baseline. An import used for runtime annotation resolution may need to stay outside `TYPE_CHECKING`.

### Data and implementation

- Prefer direct functions and cohesive modules. Introduce a class for meaningful state, identity, or protocol behavior. Separate pure transformations from external effects where that clarifies responsibility. Use the standard library when it meets the contract; preserve useful existing libraries and frameworks rather than imposing replacements.
- Choose a [dataclass](https://docs.python.org/3.13/library/dataclasses.html) for a real record whose boilerplate it can remove. Inspect generated equality/hash, representation, field order, constructor arguments, pattern matching, and pickle behavior. `frozen`, `slots`, and keyword-only fields change contracts; they are not universal defaults. Use `default_factory` for per-instance mutable values and never add `unsafe_hash` just to satisfy typing.
- Use comprehensions for simple transformations, and ordinary loops for substantial branching, side effects, or resource handling. Preserve order, multiplicity, laziness, consumption, evaluation timing, and exception timing when changing loops, generators, sets, or dictionaries. Do not replace a readable loop just because a simplification lint prefers an expression.
- Distinguish `None` from valid falsey values. Add `zip(strict=True)` only when equal lengths are an actual invariant; truncation may be deliberate. Preserve numeric precision and rounding, bytes/text distinctions, timezone assumptions, encodings, and newline behavior. `pathlib` is useful, but a mechanical path rewrite can change bytes-path, symlink, or error behavior.
- Keep explicit imports and package boundaries. Preserve public re-exports, import-time side effects, and `__all__`. Do not sort imports automatically or move runtime dependencies behind `TYPE_CHECKING` solely to appease lint. Avoid global patching, hidden caches, and import-time I/O without a concrete existing responsibility.

### Failures and resource ownership

- Catch the narrow expected [exception](https://docs.python.org/3.13/tutorial/errors.html) around the operation that raises it. Keep unrelated logic outside the `try`. Translate at a meaningful boundary, preserving the cause when useful; do not mandate exception boilerplate for every raise. Deliberate process/server boundaries may catch broadly if they preserve the failure contract.
- Do not turn errors into empty values, unconditional defaults, or logging-only success paths. Validate public input with runtime checks; reserve assertions for internal invariants, and keep necessary side effects out of assertions.
- Own files, locks, transactions, and other resources with `with`/`async with` or explicit `try/finally`. Use [`ExitStack`/`AsyncExitStack`](https://docs.python.org/3.13/library/contextlib.html) for a variable set of resources, not as a wrapper around one context manager. Preserve acquisition/release order and lock scope. A generator-based context manager that catches an exception must re-raise unless suppression is the intended contract.
- Treat serialization, subprocesses, files, and remote calls as real trust boundaries. Preserve argument-array subprocess invocation, required TLS verification, safe deserialization, and existing timeout/cancellation behavior. Investigate a security finding before changing a public contract; an arbitrary new timeout or parser fallback is not a style fix.

### Concurrency

- Stay within the project's synchronous/async/thread/process model. Do not replace AnyIO/Trio with asyncio or turn synchronous code async as a style exercise. Do not assume the GIL makes shared state safe, or enable free-threading/JIT/runtime modes during a refactor.
- In asyncio code, use [`TaskGroup`](https://docs.python.org/3.13/library/asyncio-task.html#task-groups) when child tasks truly share a lifetime and failure boundary. Bound concurrency and resources. Do not mechanically replace `gather`: sibling cancellation and exception-group behavior differ.
- Every task needs an owner that observes completion and failures. Intentional background work needs an explicit lifetime, retained ownership, and shutdown path. Merely keeping a task in a set does not handle its failure.
- Clean up in context managers or `finally` and propagate [`CancelledError`](https://docs.python.org/3.13/library/asyncio-task.html#task-cancellation) after cleanup. Swallowing cancellation can break timeout and task-group behavior. Thread offload does not make arbitrary blocking work cancellable; inspect ownership and context before moving it off the event loop.

### Tool policy

Do not install, configure, or run formatters: no `ruff format`, Black, autopep8, YAPF, or equivalents, including check-only runs, editor actions, hooks, and aggregate commands that invoke them; run the permitted constituent checks instead. Do not stand in for a formatter with whitespace, quote, line-length, import-sorting, or reflow lints. Keep local layout without cosmetic churn.

Strictness protects types and behavior; it does not mean every rule. Do not enable Ruff `ALL`, blanket pedantic/style families, blanket mandatory docstrings, complexity quotas, or annotations on every local/private return. Do not use ty `--error=all` as a substitute for choosing its useful strict settings. Retain relevant existing correctness checks. Reject needless wrappers, temporary variables, casts, comments, and changed error messages introduced solely to satisfy a noisy lint.

Run lint diagnostics without fixes first. Apply only understood, selected lint fixes and inspect the diff; an automatic fix's safety classification does not prove compatibility. Do not run blanket unsafe fixes, generate ignore comments, weaken checking globally, or exclude troublesome first-party code. Suppress only a demonstrated false positive at the smallest scope with a specific rule and reason permitted by repository policy.

### Verify

Run pinned `ty check` and `ruff check` through the project's runner and dependency environment; keep type checking independent. Verify actual file and config discovery. Use the declared minimum runtime when syntax or behavior needs runtime proof; static checks do not establish it.

Exercise boundary/omission semantics, failures, cleanup, iteration, and cancellation where changed. Never weaken types, validators, or check coverage to get green results. Measure performance claims.

Review the diff and rescan scope for accidental contracts, churn, suppressions, and obsolete code/configuration. Separate baseline failures from regressions. Stale checks, empty selections, and excluded code are not passes. State any missing proof as a specific gap.

## Adoption

Apply these only when bringing a whole repository up to this standard with `/standardize`, not at the completion gate.

The configurations below were exercised with ty 0.0.91 and Ruff 0.17.2 on 2026-10-24. Those versions identify the checked configuration, not permanent pins. Resolve the latest published non-prerelease [ty](https://github.com/astral-sh/ty/releases) and [Ruff](https://github.com/astral-sh/ruff/releases) when adopting/updating tooling. Review new settings and diagnostics before changing the project's exact pins.

- A whole-codebase run sets the floor to Python 3.13, or to the project's declared minimum if newer, and adopts the tools below. A narrow run keeps the declared floor, does not migrate runtime or tooling repository-wide, and reports a floor below 3.13 instead of adding old-version shims. Never use features newer than the floor just because the host supports them.
- Use the latest published non-prerelease **ty** and **Ruff** when adopting/updating tooling, pinned through the project's existing mechanism. Reuse those pins during the refactor. Do not impose a package manager or framework. A narrow task uses existing tools and reports missing gates; it does not add pins or silently raise the runtime floor.
- In an in-scope tooling migration, use the strict ty/Ruff profiles with matching runtime targets. Repair causes; retire replaced checkers only after necessary coverage is established. Do not silence unknown imports or dynamic values to get green results.

### Versions and environment

- Keep the existing package/tool manager and lock mechanism. Use exact tool pins or a resolved lock entry; record the versions actually executed. Do not install tool dependencies as application runtime dependencies. A `0.0.x` release number alone does not make a published ty release a prerelease.
- Align `requires-python`, the runtime/deployment floor, ty's `python-version`, and Ruff's `target-version`. The examples assume a 3.13 minimum; use the actual higher minimum where declared. Do not raise the minimum beyond 3.13 merely to use a new idiom, or infer it from the host interpreter.
- Point ty at the project's real dependency environment. [Target version](https://docs.astral.sh/ty/python-version/) and `environment.python`/`--python` have different jobs: the former sets the analyzed language/stubs, the latter locates dependencies. Inspect import resolution before ignoring a missing import. Test minimum-version runtime compatibility separately when relevant.
- Merge settings into the existing authoritative configuration. For `ty.toml`, drop the `tool.ty.` prefix; for `ruff.toml`, drop `tool.ruff.`. Inspect nested configs and existing excludes/overrides. Do not create a second competing config, silently weaken meaningful existing checks, or blanket-exclude tests, scripts, or difficult first-party modules.


### ty baseline

ty has no `--strict` flag. Its [migration guidance](https://docs.astral.sh/ty/coming-from-mypy-or-pyright/) recommends targeted extra rules instead of `--error=all`. Retain default diagnostics, add the soundness/suppression checks below, and fail on warnings as well as errors. [Configuration](https://docs.astral.sh/ty/reference/configuration/) is version-sensitive; validate it with the pinned binary.

```toml
[tool.ty.environment]
python-version = "3.13"

[tool.ty.analysis]
return-type-inference = "always"
strict-equality-semantics = true
strict-generic-narrowing = true
respect-type-ignore-comments = false

[tool.ty.rules]
blanket-ignore-comment = "error"
disjoint-cast = "error"
dynamic-function-decorator-return = "error"
missing-type-argument = "error"
possibly-unresolved-reference = "error"
unsound-assignment = "error"
unsound-return-statement = "error"
unsound-yield = "error"
unsupported-dynamic-base = "error"
unused-ignore-comment = "error"

[tool.ty.terminal]
error-on-warning = true
output-format = "concise"
```

The unsound-flow rules constrain dynamic values crossing declared assignments, returns, and yields. `disjoint-cast` rejects impossible conversions such as `cast(str, an_int)`; overlapping casts still require evidence and never validate data. Decorator/base-class checks protect signatures and inheritance from becoming dynamic unnoticed. Require real type arguments rather than filling generics with `Any` merely to silence a diagnostic.

Strict equality/generic analysis avoids permissive narrowing assumptions about subclass equality and generic runtime checks. Keep these settings unless a demonstrated limitation needs a narrow override; do not make public classes `final`, change equality, or insert unchecked casts to appease the checker. Return inference reduces needless private synchronous return annotations. The checked version does not infer async/generator returns through this option: manually check those annotations, including private functions. Also review public static/class/property return surfaces that the selected `ANN201` rule does not fully cover. Do not enable blanket private-return annotation rules to approximate this targeted review.


### ty limits and exceptions

- Keep noisy opt-ins such as `division-by-zero`, `possibly-missing-attribute`, `possibly-missing-import`, and `redundant-condition-strict` at their default settings unless a concrete codebase need justifies them. Read the current [rule explanations](https://docs.astral.sh/ty/reference/rules/) before adding an opt-in. `possibly-unresolved-reference` is valuable but can also need a targeted exception for a proven control-flow limitation.
- Unannotated inputs and gradual types remain a coverage gap: `Unknown` behaves dynamically, and ty does not require annotations. Use Ruff's selected annotation rules below, explicit boundaries, and the [typing FAQ](https://docs.astral.sh/ty/reference/typing-faq/) to interpret checker limitations. A green run does not prove the absence of unchecked values. Supply narrow compatible stubs or adapters when genuinely needed, without fabricating signatures.
- `respect-type-ignore-comments = false` prevents legacy `type: ignore` directives from concealing ty findings. It also prevents ty from checking whether those legacy directives are unused. Review and remove/migrate them deliberately; preserve directives still required by another active checker until that checker is retired.
- Use `# ty: ignore[specific-rule]` only for a demonstrated false positive, with the concrete reason permitted by repository policy. `blanket-ignore-comment` and `unused-ignore-comment` catch broad/stale ty suppressions. Do not use `--add-ignore`, global unresolved-import allowances, or wholesale `replace-imports-with-any` as a migration strategy.
- Do not universally require decorators on every override or enable preview/integration-dependent rules. For example, `missing-direct-dependency` currently depends on uv integration; this standard does not force uv. Inspect dependencies directly when needed. ty does not support mypy plugins: check actual framework typing coverage before retiring an existing checker, and report a blocker rather than masking the gap.


### Ruff baseline

Use stable [rules](https://docs.astral.sh/ruff/rules/) with an explicit selection. Current [defaults](https://docs.astral.sh/ruff/default-rules/) include style changes, so zero configuration is not this standard's policy. Category selectors such as `correctness`/`suspicious` currently require preview; do not enable preview or `ALL` to approximate practical strictness. The selection below chooses bug checks and removes verbose members of otherwise useful families.

```toml
[tool.ruff]
target-version = "py313"
preview = false
fix = false
unsafe-fixes = false

[tool.ruff.lint]
select = [
    "F", "B", "BLE001", "PLE", "YTT",
    "E722", "E902", "W605",
    "ANN001", "ANN002", "ANN003", "ANN201",
    "ASYNC100", "ASYNC105", "ASYNC2",
    "DTZ003", "DTZ004",
    "LOG001", "LOG002", "LOG009", "LOG014",
    "G010", "G101", "G201", "G202",
    "PIE794", "PIE796",
    "SIM107", "SIM115", "SIM220", "SIM221", "SIM222", "SIM223",
    "TC004", "TC005", "TC007", "TC010",
    "PLW0127", "PLW0128", "PLW0129", "PLW0133", "PLW0177",
    "PLW0245", "PLW0711", "PLW1501", "PLW1507", "PLW1508",
    "PLW1509", "PLW1510", "PLW2101",
    "RUF006", "RUF008", "RUF009", "RUF012", "RUF013",
    "RUF016", "RUF017", "RUF018", "RUF020", "RUF024",
    "RUF026", "RUF030", "RUF032", "RUF033", "RUF034",
    "RUF040", "RUF048", "RUF049", "RUF053", "RUF060",
    "RUF063", "RUF068", "RUF071", "RUF100", "RUF101",
    "RUF102", "RUF103", "RUF104", "RUF200",
    "S113", "S306", "S323", "S501", "S506", "S507",
]
ignore = [
    "B007", "B009", "B010", "B011", "B013", "B028", "B034",
    "B904", "B905", "B911", "B912",
    "PLE0237", "PLE0302",
]

[tool.ruff.lint.flake8-annotations]
suppress-dummy-args = true
suppress-none-returning = true
```

Validate supported rule codes with the installed binary; this profile should parse without unknown/deprecated/preview-rule warnings. Review added rules when upgrading, since family prefixes can expand. Do not copy a warning-laden config and silence warnings globally.


### Ruff choices

| Concern | Policy |
| --- | --- |
| Broken Python and suspicious behavior | Pyflakes, selected bugbear/Pylint/Ruff rules: names, invalid operations, mutable defaults, late-bound closures, state and collection mistakes. Check framework-specific exceptions to defaults such as dependency-injection calls. |
| Annotation boundaries | `ANN001`/`002`/`003` cover inputs; `ANN201` covers meaningful public returns. Infer private returns and ordinary locals. Ignore unused dummy parameters and trivial `None` returns. Do not add broad `ANN`/`ANN401`, needless `Any`, or redundant test-return annotations. |
| Async/resources | Selected async checks cover blocking calls and cancellation mistakes; `RUF006` highlights unowned tasks, and `SIM115` highlights file ownership. Correct ownership requires more than satisfying the lint. |
| Failures/logging | Catch swallowed or misleading errors and broken logging calls. `BLE001` permits re-raising or exception logging; do not add useless logging to appease it. A deliberate outer boundary may need a narrow waiver. |
| Specific security mistakes | The selected `S` rules flag missing Requests timeouts, unsafe temporary names/YAML, and disabled TLS/SSH verification. Investigate intent and deployment; do not invent timeout values or rewrite safe serialization blindly. |
| Suppression hygiene | Flag stale, invalid, and unmatched directives. Do not enable every rule just to make a historical suppression seem necessary. |

Do not enable whole style/mixed families such as `E`, `W`, `S`, `PL`, `RUF`, `UP`, `ANN`, `D`, `I`, `Q`, `COM`, `C4`, `SIM`, or `PTH` without selecting their applicable rules. Keep formatter-equivalent rules off. Do not add quote/line-length/import-order rules, docstring requirements, naming/complexity quotas, forced `pathlib`/f-string conversions, or local-annotation mandates.

The exclusions deliberately avoid mandatory `strict=` on every `zip`/`map`/`batched`, exception-cause boilerplate on every raise, unused-loop-variable renaming, forced warning `stacklevel`, and redundant structural policing already better handled by types. Preserve equal-length invariants, error causality, and meaningful warnings through design review where they matter. Do not replace `assert`, `print`, or ordinary randomness indiscriminately.

Add narrowly selected domain-specific checks only when they catch a concrete mistake in the actual framework, stubs, async library, or security boundary. Keep existing useful checks even if absent from this baseline. When a rule is wrong, use the smallest specific exception with its reason; do not pile on casts, temporary variables, logging, or wrappers to make code longer without improving it.


### Run and migrate

1. Inspect actual commands, environment, pins, configs, and existing diagnostics. Resolve/pin the latest tools when migration is in scope. Do not run any formatter, format check, import sorter, editor formatting action, or aggregate task that invokes one. Use permitted constituent commands.
2. Merge profiles only when tooling migration is in scope. Run pinned `ty check` and `ruff check` for the relevant first-party paths through the established runner. For an existing uv project, `uv run ty check` and `uv run ruff check` are appropriate; other runners remain valid. For a narrow task lacking the tools or compatible floor, use applicable existing checks and report the blocked gate; do not add pins or raise the runtime floor. Inspect scripts for hidden formatting or automatic fixes first.
3. Treat diagnostics as code/design work. Check public re-exports before removing imports; preserve runtime annotation imports, timezone/wire contracts, and resource/cancellation behavior. [Fix safety](https://docs.astral.sh/ruff/linter/#fix-safety) is a tool classification, not proof that a change is compatible. Apply only selected, understood lint fixes; no blanket unsafe fixes or `--add-noqa`.
4. Retire replaced mypy/Pyright/Flake8/plugin plumbing only after required coverage is established. Remove obsolete formatter dependencies/configuration when tooling cleanup is in scope, without running them. Do not replace configuration by excluding the code that fails. Keep CI edits within an explicit CI request.
5. Verify the changed contracts with narrow existing tests and minimum-version execution where needed. Reuse results while their inputs remain valid. Report actual versions, checks, justified exceptions, missing coverage, and unavailable checks; a static check is not a runtime test.

### Inspect

Read instructions, working changes, metadata/pins, targets, entrypoints, imports, callers, schemas, tests, and verification commands. Distinguish application internals, published APIs, scripts/stubs, and framework contracts. Inspect task definitions before running aggregate commands.

### Passes

1. Model precise inputs/public returns, honest unions, and missing-versus-null states. Replace unjustified `Any`, casts, raw generics, and untyped decorators. Validate at real boundaries; annotations and `TypedDict` do not validate. Infer obvious locals and safe private synchronous returns; manually verify async/generator return annotations, including private functions.
2. Simplify the implementation: direct functions, cohesive modules, straightforward control flow, and the standard library where it meets the contract. Remove redundant state and abstraction. Choose records, protocols, generics, and immutable views for a concrete responsibility, not for uniformity.
3. Make failures and resources explicit: narrow exception handling, meaningful exception translation, owned context managers, bounded concurrency, and observed task failures. Preserve cancellation and cleanup; do not hide errors behind empty values or logging-only success paths.
4. Modernize touched code within the Python floor. Check runtime introspection, variance, dataclass behavior, and annotation evaluation before changing generics, aliases, narrowing, or typing imports. Avoid syntax-only sweeps.
5. Update affected callers and existing tests together. Complete the requested scope, not only the first easy file. Keep narrow, evidenced exceptions when a checker cannot express a sound contract.

**Report:** Python floor and resolved tool versions; relevant strictness choices and justified exceptions.
