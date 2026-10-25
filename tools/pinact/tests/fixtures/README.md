# Differential corpus

Run from the repository root:

```sh
mkdir -p .work/tmp
PYTHONDONTWRITEBYTECODE=1 TMPDIR="$PWD/.work/tmp" python3.13 -I tools/pinact/tests/corpus.py
```

The runner compares `jactionlint` and the in-tree `pinact` on the same files with both the
`correctness` and `default` profiles. `jactionlint` is optional; when installed, it provides a
differential result. The runner makes no network requests and checks that `pinact fix --diff`
leaves every input file byte-identical.

The corpus has seven source families:

| Family | Source |
| --- | --- |
| `usr` | The repository's `.github/workflows/test.yml` |
| `repomod` | `repomod`'s main workflow and two release workflow fixtures |
| `repomod-real` | Five release workflows copied from repomod's binary-release policy fixtures |
| `catalog` | The local `laputa-systems/rg` release workflow |
| `actionlint` | A small event-filter typo based on [actionlint checks](https://github.com/rhysd/actionlint/blob/main/docs/checks.md) |
| `jactionlint` | The correctness example from the [jactionlint README](https://github.com/jdx/jactionlint/blob/main/README.md) |
| `zizmor` | Template-injection and checkout-credential cases based on the [zizmor audit reference](https://docs.zizmor.sh/audits/) |
| `custom` | YAML, expression, dependency, permission, trigger, credential, and safe-dynamic cases |

The upstream-derived examples are small adaptations, not copied upstream test trees. The
`repomod-real` files preserve workflows from repomod's checked-in binary-release fixtures. The local
machine has `jactionlint 2.3.0`; `actionlint` and `zizmor` are not installed, so those two upstream
analyzers are represented by fixtures and are not reported as independently executed.

Each expected defect is labelled by file, line, semantic family, and weight in `corpus.py`. The
weighted defect score uses `default`, the consumer profile. Findings match by semantic family rather
than message text or rule name. The weight is 3 for high-risk security defects, 2 for
workflow-breaking errors, and 1 for mutable action references. Extra findings and families are
printed as unscored; the corpus does not treat an analyzer's rule set as ground truth.

See [coverage](coverage.md) for the checked-in denominators and results.
