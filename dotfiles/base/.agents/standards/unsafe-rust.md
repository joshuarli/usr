+++
name = "unsafe-rust"
summary = "Unsafe Rust stays sound behind safe APIs: one documented operation per unsafe block, explicit unsafe in unsafe fn bodies, Rust 2024 unsafe extern and attribute forms, no references to static mut, and FFI that only translates."

[[trigger]]
paths = ["*.rs"]
content = ['\bunsafe\b', '\bextern\s+"C', '#\[\s*(unsafe\s*\(\s*)?(no_mangle|export_name|link_section)', '\bstatic\s+mut\b', '\b(transmute|MaybeUninit|from_raw_parts(_mut)?|from_raw|into_raw)\b']

[examples]
match = [
  { path = "kernel/rust/src/lock.rs", text = "    unsafe { *ptr }\n" },
  { path = "src/ffi.rs", text = "#[unsafe(no_mangle)]\npub extern \"C\" fn init() {}\n" },
  { path = "src/buf.rs", text = "let s = std::slice::from_raw_parts(p, n);\n" },
]
skip = [
  { path = "src/lib.rs", text = "pub fn safe() {}\n" },
  { path = "docs/unsafe.md", text = "unsafe { *ptr }\n" },
  { path = "src/lint.rs", text = "#![forbid(unsafe_code)]\n" },
]
+++

# Unsafe Rust

This extends the `rust` standard, whose "Documentation and unsafe code" section owns the base rules: prefer safe code, encapsulate unsafe in sound abstractions, justify it with `SAFETY:` comments, establish the affected invariants, and use existing Miri and sanitizer gates. Sources: the [Rustonomicon](https://doc.rust-lang.org/nomicon/), the [Unsafe Code Guidelines](https://rust-lang.github.io/unsafe-code-guidelines/), the [Rust 2024 edition guide](https://doc.rust-lang.org/edition-guide/rust-2024/index.html), the `# Safety` sections of the standard library docs, and Microsoft's [Pragmatic Rust Guidelines](https://microsoft.github.io/rust-guidelines/) (M-UNSAFE, M-UNSAFE-IMPLIES-UB, M-UNSOUND, M-FFI-TRANSLATES).

## Code

### Soundness

- No safe function may cause undefined behavior for any input safe code can supply (M-UNSOUND). When soundness depends on the caller, make the function `unsafe fn` and document its preconditions under `# Safety`. A safe wrapper never relies on caller discipline.
- `unsafe` needs a reason: FFI, a novel abstraction, or a measured performance need (M-UNSAFE). Marking something `unsafe` means misuse can cause undefined behavior (M-UNSAFE-IMPLIES-UB); do not use it as a "be careful" label.
- `unsafe impl Send` or `unsafe impl Sync` carries a `SAFETY:` argument covering every field. Prefer letting the auto traits derive.

### Unsafe blocks

- Keep each `unsafe {}` block to one unsafe operation where practical, with a `// SAFETY:` comment directly above it (`clippy::undocumented_unsafe_blocks`, `clippy::multiple_unsafe_ops_per_block`).
- An `unsafe fn` body is not an unsafe context: wrap each unsafe operation in its own block (`unsafe_op_in_unsafe_fn`, warn by default in the 2024 edition).

### Rust 2024 forms

- Declare foreign items in `unsafe extern` blocks, and mark each item `safe` or `unsafe`.
- Write `#[unsafe(no_mangle)]`, `#[unsafe(export_name = "...")]`, and `#[unsafe(link_section = "...")]`.
- Never take a reference to a `static mut` (`static_mut_refs`, deny by default in 2024). Use `&raw const` or `&raw mut`, or replace the static with an atomic, `Mutex`, or `OnceLock`.
- `std::env::set_var` and `std::env::remove_var` are `unsafe` because another thread may read the environment. Set a child's environment on `Command` instead.

### Pointers and memory

- Take raw pointers with `&raw const` or `&raw mut` rather than creating a reference to data that may be unaligned, packed, or uninitialized.
- Use `MaybeUninit` for uninitialized memory; never `mem::uninitialized`, and `mem::zeroed` only for types whose all-zero bit pattern is valid.
- Give `transmute` explicit source and target types, and prefer a safe conversion (`from_bits`, `to_ne_bytes`, `cast`, `try_into`) when one exists.
- `slice::from_raw_parts` needs a non-null, aligned pointer even for length 0 (use `NonNull::dangling()`), and a total size of at most `isize::MAX` bytes.
- Pair `Box::into_raw` with exactly one `Box::from_raw`, and document which side frees.

### FFI

- Keep business logic in safe Rust; the FFI layer only translates and validates pointers, lengths, and encodings at the boundary (M-FFI-TRANSLATES).
- A panic that reaches an `extern "C"` boundary aborts the process. Catch it before the boundary, or declare `extern "C-unwind"` when foreign code is built to unwind.

### Verify

- Run the crate's existing Miri, sanitizer, or loom gates on changed unsafe paths. Where none exists, state that the unsafe change is unverified beyond its invariant argument; do not install a nightly toolchain to add one.
- Test the boundary cases the `SAFETY:` comment depends on: zero length, maximum length, alignment, and the error path.

## Adoption

Apply these only when bringing a whole repository up to this standard with `/standardize`, not at the completion gate.

- Add `#![forbid(unsafe_code)]` to every crate root that contains no unsafe code.
- Enable `unsafe_op_in_unsafe_fn` on crates still on an edition before 2024, and the Clippy lints `undocumented_unsafe_blocks` and `multiple_unsafe_ops_per_block`.
- Migrate to the 2024 forms above. Adding a Miri gate needs a nightly toolchain, which is the owner's decision; report it rather than adding one.

**Report:** unsafe blocks added, removed, or narrowed; soundness arguments changed; gates run and unsafe paths left unverified.
