# Dead Code and Legacy Archaeology

You are improving this codebase so obsolete behavior and historical compatibility residue are either proven live, quarantined as compatibility, or removed coherently.

The goal is to prove what is still live and remove or quarantine what is not.

Scope: dead code, deprecated APIs, compatibility wrappers, stale config/env keys, old formats, feature flags, fallbacks, scripts, tests, and docs.

Applicability: Apply this prompt only when historical paths plausibly remain after their callers, rollout, migration, or compatibility requirement has ended. If the condition is materially absent, report that evidence and make no speculative changes.

Preserve: Existing valid behavior, public contracts, persisted data and formats, output, side effects, permissions, state transitions, and supported-platform semantics unless this request explicitly changes them.

Intentional changes: Only changes explicitly authorized by the invoking request; otherwise none.

If inspection shows that the relevant contract already holds, do not manufacture
changes. Verify it, correct only concrete gaps, and report the evidence.

## First inspect the repository

Before editing:

Inventory suspicious artifacts:

- unused modules/functions/types
- deprecated APIs
- compatibility wrappers
- old config keys
- stale env vars
- feature flags
- migrations
- fallback branches
- legacy serializers
- old protocol versions
- disabled code
- ignored tests
- TODOs referencing completed work
- commented-out code
- obsolete scripts
- stale documentation

Search call sites, tests, docs, operational scripts, config, and generated inputs.

- Record failures that predate the work.

## Non-negotiable design

Each numbered requirement defines an invariant or observable behavior, its
authoritative owner or boundary, the shortcut or ambiguous state it prohibits,
and the evidence that proves it. Do not prescribe incidental implementation
structure unless that structure is itself part of the contract.

### 1. Require evidence of liveness before retaining or deleting historical code

#### Require evidence of liveness


For each legacy-looking artifact, determine whether it is:

- actively used
- externally consumed
- persisted in old data
- required for compatibility
- required for migration
- truly dead

Do not infer deadness solely from a compiler warning.

#### Remove dead implementations completely


When safe, remove:

- implementation
- tests that only cover it
- config
- docs
- exports
- feature gates
- compatibility glue

Do not leave tombstones everywhere.

### 2. Quarantine compatibility while removing stale fallbacks and completed flags

#### Quarantine required compatibility


If legacy behavior must remain:

- mark it deprecated
- name the canonical replacement
- prevent new code from using it
- route through the canonical implementation where possible

#### Remove stale fallbacks


Fallbacks are suspicious when the primary condition that justified them no longer exists.

Verify before removing.

#### Clean stale feature flags


For completed rollouts, choose the final behavior and remove dual paths.

Do not preserve permanent branching after the decision has been made.

### 3. Keep legacy persisted formats compatible without preserving old writers


Legacy parsers/readers may still be needed for old data.

Separate read compatibility from new-write behavior.

New writes should use the canonical format.

### 4. Remove commented-out implementation residue and stale documentation

#### Delete commented-out code


Version control is the archive.

Retain comments only when they explain current behavior.

#### Reconcile documentation


Remove references to deleted flags, APIs, paths, workflows, and old architecture.


## Explicit anti-patterns

Do not:

- delete compatibility code without checking external/persisted consumers
- preserve dead code "just in case"
- leave deprecated paths equally visible to new callers
- keep completed feature flags forever
- retain old writers merely because old readers remain
- use comments as a museum of previous implementations


## Verification

After editing:

- Run the nearest hard judge for dead code, deprecated APIs, compatibility wrappers, stale config/env keys, old formats, feature flags, fallbacks, scripts, tests, and docs: the compiler, type checker, schema/build check, or focused tests that can reject an invalid change.
- Test the observable success behavior, failure behavior, edge cases, and invariants established by the numbered requirements.
- Audit liveness evidence, deprecations, fallbacks, flags, old readers/writers, commented code, and stale documentation; classify every remaining exception rather than assuming it is harmless.
- Broaden checks only when the changed boundary warrants it, and distinguish pre-existing failures from regressions introduced by this work.

## Acceptance criteria

The work is complete only when:

- legacy artifacts have been classified
- truly dead code and configuration are removed
- required compatibility paths are visibly secondary
- new code does not choose deprecated paths
- completed feature flags and stale fallbacks are removed
- legacy persisted formats are read-only where appropriate
- documentation matches the live system
- no compatibility contract is broken accidentally

The architectural principle is: **historical complexity should have to justify its continued existence.**
