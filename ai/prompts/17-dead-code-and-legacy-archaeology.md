# Dead Code and Legacy Archaeology

You are improving an existing codebase by finding obsolete behavior, compatibility paths, stale configuration, dead abstractions, and historical leftovers that still consume reasoning bandwidth.

The goal is not indiscriminate deletion. The goal is to prove what is still live and remove or quarantine what is not.

Preserve compatibility unless evidence and the task permit removal.

## First inspect the repository

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

## 1. Require evidence of liveness

For each legacy-looking artifact, determine whether it is:

- actively used
- externally consumed
- persisted in old data
- required for compatibility
- required for migration
- truly dead

Do not infer deadness solely from a compiler warning.

## 2. Remove dead implementations completely

When safe, remove:

- implementation
- tests that only cover it
- config
- docs
- exports
- feature gates
- compatibility glue

Do not leave tombstones everywhere.

## 3. Quarantine required compatibility

If legacy behavior must remain:

- mark it deprecated
- name the canonical replacement
- prevent new code from using it
- route through the canonical implementation where possible

## 4. Remove stale fallbacks

Fallbacks are suspicious when the primary condition that justified them no longer exists.

Verify before removing.

## 5. Clean stale feature flags

For completed rollouts, choose the final behavior and remove dual paths.

Do not preserve permanent branching after the decision has been made.

## 6. Audit old persisted formats

Legacy parsers/readers may still be needed for old data.

Separate read compatibility from new-write behavior.

New writes should use the canonical format.

## 7. Delete commented-out code

Version control is the archive.

Retain comments only when they explain current behavior.

## 8. Reconcile documentation

Remove references to deleted flags, APIs, paths, workflows, and old architecture.

## Explicit anti-patterns

Do not:

- delete compatibility code without checking external/persisted consumers
- preserve dead code "just in case"
- leave deprecated paths equally visible to new callers
- keep completed feature flags forever
- retain old writers merely because old readers remain
- use comments as a museum of previous implementations

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
