# Verifier assessment

Use this method when a task changes behavior covered by a local verifier, or when an existing procedure may be stale.

## Check what the procedure proves

Identify the public behavior exercised, implementation boundaries reached, prerequisites, expected results, important rejection or failure cases, and evidence limits. When relevant code changes, compare the procedure's commands, assumptions, fixtures, and expected results with the current implementation and caller contract. A passing old procedure is insufficient when its subject or assumptions changed.

Classify disagreement before changing anything:

- **Procedure drift:** instructions, commands, fixtures, or expected output no longer match the supported contract.
- **Harness limitation:** the required surface or observation cannot be exercised by the available harness.
- **Intentional contract change:** the request or recorded decision authorizes the changed behavior.
- **Product regression:** implementation violates the supported contract.
- **Unavailable prerequisite:** a required tool, service, credential, or environment is missing.

Do not rewrite expected results to conceal a product regression. Keep read-only and plan-only requests read-only and plan-only.

## Exercise the public path

Use the real interface for one meaningful success and one rejection or failure path. If a procedure creates resources, check cleanup, retained useful evidence, and repeatability. For an important invariant, test whether the verifier catches a plausible violation with a controlled broken fixture or disposable mutation when safe and worth the cost. The negative control must fail for the intended reason. Never mutate the user's working tree for this experiment.

For an existing formal model or proof, check that its transitions, atomicity, assumptions, and covered code still match the implementation. State its bounds and exclusions. A model does not prove behavior outside its scope.

## Report the limit

Name the public behavior and boundaries exercised, prerequisites, expected results, negative cases, and evidence limits. Record a last-checked revision only when a maintenance procedure needs it. A revision alone does not show that assumptions match uncommitted changes. Reuse project verifiers; do not add exhaustive feature maps, a general verification framework, or universal provenance records.

**The test:** the verifier exercises the supported interface, rejects a plausible bad result for the right reason when sensitivity matters, and clearly states what it does not establish.

**Report:** behavior covered, path and negative case exercised, drift or regression classification, cleanup and repeatability when relevant, and evidence limits.
