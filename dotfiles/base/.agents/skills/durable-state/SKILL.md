---
name: durable-state
description: Use when changing or reviewing database schemas, migrations, persisted or wire formats, transactions, read-modify-write paths, caches over durable data, or retried and leased background jobs.
---

# Durable State

Make durable state an explicit contract: what is stored, in what format, what must change atomically, and what happens after a crash. Apply this to the code being changed or the scope the user names. Do not widen into a repository-wide audit unless asked; if nothing here applies, say so and change nothing.

Read repository and scoped `AGENTS.md` first. Inventory the affected tables, formats, transactions, and jobs, and run the narrowest baseline check before editing.

## Rules

- A transaction covers changes that must succeed or fail together. Keep persistence mechanics at one boundary; domain code decides, persistence code executes.
- Enforce facts that must hold on every write path in the datastore (NOT NULL, UNIQUE, CHECK, foreign keys). Handle concurrent writers with atomic updates, version checks, or locks, never a read that is assumed to stay current. Consider existing data before adding a constraint.
- Persisted and wire field names, discriminants, defaults, and null semantics are compatibility commitments. Choose the versioning strategy explicitly, decide unknown-field behavior, keep absent, null, empty, and default distinct, and treat deserialization as untrusted until validated. Keep one canonical writer; old readers may stay, old writers should not.
- Model each fact once. Constrain cardinality and uniqueness, give null one specific meaning, name timestamps for what they record, keep core facts out of opaque blobs, and keep tenant scope visible in queries.
- Name delivery semantics honestly (at-most-once, at-least-once, effectively-once). Make job states explicit, enforce lease ownership with compare-and-set, and walk each crash window: after the side effect but before the acknowledgement, after claim but before execution, after the result but before the status update. Retries are bounded; dedupe keys state their scope.
- A cache or derived index never becomes the source of truth; define its invalidation next to the mutation.
- Measure before optimizing query shape; fix N+1 and broad fetch-then-filter when found.

## Verify

Test the failure windows and the invalid-write path, not just the happy path: old-format fixtures, malformed input, constraint rejection, stale-owner completion, duplicate delivery. Distinguish pre-existing failures from regressions.

Load `reference.md` for the full inspection checklist, anti-patterns, and acceptance criteria when the change is a broad audit or the design is non-trivial. Where it says "this codebase" or "repository-wide", read it as the requested scope.

## Handoff

Report the contracts you established or tightened, any data or format compatibility impact, checks actually run, and decisions the user must make. Surface changes to schemas, formats, or transaction boundaries explicitly.
