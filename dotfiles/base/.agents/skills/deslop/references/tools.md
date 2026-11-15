# Deslop tools

Pins live in the repository's own manifests; fleet approvals live in stuff's `fleet/policy/`. Use only what the stuff registries serve, except where a row says to install from upstream into scratch. A recipe is qualified for a CI lane only after it has run in CI with its negative controls failing for the intended reason; a scratch run qualifies nothing.

**Escape-hatch count** (first-party, non-vendored sources):

- Rust: `rg -c '\bunsafe\b|#!?\[allow\(|\.unwrap\(\)|\.expect\('`
- Python: `rg -c 'cast\(|# type: ignore|# ty: ignore|\bAny\b|# noqa'`
- TypeScript: `rg -Pc '\bas (?!const\b)|\bany\b|@ts-(ignore|expect-error)|(oxlint|eslint)-disable'`

A lower count is evidence only when the claim that replaced each hatch is sound (typing-audit).

## Rust

| Purpose | Tool | Recipe |
| --- | --- | --- |
| Coverage | `cargo-llvm-cov` | `llvm-tools` is already in the fleet toolchain. `cargo llvm-cov --branch --html --output-dir .work/coverage`, then `cargo llvm-cov report --branch --summary-only` (branch coverage works on the pinned nightly). |
| Mutation | `cargo-mutants` 27.1.0 | `cargo mutants --baseline run --gitignore true --timeout 10 --build-timeout 300 --output .work/mutants` (keep the timeout near ten times the suite's run time; without `--gitignore true` the copy recurses into an in-tree `TMPDIR`). Exit 3 means only timeouts: not a pass by itself (see the lane row). Exclusions go in `.cargo/mutants.toml` `exclude_re`, one comment per entry, equivalent mutants apart from accepted risks; never a whole module. |
| Mutation lane | `taiki-e/install-action` (approved pin in `fleet/policy/actions.toml`) with `tool: cargo-mutants@27.1.0`; checkout with `fetch-depth: 0`; pass `github.base_ref` through `env`. | `make mutants-diff BASE=origin/$BASE_REF` runs srv's gate (`scripts/mutants_gate.py`, `.cargo/mutants-gate.toml`; srv#38): it classifies the whole change and selects a union (changed production lines, plus the configured bounded scope for tests, fixtures, configuration and the gate), reads `outcomes.json`, confirms timeouts by rerun, and fails on missing results, empty relevant selection, or budget exhaustion. The bounded scope is measured per repository; never copy a whole-crate scope into a large crate. srv: 235 mutants, 9m43s in CI. loc's critical modules are 916 of 2,433 mutants (about 50 minutes on 4 jobs): too large for one lane job without sharding (`--shard k/n` across a matrix, each shard gated on its own listing). |
| Dead code | rustc `dead_code`, `unreachable_pub` in binary crates, `cargo-machete`, then `cargo +nightly udeps` to settle a disputed dependency | |

Rust candidates: workspace `[lints]` `unsafe_code = "forbid"`; clippy `wildcard_enum_match_arm`, `match_wildcard_for_single_variants`, `cast_possible_truncation`, `cast_sign_loss`, `unwrap_used` and `expect_used` outside tests, `redundant_clone`, `needless_pass_by_value`. Evidence so far: `unsafe_code = "forbid"` adopted where unsafe was hand-written FFI with a safe std equivalent. Rejected for false positives on idiomatic code: `wildcard_enum_match_arm` (matches on `Ordering`), `cast_possible_truncation` (bounded cursors), `unwrap_used` (infallible `write!` to `String`), `indexing_slicing`, `as_conversions`. On loc every candidate was a false positive or had no witness (mmap and SIMD need `unsafe`).

## Python

| Purpose | Tool | Recipe |
| --- | --- | --- |
| Coverage | coverage.py with pytest-cov (mirrored) | Branch coverage, `source` set to the package so unimported files count; `patch = ["subprocess"]` when tests spawn the CLI. pytest-parallel has no coverage support yet: run coverage serially there. |
| Mutation | `mutmut` 3.8.1 from upstream PyPI into a scratch environment (not mirrored: libcst and setproctitle lack wheels for every platform stuff serves) | Copy the repository to `.work/tmp/`, append `[tool.mutmut]` with `paths_to_mutate` to the copy's `pyproject.toml`, then `uv run --locked --with mutmut==3.8.1 --index https://pypi.org/simple mutmut run`. No CI lane until the tool is mirrored. mutmut cannot run through pytest-parallel (the plugin rejects mutmut's in-memory stats collector before workers start); for pytest-parallel consumers set `pytest_add_cli_args = ["-p", "no:parallel"]` and run serially (pytest-parallel#14). |
| Dead code | Ruff `F401`/`F841`, `vulture` 2.16 and `deptry` 0.25.1 (mirrored) | vulture at `--min-confidence 60` for discovery, whitelisting only proven dynamic uses; deptry for unused and missing dependencies. |

Python candidates: ty with every rule at error; Ruff `ANN`, `ANN401`, `PGH003`, `TC`, `B`, `RET`; start from stuff's `pyproject.toml`. Evidence so far: ty `unused-ignore-comment` at error, which turns a `# ty: ignore[code]` on a must-reject program into a checker witness (buildlib `tests/typing_witnesses.py`); ty `missing-type-argument` and `unsound-return-statement` at error (they found bare `dict` reports and `Any` returned as `tuple[str, ...]`), Ruff `ANN401` with tests ignored where helpers build deliberately malformed documents. Rejected: `truthiness-test-of-none-union` (intentional `not value` on `str | None`), `missing-override-decorator`, `TC003`, `FBT`.

## TypeScript

| Purpose | Tool | Recipe |
| --- | --- | --- |
| Coverage | `@vitest/coverage-v8` | Set `coverage.include` to first-party sources so unimported files count; keep runtime-specific checks (Workers cannot be profiled). |
| Mutation | Stryker 10.1.1 with its Vitest runner, from a scratch install | Stryker needs `typescript` and the Vitest runner plugin listed explicitly in its config, even when the repository compiles with another tool. `--mutate 'src/file.ts:10-40'` scopes a run to lines (5s on extensions; its critical parser, storage and URL modules take 657s). Node tests with mocked browser APIs qualify only Node-level logic; extension and browser runtimes need a separate bounded run. |
| Dead code | knip 6.45.1, from a scratch install | Configure the real build entries (Vite inputs, injected scripts) first, then run default and `--production` modes. `--production` ignores test consumers, so its findings are not removal evidence on their own. |

TypeScript candidates: `strict`, `noUncheckedIndexedAccess`, `exactOptionalPropertyTypes`, `noImplicitOverride`, `noPropertyAccessFromIndexSignature`; type-aware Oxlint `no-explicit-any`, `no-unsafe-*`, `no-non-null-assertion`, `no-floating-promises`, `switch-exhaustiveness-check`.

Stryker, knip, and mutmut are not mirrored yet (stuff `STUF-83`): install them from upstream into a scratch copy of the repository under `.work/tmp/`, never into the committed manifests, and add no CI mutation lane for that language until they are mirrored.

## Report

The `## Report` section in the header of `TODO-DESLOP.md`:

- **Scorecard:** before and after for source lines, test lines, warm `make test`, line and branch coverage, mutants caught/missed/timeout/unviable, escape hatches, dead code removed (lines, dependencies), findings filed and fixed by priority, perf verdict, escaped regressions.
- **Per step:** what it found and what it cost (wall time, CI minutes).
- **Method feedback:** a rule that would have caught something that slipped through, a tool that misfired, a step that found nothing.
- **Shared-file gaps:** what stuff or usr would need to change.
