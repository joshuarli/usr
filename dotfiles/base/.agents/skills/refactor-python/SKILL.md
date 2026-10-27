---
name: refactor-python
description: "Refactor Python 3.13+ with modern type and resource design, latest ty, and practical strict Ruff checks. Use only when explicitly requested by name or for this Python refactoring workflow."
disable-model-invocation: true
metadata:
  opencode/slash: "true"
  opencode/autoinvoke: "false"
---

# Refactor Python

Refactor code, types, boundaries, and resource ownership. Preserve behavior and public contracts unless their change is authorized. Upgrades or lint alone do not complete actionable work. A justified no-op is valid; make no edits to look busy.

Use the requested paths/packages; an unqualified invocation covers the repository's first-party Python. Include affected callers and existing tests; exclude vendored code and generated outputs. If no Python is present, report that and stop.

## Baseline and authority

- A whole-codebase run sets the floor to Python 3.13, or to the project's declared minimum if newer, and adopts the tools below. A narrow run keeps the declared floor, does not migrate runtime or tooling repository-wide, and reports a floor below 3.13 instead of adding old-version shims. Never use features newer than the floor just because the host supports them.
- Use the latest published non-prerelease **ty** and **Ruff** when adopting/updating tooling, pinned through the project's existing mechanism. Reuse those pins during the refactor. Do not impose a package manager or framework. A narrow task uses existing tools and reports missing gates; it does not add pins or silently raise the runtime floor.
- Read [Python design](references/python.md) and [ty and Ruff](references/tooling.md) before editing. Use versioned Python docs, the typing specification, and installed tool behavior as authorities. Check official release notes/configuration when changing pins. If upstream is unavailable, use installed evidence and state the limitation.
- Apply the user's request and repository instructions before generic preferences. Preserve unrelated work. Invoking this skill does not authorize deploying.

## Inspect the contract

Read instructions, working changes, metadata/pins, targets, entrypoints, imports, callers, schemas, tests, and verification commands. Distinguish application internals, published APIs, scripts/stubs, and framework contracts. Inspect task definitions before running aggregate commands.

Preserve signatures/keyword names, imports/re-exports, key presence, serialization/pickling, exceptions/exit status, order/duplicates, iterator consumption, mutation/aliasing, evaluation timing, resource/lock lifetimes, cancellation, and performance constraints. Internal APIs may change with all callers. Establish a focused baseline or record why it cannot run.

Survey scope. For each batch identify its concrete benefit, preserved invariant, and smallest regression check. Lint findings are leads, not proof. Stronger validation, changed defaults, and new failure cases are contract changes. Fix incidental bugs only within authorized behavior; otherwise report them and continue.

## Refactor in coherent passes

1. Model precise inputs/public returns, honest unions, and missing-versus-null states. Replace unjustified `Any`, casts, raw generics, and untyped decorators. Validate at real boundaries; annotations and `TypedDict` do not validate. Infer obvious locals and safe private synchronous returns; manually verify async/generator return annotations, including private functions.
2. Simplify the implementation: direct functions, cohesive modules, straightforward control flow, and the standard library where it meets the contract. Remove redundant state and abstraction. Choose records, protocols, generics, and immutable views for a concrete responsibility, not for uniformity.
3. Make failures and resources explicit: narrow exception handling, meaningful exception translation, owned context managers, bounded concurrency, and observed task failures. Preserve cancellation and cleanup; do not hide errors behind empty values or logging-only success paths.
4. Modernize touched code within the Python floor. Check runtime introspection, variance, dataclass behavior, and annotation evaluation before changing generics, aliases, narrowing, or typing imports. Avoid syntax-only sweeps.
5. In an in-scope tooling migration, use the strict ty/Ruff profiles with matching runtime targets. Repair causes; retire replaced checkers only after necessary coverage is established. Do not silence unknown imports or dynamic values to get green results.
6. Update affected callers and existing tests together. Complete the requested scope, not only the first easy file. Keep narrow, evidenced exceptions when a checker cannot express a sound contract.

## Tool policy

Do not install, configure, or run formatters: no `ruff format`, Black, autopep8, YAPF, or equivalents, including check-only runs, editor actions, hooks, and aggregate commands that invoke them; run the permitted constituent checks instead. Do not stand in for a formatter with whitespace, quote, line-length, import-sorting, or reflow lints. Keep local layout without cosmetic churn.

Strictness protects types and behavior; it does not mean every rule. Do not enable Ruff `ALL`, blanket pedantic/style families, blanket mandatory docstrings, complexity quotas, or annotations on every local/private return. Do not use ty `--error=all` as a substitute for choosing its useful strict settings. Retain relevant existing correctness checks. Reject needless wrappers, temporary variables, casts, comments, and changed error messages introduced solely to satisfy a noisy lint.

Run lint diagnostics without fixes first. Apply only understood, selected lint fixes and inspect the diff; an automatic fix's safety classification does not prove compatibility. Do not run blanket unsafe fixes, generate ignore comments, weaken checking globally, or exclude troublesome first-party code. Suppress only a demonstrated false positive at the smallest scope with a specific rule and reason permitted by repository policy.

## Verify and finish

Run pinned `ty check` and `ruff check` through the project's runner and dependency environment; keep type checking independent. Verify actual file and config discovery. Use the declared minimum runtime when syntax or behavior needs runtime proof; static checks do not establish it.

Exercise boundary/omission semantics, failures, cleanup, iteration, and cancellation where changed. Never weaken types, validators, or check coverage to get green results. Measure performance claims.

Review the diff and rescan scope for accidental contracts, churn, suppressions, and obsolete code/configuration. Separate baseline failures from regressions. Stale checks, empty selections, and excluded code are not passes. State any missing proof as a specific gap.

**The test:** pinned `ty check` and `ruff check` pass on the final diff, no suppression or weakened check was added to get there, and behavior and public contracts are preserved unless a change was authorized.

**Report:** scope and representative code/design improvements; Python floor and resolved tool versions; relevant strictness choices and justified exceptions; preserved or authorized changed contracts; checks run and results, preexisting failures, and checks not run.
