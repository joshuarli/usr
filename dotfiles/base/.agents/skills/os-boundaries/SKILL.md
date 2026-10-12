---
name: os-boundaries
description: Use when code touches file paths, symlinks, atomic writes or temp files, directory traversal, file metadata, platform-specific code (cfg, OS checks, syscalls), or unsafe, FFI, and raw pointers.
---

# OS Boundaries

Give the boundary with the operating system explicit semantics: filesystem behavior, the platform contract, and unsafe code. Apply this to the code being changed or the scope the user names. Do not widen into a repository-wide audit unless asked; if nothing here applies, say so and change nothing.

Read repository and scoped `AGENTS.md` first. Inventory the affected path handling, mutations, platform conditionals, and unsafe blocks, and run the narrowest baseline check before editing.

## Filesystem

- Use native path types (`Path`, `OsStr`) and convert to text only at presentation or protocol boundaries. Never lossy-convert paths or arguments.
- For each operation decide: follow symlinks, operate on the link, reject, or preserve. Do not inherit the choice from a convenience API.
- Treat check-then-act as a race wherever the path can change in between; prefer handle-relative or atomic primitives. Lexical normalization is not secure resolution.
- Define replacement policy (existing destination, file versus directory, cross-filesystem). Important updates go through temp file in the same directory, write, flush, fsync only if durability is required, atomic rename, cleanup on failure. Atomicity and durability are different guarantees.
- Make traversal order, special files, cycles, permission failures, and metadata preservation explicit, and avoid comparisons that detect false differences from timestamp precision.

## Platform

- State which OS and architecture combinations are supported; an unsupported target should fail loudly at compile or configuration time. Compiling is not support.
- Keep platform mechanism behind one application contract, and do not duplicate whole workflows for one differing syscall. Every fallback states why it exists, what semantics differ, and how it is tested.

## Unsafe, FFI, and syscalls

- Keep `unsafe` blocks to the operations that need them and document each precondition (`# Safety`). Wrap raw contracts in safe types at the boundary.
- Know the creator, owner, transfer, and destructor of every native resource. Check integer and pointer conversions, use explicit layout, never unwind across a forbidding ABI, and read `errno` before anything can clobber it.

## Verify

Test against the real filesystem, not mocks: symlinks, replacement, permissions, non-UTF-8 names where supported, interruption and cleanup. Cover zero length, maximum size, invalid handle, and short I/O for native code. Distinguish pre-existing failures from regressions.

Load `reference.md` for the full inspection checklist, anti-patterns, and acceptance criteria when the change is a broad audit or the design is non-trivial. Where it says "this codebase" or "repository-wide", read it as the requested scope.

## Handoff

Report the semantics you made explicit (symlink policy, atomicity, supported platforms, safety preconditions), checks actually run, and decisions the user must make.
