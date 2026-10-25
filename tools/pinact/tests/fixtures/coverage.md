# U6 coverage results

The checked-in corpus has 23 files from eight source families and 31 labelled defects. High-risk
security findings weigh 3, workflow-breaking errors weigh 2, and mutable action references weigh 1.
The raw denominator is 31 defects and the weighted denominator is 63. The score uses Pinact's
`default` profile, which is also the profile repomod consumes.

| Defect family | Defects | Weight | jactionlint default | pinact default |
| --- | ---: | ---: | ---: | ---: |
| Checkout credentials | 7 | 21 | 7/7 | 7/7 |
| Credential exposure | 1 | 3 | 0/1 | 1/1 |
| Dangerous trigger | 1 | 3 | 0/1 | 1/1 |
| Event filter | 2 | 4 | 2/2 | 2/2 |
| Excessive permissions | 1 | 3 | 1/1 | 1/1 |
| Expression syntax | 1 | 2 | 1/1 | 1/1 |
| Needs cycle | 1 | 2 | 1/1 | 1/1 |
| Template injection | 3 | 9 | 3/3 | 3/3 |
| Undefined property | 1 | 2 | 1/1 | 1/1 |
| Unpinned action | 12 | 12 | 12/12 | 12/12 |
| YAML syntax | 1 | 2 | 1/1 | 1/1 |
| **Total** | **31** | **63** | **57/63 weighted** | **63/63 weighted** |

Pinact detected all 31 expected defects at the labelled source line: 63/63 weighted recall in this
selected corpus. jactionlint missed the checked-in dangerous-trigger and credential-exposure cases;
it reported the other 29 defects at the labelled location. This result is not evidence of
fleet-wide parity: the corpus contains 31 selected defects, with 19 in unpinned-action and
checkout-credential cases. Its valid side has nine workflows, five copied from repomod's checked-in
release fixtures, but that remains a small sample.

Pinact reported zero errors under both `correctness` and `default` across all nine valid workflows,
including `custom/dynamic-matrix.yml`. jactionlint reported one correctness error and three default
errors for that valid dynamic matrix, which uses `matrix: ${{ fromJSON(...) }}`. Its other valid
workflows had zero correctness errors. Their default findings ranged from one to six.

The runner reports unscored default-profile findings so policy and shell-analysis gaps stay visible
without treating every upstream rule as a Pinact requirement. In this run, jactionlint reported 13
concurrency, 1 expression-type, 9 missing-permissions, 21 missing-timeout, 2
pipeline-without-pipefail, 1 excessive-permissions, and 6 artipacked findings outside the weighted
set. Pinact reported six unscored checkout-credentials findings on the real release workflows.
These families remain outside this corpus's weighted defect gate.

`pinact fix --diff` returned its expected edit status and left all 23 fixtures byte-identical. The
autofix engine's per-edit safety proof remains covered by `tests/test_fix.py`.

Only `jactionlint 2.3.0` was available as an external executable. The actionlint and zizmor source
families use small documented examples; those analyzers were not independently run. Their original
sources and the exact corpus command are listed in [the fixture guide](README.md).
