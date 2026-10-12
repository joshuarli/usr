# OS Boundaries: Filesystem, Platform, and Unsafe/Syscall Code

You are improving this codebase so its boundary with the operating system is explicit: filesystem operations have defined semantics for paths, symlinks, atomicity, durability, permissions, races, partial failure, and non-UTF-8 names; platform differences are isolated and tested; and unsafe, FFI, and syscall code is narrow, documented, and wrapped by safe contracts.

The goal is to stop treating the filesystem like an in-memory map of string keys, to stop implying portability because code compiles, and to concentrate unsafe proof obligations at a small boundary.

Scope: path handling, file mutation, symlinks, traversal, metadata, temp files, atomic replacement, durability, claimed OS/architecture support, platform conditionals, unsafe blocks, FFI declarations, raw pointers, native handles, syscalls, and callbacks.

Applicability: Apply this prompt only when the codebase performs non-trivial filesystem operations where path fidelity, races, symlinks, partial failure, or metadata matter, targets more than one OS or architecture, or contains unsafe/native code. If the condition is materially absent, report that evidence and make no speculative changes.

Preserve: Existing valid behavior, public contracts, persisted data and formats, output, side effects, permissions, state transitions, and supported-platform semantics unless this request explicitly changes them.

Intentional changes: Only changes explicitly authorized by the invoking request; otherwise none.

If inspection shows that the relevant contract already holds, do not manufacture
changes. Verify it, correct only concrete gaps, and report the evidence.

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
- inventory `cfg` blocks, build tags, OS and architecture checks, and the CI platform matrix; note repeated platform conditionals and rarely tested fallbacks
- inventory every unsafe block and function, FFI declaration, raw pointer, manual allocation, transmute or cast, memory map, file-descriptor or handle owner, syscall wrapper, and callback crossing a language boundary
- run focused baseline tests on supported platforms

- Record failures that predate the work.

## Non-negotiable design

Each numbered requirement defines an invariant or observable behavior, its
authoritative owner or boundary, the shortcut or ambiguous state it prohibits,
and the evidence that proves it. Do not prescribe incidental implementation
structure unless that structure is itself part of the contract.

### 1. Preserve native paths and define secure resolution semantics

#### Use path-native representations


Use `Path`/`PathBuf`, `OsStr`/`OsString`, or equivalent native path types.

Do not lossy-convert paths to UTF-8 merely for convenience.

Convert to text only at presentation or protocol boundaries that genuinely require it.

#### Define symlink semantics explicitly


For each operation, decide whether to:

- follow symlinks
- operate on the link itself
- reject symlinks
- preserve symlinks
- traverse symlinked directories

Do not inherit behavior accidentally from convenience APIs.

#### Avoid TOCTOU where correctness/security matters


Be skeptical of:

```text
check path
then later operate on path
```

when the path can change between operations.

Prefer descriptor/handle-relative operations or atomic primitives where appropriate.

### 2. Define replacement, atomicity, durability, and interrupted-write behavior

#### Define replacement semantics


For writes/copies/moves, decide:

- may destination already exist?
- file vs directory mismatch behavior
- overwrite policy
- symlink replacement behavior
- cross-filesystem behavior

Do not let platform defaults silently choose policy.

#### Use atomic update patterns where needed


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

#### Distinguish atomicity from durability


A successful rename does not necessarily mean data survives power loss.

Use fsync/sync semantics only where the product contract requires durability.

Do not add expensive durability barriers everywhere without need.

#### Handle partial writes and interrupted operations


Do not assume one write call writes everything.

Make partial state and cleanup semantics explicit.

### 3. Make traversal, metadata, and filesystem precision explicit

#### Define recursive traversal behavior


For tree operations:

- deterministic ordering where observable
- symlink policy
- permission failures
- mount/filesystem boundaries if relevant
- special files
- cycles
- concurrent mutation
- error aggregation

#### Preserve metadata deliberately


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

#### Account for filesystem precision and normalization


Consider:

- timestamp precision
- case sensitivity
- Unicode normalization
- filename length
- reserved names
- path length
- file identity

Do not compare metadata in ways that make idempotent operations perpetually detect false differences.

### 4. Use safe temporary-file patterns and real filesystem tests

#### Treat temp files as filesystem operations, not strings


Use safe creation primitives.

Prefer same-directory/same-filesystem placement when atomic rename is required.

#### Test real filesystem semantics


Use integration tests for:

- symlinks
- rename/replacement
- permissions
- non-UTF-8 paths where supported
- interruption/cleanup
- metadata precision
- cross-platform differences

Do not mock the filesystem when the filesystem behavior itself is the contract.

### 5. State the platform contract and isolate mechanisms

- State which OS, architecture, and runtime combinations are supported. Do not
  imply support because code happens to compile; make an unsupported target a
  clear compile or configuration error rather than a partially working binary.
- Keep platform mechanism separate from application contract. A macOS and a
  Linux implementation may use different syscalls behind one semantic contract;
  do not duplicate whole workflows when only one mechanism differs. Collect a
  distinction that recurs across many files behind a narrow platform module, but
  do not build a portability layer for one branch.
- Preserve native values (paths, arguments, identifiers, metadata) rather than
  forcing them through UTF-8 strings for portability.
- Give every fallback a stated reason, semantic difference, supported platforms,
  and test coverage; never silently fall back to weaker correctness.
- Scope platform-specific dependencies to the targets that need them.
- Test real platform behavior on every claimed target available; semantics that
  cannot be faithfully mocked need integration tests, not only compilation.
- When low-level code depends on pointer width, endianness, alignment, page
  size, or atomic support, say so and check it.

### 6. Keep unsafe, FFI, and syscalls narrow and wrapped

- Keep only the operations that need `unsafe` inside the block; do validation,
  arithmetic, and control flow outside it.
- Document each unsafe function and block's preconditions (`# Safety` where
  applicable): pointer validity, alignment, initialization, aliasing, lifetime,
  ownership, thread safety, descriptor validity, callback lifetime.
- Convert raw external contracts into safe types as close to the boundary as
  possible, so the rest of the code never upholds FFI or syscall invariants.
- For each native resource, know the creator, owner, transfer semantics, and
  destructor, and avoid double-close, leaks, and use-after-free. Do not expose
  raw pointers or handles to unrelated modules.
- Check integer and pointer conversions (signedness, truncation, alignment,
  offsets, lengths, nullability) when external values control them; use typed
  conversions instead of `transmute` or blind casts, and explicit layout
  annotations instead of assumed ABI layout.
- For callbacks, define context ownership, lifetime, invoking thread,
  unregistration, and panic behavior; never unwind across an ABI that forbids it.
- Read `errno` or last-error state before any call that could clobber it.
- Test zero lengths, max sizes, invalid handles, short I/O, and callback
  teardown. Use Miri, sanitizers, or fuzzing only where they have a meaningful
  target.

### Migration and compatibility policy

Do not create parallel legacy and canonical implementations as part of this work.
If a rename, move, replacement, or contract change becomes necessary, inventory all
references first, keep one canonical path, and retain compatibility only when the
invoking request or an existing external contract requires it.

## Explicit anti-patterns

Do not:

- claim portability because compilation succeeds
- scatter identical OS checks everywhere, or add a portability framework for one branch
- silently downgrade correctness on a fallback path
- spread `unsafe` to avoid designing a wrapper, or rely on comments without a safe boundary
- leave native resource ownership ambiguous
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


- Distinguish failures that predate the work from regressions introduced by this change.

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
- the support matrix is explicit, unsupported targets fail clearly, platform mechanisms are isolated, and claimed platforms have real test coverage
- unsafe regions are narrow with documented preconditions, native ownership and conversions are explicit, and raw contracts are wrapped by safe APIs

The architectural principle is: **the OS is a concurrent, stateful external system with platform-specific semantics (the filesystem is not a dictionary of filenames, and operating systems are not interchangeable), and unsafe code should concentrate proof obligations at a small boundary so the rest of the program stays ordinary safe code.**
