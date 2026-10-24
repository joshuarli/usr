# ty and Ruff: strict types, useful lint

The configurations below were exercised with ty 0.0.91 and Ruff 0.17.2 on 2026-10-24. Those versions identify the checked configuration, not permanent pins. Resolve the latest published non-prerelease [ty](https://github.com/astral-sh/ty/releases) and [Ruff](https://github.com/astral-sh/ruff/releases) when adopting/updating tooling. Review new settings and diagnostics before changing the project's exact pins.

## Contents

- [Versions and environment](#versions-and-environment)
- [ty baseline](#ty-baseline)
- [ty limits and exceptions](#ty-limits-and-exceptions)
- [Ruff baseline](#ruff-baseline)
- [Ruff choices](#ruff-choices)
- [Run and migrate](#run-and-migrate)

## Versions and environment

- Keep the existing package/tool manager and lock mechanism. Use exact tool pins or a resolved lock entry; record the versions actually executed. Do not install tool dependencies as application runtime dependencies. A `0.0.x` release number alone does not make a published ty release a prerelease.
- Align `requires-python`, the runtime/deployment floor, ty's `python-version`, and Ruff's `target-version`. The examples assume a 3.13 minimum; use the actual higher minimum where declared. Do not raise the minimum beyond 3.13 merely to use a new idiom, or infer it from the host interpreter.
- Point ty at the project's real dependency environment. [Target version](https://docs.astral.sh/ty/python-version/) and `environment.python`/`--python` have different jobs: the former sets the analyzed language/stubs, the latter locates dependencies. Inspect import resolution before ignoring a missing import. Test minimum-version runtime compatibility separately when relevant.
- Merge settings into the existing authoritative configuration. For `ty.toml`, drop the `tool.ty.` prefix; for `ruff.toml`, drop `tool.ruff.`. Inspect nested configs and existing excludes/overrides. Do not create a second competing config, silently weaken meaningful existing checks, or blanket-exclude tests, scripts, or difficult first-party modules.

## ty baseline

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

The unsound-flow rules constrain dynamic values crossing declared assignments, returns, and yields. Decorator/base-class checks protect signatures and inheritance from becoming dynamic unnoticed. Require real type arguments rather than filling generics with `Any` merely to silence a diagnostic.

Strict equality/generic analysis avoids permissive narrowing assumptions about subclass equality and generic runtime checks. Keep these settings unless a demonstrated limitation needs a narrow override; do not make public classes `final`, change equality, or insert unchecked casts to appease the checker. Return inference reduces needless private synchronous return annotations; the checked version does not infer asynchronous/generator returns through this option, so annotate those contracts explicitly.

## ty limits and exceptions

- Keep noisy opt-ins such as `division-by-zero`, `possibly-missing-attribute`, `possibly-missing-import`, and `redundant-condition-strict` at their default settings unless a concrete codebase need justifies them. Read the current [rule explanations](https://docs.astral.sh/ty/reference/rules/) before adding an opt-in. `possibly-unresolved-reference` is valuable but can also need a targeted exception for a proven control-flow limitation.
- Unannotated inputs and gradual types remain a coverage gap: `Unknown` behaves dynamically, and ty does not require annotations. Use Ruff's selected annotation rules below, explicit boundaries, and the [typing FAQ](https://docs.astral.sh/ty/reference/typing-faq/) to interpret checker limitations. A green run does not prove the absence of unchecked values. Supply narrow compatible stubs or adapters when genuinely needed, without fabricating signatures.
- `respect-type-ignore-comments = false` prevents legacy `type: ignore` directives from concealing ty findings. It also prevents ty from checking whether those legacy directives are unused. Review and remove/migrate them deliberately; preserve directives still required by another active checker until that checker is retired.
- Use `# ty: ignore[specific-rule]` only for a demonstrated false positive, with the concrete reason permitted by repository policy. `blanket-ignore-comment` and `unused-ignore-comment` catch broad/stale ty suppressions. Do not use `--add-ignore`, global unresolved-import allowances, or wholesale `replace-imports-with-any` as a migration strategy.
- Do not universally require decorators on every override or enable preview/integration-dependent rules. For example, `missing-direct-dependency` currently depends on uv integration; this workflow does not force uv. Inspect dependencies directly when needed. ty does not support mypy plugins: check actual framework typing coverage before retiring an existing checker, and report a blocker rather than masking the gap.

## Ruff baseline

Use stable [rules](https://docs.astral.sh/ruff/rules/) with an explicit selection. Current [defaults](https://docs.astral.sh/ruff/default-rules/) include style changes, so zero configuration is not this workflow's policy. Category selectors such as `correctness`/`suspicious` currently require preview; do not enable preview or `ALL` to approximate practical strictness. The selection below chooses bug checks and removes verbose members of otherwise useful families.

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

## Ruff choices

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

## Run and migrate

1. Inspect actual commands, environment, pins, configs, and existing diagnostics. Resolve/pin the latest tools when migration is in scope. Do not run any formatter, format check, import sorter, editor formatting action, or aggregate task that invokes one. Use permitted constituent commands.
2. Merge the profiles and run the pinned `ty check` and `ruff check` for the relevant first-party paths through the established runner. For an existing uv project, `uv run ty check` and `uv run ruff check` are appropriate; other runners remain valid. Inspect scripts for hidden formatting or automatic fixes first.
3. Treat diagnostics as code/design work. Check public re-exports before removing imports; preserve runtime annotation imports, timezone/wire contracts, and resource/cancellation behavior. [Fix safety](https://docs.astral.sh/ruff/linter/#fix-safety) is a tool classification, not proof that a change is compatible. Apply only selected, understood lint fixes; no blanket unsafe fixes or `--add-noqa`.
4. Retire replaced mypy/Pyright/Flake8/plugin plumbing only after required coverage is established. Remove obsolete formatter dependencies/configuration when tooling cleanup is in scope, without running them. Do not replace configuration by excluding the code that fails. Keep CI edits within an explicit CI request.
5. Verify the changed contracts with narrow existing tests and minimum-version execution where needed. Reuse results while their inputs remain valid. Report actual versions, checks, justified exceptions, missing coverage, and unavailable checks; a static check is not a runtime test.
