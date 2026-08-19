# Documentation as an Executable Contract

You are improving an existing codebase so documentation describes the system that actually exists, is discoverable from the code it explains, and mechanically resists drift where practical.

The goal is not more documentation. The goal is **fewer, authoritative documents that answer real questions and stay synchronized with code**.

Preserve runtime behavior and public contracts unless this request explicitly changes them.

## First inspect the repository

Before editing:

- inventory README files, architecture docs, API docs, module docs, examples, tutorials, runbooks, comments, AGENTS.md/CLAUDE.md, CLI help, generated docs, configuration references, and release/deployment docs
- identify duplicate explanations of the same contract
- identify stale commands, paths, flags, APIs, screenshots, config keys, architecture diagrams, and examples
- identify concepts documented only in distant prose with no local pointer
- identify code comments that restate syntax rather than rationale
- identify undocumented non-obvious invariants and compatibility constraints
- run documentation examples/tests if the ecosystem supports them

## 1. Assign ownership to documentation

Each kind of fact should have one authoritative home.

Examples:

- CLI flags -> command schema/generated help
- public API -> API/module docs
- repository navigation/conventions -> AGENTS.md or established equivalent
- architectural rationale -> architecture decision/design doc
- operational recovery -> runbook

Do not duplicate the same mutable fact across many documents.

## 2. Keep documentation close to the thing it explains

Put symbol-specific rationale near the symbol.

Put module ownership near the module.

Use higher-level docs for relationships and workflows that cannot be understood locally.

## 3. Document why, constraints, and contracts

Prioritize information code cannot express:

- why a choice exists
- compatibility constraints
- ordering rules
- invariants
- platform quirks
- lifecycle requirements
- tradeoffs
- operational recovery

Avoid comments such as:

```text
increment counter
loop over files
return error
```

## 4. Make examples real

Examples should compile/run where practical.

Prefer doctests, fixture-backed examples, or CI-checked scripts over prose snippets that rot silently.

## 5. Generate reference material from authoritative schemas

Where possible, derive:

- CLI help
- config reference
- protocol enumerations
- feature lists

from the same metadata the implementation uses.

Do not hand-maintain large tables that duplicate source.

## 6. Keep architecture docs current and bounded

An architecture document should explain:

- major components
- ownership
- dependency direction
- data flow
- important boundaries

Do not document every file.

Update or delete diagrams that no longer match reality.

## 7. Record repository navigation conventions

Coding agents and humans should know:

- where domain code lives
- where tests live
- where generated code lives
- canonical commands
- naming conventions
- important support/platform constraints

Keep this concise and repository-specific.

## 8. Document compatibility and legacy paths at the boundary

Deprecated APIs/config/format paths should name:

- replacement
- compatibility reason
- removal policy if known

Do not let old behavior remain discoverable without status.

## 9. Test documentation where practical

Use:

- doctests
- command smoke tests
- generated-reference drift checks
- link checks
- example compilation

Avoid heavy doc tooling when simpler tests suffice.

## 10. Delete stale documentation aggressively

Incorrect docs are worse than missing docs.

When a workflow or API disappears, remove its documentation in the same change.

## 11. Keep operational docs outcome-oriented

Runbooks should state:

- symptom
- diagnostic command/query
- expected signals
- recovery action
- safety/rollback considerations

Avoid vague narrative.

## Explicit anti-patterns

Do not:

- create docs for every module regardless of need
- duplicate mutable reference tables by hand
- place all rationale in one giant architecture document
- leave stale screenshots/examples
- write comments that paraphrase code
- keep deprecated paths undocumented
- maintain diagrams no one updates
- treat AGENTS.md as a dumping ground for general programming advice

## Verification

After editing:

- search documented commands/paths/symbols and confirm they exist
- run checked examples/doctests
- regenerate derived reference docs and check for drift
- inspect old terminology and removed APIs in docs
- verify repository conventions match the actual tree
- verify important local rationale is near its definition

## Acceptance criteria

The work is complete only when:

- documentation has clear ownership
- mutable reference facts are generated or mechanically checked where practical
- symbol-specific rationale is local
- architecture docs describe real boundaries rather than every implementation detail
- examples are executable/checkable where useful
- repository navigation guidance matches reality
- legacy behavior is visibly marked
- stale documentation is removed
- operational docs are actionable
- documentation volume has not increased without corresponding information value

The architectural principle is: **documentation should encode contracts and rationale that code cannot, while deriving everything else from the code whenever possible.**
