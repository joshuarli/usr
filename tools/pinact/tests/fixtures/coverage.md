# U6 coverage results

The checked-in corpus has 18 files from seven source families and 31 labelled defects. High-risk
security findings weigh 3, workflow-breaking errors weigh 2, and mutable action references weigh 1.
The raw denominator is 31 defects and the weighted denominator is 63. The runner merges correctness
and default profile results by semantic family and source location.

| Defect family | Defects | Weight | jactionlint exact | pinact exact |
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

Pinact detected all 31 expected defects at the labelled source line: 63/63 weighted recall. The
jactionlint comparison missed the checked-in dangerous-trigger and credential-exposure cases; these
are findings outside its current result set for this corpus. It reported the other 29 defects at
the labelled location. Pinact produced 0 correctness errors across the three reviewed valid files;
the jactionlint correctness profile also produced 0/3. The dynamic matrix case is kept separately
because jactionlint reports its `matrix.os` value as an array in an inline expression; Pinact
accepts the dynamic matrix property as unknown at analysis time.

The runner also reports unscored default-profile findings so policy and shell-analysis gaps stay
visible without treating every upstream rule as a Pinact requirement. In this run, jactionlint
reported 13 concurrency, 2 expression-type, 9 missing-permissions, 19 missing-timeout, and 1
pipeline-without-pipefail finding outside the weighted set. Pinact reported one `invalid-matrix`
finding outside the weighted set. These families remain outside this corpus's common-defect gate.

`pinact fix --diff` returned its expected edit status and left all 18 fixtures byte-identical. The
autofix engine's per-edit safety proof remains covered by `tests/test_fix.py`.

Only `jactionlint 2.3.0` was available as an external executable. The actionlint and zizmor source
families use small documented examples; those analyzers were not independently run. Their original
sources and the exact corpus command are listed in [the fixture guide](README.md).
