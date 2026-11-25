+++
name = "zig"
summary = "Zig makes ownership, errors, bounds and test coverage explicit; lint and benchmark results must prove the intended code ran under the pinned toolchain."

[[trigger]]
paths = ["*.zig", "*.zon"]

[examples]
match = ["zig/src/main.zig", "build.zig", "build.zig.zon"]
skip = ["zig-out/bin/tf", "docs/zig-conformance.md", "src/main.rs"]
+++

# Zig

Naming, redundancy, and doc-comment rules come from the [Zig language reference style guide](https://ziglang.org/documentation/master/#Style-Guide). The safety rules adapt [TigerBeetle's TIGER_STYLE](https://github.com/tigerbeetle/tigerbeetle/blob/main/docs/TIGER_STYLE.md) to ordinary projects: its snake_case function names, zero-dependency policy, static-only allocation, and line quotas do not apply. Repository-level requirements (toolchain pin, dependency hashes, no `zig fmt`, `make test` and `make lint`, known failures, published artifacts) belong to the fleet Zig project standard, `docs/zig-standard.md` in `laputa-systems/stuff`; follow it, and never contradict it here. Neither standard asks for renames of existing code or bans language features such as `@ptrCast`.

The lint and verification guidance also draws on reviewed [ziglint](https://github.com/baskingspot/ziglint/tree/281f71a6c2ea3d1e88c35ffe471813da249d6bc0), [testingx](https://github.com/baskingspot/testingx/tree/572fdeeab652857ba0af03ed2f50ce117a0c66d5), and [utf's comparison protocol](https://github.com/baskingspot/utf/blob/810b70233d9725929dfffd7b49a100384a652994/bench/README.md). These are sources to evaluate, not mandatory dependencies or substitutes for the pinned compiler's contracts.

## Code

### Names

- Types, type aliases, and functions that return `type` use `TitleCase`. Other callables use `camelCase`. Everything else uses `snake_case`, including a namespace: a struct with no fields that is never instantiated.
- A file with top-level fields is named like a struct (`TitleCase`); other files and every directory use `snake_case`.
- Acronyms follow the same casing rules, even two-letter ones. An established convention, such as `ENOENT`, takes precedence.
- Apply these to names you add or already change. Do not rename existing declarations for style.
- `_result` is an ordinary binding, not a discard. Give a used value a meaningful name; use `_ = value` only when intentionally discarding a non-error value.

### Avoid redundancy

- Keep `Value`, `Data`, `Context`, `Manager`, `State`, `utils`, `misc`, and initials out of type names: they apply to every type and say nothing.
- Name by the fully qualified path: `json.Value`, not `json.JsonValue`. Repeat a segment only when a more specific name would be wrong.
- Put a helper at the root of the module that needs it instead of in a `utils` namespace.

### Doc comments

- Omit what the name already says. Repeating information across similar functions is fine; it improves editor help.
- Write "assume" for an invariant whose violation is unchecked Illegal Behavior, and "assert" for one whose violation is safety-checked.
- State ownership: who frees a returned slice or struct, which allocator it came from, and how long a borrowed result remains valid. Document invalidation on reset or mutation, allowed input/output overlap, capacity limits and whether failure leaves partial output.
- Expose a named type or error set when callers need to name it. A deliberately inferred private formatter/result type is valid; do not expand the public API merely to silence an AST linter.

### Errors

- Handle every error. Operating errors (I/O, input, resource limits) travel as error unions; programmer errors are assertions. Never turn an environmental failure into `unreachable`. Discard an error only at a documented best-effort boundary whose contract permits that loss; required writes, permission changes and persistence are not best effort.
- Give a public function an explicit error set when callers switch on its errors; an inferred `!T` is fine for internal code.
- Use `try` for unchanged propagation; reserve `catch` for recovery, translation or added context. Do not replace an empty catch with `catch unreachable` or a dummy statement to satisfy a lint.
- Pair each acquisition with `defer` for cleanup on every path and `errdefer` for cleanup only on failure, placed directly after the acquisition. Group an allocation and its `defer` together, separated from surrounding code by a blank line.

### Memory

- Pass allocators explicitly and name them by role (`gpa`, `arena`), not `allocator`, when more than one is in play. Do not hide a global allocator in a library.
- Prefer borrowed slices and caller-owned output or scratch buffers for reusable primitives when that fits their contract; make allocating variants explicit. Pass the pinned `std.Io` capability to code that performs I/O instead of constructing a hidden runtime in a helper. Pure parsing and computation should not need it.
- Put a bound on every loop, queue, and buffer that external input can grow. A loop that must not terminate, such as an event loop, asserts that.
- Use `std.testing.allocator` in tests so a leak fails the test.
- A terminal `deinit` may invalidate a still-live caller-owned receiver with `self.* = undefined`; never write after `destroy(self)` or erase state needed by an intentional reuse contract. Undefined memory is not a guaranteed use-after-free detector.

### Assertions, integers, and control flow

- Validate external input with errors before asserting internal arguments, return values, preconditions, postconditions and invariants with `std.debug.assert`. Safety-disabled builds must still reject invalid input. Split conjunctions into separate assertions (`assert(a); assert(b);`), assert implications with `if (a) assert(b)`, and check relationships between compile-time constants with `comptime assert`.
- Use explicitly sized integers for persisted, wire, and domain arithmetic values, and `usize` for lengths and indices. Treat index, count, and size as distinct quantities.
- Check input-derived size arithmetic before allocating, indexing or slicing; checking the result of an already-overflowed expression is too late. Ordinary integer overflow is Illegal Behavior, not implicit wrapping in ReleaseFast. Use wrapping arithmetic only when modulo behavior is the algorithm's contract.
- Narrow with `@intCast` only after the range is validated or internally established; use `@truncate` only when retaining low bits is intentional. Show division intent with `@divExact`, `@divFloor`, or `std.math.divCeil`.
- Prefer simple, explicit control flow. Recursion needs a bounded, asserted depth. Keep leaf functions pure and centralize state changes in their caller ("push `if`s up and `for`s down"). State conditions positively, such as `index < count`.

### Reuse and build boundaries

- Before adding a helper or dependency, inspect the pinned standard library and the repository's existing implementation. Compare exact semantics, supported targets and lifecycle costs; a matching function name or an upstream benchmark is not sufficient evidence to replace it.
- Keep test runners, benchmark helpers and docs generators out of ordinary consumers' dependency fetch/build graphs. Keep optional profiling clients out of normal compilation, linkage and runtime; bundled inert source is not a runtime dependency. Use lazy dependencies and conditional build wiring where supported; verify both enabled and disabled paths when changing that wiring.

### Verify

- Run the repository's `make test` and `make lint`, which wrap its `zig build` gates; never a formatter. Compare failures with the repository's known-failures document; a failure not listed there is a regression.
- Test invalid input as well as valid input, and run tests in a safety-checked build mode (Debug or ReleaseSafe) so Illegal Behavior traps.
- When changing allocation ownership, exercise failure cleanup with the pinned library's allocation-failure helper or a failing allocator. When changing parser behavior or optimized kernel code, compare the affected behavior with an independent oracle or simple reference on boundaries, malformed inputs, alignment/tails and overlap where applicable. Reuse existing relevant checks; retain the failing seed or fixture.
- Prefer diagnostic assertions (`expectEqual`, `expectEqualSlices`, `expectEqualStrings`, `expectError`) with expected before actual, so failures explain the mismatch. Compile public documentation examples whose API you change.
- When changing test roots, runners or filters, prove the intended tests are reachable and executed. Reject an unexpectedly empty selection; report skips separately. Use a planted failure/leak to verify changed runner failure reporting, and preserve the compiler's fuzz-runner protocol. A custom plain-text runner is not automatically fuzz-compatible.

### Measure

- Match the deployed workload's optimize mode, target and CPU features, and verify them on every measured imported module, not just the benchmark executable. A ReleaseFast harness can import a Debug module; changing only the harness is not an optimization of the library.
- Keep setup outside timing unless it is the workload, reset mutable inputs between repetitions, and consume a result that depends on the measured work. Verify equivalent outputs before comparing timings; report construction cost as well as steady-state cost when adopting a data structure.
- Keep paired raw runs and input/compiler identities. Separate checked-input from assumed-valid APIs, cold from warm work and profiling from uninstrumented acceptance timings. Restrict claims to the actual OS, architecture and implementation selected.
- Label allocation counters by the allocator they observe; they are not total RSS or GPU memory. Time asynchronous completion separately from submission: a CPU zone around a GPU enqueue is not GPU execution time.

## Adoption

Apply these only when bringing a whole repository up to this standard with `/standardize`, not at the completion gate.

- Bring the repository to the fleet Zig project standard (Z1 to Z6) first; it owns every configuration and CI requirement.
- Then work in passes: unhandled or discarded errors and missing `errdefer`; assertions at module boundaries; bounds on input-driven loops and buffers; doc-comment ownership statements. Do not run a renaming sweep.

### Opinionated lint, with a verified gate

Evaluate `baskingspot/ziglint` as an additional static check behind the existing `zig build`/`make lint` entrypoint. It neither formats nor autofixes. Keep compilation and domain checks: an AST linter does not establish instantiated types, ownership or runtime correctness.

1. Pin the linter revision or release and verify its download hash. Prove parser and standard-library resolution against the repository's exact Zig pin, including representative syntax; a linter's build compiler need not be the project's compiler. Do not downgrade the project to suit a linter. At review, ziglint v0.9.0 declares a minimum Zig version of 0.16.0; verify it against the fleet's exact 0.17.1 compiler and standard library.
2. Audit a small owned source scope first, with an explicit rule set. A starting profile is `--only Z002 --only Z003 --only Z007 --only Z013 --only Z016 --only Z025 --only Z026`: named discards, parse errors, duplicate/unused imports, compound assertions, redundant error propagation and empty catches. Review findings before making any rule blocking. Keep API-visibility checks Z012/Z015 and blanket deinit invalidation Z030 advisory; intentional private result types and receiver lifetimes need judgment. Naming rules apply only to names already being added or changed.
3. Make the wrapper fail closed. Supply a verified standard-library path, check every requested path, and prove a nonempty selection of owned `.zig` files; exclude generated, vendored and cache trees. In nonverbose mode, require exit zero and no diagnostics. The reviewed v0.9.0 can exit zero for missing/unreadable input and fall back to defaults after an invalid config, so exit status alone is insufficient. Prove rejection of a missing input, malformed config and a known violation, plus acceptance of a clean fixture.
4. Keep rule choices and justified exclusions in version control. A local `// ziglint-ignore: Z026` needs an adjacent explanation of why losing that error is allowed. Triage existing findings without a mass rewrite; do not silence a rule globally for one legitimate exception or run all upstream defaults blindly. Report unavailable or incompatible tooling as unverified, never as a passed gate.

**Report:** fleet requirements met or open; ownership/error/bound changes by module; lint revision, exact rule set and checked scope; test reachability and the limits of any measurements.
