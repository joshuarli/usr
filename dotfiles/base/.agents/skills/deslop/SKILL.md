---
name: deslop
description: "Use for /deslop or a TODO-DESLOP.md ticket whose Fix with is deslop: run one repository's deslop pass (ground, diagnose, types, tests, dead code, bench, findings, report) without losing behavior or performance. Skip repositories without a TODO-DESLOP.md unless the owner names one."
disable-model-invocation: true
metadata:
  opencode/autoinvoke: "false"
---

# Deslop

One repository, worked through its `TODO-DESLOP.md`. The pass makes types truthful and tests catch real defects at caller boundaries, removes dead code and fixes top findings, losing nothing the owner relies on. The deslop campaign's section in the coordinating repository's `docs/roadmap.md` holds only scope, decisions, sequencing and status.

## Rules

- **One agent, one repository.** Take the lowest-numbered open ticket whose area does not start with `Needs owner ·`. After DSLP-5, run Bench as its own ticket, then open P1 and P2 findings, then fill in `## Report` in the header. P3 and P4 stay open.
- **Never edit another repository**, the canonical checkout, or shared fleet files (stuff's `repomod/` and `fleet/`, usr's skills and tools). Report a gap in them under `## Report`.
- **Work in a fresh clone** under `.work/wt/`, with `TMPDIR=$PWD/.work/tmp`, on a branch `deslop/<step>`. One PR per step or finding, labeled `deslop` (`gh label create deslop --color 5319e7 --force` first). Merge it pinned to its head (`--match-head-commit`) when required CI is green and the step's acceptance passed. A docs-only PR may merge when every failing check also fails on the default branch; record that red in DSLP-1.
- **Tickets go through `todo --file TODO-DESLOP.md`.** Owner items take an area starting `Needs owner ·`, never a heading; the Report stays in the header, because `todo` moves trailing text.
- **Preserve behavior.** A behavior-preserving cut lands. Removing live behavior or a public contract (flag, API, format, compatibility path) is a walk-back: file it as a `Needs owner ·` ticket and leave the code. A runtime change a truthful type or test needs ships in its own commit with a test that failed before it.
- **Revalidate a ticket before implementing it.** Its proposed model or fix is a hypothesis: read the code it names, keep behavior the ticket did not see (an open-ended value, a supported state), and split concerns it conflated.
- **Cause before retry.** A failing step gets two attempts after `root-cause`, then a ticket with the cause.
- **No evidence files.** Step evidence goes in the PR body, open work in `TODO-DESLOP.md` or `TODO.md`. `docs/` is durable project documentation; fold a lasting conclusion into the topic doc it concerns.
- No formatters, no pinned-toolchain changes, no releases or publishing, no new dependency the stuff registries do not serve.

## Steps

Each step ends on its acceptance plus `make test` and `make lint`.

1. **Ground.** Time `make test` (cold, warm) and `make lint`; fix reds with an obvious cause, ticket the rest. Add a `## Verification` section to AGENTS.md, at most 25 lines: commands and costs; each public boundary (CLI flags and exit codes, API, file and wire formats, endpoints) with the test that guards it or `none`; the performance workload or `none` with a reason; components for repos over 50k lines; consumers for libraries. Record each vendored tree's upstream URL and revision (an existing `UPSTREAM`, `NOTICE`, or `upstream.json` counts). Correct stale seeded facts. When Types, Tests, or Dead code is too large for one PR, rewrite DSLP-3 to DSLP-5 as bounded component tasks, each naming its contracts, affected consumers, and acceptance command; do not expand the rest of the backlog. *Accept:* CI runs `make test` in a supported shape (`gha-test-workflow` is clean).
2. **Diagnose.** Run `ultrareview`, filing into `TODO-DESLOP.md`. Reproduce a finding against the built product before filing it as a defect. *Accept:* the diff is docs, comments, and the backlog.
3. **Types.** Measure each strict-profile candidate ([tools](references/tools.md); candidates only, not `refactor-*` refactors). Adopt a setting only when it rejects a real defect or deletes an escape hatch with at most one false positive per 5k lines; list adopted and rejected settings with counts in the PR. Fix the typing findings per `typing-audit`. *Accept:* clean at the adopted profile, escape hatches not increased, each fixed contract has a witness.
4. **Tests.** Run a `test-pyramid` audit first: record its tiers and costs in `## Verification` and fix false passes. Then run `make coverage` and a bounded mutation run of the critical contracts, before and after; wider sweeps are advisory. Follow `test-audit` and its [mutation reference](../test-audit/references/mutation.md) for scope and budget: a test for each `none` boundary; survivors grouped by behavior, each critical group dispositioned (asserted, equivalent with a reason in the tool's config, unobservable, dead, or a defect filed). Prove each new boundary test with one injected fault. Add `make coverage`, `make mutants-diff`, and a CI lane for the critical scope where the tools are mirrored and the recipe qualified ([tools](references/tools.md)). *Accept:* no undispositioned survivor in the required scope; warm `make test` rose at most 20% or 30s.
5. **Dead code and simplification.** Run the dead-code tools, then [simplify](../simplify/SKILL.md) within the ticket's scope, reusing the campaign's verification evidence. Proposals to remove supported behavior become `Needs owner ·` tickets. Each PR records the complexity removed, the entry points, registrations, build and package references and consumers checked, the platforms and features covered, and the consumer tests run. *Accept:* tools clean or allowlisted (at most 5 entries, each with a reason).
6. **Bench.** Run `bench-pyramid`, filing its ranked gaps here. Where benchmarks exist, add its entrypoint, proven at Edit and one Change workload; never run Full. *Accept:* audit in `## Report`; entrypoint proven, or no benchmarks with the outcome list.
7. **Findings.** One PR per open P1 or P2, with its `Fix with` skill. A perf-sensitive repo runs its workload: at least 5 interleaved baseline/candidate pairs of the shipped profile. On a quiet host, a regression larger than the spread and 2% parks the PR. On a busy host, use [busy-host evidence](../../instructions/performance.md#busy-host-evidence): merge when the paired or scaling ratios decide the claim, and record any undecided absolute number as deferred.
8. **Report.** Run `review` on the cumulative diff from the DSLP-1 base and fix what it demonstrates. Fill in `## Report` ([format](references/tools.md#report)).

## Before merging a runtime-affecting slice

A Types, Tests, Dead code, or Findings PR that changes what runs:

- **Contracts:** name the public contracts it affects (flags, exit codes, API, formats, endpoints), or none.
- **Consumers:** run each affected consumer's tests against the candidate, with evidence that it loaded the candidate (the path or override and the resolved revision it printed), not its released pin.
- **Performance:** run the declared workload's gate when the change touches its path.
- **Evidence:** base and candidate SHA, exact commands, tool versions and configuration, platform and features, scope, result classes, and cost, compactly in the PR body.

Missing evidence leaves the PR unmerged. A purely static or documentary change records "unaffected" with its reason instead. A later check-up never replaces it.

## Lessons that hold

- Mutation finds gaps coverage and review miss; count behaviors protected, not kills.
- Assert exact outputs; table-test both directions of a comparison.
- Spawned processes and sockets get deadlines and kill-on-drop; tests bind port 0.
- Simplify code that only produces equivalent mutants instead of excluding them.
- The completion review earns its cost (on srv it found unbounded connection threads no test or mutant saw). Test resource bounds wherever a change adds concurrency.
- PRs target the default branch; some are `master`.
- Merge when every required check has succeeded; advisory lanes are evidence, not gates. `gh pr checks --watch` can return early.

**The test:** another agent can read `## Report` and the merged PRs and know what each step found, what it cost, and what still needs the owner.

**Report:** the tickets closed and filed, PRs merged and parked, the Report's numbers, and open `Needs owner ·` items.
