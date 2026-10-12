---
name: single-source-of-truth
description: Use when the same fact, closed set, default, or magic value is maintained in more than one place (parser plus help text, enum plus string table, "keep in sync" comments), or when settings, defaults, limits, and timeouts are scattered.
disable-model-invocation: true
---

# Single Source of Truth

Make each fact have one owner, with other representations derived from it or mechanically checked against it, and give tunable policy one typed home. Apply this to the scope the user names. Do not widen into a repository-wide audit unless asked; if no fact is duplicated, report the evidence and change nothing.

Read repository and scoped `AGENTS.md` first. Inventory the duplicates (registries, enums with separate parsers, schemas with hand-kept metadata, repeated defaults and literals, "keep in sync" comments, drift-catching tests), and run the narrowest baseline check before editing.

## Rules

- Merge facts that must evolve together, not code that merely looks similar. Distinct contracts stay distinct: a wire model and a domain model may differ, so centralize the mapping instead.
- Choose the authority explicitly (the type, a declarative schema, a registry, the database schema, an upstream spec) and derive the rest one way. No circular derivation, and never make generated output the authority when its input is the real source.
- Remove "keep in sync" obligations by removing the synchronization work. Where duplication is irreducible (language boundary, public protocol, docs), name the authoritative side, explain the copy, and add a test that fails when they diverge.
- Prefer a readable declaration over clever metaprogramming. Do not add a generator to remove three harmless lines.
- If existing copies disagree, investigate the discrepancy; do not silently pick one.
- Settings: classify runtime settings, application policy, protocol constants, and local constants before moving anything. Protocol constants stay with the format that owns them. One default per setting, raw sources (CLI, env, config) read and resolved once at a narrow boundary, typed values with units (`Duration`, `NonZero*`), invalid combinations rejected at construction. Do not merge values because their literals match, and do not create a `constants` drawer or mutable global configuration.

## Verify

Search for each former duplicate and retired spelling and classify what remains. Confirm every consumer (parser, renderer, validator, serializer, docs, tests, generated artifacts) now derives from the owner. Preserve existing defaults and precedence unless the request changes them. Distinguish pre-existing failures from regressions.

Load `reference.md` for the full inspection checklist, anti-patterns, and acceptance criteria when doing a broad audit. Where it says "this codebase" or "repository-wide", read it as the requested scope.

## Handoff

Report each fact and its new owner, intentional duplicates left with their drift checks, checks actually run, and decisions the user must make. Surface any change to defaults or precedence.
