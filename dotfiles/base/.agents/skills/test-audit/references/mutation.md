# Mutation testing

A mutant is a small injected change: a flipped comparison, a removed call, a constant return. A caught mutant shows that some test's oracle distinguishes that change. A missed one shows the tests did not; it may expose a missing assertion, an incidental detail, an equivalent program, or an unsuitable harness, and it is not by itself a defect in the original program. Mutation results are evidence of test sensitivity; coverage only shows where to look.

The unit of value is an important behavior newly protected, with the reason it matters, or a real defect fixed. Several mutants exposing one missing assertion are one finding. Never add tests only to raise a kill count.

Coverage stays a report: replace an existing coverage threshold with the report, and give a test added for coverage the oracle test.

## Tools

- **Rust:** `cargo-mutants`. Use `--in-diff` for changed lines, `--baseline run`, and explicit `--timeout` and `--build-timeout`. Keep exclusions in `.cargo/mutants.toml`, each with its reason. Kache's rustc wrapper shares builds across the copies it makes.
- **Python:** `mutmut`, scoped with its paths to mutate. Use `cosmic-ray` when mutmut cannot drive the suite, for example a custom runner it cannot invoke.
- **TypeScript:** Stryker with its Vitest runner. `--mutate 'src/file.ts:10-40'` scopes a run to lines.

Pin the versions where the project pins its other tools. Instrumented and mutated builds never feed a performance measurement.

## Scope

Separate what a required check enforces from what an audit investigated, and report them apart.

- **Required (blocking):** a small, demonstrated scope around an important contract: archive admission, cache integrity, atomic publication, success and failure reporting, cleanup, authorization decisions. Name the contracts and measure the run before a lane depends on it.
- **Bounded investigation:** targeted mutation of a risky change or a suspected gap.
- **Advisory, explicitly invoked:** module or package sweeps, extra operators, wider platform matrices. Their survivors inform tickets; they do not block a pass.
- **Budget.** A new or expanded trial gets 10 aggregate runner-minutes across all jobs, shards, platforms and retries. Exceed it only for a named important unresolved behavior, with a finite experiment and its expected value. Run platform-specific behavior on its platform and portable mutation once. After two successive bounded trials that protect no distinct important behavior, stop expanding and record the disposition.
- **The whole change in CI.** Classify every changed path, deletions and renames included, and print the class of each:
  - production code mutates its changed lines, and the whole file when those lines select nothing;
  - tests, fixtures, generated inputs, manifests, lockfiles, features, toolchain and build configuration, and the mutation gate and its exclusions select the configured critical scope, never a whole package;
  - documentation alone is an explicit irrelevant pass.

  Selection is a union, never a fallback: a PR that deletes or weakens a test and also changes unrelated production code still mutates the critical scope that test protected.
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

## Disposition survivors by behavior

Group survivors by the behavior they expose and classify each group: a defect reproduced in the unmodified program, a meaningful test gap, an equivalent, redundant, cosmetic or low-priority variation, or a harness, environment or infrastructure failure. In a required scope every survivor needs one of the dispositions below. In an advisory sweep, record the groups and act on the meaningful gaps. Private temporary-name prefixes, equivalent defaults and incidental diagnostic text get one line, not a test, unless a consumer depends on them.

1. **Assert the behavior** at its owning boundary: the preferred fix for a meaningful gap. The new assertion must fail on this mutant.
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

Give the counts per result beside the exclusions (equivalent and accepted risk, counted separately), each survivor with its disposition, and the evidence: base and candidate SHA, the exact command, tool version and configuration, platform and features, scope (required or advisory), wall time, and aggregate runner-minutes.
