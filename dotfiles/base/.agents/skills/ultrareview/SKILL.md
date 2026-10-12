---
name: ultrareview
description: "Use for /ultrareview: a thorough review of one whole repository that refreshes its docs to match the code and writes a prioritized REVIEW.md. A router to the other skills, not a restatement of them."
disable-model-invocation: true
---

# Ultrareview

One repository in, two deliverables out: docs that match the code, and a single `REVIEW.md` of the few things most worth fixing. This skill only routes. The method for each topic lives in the skill named for it, so load that skill and use its tests and proof standard. Use the skills for review only: report what they find and do not run their edit steps. The only files you change are documentation and comments.

## Rules

- **The scope is the repo you are in,** not its dependencies or deployment. Name what you did not cover.
- **The code is the truth.** When docs and code disagree, fix the doc. If the code is what is wrong, leave it and file a finding.
- **Big picture only.** A finding must change what the owner does: a correctness, security, data, reliability, delivery, or maintainability risk, or something that slows every future change. No style, naming, formatting, or anything a linter would catch, unless the missing check is the finding. Most repos yield 8 to 20 findings; none is a valid result.
- **No finding without evidence:** a `file:line` you read or a command you ran. Never invent a caller, API, or version.
- **Explicit-only skills are not in your skill list.** Most lens skills are of this kind. Load one by reading `~/.agents/skills/<name>/SKILL.md`, and tell every lane you spawn to do the same.
- **Follow the repo's instructions.** Read its AGENTS.md first and obey its verification limits. Run the cheapest existing check once for a baseline and say what it was; report before starting anything expensive. No formatters, no commits, no pushes.

## Steps

1. **Orient.** Read AGENTS.md, README, manifests, CI config, any existing `REVIEW.md`, and recent `git log --stat` for churn. Find entry points, boundaries, how it is tested, built, released, and run, then take the baseline.
2. **Review** through the lenses below. On a repo too big to hold in your head, use `orchestrate`: one read-only lane per group of rows, each returning candidate findings in the entry shape and nothing else. Merge findings that share a root cause and rank them.
3. **Prove the top.** Before a P1 or P2 stands, prove the fact it depends on with the `blast-radius` ladder and say which rung you reached. Check any measured claim with `benchmark-checklist`. A finding you cannot prove is marked `unproven` or downgraded.
4. **Refresh the docs** (below).
5. **Write `REVIEW.md`** (below).
6. **Check.** `git diff --stat` shows only docs, comments, and `REVIEW.md`. Every claim you kept in a doc traces to code that exists. Every finding has a priority, a recommendation, and a `Fix with`.

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
| Tests | `test-audit` | Judge the strategy and sample the riskiest areas; do not audit every test. Do the tests guard the contracts that matter? |
| Performance | `performance-by-mechanism` | Is there removable work on the hot paths? |
| Dead weight | `dead-code-archaeology` | Dead code, finished flags, legacy paths: prove liveness. |
| Navigability | `make-code-search-a-reliable-navigation-boundary` | Does text search reach definitions, callers, tests, and docs? |
| Recurring mistakes | `correct` | Which defect classes recur in history and have no guard? |

No skill covers these, so ask directly: security beyond input handling (authn and authz, secrets in the tree or history, injection); build, release, and CI (reproducible, pinned, can it ship and roll back); dependencies (abandoned, duplicated, unpinned, heavy); operability (can an operator see a failure, configure the system, and recover).

## Docs refresh

- **Inventory every doc surface:** README, AGENTS.md and CLAUDE.md, `docs/`, contributing notes, `--help` text, config examples, doc comments.
- **Check each claim against the code:** commands, paths, flags, environment variables, versions, architecture, setup steps. Run the cheap ones. Fix what drifted and delete what is not worth keeping.
- **Make it shorter.** Cut what is outdated, duplicated, or restates what the code shows. Give each fact one home and link to it rather than copy it. Keep the why, constraints, invariants, commands, and hazards. Do not reword for taste.
- **AGENTS.md** holds commands, layout, and the conventions and hazards a newcomer cannot read from the code. It does not repeat the global instructions. Keep an existing AGENTS.md and CLAUDE.md arrangement.
- **Comments** go through `comment-cleanup`.
- **Leave dated records alone** (changelog, ADRs, release notes), marking a superseded one rather than rewriting it. For generated docs, edit the source, not the output.
- **One writer,** so edits do not overlap. Create no doc file besides `REVIEW.md` unless something essential has no home.

## REVIEW.md

Write it at the repo root, replacing any previous copy: drop findings that are fixed and re-verify the ones that remain. Use exactly this shape.

````markdown
# Review: <repo>

Reviewed `<short sha>` on <date>. Scope: <what>. Checks run: <command and result>. Not covered: <what>.

## Summary

<3 to 5 sentences: overall health, and the one or two themes behind most findings.>

| P1 | P2 | P3 | P4 |
| --- | --- | --- | --- |
| <n> | <n> | <n> | <n> |

## Findings

### R1 · P1 · <title naming the problem>

- **Area:** Architecture | Types | Config | Errors | Concurrency | Data | Security | Tests | Performance | Dead code | Navigability | Build | Dependencies | Operability | Docs
- **Where:** `path:line`, ...
- **Problem:** what is wrong, how it fails, who is hit, and the evidence. For P1 and P2, the proof rung reached or `unproven`.
- **Recommendation:** the smallest change that removes the cause.
- **Fix with:** the skill that carries out the recommendation, or `none`.
- **Effort:** S (hours) | M (days) | L (weeks)

## Open decisions

<Choices only the owner can make that block a finding, each with options and a recommendation. Omit if none.>

## Strengths to keep

<2 to 4 designs or guards a future change should not erode.>
````

Order findings by priority, then by impact. Rate by impact times likelihood, never by effort.

- **P1, fix now:** data loss or corruption, a security exposure, silently wrong results, or a broken build, release, or recovery path, on a reachable path.
- **P2, fix soon:** a real defect or structural risk that will cause incidents or tax every change, likely but not yet hit.
- **P3, plan:** a clear payoff at scale and no urgency.
- **P4, optional:** a few at most, and only if cheap. Drop it if it is a nitpick.

**The test:** the owner can hand any finding to its `Fix with` skill tomorrow without more investigation, and a newcomer can follow the docs without meeting a stale command.

**Reply:** the docs files changed or removed and what was cut; finding counts by priority with the P1 titles; checks run and not run; open decisions.
