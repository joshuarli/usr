+++
name = "os-boundaries"
summary = "Code treats the filesystem and OS as concurrent external systems: paths stay paths, symlink policy and atomic replacement are explicit, supported targets are named, unsafe holds only the unsafe operation, and signal handlers stay async-signal-safe."

[[trigger]]
paths = ["*", "!*.md", "!*.txt", "!*.rst", "!*.json", "!*.jsonl", "!*.log", "!*.csv", "!*.tsv", "!*.svg", "!*.snap", "!*.lock"]
content = ['\b(symlink|readlink|realpath|canonicalize|lstat|O_NOFOLLOW|openat|fsync|mkstemp|tempfile|NamedTemporaryFile|TemporaryDirectory|walkdir|os\.walk|read_dir)\b', '\b(os\.replace|os\.rename|fs::rename|renameat)\b', '\b(sigaction|libc::|ctypes|@cImport|syscall)\b', '\bextern\s+"C', '\bunsafe\b', '#\[cfg\(\s*(target_os|unix|windows)', '\b(sys\.platform|platform\.system|process\.platform|builtin\.os)\b']

[examples]
match = [{ path = "src/fsutil.rs", text = "std::fs::rename(&tmp, &dest)?;\n" }, { path = "tools/w.py", text = "fd, path = tempfile.mkstemp(dir=parent)\n" }, { path = "src/os.rs", text = "#[cfg(target_os = \"macos\")]\n" }]
skip = [{ path = "fixtures/data.json", text = "fsync\n" }, { path = "src/x.py", text = "path = base / name\n" }, { path = "docs/fs.md", text = "fsync\n" }]
+++

# OS Boundaries

The filesystem is a concurrent, stateful external system, and operating systems are not interchangeable.

## Code

- **Paths are not strings.** Use `Path` and `OsStr`. Convert to text only at presentation or protocol edges. Never lossy-convert a path or an argument.
- **Pick a symlink policy per operation:** follow, act on the link, reject, or preserve. Convenience APIs choose silently.
- **Check-then-act is a race.** Where the path can change in between, use handle-relative or atomic operations. Lexical normalization is not confinement.
- **Replace atomically.** Temp file in the destination directory, write, flush, fsync the file before the rename if the result must be intact after a crash (delayed allocation can leave a partial file), rename, clean up on failure. Also fsync the parent directory if the rename itself must survive a crash. Atomic is not durable. Define what happens when the destination exists, is a directory, or is a symlink.
- **Traversal states its rules:** order if observable, special files, cycles, permission errors, mount boundaries. Metadata is preserved by policy, not by accident. Never compare timestamps finer than the filesystem keeps.
- **Say what is supported.** Name the OS and architecture pairs. An unsupported target fails at compile or configure time, because compiling is not support. Keep the mechanism behind one contract and do not fork whole workflows for one differing syscall. Every fallback is named for the semantics that differ and has a test that exercises it, so no comment has to carry that.
- **Unsafe holds only the unsafe operation.** Validation and arithmetic stay outside the block. Document the preconditions (`# Safety`): validity, alignment, initialization, aliasing, lifetime, thread safety. Wrap raw handles in a safe type at the boundary with one owner and one destructor. Check integer and pointer conversions, declare layout explicitly, never unwind across an ABI that forbids it, and read `errno` before anything can clobber it.
- **Signal handlers do async-signal-safe work only.** Raw descriptor writes, no locks, no allocation; save and restore `errno` across the handler. Declare the `sigaction` layout and flag constants per OS explicitly, check the install return, and fail fast when installation fails: a silently uninstalled handler loses shutdown without a trace. Disposition and crash policy live in `lifecycle-concurrency`.

**The test:** if another process swapped a path component between two lines here, could this read or write the wrong file?

Test on the real filesystem (a temp directory), not a mock: symlinks, replacement, permissions, non-UTF-8 names, interruption. For native code, test zero length, max size, an invalid handle, and short I/O.

**Report:** the semantics you made explicit (symlink policy, atomicity, supported targets, safety preconditions).
