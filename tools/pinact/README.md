# pinact

`pinact` pins GitHub Actions references, checks workflows, and applies a limited set of safe fixes.
`sh sync` installs its launcher at `~/.local/bin/pinact`. It needs Python 3.11+ and Git. The
runtime is self-contained: it has no required config file, package installation, site-packages
import, compiled extension, GitHub API, or token.

```sh
pinact
pinact --check
pinact --refresh
pinact --allow-branches
pinact run --check
pinact lint --profile=correctness --format=json
pinact lint --format=json --catalog "$CATALOG" -- "$WORKFLOW"
pinact fix --catalog "$CATALOG" -- "$WORKFLOW"
pinact fix --diff --policy timeout-minutes=15 -- "$WORKFLOW"
```

Set `CATALOG` to an approved TOML catalog and `WORKFLOW` to the workflow file you want to check or
fix. The first five commands are the common pinning and offline check entry points.

Without filenames, commands discover tracked and untracked, non-ignored workflow and action
metadata files in the current Git checkout. Explicit paths can be used outside a Git checkout.
Pin resolution uses batched `git ls-remote`; lint and fix with an explicit catalog are offline.
`fix --pin` opts into network resolution when no catalog is supplied. A catalog is never selected
implicitly.

## Pinning

External `uses: owner/repo[/path]@ref` values become full commit SHAs with version comments.
Annotated tags resolve to their peeled commit SHA. A tag/branch name collision fails rather than
guessing, and branches require `--allow-branches`. `--refresh` only re-resolves existing SHA
references through their explicit version comments; it does not select a newer semantic version.
Use Renovate or an explicit version change to select an upgrade.

The pinner preserves comments, quoting, indentation, line endings, and file modes. Local `./` and
`docker://` actions are skipped. It ignores `uses:` keys in non-action fields and shell blocks.
Unsupported flow-style action mappings and unsupported `uses` values fail closed. It scans all
files and resolves all refs before writing. Writes use atomic replacement; a Git or input error
leaves the source unchanged.

Pinning checks establish that a reference is a full SHA, not that the SHA came from a trusted
upstream or matches a catalog. Use `lint --catalog` to check approval and `fix --catalog` to pin
only to approved versions.

## Linting

```sh
pinact lint [--profile=correctness|default|strict] [--format=text|json]
            [--select=id,...] [--catalog path] [files ...]
```

JSON output is an array of records with `filepath`, `line`, `column`, `id`, `severity`, `message`,
and `fixable`. Results have deterministic file/line/column/rule ordering. JSON mode writes no
progress text to stdout. Exit status is 0 when clean, 1 when findings remain, and 2 for invalid
usage or operational errors. `--select` accepts any known rule ID; selecting a known rule disabled
by the chosen profile can return no findings. An unknown rule ID returns status 2.

`correctness` reports syntax and proven workflow errors, including invalid event filters, bad
matrix properties, and template injection. `default` adds policy and schema checks. `strict` adds
permission and timeout recommendations. See the [rule reference](docs/rules.md) for IDs, severities,
profiles, fixes, and limits.

`--catalog path` validates the TOML catalog and reports references not approved by it. Catalog
records use `[actions."owner/repo"]` tables with `channel`, `version`, and a 40-character `sha`.
They reject malformed records, ambiguous repositories, major changes, unlabeled SHAs as proof, and
catalog downgrades. The catalog remains caller-owned policy.

## Fixing

`fix` makes conservative source-span edits for approved action pins, literal obsolete workflow
commands, and explicit `--policy` requests. It does not infer permission or timeout policy. For
example, `--policy permissions=contents:read` adds a read-only permission block, and
`--policy timeout-minutes=15` adds a job timeout. Privilege-adding or ambiguous policy edits are
refused. `--diff` prints a unified diff and never writes.

The fixer checks that planned edits match the original bytes, do not overlap, introduce no new
correctness errors, resolve their targeted finding, and are idempotent. It preserves unrelated
bytes and refuses symlinks, changed files, unsafe edit shapes, and unsupported inputs. See the
[architecture note](docs/architecture.md) for the parse and edit flow.

## Development

The source lives in `src/pinact/`; the launcher resolves this tree through the `sh sync`
links and runs under `python3 -I`. Pinact vendors pure-Python PyYAML 6.0.3 under
`src/pinact/_vendor/yaml/`; its MIT license and source details are in `PROVENANCE.txt`.

Run the focused suites from the repository root:

```sh
mkdir -p .work/tmp
PYTHONDONTWRITEBYTECODE=1 TMPDIR="$PWD/.work/tmp" python3.13 -I tools/pinact/test_pinact.py
PYTHONDONTWRITEBYTECODE=1 TMPDIR="$PWD/.work/tmp" python3.13 -I tools/pinact/tests/test_yaml.py
PYTHONDONTWRITEBYTECODE=1 TMPDIR="$PWD/.work/tmp" python3.13 -I tools/pinact/tests/test_lint_rules.py
PYTHONDONTWRITEBYTECODE=1 TMPDIR="$PWD/.work/tmp" python3.13 -I tools/pinact/tests/test_expressions.py
PYTHONDONTWRITEBYTECODE=1 TMPDIR="$PWD/.work/tmp" python3.13 -I tools/pinact/tests/test_security.py
PYTHONDONTWRITEBYTECODE=1 TMPDIR="$PWD/.work/tmp" python3.13 -I tools/pinact/tests/test_fix.py
```

The differential corpus and its limits are described in the [coverage report](tests/fixtures/coverage.md).
See the [compatibility report](docs/compatibility.md) for the supported workflow surface and
known gaps.
