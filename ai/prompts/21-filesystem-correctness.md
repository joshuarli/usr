# Filesystem Correctness and Path Semantics

You are improving an existing codebase so filesystem operations have explicit semantics for paths, symlinks, atomicity, durability, permissions, races, partial failure, and non-UTF-8 names.

The goal is to stop treating the filesystem like an in-memory map of string keys.

Preserve existing behavior unless this request explicitly changes filesystem semantics.

## First inspect the repository

Before editing:

- inventory all path construction and normalization
- inventory file/directory creation, reads, writes, renames, copies, deletion, traversal, metadata access, permissions, symlink handling, temp files, locking, and fsync/durability behavior
- identify `String` use where path-native types should be used
- identify lossy UTF-8 conversions
- identify check-then-act sequences
- identify recursive traversal and symlink-following behavior
- identify writes performed directly to destination files
- identify cleanup behavior after interruption/failure
- identify assumptions about filesystem timestamp precision, case sensitivity, or rename behavior
- run focused baseline tests on supported platforms

## 1. Use path-native representations

Use `Path`/`PathBuf`, `OsStr`/`OsString`, or equivalent native path types.

Do not lossy-convert paths to UTF-8 merely for convenience.

Convert to text only at presentation or protocol boundaries that genuinely require it.

## 2. Define symlink semantics explicitly

For each operation, decide whether to:

- follow symlinks
- operate on the link itself
- reject symlinks
- preserve symlinks
- traverse symlinked directories

Do not inherit behavior accidentally from convenience APIs.

## 3. Avoid TOCTOU where correctness/security matters

Be skeptical of:

```text
check path
then later operate on path
```

when the path can change between operations.

Prefer descriptor/handle-relative operations or atomic primitives where appropriate.

## 4. Define replacement semantics

For writes/copies/moves, decide:

- may destination already exist?
- file vs directory mismatch behavior
- overwrite policy
- symlink replacement behavior
- cross-filesystem behavior

Do not let platform defaults silently choose policy.

## 5. Use atomic update patterns where needed

For important file replacement:

```text
create temp in appropriate directory
write
flush
fsync if durability requires it
rename/replace atomically
cleanup on failure
```

Understand which guarantees actually hold on supported filesystems/platforms.

## 6. Distinguish atomicity from durability

A successful rename does not necessarily mean data survives power loss.

Use fsync/sync semantics only where the product contract requires durability.

Do not add expensive durability barriers everywhere without need.

## 7. Handle partial writes and interrupted operations

Do not assume one write call writes everything.

Make partial state and cleanup semantics explicit.

## 8. Define recursive traversal behavior

For tree operations:

- deterministic ordering where observable
- symlink policy
- permission failures
- mount/filesystem boundaries if relevant
- special files
- cycles
- concurrent mutation
- error aggregation

## 9. Preserve metadata deliberately

For copy/sync tools, decide which metadata is part of the contract:

- mode
- timestamps
- ownership
- xattrs
- ACLs
- flags
- sparse layout
- symlinks

Do not partially preserve metadata accidentally.

## 10. Account for filesystem precision and normalization

Consider:

- timestamp precision
- case sensitivity
- Unicode normalization
- filename length
- reserved names
- path length
- file identity

Do not compare metadata in ways that make idempotent operations perpetually detect false differences.

## 11. Treat temp files as filesystem operations, not strings

Use safe creation primitives.

Prefer same-directory/same-filesystem placement when atomic rename is required.

## 12. Test real filesystem semantics

Use integration tests for:

- symlinks
- rename/replacement
- permissions
- non-UTF-8 paths where supported
- interruption/cleanup
- metadata precision
- cross-platform differences

Do not mock the filesystem when the filesystem behavior itself is the contract.

## Explicit anti-patterns

Do not:

- treat paths as UTF-8 strings
- assume lexical normalization is secure resolution
- follow symlinks accidentally
- rely on check-then-act sequences where races matter
- write important destination files in place without considering partial failure
- conflate atomicity and durability
- assume timestamp equality has infinite precision
- preserve metadata accidentally rather than by policy
- fake filesystem correctness with mocks

## Verification

After editing:

- search for lossy path conversion
- classify symlink behavior for every mutating operation
- test replacement and interruption paths
- test supported-platform edge cases
- verify temp-file and cleanup semantics
- verify idempotence across filesystem metadata precision where relevant

## Acceptance criteria

The work is complete only when:

- paths use native representations
- symlink semantics are explicit
- replacement behavior is deliberate
- critical updates are atomic where required
- durability requirements are distinct from atomicity
- partial failure and cleanup behavior are defined
- recursive traversal semantics are documented/tested
- metadata preservation is intentional
- platform/filesystem precision assumptions are handled
- real filesystem tests protect meaningful contracts

The architectural principle is: **the filesystem is a concurrent, stateful external system with platform-specific semantics—not a dictionary of filenames.**
