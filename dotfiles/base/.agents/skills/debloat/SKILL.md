---
name: debloat
description: "Use for /debloat: a review of a repo, path, or change that finds reasonable simplifications (code, layers, config, dependencies, tests, CI steps to delete or collapse), reports them, and applies the ones the owner confirms. The restrained sibling of ultrareview. Skip performance work, hardening, new features, and bug hunting."
disable-model-invocation: true
---

# Debloat

Find what can go without changing what the code does. This is `ultrareview` pointed at one question: what is here that a reader must carry and the behavior does not need? It routes to the skills below and shares the `todo` skill's ticket shape and P1 to P4 definitions. Findings come first and edits come only after the owner confirms the list.

## Rules

- **Scope is the one named:** a path, a change set, or the repo when nothing is named. Name what you did not cover.
- **Subtract, never add.** A finding removes, inlines, merges, or narrows. It does not introduce an abstraction, a config knob, a dependency, a test, a check, or a CI step. A recommendation that grows the code is not a finding.
- **Behavior stays.** The change must keep observable behavior, errors, and public contracts. If it cannot, it is a contract change: say so, and let the owner decide.
- **Reasonable means a quick, confident review.** Prefer a finding the owner can approve by reading one diff. Skip a rewrite, a redesign, a cross-cutting migration, and anything that needs a new framework to land.
- **No optimization.** Do not propose faster, leaner, or more concurrent code. A removal that also helps speed is fine; the speed is a footnote, not the reason. Use `make-it-fast` only when asked.
- **No hardening.** Do not propose more validation, retries, logging, error types, or defensive checks. Pre-existing correctness bugs get one line in the reply and no ticket unless the simplification depends on them.
- **Measure the win.** Every finding states what goes: lines, files, concepts, dependencies, or steps a reader no longer holds. If the saving is small or the risk exceeds it, drop it.
- **Size is not bloat.** A large file, long function, or big test file is a finding only when you can name what in it goes. Never recommend a split, a rename, or a reorganization.
- **Owner decisions stand.** Invariants and gates the repo's AGENTS.md or docs declare, and open `TODO.md` tickets and RFCs, are not findings. A removal that touches one is dropped, or raised as a question to the owner. A ticket that is already fixed is a removal.
- **Evidence for every finding:** a `file:line` you read and, for removals, proof of liveness from `dead-code-archaeology`. Never invent a caller.
- **Nothing changes before confirmation.** Steps 1 to 4 are read-only. Apply only what the owner confirmed, and nothing you found afterward.
- **Follow the repo's instructions.** Read its AGENTS.md. Run the cheapest existing check once for a baseline. No formatters, no commits, no pushes.

## Steps

1. **Orient.** Read AGENTS.md, README, manifests, open `TODO.md` tickets, and `git log --stat` for churn. Find the entry points and the tests that cover them. Take the baseline. Then inventory two ways: lines by directory, to see where the weight is, and reachability, meaning which scripts, harnesses, fixtures, and docs a build target, package script, test, or other doc actually names. Weight points the sweep and reachability proves the cut; neither is a finding alone. Use `git log -1 --format=%cs -- PATH` to find areas untouched for a long time.
2. **Sweep** the lenses below over the scope. On a scope too big to hold, use `orchestrate`: one read-only `worker` lane per group of rows, each told which lens skill to read and returning candidates in the ticket shape and nothing else.
3. **Prove the top.** A finding to delete something stands only after you show nothing depends on it, with the `blast-radius` ladder. Mark what you cannot prove `unproven` or drop it.
4. **Rank** by reader load removed times confidence, never by effort. Cap the list at ten. Merge findings that share a root cause. An empty list is a valid result.
5. **Confirm.** Present the ranked findings and stop. Edit nothing before the owner answers. They may accept all, pick some, or drop some. File to `TODO.md` only what they defer.
6. **Apply** the confirmed findings, one logical change each, in rank order. Run the narrowest check that covers each, and revert a removal that breaks one and report it. A removal that turns out to need a contract change stops and goes back to the owner. No formatters, no commits, no pushes.

## Lenses

| Aspect | Skill | Ask |
| --- | --- | --- |
| Dead weight | `dead-code-archaeology` | Dead code, finished flags, compatibility paths with no consumer left: prove liveness, then delete. |
| Duplicated facts | `single-source-of-truth` | Which defaults, limits, and closed sets are copied and can collapse to one? |
| Layers | `api-surface-and-module-boundaries` | Wrappers with one caller, adapters with no second implementation, exports nobody imports? |
| Speculation | none | Config knobs, options, and hooks with one value in use? Abstractions built for a second case that never came? |
| Dependencies | none | Does the standard library or a few lines replace it? Is it used for one call? |
| Tests | `test-audit`, `renovate-tests` | Which tests duplicate another, assert trivia, or are smoke tests that no behavior depends on? Which narrow tests fold into one wider test? |
| Tooling | none | Which scripts, benchmark and report harnesses, drills, and generated or vendored files nothing reaches? Does one script use a different runtime from its siblings for no reason? Which suppression or lint-allow entries no longer match any code? A gate the repo declares stays; an unreachable harness for it does not. |
| CI | none | Which steps and jobs repeat a local check, guard nothing, or have never caught a failure? Report for deletion only. |
| Comments | `comment-cleanup` | Which comments excuse code that should be fixed or deleted? |
| Docs | `technical-writing` | Which docs restate the code or each other? Which backlog or ticket entries are already done? |

Skip `error-model`, `lifecycle-concurrency`, `durable-state`, `os-boundaries`, and `make-it-fast`: they find things to add or tune, which is not this review's question.

## Findings

Use the `todo` ticket shape with `Fix with` naming the skill that applies the removal. Each ticket carries the removal it buys (for example "removes 140 lines and one dependency") and the one fact that makes it safe.

**The test:** the owner can confirm the whole list and the code will be smaller and no less correct, and nothing on it asks for more code, more tests, or more CI.

**Reply:** before confirmation, the scope and baseline check, findings by priority with what each removes, and what was not covered. After applying, what was removed with the lines, files, or dependencies gone, the checks run per change and not run, findings reverted or deferred, and open decisions.
