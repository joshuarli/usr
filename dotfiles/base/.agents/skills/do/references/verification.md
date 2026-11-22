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

For a guard against a recurring defect, use the historical negative and positive controls and acceptance evidence in [recurring failures](../../audit-skills/references/failures.md#prove). A plausible injected fault is useful sensitivity evidence, but does not establish that a past incident was replayed.

## Formal models

For a new or existing model, name the invariant and its independent source, modeled states and transitions, atomicity boundaries, failure assumptions, and exploration bounds. For a progress claim, state the fairness assumptions; a safety check does not prove eventual completion.

Replay the historical bad transition or interleaving in the buggy model and require a counterexample to the intended invariant. The repaired model must satisfy that same invariant within the stated bounds. Keep the bad variant or trace reproducible so a weakened model or checker cannot silently turn the negative control green. For a new invariant without a past incident, use a labeled synthetic violation and make no historical-replay claim.

Connect model transitions to concrete implementation operations, including transaction boundaries, storage semantics, retries, cancellation, and external effects that matter to the claim. Replay the trace against the real implementation where practical, or exercise a corresponding contract test. State any missing connection: a passing abstract model alone does not prove the code correct. Keep implementation tests, including security and legal behavior guards, under [test-audit](../../test-audit/SKILL.md).

When the covered code changes, check that mapping and the model's assumptions before reusing evidence; a changed lock, transaction, timeout, or retry policy can invalidate it without changing model files. Run the smallest affected model and implementation checks. Record the checker/version, command, bounds, result, and cost with the existing acceptance evidence. Missing tooling, timeouts, skipped properties, or incomplete exploration leave the relevant claim unverified; never report them as a pass. Follow the caller's authority for dependencies, CI, and expensive runs.

## Report the limit

Name the public behavior and boundaries exercised, prerequisites, expected results, negative cases, and evidence limits. Record a last-checked revision only when a maintenance procedure needs it. A revision alone does not show that assumptions match uncommitted changes. Reuse project verifiers; do not add exhaustive feature maps, a general verification framework, or universal provenance records.

**The test:** the verifier exercises the supported interface, rejects a plausible bad result for the right reason when sensitivity matters, and clearly states what it does not establish.

**Report:** behavior covered, path and negative case exercised, drift or regression classification, cleanup and repeatability when relevant, and evidence limits.
