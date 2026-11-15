---
name: deslop
description: "Use for /deslop or a TODO-DESLOP.md ticket whose Fix with is deslop: run one repository's deslop pass (ground, diagnose, types, tests, dead code, findings, report) without losing behavior or performance. Skip repositories without a TODO-DESLOP.md unless the owner names one."
disable-model-invocation: true
metadata:
  opencode/autoinvoke: "false"
---

# Deslop

One repository, worked through its `TODO-DESLOP.md`. The pass makes types truthful, makes tests catch real defects at the boundaries callers touch, removes dead code, and fixes the review's top findings, with nothing the owner relies on lost. The campaign plan is `stuff/docs/campaigns/deslop.md`; this skill is the method its tickets name.

## Rules

- **One agent, one repository.** Take the lowest-numbered open ticket whose area does not start with `Needs owner ·`. After DSLP-5, work open P1 and P2 findings, then fill in `## Report` in the file's header. P3 and P4 stay open.
- **Never edit another repository**, the canonical checkout, or shared fleet files (stuff's `repomod/` and `fleet/`, usr's skills and tools). Report a gap in them under `## Report`.
- **Work in a fresh clone** under `.work/wt/`, with `TMPDIR=$PWD/.work/tmp`, on a branch `deslop/<step>`. One PR per step or finding, labeled `deslop` (`gh label create deslop --color 5319e7 --force` first). Merge it pinned to its head (`--match-head-commit`) when required CI is green and the step's acceptance passed. A docs-only PR may merge when every failing check also fails on the default branch; record that red in DSLP-1.
- **Tickets go through `todo --file TODO-DESLOP.md`.** Owner items take an area starting `Needs owner ·`, never a heading; the Report stays in the header, because `todo` moves trailing text.
- **Preserve behavior.** A behavior-preserving cut lands. Removing live behavior or a public contract (flag, API, format, compatibility path) is a walk-back: file it as a `Needs owner ·` ticket and leave the code. A runtime change a truthful type or test needs ships in its own commit with a test that failed before it.
- **Cause before retry.** A failing step gets two attempts after `root-cause`, then a ticket with the cause.
- No formatters, no pinned-toolchain changes, no releases or publishing, no new dependency the stuff registries do not serve.

## Steps

Each step ends on its acceptance plus `make test` and `make lint`.

1. **Ground.** Time `make test` (cold, warm) and `make lint`; fix reds with an obvious cause, ticket the rest. Add a `## Verification` section to AGENTS.md, at most 25 lines: commands and costs; each public boundary (CLI flags and exit codes, API, file and wire formats, endpoints) with the test that guards it or `none`; the performance workload or `none` with a reason; components for repos over 50k lines; consumers for libraries. Record each vendored tree's upstream URL and revision in an `UPSTREAM` file. *Accept:* CI runs `make test` (`gha-test-workflow` is clean).
2. **Diagnose.** Run `ultrareview`, filing into `TODO-DESLOP.md`. Reproduce a finding against the built product before filing it as a defect. *Accept:* the diff is docs, comments, and the backlog.
3. **Types.** Measure each strict-profile candidate ([tools](references/tools.md)). Adopt a setting only when it rejects a real defect or deletes an escape hatch with at most one false positive per 5k lines; list adopted and rejected settings with counts in the PR. Fix the typing findings per `typing-audit`. *Accept:* clean at the adopted profile, escape hatches not increased, each fixed contract has a witness.
4. **Tests.** Run `make coverage` and a full mutation run (critical modules only when the whole repo exceeds 20 minutes), before and after. Follow `test-audit`: a test for each `none` boundary; one disposition for each unrun decision region and each survivor (killed, equivalent with a reason in the tool's config, unobservable with a reason, dead, or a real defect filed as a finding). Prove each new boundary test with one injected fault. Add `make coverage`, `make mutants-diff`, and the CI lane where the language's tools are mirrored. *Accept:* no undispositioned survivor in critical code; warm `make test` rose at most 20% or 30s.
5. **Dead code.** Run the dead-code tools, then `debloat`; owner decision pre-confirms its cuts, and walk-backs become `Needs owner ·` tickets. Each PR records, per removal, the finding, the entry points, registrations, build and package references and consumers checked, the platforms and features covered, and the consumer tests run. *Accept:* tools clean or allowlisted (at most 5 entries, each with a reason).
6. **Findings.** One PR per open P1 or P2, with its `Fix with` skill. A perf-sensitive repo runs its workload: at least 5 interleaved baseline/candidate pairs of the shipped profile after `perf-gate-ready`; a regression larger than the spread and 2% parks the PR, and a busy host defers it unmerged.
7. **Report.** Run `review` on the cumulative diff from the DSLP-1 base and fix what it demonstrates. Fill in `## Report` ([format](references/tools.md#report)).

## Lessons that hold

- A test that skips when a tool is missing is a false pass: check what CI actually ran, not that it was green.
- Mutation runs find defects coverage and review miss (an unanswered request, a wrong header); read every survivor.
- Assert exact outputs (whole responses, whole JSON) and table-test both directions of a comparison.
- Spawned processes and sockets get deadlines and kill-on-drop; ports come from binding port 0 and reading the bound address, never a pre-picked free port.
- Simplify code that only produces equivalent mutants instead of excluding them.
- Merge only after every check reports success, a non-required lane included; `gh pr checks --watch` returns early while checks are still queued, so poll until none is pending.

**The test:** another agent can read `## Report` and the merged PRs and know what each step found, what it cost, and what still needs the owner.

**Report:** the tickets closed and filed, PRs merged and parked, the Report's numbers, and open `Needs owner ·` items.
