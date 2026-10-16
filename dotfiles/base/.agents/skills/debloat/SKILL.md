---
name: debloat
description: "Use for /debloat: a deep review of a repo, path, or change that weighs each mechanism's cost against what it buys, and finds what to delete, inline, merge, or walk back (dead code, speculative layers, config, dependencies, tests, tooling, docs, CI steps). Reports ranked findings, then applies the ones the owner confirms. The restrained sibling of ultrareview. Skip performance work, hardening, new features, and bug hunting."
disable-model-invocation: true
---

# Debloat

Find what can go without costing what the project needs. This is `ultrareview` pointed at one question: what is here that a reader must carry and the behavior does not need? It routes to the skills below and shares the `todo` skill's ticket shape and P1 to P4 definitions. Findings come first and edits come only after the owner confirms the list.

Dead code is the cheapest bloat to find and the least valuable. The point of this review is **over-engineering**: mechanisms whose cost exceeds their benefit, even though they are live, tested, and documented. A pass that returns only dead code, stale entries, and unreferenced files has swept one lens of ten and is not finished.

## Rules

- **Scope is the one named:** a path, a change set, or the repo when nothing is named. Name what you did not cover.
- **Subtract, never add.** A finding removes, inlines, merges, or narrows. It does not introduce an abstraction, a config knob, a dependency, a test, a check, or a CI step. A recommendation that grows the code is not a finding.
- **Weigh cost against benefit, not liveness against deadness.** Every mechanism has a cost (lines, files, concepts, indirection, tests, docs, upkeep, steps to run) and a benefit (a behavior a user depends on, an invariant the repo declares, a gate it enforces, a second case that exists today). A live mechanism whose benefit is smaller than its cost is a finding. State both sides in the ticket.
- **Two tiers of finding.**
  - **Cut:** behavior, errors, and public contracts stay. The owner can approve it by reading one diff.
  - **Walk-back:** removes a live mechanism, layer, harness, feature, or test suite whose benefit does not justify its cost. It may change observable behavior or a contract, or take more than one diff. It is a decision, not a refactor: state what is lost, who would notice, and what replaces it (often nothing). The owner decides each one. Never fold a walk-back into a cut.
- **No optimization.** Do not propose faster, leaner, or more concurrent code. A removal that also helps speed is fine; the speed is a footnote, not the reason. Use `make-it-fast` only when asked.
- **No hardening.** Do not propose more validation, retries, logging, error types, or defensive checks. Pre-existing correctness bugs get one line in the reply and no ticket unless the simplification depends on them.
- **Measure the win.** Every finding states what goes: lines, files, concepts, dependencies, or steps a reader no longer holds. If the saving is small or the risk exceeds it, drop it.
- **Size is a pointer, not a finding.** A large file or long function is a finding only when you can name what in it goes. Weight tells you where to look; it never proves a cut. Never recommend a split, a rename, or a reorganization, only removal.
- **Owner decisions stand.** Invariants and gates the repo's AGENTS.md or docs declare, and open `TODO.md` tickets and RFCs, are not findings. A removal that touches one is dropped, or raised as a question to the owner. A ticket that is already fixed is a removal. A declared gate stays; a harness nothing reaches for it does not.
- **Evidence for every finding:** a `file:line` you read. For removals, proof of liveness from `dead-code-archaeology`; for walk-backs, the callers, the second implementation that does or does not exist, and the test or doc that depends on it. Never invent a caller or a benefit.
- **Nothing changes before confirmation.** Steps 1 to 5 are read-only. Apply only what the owner confirmed, and nothing you found afterward.
- **Follow the repo's instructions.** Read its AGENTS.md. Run the cheapest existing check once for a baseline. No formatters, no commits, no pushes.

## Steps

1. **Orient.** Read AGENTS.md, README, manifests, open `TODO.md` tickets, and `git log --stat` for churn. Find the entry points and the tests that cover them. Take the baseline. Inventory three ways:
   - lines by directory, to see where the weight is;
   - reachability, meaning which scripts, harnesses, fixtures, and docs a build target, package script, test, or other doc actually names;
   - ratios: test lines to code lines per subsystem, docs to code, tooling to product.

   Weight and ratios point the sweep, and reachability proves a cut; none is a finding alone. Use `git log -1 --format=%cs -- PATH` to find areas untouched for a long time.
2. **Map the mechanisms.** List the subsystems and, for each, its moving parts: layers, modules, registries, adapters, state machines, queues, caches, config options, protocols, versioning schemes, retry or recovery paths, harnesses, report generators, procedures. For each, write one line: what it buys and who depends on it today. Anything you cannot fill in is a candidate. This map is the working material for step 3; do not skip to the lenses.
3. **Sweep** every lens below over the scope, reading the code, not only grepping. Dead-code lenses are cheap and go first; the **structural** lenses (marked below) are the point and always run. On a scope too big to hold, use `orchestrate`: one read-only `worker` lane per subsystem, not per lens, so the lane sees one subsystem's cost and benefit together. Brief each lane with the subsystem's mechanism map entries, every lens and its skill, and ask for candidates in the ticket shape with cost, benefit, tier, and evidence, and nothing else. Use `expert` for a lane whose subsystem is a cross-cutting design.
4. **Prove the top.** A cut that deletes something stands only after you show nothing depends on it, with the `blast-radius` ladder. A walk-back stands only after you name what is lost and show it is smaller than what goes. Mark what you cannot prove `unproven` or drop it.
5. **Rank** by reader load removed times confidence, never by effort. Cap each tier at ten. Merge findings that share a root cause. Do not let cheap cuts crowd out walk-backs: if the sweep found structural candidates, at least the strongest must appear. An empty list is valid only when every structural lens was swept and the reply says so.
6. **Confirm.** Present the ranked findings and stop. Edit nothing before the owner answers. They may accept all, pick some, or drop some. File to `TODO.md` only what they defer.
7. **Apply** the confirmed findings, one logical change each, in rank order. Run the narrowest check that covers each, and revert a removal that breaks one and report it. A removal that turns out to need a contract change the owner did not approve stops and goes back to the owner. No formatters, no commits, no pushes.

## Lenses

Lenses marked **structural** find live mechanisms that cost more than they buy. Each asks the same questions: what does this buy, who needs it today, and what is the cheapest thing that would do?

| Aspect | Skill | Ask |
| --- | --- | --- |
| Dead weight | `dead-code-archaeology` | Dead code, finished flags, compatibility paths with no consumer left: prove liveness, then delete. |
| Duplicated facts | `single-source-of-truth` | Which defaults, limits, and closed sets are copied and can collapse to one? |
| **Layers** (structural) | `api-surface-and-module-boundaries` | Wrappers, controllers, stores, services, and adapters with one caller or one implementation? Modules that only forward? State moved between objects that could stay put? Interfaces, event buses, or registries where a direct call would do? Follow one user action from entry to effect and count the hops that each add nothing. |
| **Speculation** (structural) | none | Config knobs, options, hooks, plug-in points, feature flags, and versioning schemes with one value or one implementation in use? Abstractions built for a second case that never came? Generality (generic types, strategy objects, pluggable backends) where the code has one case? |
| **Machinery** (structural) | none | Subsystems heavier than the problem: custom caches, queues, recovery or reconciliation engines, state machines, protocol layers, derived-state pipelines, and journals. What failure does each prevent, how likely is it, and would a simpler design (do it inline, drop the cache, recompute, fail loudly) be acceptable? Only the repo's declared invariants make a mechanism mandatory. |
| **Features** (structural) | none | Features, endpoints, commands, settings, and UI affordances that nothing in the product docs, tests, or recent history depends on? Behavior built for hypothetical users? |
| Dependencies | none | Does the standard library or a few lines replace it? Is it used for one call? Is a vendored copy mostly unused? |
| **Tests** (structural) | `test-audit`, `renovate-tests` | Which tests duplicate another, assert trivia, mirror the implementation, or are smoke tests no behavior depends on? Which narrow tests fold into one wider test? Test-only seams in production code? Fixtures, mocks, and harnesses larger than what they exercise? |
| **Tooling and process** (structural) | none | Which scripts, benchmark and report harnesses, drills, recorded results, hashes, manifests, and generated or vendored files nothing reaches or a reader does not need? Which run steps, make targets, and gates cost more to run than the failure they catch? Does one script use a different runtime from its siblings for no reason? Which suppression or lint-allow entries no longer match any code? A gate the repo declares stays; an unreachable harness for it does not. |
| CI | none | Which steps and jobs repeat a local check, guard nothing, or have never caught a failure? Report for deletion only. |
| Comments | `comment-cleanup` | Which comments excuse code that should be fixed or deleted? |
| Docs | `technical-writing` | Which docs restate the code or each other? Which describe machinery that is cut? Which backlog or ticket entries are already done? |

Skip `error-model`, `lifecycle-concurrency`, `durable-state`, `os-boundaries`, and `make-it-fast`: they find things to add or tune, which is not this review's question. When a mechanism exists because of one of those concerns, read them to learn what it buys, not to add to it.

## Findings

Use the `todo` ticket shape, with these additions:

- **Tier:** `cut` or `walk-back`.
- **Cost:** what goes (for example "removes 140 lines, one dependency, and two concepts").
- **Benefit lost:** `none` for a cut. For a walk-back, the behavior, guarantee, or convenience that goes, and who would notice.
- **Fix with:** the skill that applies the removal.
- **Safe because:** the one fact that makes a cut safe, or the reason a walk-back's loss is acceptable.

**The test:** the owner can confirm the list and the code will be smaller, and every walk-back's loss is named and judged worth it. Nothing on the list asks for more code, more tests, or more CI.

## Reply

**Before confirmation:** the scope and baseline check; findings by tier and priority with cost and benefit lost for each; a coverage line listing every lens swept and every lens or subsystem not swept, with the reason; the mechanisms you judged worth their cost, in one line each, so the owner sees the review weighed them and did not skip them; and open questions.

If the list holds only cuts, say which structural lenses came up empty and why, rather than presenting the list as the whole review.

**After applying:** what was removed with the lines, files, or dependencies gone, the checks run per change and not run, findings reverted or deferred, and open decisions.
