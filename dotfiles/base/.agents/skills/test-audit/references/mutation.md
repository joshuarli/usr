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
- **Critical modules** otherwise: parsing and validation, routing and permission decisions, state transitions, retry and deduplication, persistence, error propagation, serialization. Name them and measure the run before a lane depends on them.
- **The whole change in CI.** Classify every changed path, deletions and renames included, and print the class of each:
  - production code mutates its changed lines, and the whole file when those lines select nothing;
  - tests, fixtures, generated inputs, manifests, lockfiles, features, toolchain and build configuration, and the mutation gate and its exclusions select the configured critical scope;
  - documentation alone is an explicit irrelevant pass.

  Selection is a union, never a fallback: a PR that deletes a test and also changes unrelated production code still mutates the scope that test protected. Never copy a whole-crate fallback into a large repository without measuring it.
- **Rerun** when fixtures, configuration, dependencies, or the toolchain change. An earlier result covers only its inputs. When the scope changes between two runs, reconcile the counts before comparing them.

## Read the results

| Result | Meaning |
| --- | --- |
| Caught | A test failed. Check that it failed on an assertion about the behavior and not on an unrelated crash. |
| Missed | No test noticed. Disposition it. |
| Unviable | The mutant did not build. This is no evidence either way. |
| Timeout | Rerun it with a longer timeout. Still hanging is a confirmed hang and counts as detection; an unconfirmed timeout is unresolved and fails. |
| Budget exhausted | The run is incomplete. It is never a pass. |
| Selection error, unexpected empty selection, missing or unreadable results | The gate cannot say what ran. Each fails. |

A gate that converts a tool's exit status into success without reading its results has no evidence. A change to the gate runs the gate's own negative fixtures, so a green lane cannot mean "nothing selected".

## Disposition every survivor

1. **Assert the behavior** at its owning boundary: the preferred fix. The new assertion must fail on this mutant.
2. **Equivalent:** no input can tell the mutant from the original. Exclude that one mutant, with a reason naming why no output can differ. A public lookup table is not equivalent: test it against independently specified expected values (a registry, a spec), never against the function's own output, and do not call that test vacuous.
3. **Unobservable by construction:** a TTY entry point, or code for a platform the lane does not build. Exclude it narrowly, with the reason, and name where it is tested instead.
4. **Dead:** nothing reaches the code. Hand it to `dead-code-archaeology`.

A case-only path variant can resolve to the original file on a case-folded volume.
Record that filesystem behavior and replay the identity on a supported
case-sensitive host when one ships. [FFmpeg stage fixtures](https://github.com/laputa-systems/ffmpeg-build/pull/71) ·
[CMake native sandbox trial](https://github.com/laputa-systems/cmake-build/actions/runs/44469636774)

An **accepted risk** is observable behavior deliberately left unprotected. List it apart from equivalent mutants, with who accepted it and why. Never exclude a survivor because the test is hard to write, and never exclude a whole module to silence survivors. Survivors in glue, logging, and display text need no new test. Say so in the report.

## Fault injection

Each new boundary test gets one hand-made fault in the code it protects: a wrong result, a dropped error, an off-by-one at a real boundary, a skipped write, or success reported before the work completes. Confirm the test fails, then revert. Record the fault in the change description. This catches failure modes generic operators miss.

## Report

Give the counts per result beside the exclusions (equivalent and accepted risk, counted separately), each survivor with its disposition, and the evidence: base and candidate SHA, the exact command, tool version and configuration, platform and features, scope, and wall time.
