# Deslop scanner observations

The scan covers `tools/`, `src/`, and `host/`. Vendored PyYAML is excluded from the owned-code dead-code count. Tool invocations use scratch caches and add no project dependencies.

## Types

The existing `ty.toml` enables error-level rules. `uvx ty check tools src host` with ty 0.0.107 reports 634 diagnostics, including 422 `missing-attribute`, 57 `missing-type-argument`, 36 `missing-union-attribute`, and 30 `invalid-argument-type` diagnostics. With Python 3.15 explicitly selected and vendored PyYAML excluded, 175 first-party diagnostics remain. Triage is incomplete. Enabling every rule for measurement reports 806 diagnostics: the extra results include 63 `missing-override-decorator`, 84 `truthiness-test-of-none-union`, and 26 `redundant-condition-strict`. No extra rule was adopted.

Ruff 0.17.6 candidate scans reported: `ANN` 1,610, `ANN401` 4, `PGH003` 0, `TC` 14, `B` 18, and `RET` 1. The `B` diagnostics all concern the already excluded `B905`. `TC` includes ordinary standard-library import placement. No new Ruff rule was adopted without a defect witness and false-positive assessment.

The bridge core TypeScript profile already has `strict` enabled. The pinned tsrs checker and Node types were installed in scratch. The core profile reports zero diagnostics. Adding `noUncheckedIndexedAccess`, `exactOptionalPropertyTypes`, `noImplicitOverride`, and `noPropertyAccessFromIndexSignature` reports 178, 13, 0, and 749 diagnostics respectively. No new setting was adopted. The full bridge profile requires its documented development install and was not checked. First-party matching lines containing Python and TypeScript escape-hatch patterns are 75 and 201 respectively, including tests.

## Dead code

Ruff `F401,F841` reports no findings. Vulture 2.16 reports 133 owned-tree findings at 60 percent confidence. Many are framework callbacks, unittest discovery, record fields, or overrides. Knip 6.45.1 reports seven unused files in default mode and 23 in production mode. The latter mode excludes test consumers. Both include dynamic entries and cannot establish that these files are dead. The `debloat` command is unavailable in this environment.

Two private pinact helpers, `_mark_line_col` and `_is_falsy_str`, had no tracked source references across the repository. They had no CLI entry points, registrations, build references, or platform branches. The pinact security fixture suite passed after their removal. Other scanner findings remain untriaged; this is not a clean or allowlisted scan.
