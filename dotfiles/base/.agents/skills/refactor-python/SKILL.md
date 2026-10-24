---
name: refactor-python
description: "Refactor Python 3.13+ with modern type and resource design, latest ty, and practical strict Ruff checks. Use only when explicitly requested by name or for this Python refactoring workflow."
disable-model-invocation: true
metadata:
  opencode/slash: "true"
  opencode/autoinvoke: "false"
---

# Refactor Python

Implement a coherent refactor of the code, types, boundaries, and resource ownership. Preserve behavior and public contracts unless their change is already authorized. A tool upgrade or lint-only pass does not finish actionable work. If the code already meets the goal, report the evidence without manufacturing edits.

Use the requested paths/packages; an unqualified invocation covers the repository's first-party Python. Include affected callers and existing tests; exclude vendored code and generated outputs. If no Python is present, report that and stop.

## Baseline and authority

- Support Python 3.13 or later only. Use the project's declared minimum when it is newer; do not use features newer than that minimum just because the host supports them. A whole-codebase invocation includes adopting this floor and the tools below. A narrow refactor does not authorize a repository-wide runtime or tooling migration; report an incompatible floor instead of adding old-version shims.
- Use the latest published non-prerelease releases of **ty** for type checking and **Ruff** for linting. Resolve current releases when adopting or updating tooling and pin them through the project's existing mechanism. Reuse those pins during the refactor; do not fetch a moving latest version on every check. Do not impose a package manager or application framework.
- Read [Python design](references/python.md) and [ty and Ruff](references/tooling.md) before editing. Use versioned Python docs, the typing specification, and installed tool behavior as authorities. Check official release notes/configuration when changing pins. If upstream is unavailable, use installed evidence and state the limitation.
- Apply the user's request and active repository instructions before generic preferences. Preserve unrelated work. Keep commits, pushes, deployment, and CI changes within existing authorization; invoking this skill alone does not authorize publishing or editing CI.

## Inspect the contract

Read instructions, the working diff, package metadata, dependency/tool pins, Python targets, entrypoints, imports, callers, data schemas, tests, and verification commands. Distinguish application internals from published APIs, scripts, stubs, and framework entrypoints. Inspect actual task definitions before running an aggregate command.

Preserve signatures/keyword names, imports/re-exports, key presence, serialization/pickling, exceptions/exit status, order/duplicates, iterator consumption, mutation/aliasing, evaluation timing, resource/lock lifetimes, cancellation, and performance constraints. Internal APIs may change with all callers. Establish a focused baseline or record why it cannot run.

Survey the requested scope and keep a lightweight assessment of changes to implement, deliberate exceptions, and contract conflicts. Lint findings are leads, not proof that a rewrite is correct.

## Refactor in coherent passes

1. Model the domain: precise input and public return contracts, honest unions, and explicit missing-versus-null states. Replace unjustified `Any`, casts, raw generics, and untyped decorators. Validate external values at the boundary; annotations and `TypedDict` do not validate at runtime. Infer obvious locals and safe private returns.
2. Simplify the implementation: direct functions, cohesive modules, straightforward control flow, and the standard library where it meets the contract. Remove redundant state and abstraction. Choose records, protocols, generics, and immutable views for a concrete responsibility, not for uniformity.
3. Make failures and resources explicit: narrow exception handling, meaningful exception translation, owned context managers, bounded concurrency, and observed task failures. Preserve cancellation and cleanup; do not hide errors behind empty values or logging-only success paths.
4. Modernize touched code within the declared Python floor. Use modern generics, aliases, narrowing, and standard typing imports where their semantics fit. Check runtime introspection, variance, dataclass behavior, and annotation evaluation before changing them. Avoid syntax-only sweeps.
5. When tooling migration is in scope, configure the reference's strict ty profile and curated Ruff checks, with targets matching the minimum runtime. Repair underlying problems, then remove replaced checker/linter plumbing only after its necessary coverage is accounted for. Do not silence unknown imports or dynamic types to make a green check.
6. Update affected callers and existing tests together. Complete the requested scope, not only the first easy file. Keep narrow, evidenced exceptions when a checker cannot express a sound contract.

## Tool policy

Do not install, configure, or run formatters: no `ruff format`, Black, autopep8, YAPF, or equivalents, including check-only runs, editor actions, hooks, and aggregate commands that invoke them. Run permitted constituent checks instead. Do not reproduce a formatter with whitespace, quote, line-length, import-sorting, or reflow lints. Preserve readable local layout without cosmetic churn.

Strictness protects types and behavior; it does not mean every rule. Do not enable Ruff `ALL`, blanket pedantic/style families, blanket mandatory docstrings, complexity quotas, or annotations on every local/private return. Do not use ty `--error=all` as a substitute for choosing its useful strict settings. Retain relevant existing correctness checks. Reject needless wrappers, temporary variables, casts, comments, and changed error messages introduced solely to satisfy a noisy lint.

Run lint diagnostics without fixes first. Apply only understood, selected lint fixes and inspect the diff; an automatic fix's safety classification does not prove compatibility. Do not run blanket unsafe fixes, generate ignore comments, weaken checking globally, or exclude troublesome first-party code. Suppress only a demonstrated false positive at the smallest scope with a specific rule and reason permitted by repository policy.

## Verify and finish

Follow active verification instructions and reuse valid results. Run the pinned `ty check` and `ruff check` against the affected first-party scope through the project's runner and real dependency environment. Keep an independent type-check gate. Validate on the declared minimum runtime when changed syntax or runtime behavior needs it; a newer interpreter or static check alone does not establish minimum-version runtime compatibility.

Use existing focused tests for changed behavior, especially boundary validation, omission semantics, errors, resource cleanup, iteration, and cancellation. Add a regression test only for an uncovered observable contract or invariant and when authorized by the verification policy; never assert code shape. Respect verification opt-outs and report what remains unproven. Widen checks only for a concrete integration risk. Measure a claimed performance improvement rather than guessing.

Review the diff and rescan scope for accidental contract changes, formatting churn, new suppressions, and obsolete code/configuration. Separate preexisting failures from regressions; unavailable checks are limitations, not passes.

**Report:** scope and representative code/design improvements; Python floor and resolved tool versions; relevant strictness choices and justified exceptions; preserved or authorized changed contracts; checks run and results, preexisting failures, and checks not run.
