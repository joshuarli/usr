---
name: standardize
description: "Use for /standardize [standard...] [path...]: bring a repository, or the named paths, up to every applicable coding standard in ~/.agents/standards, including each standard's adoption work on whole-repository runs. Skip one-change checks; the completion gate covers those."
disable-model-invocation: true
metadata:
  opencode/slash: "true"
  opencode/autoinvoke: "false"
---

# Standardize

Bring code up to the coding standards in `~/.agents/standards/`. Each standard owns its rules: `## Code` for how code must look, `## Adoption` for repository-wide tool, floor, and migration work. This skill owns the process of applying them safely. Preserve behavior and public contracts unless their change is authorized. Upgrades or lint alone do not complete actionable work. A justified no-op is valid; make no edits to look busy.

## Scope and authority

- **Choose the standards.** Named standards (`standards list` shows them) select exactly those. Without names, run `standards select --tree` in the repository and take every standard it lists. Read each chosen standard in full before editing.
- **Choose the code.** Named paths limit the scope; an unqualified invocation covers the repository's first-party code. Include affected callers and existing tests; exclude vendored code and generated outputs. If no code in scope matches a chosen standard, report that and stop.
- **Adoption needs a whole-repository run.** An unqualified run applies `## Code` throughout scope and the `## Adoption` work: runtime floors, tool pins and profiles, stack migrations. A path-limited run applies only `## Code`, keeps the declared floor and existing tools, and reports missing gates instead of adding pins, raising floors, or migrating the repository.
- **The owner's instructions win.** Apply the request and repository instructions before a standard's preferences, and report a material conflict instead of rewriting policy. Use the upstream and versioned sources a standard names; when they are unavailable, use installed evidence and state the limitation. Preserve unrelated work. Invoking this skill does not authorize deploying, CI edits, or running formatters.

## Inspect the contract

Read applicable instructions, the working diff, manifests and lockfiles, toolchain and runtime targets, entrypoints, exports, callers, schemas, tests, and verification commands, plus anything a standard's `### Inspect` adds. Distinguish application internals from published APIs and framework contracts. Preserve the contracts each standard lists. Run the narrowest relevant baseline checks, or record why they cannot run, and separate preexisting failures from regressions.

Survey the entire scope. For each batch, identify the concrete improvement, the rule or exception that applies, the invariant it preserves, and the smallest check that could expose a regression. Searches and lint findings are leads, not proof. Stronger validation, changed defaults, and new failure cases are contract changes. Fix incidental bugs only within authorized behavior; otherwise report them and continue.

## Work in coherent passes

- Run a standard's adoption work that changes owners, such as a runtime floor, a type checker, or a package manager, before its code passes, and replace each old responsibility with its new owner before deleting the old one. Follow the order in each standard's `### Passes` where it has one.
- Check affected callers after each batch, and update callers, public documentation, and tests together. Complete the requested scope, not only the first easy file. Keep narrow, evidenced exceptions where a rule cannot express a sound contract; do not add abstractions, dependencies, or compatibility wrappers merely to satisfy a checklist.
- When standards or components touch disjoint files, they may run as parallel lanes under `orchestrate`. Name the standard file in each brief, and integrate and review each lane yourself.

## Verify and finish

Run each applied standard's `### Verify` checks on the final diff. Never weaken types, schemas, validators, or check coverage to get green results; suppress only a demonstrated false positive at the smallest scope with its reason. Exercise changed behavior and callers, and measure any performance claim.

Review the final diff for contract changes, weakened checks, suppressions, and unrelated churn, and rescan scope so every remaining deviation is deliberate or blocked. Stale checks, empty test selections, and excluded code are not passes. State any missing proof as a specific gap.

**The test:** every applicable standard's remaining deviations in scope are deliberate or blocked, each standard's checks pass on the final diff, and behavior and public contracts are preserved unless a change was authorized.

**Report:** standards applied and the scope; for each standard, representative changes and the items its `**Report:**` line names; deliberate exceptions and policy conflicts; remaining incompatible changes and the decision each needs; checks run and results, preexisting failures, and checks not run; contract changes made or authorized.
