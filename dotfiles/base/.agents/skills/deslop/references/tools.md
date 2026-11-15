# Deslop tools

Pins live in the repository's own manifests; fleet approvals live in stuff's `fleet/policy/`. Use only what the stuff registries serve, except where a row says to install from upstream into scratch.

## Rust

| Purpose | Tool | Recipe |
| --- | --- | --- |
| Coverage | `cargo-llvm-cov` | `llvm-tools` is already in the fleet toolchain. `cargo llvm-cov --branch --html --output-dir .work/coverage`, then `cargo llvm-cov report --branch --summary-only` (branch coverage works on the pinned nightly). |
| Mutation | `cargo-mutants` 27.1.0 | `cargo mutants --baseline run --timeout 10 --build-timeout 300 --output .work/mutants` (keep the timeout near ten times the suite's run time). Exit 3 means mutants only timed out and none were missed: a hang is detection, so the lane passes on 3 and prints `mutants.out/timeout.txt`. Exclusions go in `.cargo/mutants.toml` `exclude_re`, one comment per entry giving the reason; never a whole module. |
| Mutation lane | `taiki-e/install-action` (approved pin in `fleet/policy/actions.toml`) with `tool: cargo-mutants@27.1.0`; checkout with `fetch-depth: 0`; pass `github.base_ref` through `env`. | `make mutants-diff BASE=origin/$BASE_REF`: `git diff --merge-base` into `.work/mutants/pr.diff`; `--in-diff` when `cargo mutants --list --in-diff` is non-empty, otherwise the whole crate (a test-only diff). |
| Dead code | rustc `dead_code`, `unreachable_pub` in binary crates, `cargo-machete`, then `cargo +nightly udeps` to settle a disputed dependency | |

Strict-profile evidence so far: `unsafe_code = "forbid"` adopted where unsafe was hand-written FFI with a safe std equivalent. Rejected for false positives on idiomatic code: `wildcard_enum_match_arm` (matches on `Ordering`), `cast_possible_truncation` (bounded cursors), `unwrap_used` (infallible `write!` to `String`), `indexing_slicing`, `as_conversions`.

## Python

| Purpose | Tool | Recipe |
| --- | --- | --- |
| Coverage | coverage.py with pytest-cov (mirrored) | Branch coverage, `source` set to the package so unimported files count; `patch = ["subprocess"]` when tests spawn the CLI. pytest-parallel has no coverage support yet: run coverage serially there. |
| Mutation | `mutmut` 3.8.1 (mirrored) | Install from the stuff pypi mirror (`--index-url https://pypi.17166969.xyz/simple`). Copy the repository to `.work/tmp/`, append `[tool.mutmut]` with `source_paths` to the copy's `pyproject.toml`, then run `mutmut run`. cp315 native wheels are mirrored for linux x86_64/aarch64/musl and macOS arm64. |
| Dead code | Ruff `F401`/`F841`, `vulture` 2.16 and `deptry` 0.25.1 (mirrored) | vulture at `--min-confidence 60` for discovery, whitelisting only proven dynamic uses; deptry for unused and missing dependencies. |

Strict-profile evidence so far: ty `missing-type-argument` and `unsound-return-statement` at error (they found bare `dict` reports and `Any` returned as `tuple[str, ...]`), Ruff `ANN401` with tests ignored where helpers build deliberately malformed documents. Rejected: `truthiness-test-of-none-union` (intentional `not value` on `str | None`), `missing-override-decorator`, `TC003`, `FBT`.

## TypeScript

| Purpose | Tool | Recipe |
| --- | --- | --- |
| Coverage | `@vitest/coverage-v8` 5.1.0 (mirrored) | Set `coverage.include` to first-party sources so unimported files count; keep runtime-specific checks (Workers cannot be profiled). |
| Mutation | Stryker 10.1.1 with its Vitest runner (mirrored) | `--mutate 'src/file.ts:10-40'` scopes a run to lines. |
| Dead code | knip 6.45.1 (mirrored) | Resolve its configuration hints first, then run default and `--production` modes. |

Stryker, knip, `@vitest/coverage-v8`, and mutmut are all on the stuff registries (stuff `STUF-83`, 2026-11-15): install them like any other dependency (npm `registry=https://npm.17166969.xyz/current`, pypi `--index-url https://pypi.17166969.xyz/simple`), never from upstream into a scratch copy. A TypeScript or Python repository may add its CI mutation lane from the mirror; each repo decides its scope and timeout like the Rust lane.

## Report

The `## Report` section in the header of `TODO-DESLOP.md`:

- **Scorecard:** before and after for source lines, test lines, warm `make test`, line and branch coverage, mutants caught/missed/timeout/unviable, escape hatches, dead code removed (lines, dependencies), findings filed and fixed by priority, perf verdict, escaped regressions.
- **Per step:** what it found and what it cost (wall time, CI minutes).
- **Method feedback:** a rule that would have caught something that slipped through, a tool that misfired, a step that found nothing.
- **Shared-file gaps:** what stuff or usr would need to change.
