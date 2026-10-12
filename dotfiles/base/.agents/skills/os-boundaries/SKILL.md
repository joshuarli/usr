---
name: os-boundaries
description: "Apply when code touches file paths, symlinks, temp files or atomic writes, directory traversal, platform conditionals, syscalls, or unsafe and FFI."
---

# OS Boundaries

The filesystem is a concurrent, stateful external system, and operating systems are not interchangeable. Work on the code at hand; audit the whole repo only when asked.

- **Paths are not strings.** Use `Path` and `OsStr`. Convert to text only at presentation or protocol edges. Never lossy-convert a path or an argument.
- **Pick a symlink policy per operation:** follow, act on the link, reject, or preserve. Convenience APIs choose silently.
- **Check-then-act is a race.** Where the path can change in between, use handle-relative or atomic operations. Lexical normalization is not confinement.
- **Replace atomically.** Temp file in the destination directory, write, flush, fsync only if durability is required, rename, clean up on failure. Atomic is not durable. Define what happens when the destination exists, is a directory, or is a symlink.
- **Traversal states its rules:** order if observable, special files, cycles, permission errors, mount boundaries. Metadata is preserved by policy, not by accident. Never compare timestamps finer than the filesystem keeps.
- **Say what is supported.** Name the OS and architecture pairs. An unsupported target fails at compile or configure time, because compiling is not support. Keep the mechanism behind one contract and do not fork whole workflows for one differing syscall. Every fallback states why it exists, what semantics differ, and where it is tested.
- **Unsafe holds only the unsafe operation.** Validation and arithmetic stay outside the block. Document the preconditions (`# Safety`): validity, alignment, initialization, aliasing, lifetime, thread safety. Wrap raw handles in a safe type at the boundary with one owner and one destructor. Check integer and pointer conversions, declare layout explicitly, never unwind across an ABI that forbids it, and read `errno` before anything can clobber it.

**The test:** if another process swapped a path component between two lines here, could this read or write the wrong file?

Test on the real filesystem, not a mock: symlinks, replacement, permissions, non-UTF-8 names, interruption. For native code, test zero length, max size, an invalid handle, and short I/O.

**Reply:** the semantics you made explicit (symlink policy, atomicity, supported targets, safety preconditions).
