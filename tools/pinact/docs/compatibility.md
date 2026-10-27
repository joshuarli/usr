# Pinact compatibility

Pinact is a conservative workflow and action metadata checker. It is not a complete implementation
of GitHub's workflow validator. It checks source forms and rule families with closed, testable
semantics and leaves dynamic or unfamiliar values unknown.

## Supported interface

- Python 3.11+ and Git, with the launcher usable under `python3 -I`.
- Legacy pin commands, `pinact run`, `--check`, `--refresh`, and `--allow-branches`.
- `lint` text/JSON output with `correctness`, `default`, and `strict` profiles.
- Explicit TOML catalogs for approval checks and offline fixes.
- `fix` with `--diff`, optional network pin resolution, and explicit policy values.
- Workflow and action YAML parsed with the vendored pure-Python PyYAML 6.0.3 parser.

The syntax and rule limits are listed in the [architecture note](architecture.md) and
[rule reference](rules.md). The parser preserves source positions and edits; it does not rewrite a
workflow by serializing a YAML tree.

## Differential evidence

The [coverage report](../tests/fixtures/coverage.md) records the exact labelled corpus, commands,
denominators, and findings. On 31 selected defects weighted to 63, Pinact detected 63/63 at the
labelled locations under `default`; jactionlint 2.3.0 detected 57/63. Pinact reported zero errors
under both profiles across nine valid workflows, including five copied from repomod's release
fixtures. jactionlint reported errors for the valid dynamic-matrix workflow. The corpus confirms
`fix --diff` leaves all 23 inputs byte-identical.

This result applies only to the checked-in labels and valid fixtures. It does not establish complete
GitHub Actions syntax or security parity. The actionlint and zizmor examples are documentation-based
fixtures; those executables were unavailable and were not independently run. jactionlint's
additional concurrency, expression-type, permission, timeout, and shell findings are listed as
unscored families in the report.

## Known boundaries

- Expressions use a bounded parser and conservative context table. Dynamic matrices and unknown
  action inputs are not treated as statically known values.
- Security rules report recognized source-to-sink paths and known high-risk trigger contexts; they
  do not replace a full security audit.
- Catalog approval proves agreement with the supplied catalog, not the upstream identity of a
  SHA. Unlabeled SHAs are never accepted as catalog proof.
- Fixes are limited to deterministic source-span edits. Ambiguous shell commands, aliases, unsafe
  policy changes, and unsupported YAML forms remain manual work.
- The differential suite is local and offline when jactionlint is installed. Pinact itself does not
  require that executable or an online service.

## Scope

Pinact checks and fixes workflow and action files. Callers such as repomod own fleet policy, the
approved-version catalog, worktrees, commits, and pull requests; Pinact takes a catalog only through
an explicit `--catalog` path and never ships or selects a default.

Out of scope: other Git hosts, CI execution or GitHub API simulation, a complete shell interpreter or
type checker, exhaustive shell taint, full JavaScript analysis, SARIF, LSP, persistent caches or
daemons, plugin or user rule systems, config DSLs, reformatting or reserializing unrelated YAML,
online advisories, registry scanning, remote mutation, pull request creation, and autonomous
updates.
