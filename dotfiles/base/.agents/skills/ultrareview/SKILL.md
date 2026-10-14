---
name: ultrareview
description: "Use for /ultrareview: a thorough review of one whole repository that refreshes its docs to match the code and files prioritized findings as tickets and RFCs. A router to the other skills, not a restatement of them."
disable-model-invocation: true
---

# Ultrareview

One repository in, two deliverables out: docs that match the code, and tickets in `TODO.md` (with RFCs where a design or a decision needs sign-off) for the few things most worth fixing. This skill only routes. The method for each topic lives in the skill named for it, so load that skill and use its tests and proof standard. Use the skills for review only: report what they find and do not run their edit steps. The only files you change are documentation, comments, `TODO.md`, and RFCs.

## Rules

- **The scope is the repo you are in,** not its dependencies or deployment. Name what you did not cover.
- **The code is the truth.** When docs and code disagree, fix the doc. If the code is what is wrong, leave it and file a finding.
- **Big picture only.** A finding must change what the owner does: a correctness, security, data, reliability, delivery, or maintainability risk, or something that slows every future change. No style, naming, formatting, or anything a linter would catch, unless the missing check is the finding. Most repos yield 8 to 20 findings; none is a valid result.
- **No finding without evidence:** a `file:line` you read or a command you ran. Never invent a caller, API, or version.
- **Follow the repo's instructions.** Read its AGENTS.md first and obey its verification limits. Run the cheapest existing check once for a baseline and say what it was; report before starting anything expensive. No formatters, no commits, no pushes.

## Steps

1. **Orient.** Read AGENTS.md, README, manifests, CI config, the open tickets in `TODO.md`, and recent `git log --stat` for churn. Find entry points, boundaries, how it is tested, built, released, and run, then take the baseline.
2. **Review** through the lenses below. On a repo too big to hold in your head, use `orchestrate`: one read-only lane per group of rows, each told which lens skill files to read and returning candidate findings in the `todo` ticket shape and nothing else. Run lanes as `worker`, and as `scout` for pure inventory such as the build, CI, and dependency row. A lane with a named method and a lens skill is a `worker` task however large the code. Use `expert` only for a lane that reasons about crash consistency, races, or `unsafe` soundness where a wrong call is costly, and state why in the lane brief. Merge findings that share a root cause and rank them.
3. **Prove the top.** Before a P1 or P2 stands, prove the fact it depends on with the `blast-radius` ladder. Check any measured claim with `benchmark-checklist`. A finding you cannot prove is marked `unproven` or downgraded.
4. **Refresh the docs** (below), after the review, so dead code you found is not documented.
5. **File the findings** (below).
6. **Check.** `git diff --stat` shows only docs, comments, `TODO.md`, `docs/rfc/`, and deleted completed campaign docs, and nothing durable in them was lost. Every claim you kept in a doc traces to code that exists. Every finding has a priority, a recommendation, and a `Fix with`.

## Lenses

| Aspect | Skill | Ask at repo scale |
| --- | --- | --- |
| Boundaries and public API | `api-surface-and-module-boundaries` | Is the surface wider than the contract? Do dependencies run one way? |
| Domain model | `make-invalid-states-unrepresentable` | Do the core types admit states the domain forbids? |
| Duplicated facts, config | `single-source-of-truth` | Which facts, defaults, and limits live in several places? |
| Effects and testability | `isolate-effects` | Is decision logic tangled with I/O, clocks, and environment? |
| Errors | `error-model` | Are failures typed, propagated, and mapped consistently, or swallowed? |
| Concurrency, lifecycle | `lifecycle-concurrency` | Leaked tasks or processes, unbounded queues, retries, shutdown? |
| Persisted state | `durable-state` | Can the schema or wire format evolve safely? Who writes concurrently? |
| Untrusted input, OS | `os-boundaries` | Paths, symlinks, temp files, platform code, `unsafe`? |
| Tests | `test-audit`, `renovate-tests` | Judge the strategy and sample the riskiest areas; do not audit every test. Judge against the suite shape `renovate-tests` defines. |
| Performance | `make-it-fast` | Is there removable work on the hot paths? |
| Dead weight | `dead-code-archaeology` | Dead code, finished flags, legacy paths: prove liveness. |
| Navigability | `make-code-search-a-reliable-navigation-boundary` | Does text search reach definitions, callers, tests, and docs? |
| Comments | `comment-cleanup` | Which comments excuse a workaround or claim a constraint nothing enforces? Each is a finding about that code, and the spreading ones are the worst. |
| Recurring mistakes | `correct` | Which defect classes recur in history and have no guard? |

No skill covers these, so ask directly: security beyond input handling (authn and authz, secrets in the tree or history, injection), which gets a short pass unless the repo has auth, secrets, multi-tenant data, or network exposure, and a hard look when it does; build, release, and CI (reproducible, pinned, can it ship and roll back); dependencies (abandoned, duplicated, unpinned, heavy); operability (can an operator see a failure, configure the system, and recover).

## Docs refresh

Run `docs-refresh` over the whole repo, with one writer. Where it finds the code wrong rather than the doc, that becomes a finding. `TODO.md` and `docs/rfc/` are the only doc files you create. Comments follow `comment-cleanup` in its review mode, and its findings take the area of the code they excuse.

The docs lane runs one `mdtool check` when installed; it combines all checks with grouped output and anchor suggestions. Use `--untracked` for new docs and `--since HEAD` for new findings after edits. Request `--verbose` or `--json` only for complete occurrence details; `mdtool anchors FILE...` is only for a heading inventory. Without it, follow the fallback searches in `docs-refresh` and inspect targets manually.

Then roll up campaigns. For each `docs/CAMPAIGN-*.md` whose header status says it is complete, and whose deliverables you confirm in the code, move what a future reader needs (the design rationale, invariants, constraints, and decisions still in force) into the durable docs (README, AGENTS.md, or `docs/` topic files), stated in domain terms with no campaign names or IDs. Then delete the campaign doc and any `DECISIONS.md` entries it owned. Do not keep logs of what was completed or per-item histories; git history is the record. Leave campaigns that are active, paused, or winding down untouched, and file a finding for a "complete" one whose deliverables are not in the code.

## Findings

File each finding as a `todo` ticket in `TODO.md`, in that skill's shape, priority definitions, and ID rules. Order tickets by priority, then impact. Rate by impact times likelihood, never by effort.

- **Tickets already open** are re-verified, not duplicated: delete one that is fixed, update one that drifted, and keep its ID. A new finding takes the next ID.
- **A finding that needs a design or an owner's call** gets a draft RFC under `docs/rfc/`, linked from its ticket. Choices only the owner can make, each with options and a recommendation, belong in the RFC's Open questions.
- **The reply carries what a ticket cannot:** scope, the baseline check, what was not covered, a 3 to 5 sentence summary naming the one or two themes behind most findings, and 2 to 4 designs or guards a future change should not erode.

**The test:** the owner can hand any finding to its `Fix with` skill tomorrow without more investigation, and a newcomer can follow the docs without meeting a stale command.

**Reply:** the docs files changed or removed (including campaign docs rolled up and where their content went) and what was cut; finding counts by priority with the P1 titles and the ticket and RFC IDs filed; checks run and not run; open decisions.
