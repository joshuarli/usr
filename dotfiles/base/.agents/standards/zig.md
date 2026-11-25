+++
name = "zig"
summary = "Zig follows the language reference's naming rules, handles every error, pairs each acquisition with defer or errdefer, passes allocators explicitly, and asserts arguments, invariants, and bounds."

[[trigger]]
paths = ["*.zig", "*.zon"]

[examples]
match = ["zig/src/main.zig", "build.zig", "build.zig.zon"]
skip = ["zig-out/bin/tf", "docs/zig-conformance.md", "src/main.rs"]
+++

# Zig

Naming, redundancy, and doc-comment rules come from the [Zig language reference style guide](https://ziglang.org/documentation/master/#Style-Guide). The safety rules adapt [TigerBeetle's TIGER_STYLE](https://github.com/tigerbeetle/tigerbeetle/blob/main/docs/TIGER_STYLE.md) to ordinary projects: its snake_case function names, zero-dependency policy, static-only allocation, and line quotas do not apply. Repository-level requirements (toolchain pin, dependency hashes, no `zig fmt`, `make test` and `make lint`, known failures, published artifacts) belong to the fleet Zig project standard, `docs/zig-standard.md` in `laputa-systems/stuff`; follow it, and never contradict it here. Neither standard asks for renames of existing code or bans language features such as `@ptrCast`.

## Code

### Names

- Types, type aliases, and functions that return `type` use `TitleCase`. Other callables use `camelCase`. Everything else uses `snake_case`, including a namespace: a struct with no fields that is never instantiated.
- A file with top-level fields is named like a struct (`TitleCase`); other files and every directory use `snake_case`.
- Acronyms follow the same casing rules, even two-letter ones. An established convention, such as `ENOENT`, takes precedence.
- Apply these to names you add or already change. Do not rename existing declarations for style.

### Avoid redundancy

- Keep `Value`, `Data`, `Context`, `Manager`, `State`, `utils`, `misc`, and initials out of type names: they apply to every type and say nothing.
- Name by the fully qualified path: `json.Value`, not `json.JsonValue`. Repeat a segment only when a more specific name would be wrong.
- Put a helper at the root of the module that needs it instead of in a `utils` namespace.

### Doc comments

- Omit what the name already says. Repeating information across similar functions is fine; it improves editor help.
- Write "assume" for an invariant whose violation is unchecked Illegal Behavior, and "assert" for one whose violation is safety-checked.
- State ownership: who frees a returned slice or struct, and which allocator it came from.

### Errors

- Handle every error. Operating errors (I/O, input, resource limits) travel as error unions; programmer errors are assertions. Never `catch unreachable` or discard an error the environment can cause.
- Give a public function an explicit error set when callers switch on its errors; an inferred `!T` is fine for internal code.
- Pair each acquisition with `defer` for cleanup on every path and `errdefer` for cleanup only on failure, placed directly after the acquisition. Group an allocation and its `defer` together, separated from surrounding code by a blank line.

### Memory

- Pass allocators explicitly and name them by role (`gpa`, `arena`), not `allocator`, when more than one is in play. Do not hide a global allocator in a library.
- Put a bound on every loop, queue, and buffer that external input can grow. A loop that must not terminate, such as an event loop, asserts that.
- Use `std.testing.allocator` in tests so a leak fails the test.

### Assertions, integers, and control flow

- Assert function arguments, return values, preconditions, postconditions, and invariants with `std.debug.assert`. Split compound assertions (`assert(a); assert(b);`), assert implications with `if (a) assert(b)`, and check relationships between compile-time constants with `comptime assert`.
- Use explicitly sized integers for persisted, wire, and domain arithmetic values, and `usize` for lengths and indices. Treat index, count, and size as distinct quantities.
- Narrow with `@intCast` or `@truncate` only after the range is established or asserted. Show division intent with `@divExact`, `@divFloor`, or `std.math.divCeil`.
- Prefer simple, explicit control flow. Recursion needs a bounded, asserted depth. Keep leaf functions pure and centralize state changes in their caller ("push `if`s up and `for`s down"). State conditions positively, such as `index < count`.

### Verify

- Run the repository's `make test` and `make lint`, which wrap its `zig build` gates; never a formatter. Compare failures with the repository's known-failures document; a failure not listed there is a regression.
- Test invalid input as well as valid input, and run tests in a safety-checked build mode (Debug or ReleaseSafe) so Illegal Behavior traps.

## Adoption

Apply these only when bringing a whole repository up to this standard with `/standardize`, not at the completion gate.

- Bring the repository to the fleet Zig project standard (Z1 to Z6) first; it owns every configuration and CI requirement.
- Then work in passes: unhandled or discarded errors and missing `errdefer`; assertions at module boundaries; bounds on input-driven loops and buffers; doc-comment ownership statements. Do not run a renaming sweep.

**Report:** fleet standard requirements met or still open; error, assertion, and bound changes by module.
