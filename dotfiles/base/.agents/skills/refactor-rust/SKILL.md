---
name: refactor-rust
description: "Refactor Rust code according to Google's Rust Style Guide. Use only when explicitly requested by name or for a Google-style Rust refactor."
disable-model-invocation: true
metadata:
  opencode/slash: "true"
  opencode/autoinvoke: "false"
---

# Refactor Rust

Refactor code and API design using the [Google Rust Style Guide](https://google.github.io/styleguide/rustguide.html). An audit or lint pass alone does not complete actionable work. If the code already conforms or candidates are justified exceptions or incompatible changes, report the evidence without manufacturing edits.

Use the requested paths or crates. For an unqualified invocation, use the current Rust workspace's first-party code. Include affected callers and tests; exclude vendored code and generated outputs. If the scope contains no Rust code, report that and stop.

## Establish the contract

- Read applicable instructions, the working diff, manifests, toolchain/MSRV, feature and target configuration, build scripts, relevant callers, tests, and existing verification commands. Preserve unrelated work.
- Distinguish reusable library APIs from application internals. Google's API rules are binding guidance for reusable libraries; application code should favor directness over generalized interfaces.
- Read the [rule checklist](references/google-rust-guide.md) before editing. Consult its upstream links for applicable rules and exceptions, using current upstream wording when available. If the site is unavailable, use the bundled snapshot and disclose that limitation.
- Apply the user's request and active repository instructions before style preferences. In particular, respect policies on formatting, comments, toolchain pins, dependencies, and verification. Report material conflicts instead of silently rewriting those policies.
- Preserve public paths/signatures, trait and auto-trait contracts, serialization/FFI layout, output/exit status, errors/panics, ordering, side effects, resource/lock lifetime, cancellation, and performance constraints unless their change is authorized. Internal APIs may change with all callers.
- Run the narrowest relevant baseline checks, or record why they cannot run. Separate preexisting failures from regressions.

## Survey, then refactor

Survey the entire requested scope. For each batch, identify the concrete improvement, applicable rule/exception, preserved invariant, and smallest check that could expose a regression. Use searches and Clippy findings as leads, not proof. Keep this assessment lightweight. Stronger validation, changed defaults, and new failure cases are contract changes. Fix incidental bugs only within authorized behavior; otherwise report them and continue independent refactoring.

Work in coherent batches, checking affected callers after each:

1. Clarify module boundaries, imports, names, and control flow. Replace check-then-unwrap patterns, opaque inference, and complicated stateful iterator chains where simpler Rust expresses the same operation.
2. Simplify ownership and borrowed inputs where lifetimes remain clear. Remove unnecessary allocation or deep copies without changing evaluation timing, ownership, or resource release.
3. Improve types, error contracts, traits, constructors, accessors, and public API documentation where compatible. Complete related API sets and use derives only when semantics and generic bounds remain equivalent.
4. Review unsafe code, concurrency, macro/code generation choices, initialization, and API evolution. Make only changes whose safety and behavior can be established.

Complete applicable changes throughout scope. Do not add traits, newtypes, crates, generics, dependencies, or compatibility wrappers merely for the checklist. Keep useful application slices/vectors, justified shared ownership, short iterator chains, and established third-party preludes.

## Refactor without changing the product

- Do not apply Chromium's crate layout, import macro, async/thread restrictions, or Google's platform-specific test frameworks to an ordinary Cargo project. Apply a platform rule only in that platform's codebase.
- Check public additions as well as removals: inherent methods and trait implementations can redirect downstream resolution. Preserve bounds, auto traits, dyn compatibility, and lifetime capture; do not blindly add `#[non_exhaustive]`, iterator returns, or derives. Check representative consumers and report incompatible candidates precisely.
- Trace evaluation and drop order when changing iterators, borrows, accessors, or matches. For async code preserve cancellation, ownership/joining of tasks, and state or guards held across `.await`; spawning work is not equivalent to awaiting it.
- Do not mechanically remove poison handling, unwind boundaries, pre-main initialization, required unsafe, or unstable features. Trace their contract first. Prefer a safe equivalent; report necessary departures without adding silent fallbacks or disguising them with lint suppressions.
- Preserve the selected toolchain and MSRV. Do not install nightly, change dependencies, or rewrite CI just to follow a style preference. Do not install, configure, or run formatters, including `rustfmt`, `cargo fmt`, check-only runs, editor actions, hooks, or aggregate commands that invoke them. Inspect task definitions and run permitted constituent checks instead. Preserve local layout; do not substitute formatting/import-sorting lints or manual reflow for a formatter.
- Do not weaken types, safety invariants, tests, or check coverage to get green results. Permit a narrow lint suppression only for a demonstrated false positive. Keep pushes and CI edits within existing authorization; invocation alone does not authorize them.

## Verify and finish

Run focused verification by default, honoring explicit opt-outs and active instructions. Use existing build wrappers and the affected Cargo packages, targets, and supported feature combinations for checking, tests, and Clippy; check public docs/examples when changed. Verify the intended files/features were actually checked. Reuse results only while their relevant code, dependencies, configuration, and environment remain unchanged. Do not assume `--all-features` is valid or run whole-workspace checks without a concrete integration risk.

Favor correctness and substantive performance lints. Do not blanket-enable pedantic, nursery, or restriction groups, force verbosity, or run blanket autofixes. Keep useful existing checks. For unsafe or synchronization edits, establish the pointer, aliasing, lifetime, pinning, and ordering invariants actually affected. Use relevant existing Miri/model-checking/sanitizer gates where available; neither a `SAFETY:` comment nor passing ordinary tests proves soundness. Do not install nightly or alter toolchain pins for this pass.

Exercise affected behavior and callers. Add a test only for an uncovered observable contract or invariant, never code shape. An authorized bug fix needs a failing reproducer followed by a passing result. Use existing representative measurements for performance claims, following repository policy.

Review the final diff for contract changes, weakened checks, suppressions, and unrelated churn. Rescan scope so remaining deviations are deliberate or blocked. Bind results to the final changes: stale checks, empty test selections, or excluded code are not evidence. Missing required proof means unverified/partial, not complete; state the specific gap.

**Report:** scope and rule groups changed with representative symbols; deliberate exceptions and policy conflicts; remaining incompatible changes and the decision each needs; checks run and results, preexisting failures, and checks not run. State whether behavior and public compatibility were preserved, and name any authorized contract changes.
