# Unsafe, FFI, and Syscall Boundary Audit

You are improving an existing systems codebase so unsafe operations, FFI, raw syscalls, pointer manipulation, memory mapping, and platform-native interfaces are narrow, documented, and wrapped by safe contracts.

The goal is not to eliminate unsafe code categorically. The goal is to ensure every unsafe boundary has explicit preconditions and the rest of the codebase does not need to reason about them.

Preserve low-level semantics and performance unless fixing a correctness bug.

## First inspect the repository

Before editing:

- inventory every unsafe block/function
- inventory FFI declarations
- inventory raw pointers
- inventory manual allocation/deallocation
- inventory transmute/casts
- inventory memory maps
- inventory file descriptor/handle ownership
- inventory syscall wrappers
- inventory callbacks crossing language boundaries
- inventory C-string/string conversions
- identify external lifetime/aliasing assumptions
- run sanitizer/Miri/Valgrind/platform tools where available and appropriate
- run baseline tests

## 1. Make unsafe blocks minimal

Keep only the operations requiring unsafe inside the block.

Move validation, arithmetic, and ordinary control flow outside.

## 2. Document safety preconditions

Every unsafe function/block should make relevant assumptions clear:

- pointer validity
- alignment
- initialized memory
- aliasing
- lifetime
- ownership
- thread safety
- file descriptor validity
- callback lifetime

Use language conventions such as `# Safety` documentation where applicable.

## 3. Build safe wrappers

Convert raw external contracts into safe domain/API types as close to the boundary as possible.

The rest of the codebase should not repeatedly uphold FFI/syscall invariants.

## 4. Audit ownership transfer

For every native resource/pointer, identify:

- creator
- owner
- transfer semantics
- destructor/free function
- duplicate/borrow semantics

Avoid double-close, leaks, and use-after-free.

## 5. Check integer and pointer conversions

Validate:

- signed/unsigned conversions
- size truncation
- alignment
- offsets
- length calculations
- nullability

Do not rely on unchecked casts when external values control them.

## 6. Keep ABI representations explicit

Use correct representation/layout annotations and types.

Do not assume Rust/C/etc. enum, struct, boolean, or string layouts match without a contract.

## 7. Handle callbacks carefully

For callbacks crossing FFI:

- define context ownership
- lifetime
- thread of invocation
- panic/exception behavior
- cancellation/unregistration

Never unwind across an ABI that forbids it.

## 8. Audit errno/last-error semantics

Capture mechanism-specific error state at the correct moment.

Do not call unrelated APIs before reading thread-local/native error state where that would destroy it.

## 9. Test edge conditions

Cover:

- zero lengths
- null pointers where permitted
- max sizes
- invalid handles
- short I/O
- callback teardown
- concurrent use

## 10. Use dynamic analysis where practical

For Rust/system code, consider tools appropriate to the boundary:

- Miri
- sanitizers
- valgrind
- platform syscall tracing
- fuzzing

Do not add heavyweight tooling without a meaningful target.

## Explicit anti-patterns

Do not:

- spread unsafe merely to avoid wrapper design
- rely on comments without a safe boundary
- use `transmute` when typed conversion exists
- cast sizes blindly
- let native resource ownership remain ambiguous
- expose raw pointers/handles to unrelated modules
- unwind across unsupported FFI boundaries
- assume ABI layouts

## Acceptance criteria

The work is complete only when:

- unsafe regions are narrow
- safety preconditions are documented
- raw contracts are wrapped by safe APIs where practical
- native resource ownership is explicit
- integer/pointer conversions are checked
- ABI layouts are deliberate
- callbacks have lifecycle semantics
- native error handling is correct
- meaningful edge tests/dynamic analysis cover risky paths

The architectural principle is: **unsafe code should concentrate proof obligations at a small boundary so the rest of the program can remain ordinary safe code.**
