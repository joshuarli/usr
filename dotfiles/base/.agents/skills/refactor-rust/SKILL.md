---
name: refactor-rust
description: "Refactor Rust code according to Google's Rust Style Guide. Use only when explicitly requested by name or for a Google-style Rust refactor."
disable-model-invocation: true
metadata:
  opencode/slash: "true"
  opencode/autoinvoke: "false"
---

# Refactor Rust

Implement a coherent refactor using the [Google Rust Style Guide](https://google.github.io/styleguide/rustguide.html), including API and implementation design. Improve the code itself; an audit or a formatter/linter pass alone does not complete actionable work. If the code already conforms or every candidate is a justified exception or contract conflict, report the evidence and unresolved departures without manufacturing edits.

Use the requested paths or crates. For an unqualified invocation, use the current Rust workspace's first-party code. Include affected callers and tests; exclude vendored code and generated outputs. If the scope contains no Rust code, report that and stop.

## Establish the contract

- Read applicable instructions, the working diff, manifests, toolchain/MSRV, feature and target configuration, build scripts, relevant callers, tests, and existing verification commands. Preserve unrelated work.
- Distinguish reusable library APIs from application internals. Google's API rules are binding guidance for reusable libraries; application code should favor directness over generalized interfaces.
- Read the [rule checklist](references/google-rust-guide.md) before editing. Consult its upstream links for applicable rules and exceptions, using current upstream wording when available. If the site is unavailable, use the bundled snapshot and disclose that limitation.
- Apply the user's request and active repository instructions before style preferences. In particular, respect policies on formatting, comments, toolchain pins, dependencies, and verification. Report material conflicts instead of silently rewriting those policies.
- Preserve observable behavior and compatibility unless a change is already authorized: public API paths/signatures and trait contracts, serialization and FFI layout, CLI output and exit status, errors and panic policy, ordering, side effects, resource lifetime, lock scope, and performance-sensitive behavior. Internal APIs may change with their callers.
- Run the narrowest relevant baseline checks, or record why they cannot run. Separate preexisting failures from regressions.

## Survey, then refactor

Survey the entire requested scope against the checklist. For each candidate, identify the concrete code, the applicable rule, any exception, and the callers or invariants that constrain the change. Use searches and Clippy findings as leads, not proof. Distinguish changes to implement, justified exceptions, and changes blocked by a contract or unavailable evidence; keep this working assessment lightweight.

Work in coherent batches, checking affected callers after each:

1. Clarify module boundaries, imports, names, and control flow. Replace check-then-unwrap patterns, opaque inference, and complicated stateful iterator chains where simpler Rust expresses the same operation.
2. Simplify ownership and borrowed inputs where lifetimes remain clear. Remove unnecessary allocation or deep copies without changing evaluation timing, ownership, or resource release.
3. Improve types, error contracts, traits, constructors, accessors, and public API documentation where compatible. Complete related API sets and use derives only when semantics and generic bounds remain equivalent.
4. Review unsafe code, concurrency, macro/code generation choices, initialization, and API evolution. Make only changes whose safety and behavior can be established.

Complete all applicable changes in scope; do not stop after the first easy file. Do not create traits, newtypes, crates, generic APIs, dependencies, or compatibility wrappers merely to satisfy a checklist. Preserve useful exceptions such as simple application slices/vectors, justified shared ownership, short iterator chains, and established third-party preludes.

## Refactor without changing the product

- Do not apply Chromium's crate layout, import macro, async/thread restrictions, or Google's platform-specific test frameworks to an ordinary Cargo project. Apply a platform rule only in that platform's codebase.
- Do not blindly rename published constructors, change return types to iterators, add `#[non_exhaustive]`, alter generic bounds, or replace custom trait behavior with derives. These can break users despite looking like style changes. Implement compatible improvements and report incompatible candidates precisely; ask only when the unresolved decision prevents requested work.
- A lazy iterator can change when errors or side effects happen. A borrow, closure accessor, or match rewrite can change drop order or how long a lock is held. Check these properties explicitly where affected.
- Do not mechanically remove poison handling, unwind boundaries, pre-main initialization, required unsafe, or unstable features. Trace their contract first. Prefer a safe equivalent; report necessary departures without adding silent fallbacks or disguising them with lint suppressions.
- Preserve the selected toolchain and MSRV. Do not install nightly, change dependencies, or rewrite CI just to follow a style preference. Do not install, configure, or run formatters, including `rustfmt`, `cargo fmt`, check-only runs, editor actions, hooks, or aggregate commands that invoke them. Inspect task definitions and run permitted constituent checks instead. Preserve local layout; do not substitute formatting/import-sorting lints or manual reflow for a formatter.
- Keep commits and pushes within the session's existing authorization; invoking this skill alone does not authorize publishing changes.

## Verify and finish

Use the project's existing focused commands and build wrappers. For Cargo projects, select the affected packages, targets, and supported feature combinations for `cargo check`, `cargo test`, and `cargo clippy` as appropriate. Run doctests/rustdoc checks when public docs or examples change. Do not assume `--all-features` is valid or expand to whole-workspace builds without a concrete integration risk. Favor correctness and substantive performance lints; do not blanket-enable Clippy's pedantic, nursery, or restriction groups. Retain relevant existing correctness checks, but avoid new lints that demand verbosity, redundant annotations, or stylistic churn. Review selected lint fixes; do not run blanket autofixes.

Exercise the affected behavior and callers. Add a regression test only for an uncovered observable contract or invariant; do not add tests that assert code shape. For meaningful performance-sensitive changes, use existing representative benchmarks or allocation/size checks and the repository's measurement policy. Do not claim a performance improvement without measurements.

Review the final diff for unrelated edits, accidental public API or behavior changes, weakened tests, new suppressions, and dependency or lockfile churn. Re-scan the requested scope so remaining deviations are deliberate, blocked, or outside scope. Report unavailable checks as limitations, not passes.

**Report:** scope and rule groups changed with representative symbols; deliberate exceptions and policy conflicts; remaining incompatible changes and the decision each needs; checks run and results, preexisting failures, and checks not run. State whether behavior and public compatibility were preserved, and name any authorized contract changes.
