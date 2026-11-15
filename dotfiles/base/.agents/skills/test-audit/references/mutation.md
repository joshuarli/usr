# Mutation testing

A mutant is a small plausible defect: a flipped comparison, a removed call, a constant return. A caught mutant shows that some test's oracle detects that defect. A missed one is a defect the suite would ship. Mutation results are the evidence a suite works; coverage only shows where to look.

Coverage stays a report: replace an existing coverage threshold with the report, and give a test added for coverage the oracle test.

## Tools

- **Rust:** `cargo-mutants`. Use `--in-diff` for changed lines, `--baseline run`, and explicit `--timeout` and `--build-timeout`. Keep exclusions in `.cargo/mutants.toml`, each with its reason. Kache's rustc wrapper shares builds across the copies it makes.
- **Python:** `mutmut`, scoped with its paths to mutate. Use `cosmic-ray` when mutmut cannot drive the suite, for example a custom runner it cannot invoke.
- **TypeScript:** Stryker with its Vitest runner. `--mutate 'src/file.ts:10-40'` scopes a run to lines.

Pin the versions where the project pins its other tools. Instrumented and mutated builds never feed a performance measurement.

## Scope

- **Whole package** when a run fits the scenario budget (about 20 minutes).
- **Critical modules** otherwise: parsing and validation, routing and permission decisions, state transitions, retry and deduplication, persistence, error propagation, serialization.
- **Changed lines** in CI. A diff that changes only tests still selects the production code those tests cover, so deleting or weakening a test cannot pass with zero mutants. A source change that selects zero mutants fails the lane.
- **Rerun** when fixtures, configuration, dependencies, or the toolchain change. An earlier result covers only its inputs.

## Read the results

| Result | Meaning |
| --- | --- |
| Caught | A test failed. Check that it failed on an assertion about the behavior and not on an unrelated crash. |
| Missed | No test noticed. Disposition it. |
| Unviable | The mutant did not build. This is no evidence either way. |
| Timeout | Usually an infinite loop the mutation caused. Confirm it before counting it as caught. |
| Budget exhausted | The run is incomplete. It is never a pass. |

## Disposition every survivor

1. **Assert the behavior** at its owning boundary: the preferred fix. The new assertion must fail on this mutant.
2. **Equivalent:** no input can tell the mutant from the original. Exclude that one mutant, with a reason naming why no output can differ.
3. **Unobservable by construction:** a TTY entry point, or code for a platform the lane does not build. Exclude it narrowly, with the reason, and name where it is tested instead.
4. **Dead:** nothing reaches the code. Hand it to `dead-code-archaeology`.

Never exclude a survivor because the test is hard to write, and never exclude a whole module to silence survivors. Survivors in glue, logging, and display text need no new test. Say so in the report.

## Fault injection

Each new boundary test gets one hand-made fault in the code it protects: a wrong result, a dropped error, an off-by-one at a real boundary, a skipped write, or success reported before the work completes. Confirm the test fails, then revert. Record the fault in the change description. This catches failure modes generic operators miss.

## Report

Give the counts per result, each survivor with its disposition, the exclusions added and their reasons, and the wall time.
