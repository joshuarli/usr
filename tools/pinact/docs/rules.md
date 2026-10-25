# Pinact rule reference

Rule IDs are stable machine-readable identifiers. Findings report a source file, line, column,
severity, message, and whether a supported fixer can address the finding. Profile membership is
closed to the sets below; `--select` can name any known rule ID but does not enable rules omitted
by the chosen profile.

| Rule ID | Description | Severity | Profiles | Fix | Limits |
| --- | --- | --- | --- | --- | --- |
| `yaml-syntax` | YAML cannot be composed safely | error | correctness, default, strict | none | Unresolvable aliases fail closed |
| `duplicate-key` | A mapping repeats a key | error | correctness, default, strict | none | Reports the repeated key location |
| `invalid-type` | A workflow or action field has a disallowed shape | error | correctness, default, strict | none | Only closed schema fields are checked |
| `missing-key` | A required workflow or action field is absent | error | correctness, default, strict | none | Does not infer project-specific values |
| `unknown-key` | A closed schema mapping contains an unknown field | error | default, strict | none | Future or open-ended mappings remain unchecked |
| `invalid-job-id` | A job identifier violates the accepted syntax | error | correctness, default, strict | none | Does not validate third-party action inputs |
| `invalid-needs` | Job dependency is malformed or names no job | error | correctness, default, strict | none | Dynamic job names are not inferred |
| `needs-cycle` | Job dependencies contain a cycle | error | correctness, default, strict | none | Reports the job entry that closes the cycle |
| `invalid-event` | A workflow trigger name is unknown | error | default, strict | none | Only known GitHub event names are accepted |
| `invalid-event-filter` | A trigger uses a filter not supported by that event | error | correctness, default, strict | none | Filter keys are checked against closed event sets |
| `invalid-cron` | A schedule expression is malformed | error | default, strict | none | Schedule timing policy is not evaluated |
| `invalid-matrix` | A statically visible strategy matrix has an invalid shape | error | default, strict | none | Dynamic matrices remain unknown |
| `invalid-permissions` | A permission scope or value is invalid | error | default, strict | none | Dynamic permission expressions are not resolved |
| `invalid-uses` | An action reference uses an unsupported source form | error | correctness, default, strict | none | Local and Docker actions are outside SHA pinning |
| `unpinned-uses` | An external action ref is not a full commit SHA | error | correctness, default, strict | catalog or explicit `--pin` | Pinning checks SHA shape, not upstream provenance |
| `expression-syntax` | An expression cannot be parsed | error | correctness, default, strict | none | Unsupported syntax stays unknown when parsing succeeds |
| `invalid-expression` | A known expression context or operation is invalid | error | default, strict | none | Dynamic values and unknown third-party fields are not errors |
| `undefined-property` | A statically known matrix property is absent or unavailable | error | correctness, default, strict | none | Dynamic matrix keys remain unknown |
| `template-injection` | Untrusted event data is interpolated into a shell command | error | correctness, default, strict | none | Report only; move the value through `env:` and quote it in the shell |
| `checkout-credentials` | Checkout keeps the workflow token available to later commands | warning | default, strict | none | Missing setting uses upstream default `true`; explicit `false` is safe |
| `excessive-permissions` | Workflow or job grants broad write permissions | error | default, strict | none | Proven broad grants only |
| `missing-permissions` | A workflow or job lacks explicit permission policy | warning | strict | explicit `--policy permissions=...` | Pinact does not choose privilege policy |
| `suggest-permissions` | Explicit permission scopes are recommended | warning | strict | explicit `--policy permissions=...` | Recommendation only |
| `suggest-timeout` | A job timeout is recommended | warning | strict | explicit `--policy timeout-minutes=...` | Reusable workflow jobs are excluded |
| `dangerous-trigger` | A high-risk trigger reaches an untrusted execution path | error | default, strict | none | A trusted `workflow_dispatch` alone is not high risk |
| `credential-exposure` | A secret or token reaches an unsafe workflow output | error | default, strict | none | Only recognized source-to-sink paths are reported |
| `deprecated-command` | A shell step uses a retired workflow command | error | default, strict | safe literal rewrites only | Expressions and ambiguous shell syntax remain unchanged |
| `unapproved-pin` | A pinned or versioned action is not approved by the supplied catalog | error | default, strict | approved catalog pin | An unlabeled SHA is not proof of approval |

The `correctness` profile includes syntax, structural errors, unpinned action refs, proven
expression errors, and template injection. `default` adds schema and security policy findings.
`strict` adds explicit permission and timeout recommendations. Catalog findings require
`--catalog`; catalog selection is never implicit.

## Safe fixes

`pinact fix` only edits findings with a deterministic source-span rewrite:

| Finding | Method | Conditions |
| --- | --- | --- |
| `unpinned-uses` | Replace the ref with the approved full SHA and version annotation | Explicit catalog, or network opt-in with `--pin` |
| `deprecated-command` | Write literal values to the matching GitHub environment file | Only recognized literal shell forms |
| `missing-permissions` / `suggest-permissions` | Insert an explicit permission block | Caller supplies a read-only `--policy` value |
| `suggest-timeout` | Add a job timeout | Caller supplies `--policy timeout-minutes=N` |

`--diff` shows the plan without writing. Other rules have no automatic fix. Unsafe spans, aliases,
symlinks, edits that fail lint validation, and changes that are not idempotent are refused.
