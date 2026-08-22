# Unsafe, FFI, and Syscall Boundary Audit

You are improving this codebase so unsafe operations, FFI, raw syscalls, pointer manipulation, memory mapping, and platform-native interfaces are narrow, documented, and wrapped by safe contracts.

The goal is to ensure every unsafe boundary has explicit preconditions and the rest of the codebase does not need to reason about them.

Scope: unsafe blocks/functions, FFI declarations, raw pointers, native handles, manual memory, casts, mmap, syscalls, callbacks, and ABI boundaries.

Applicability: Apply this prompt only when the codebase contains unsafe/native/FFI operations. If the condition is materially absent, report that evidence and make no speculative changes.

Preserve: Existing valid behavior, public contracts, persisted data and formats, output, side effects, permissions, state transitions, and supported-platform semantics unless this request explicitly changes them.

Intentional changes: Only changes explicitly authorized by the invoking request; otherwise none.

If inspection shows that the relevant contract already holds, do not manufacture
changes. Verify it, correct only concrete gaps, and report the evidence.

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

- Record failures that predate the work.

## Non-negotiable design

Each numbered requirement defines an invariant or observable behavior, its
authoritative owner or boundary, the shortcut or ambiguous state it prohibits,
and the evidence that proves it. Do not prescribe incidental implementation
structure unless that structure is itself part of the contract.

### 1. Keep unsafe proof obligations narrow, documented, and safely wrapped

#### Make unsafe blocks minimal


Keep only the operations requiring unsafe inside the block.

Move validation, arithmetic, and ordinary control flow outside.

#### Document safety preconditions


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

#### Build safe wrappers


Convert raw external contracts into safe domain/API types as close to the boundary as possible.

The rest of the codebase should not repeatedly uphold FFI/syscall invariants.

### 2. Make native ownership, conversions, and ABI layout explicit

#### Audit ownership transfer


For every native resource/pointer, identify:

- creator
- owner
- transfer semantics
- destructor/free function
- duplicate/borrow semantics

Avoid double-close, leaks, and use-after-free.

#### Check integer and pointer conversions


Validate:

- signed/unsigned conversions
- size truncation
- alignment
- offsets
- length calculations
- nullability

Do not rely on unchecked casts when external values control them.

#### Keep ABI representations explicit


Use correct representation/layout annotations and types.

Do not assume Rust/C/etc. enum, struct, boolean, or string layouts match without a contract.

### 3. Define callback lifecycle and native error capture correctly

#### Handle callbacks carefully


For callbacks crossing FFI:

- define context ownership
- lifetime
- thread of invocation
- panic/exception behavior
- cancellation/unregistration

Never unwind across an ABI that forbids it.

#### Audit errno/last-error semantics


Capture mechanism-specific error state at the correct moment.

Do not call unrelated APIs before reading thread-local/native error state where that would destroy it.

### 4. Test edge conditions and apply targeted dynamic analysis

#### Test edge conditions


Cover:

- zero lengths
- null pointers where permitted
- max sizes
- invalid handles
- short I/O
- callback teardown
- concurrent use

#### Use dynamic analysis where practical


For Rust/system code, consider tools appropriate to the boundary:

- Miri
- sanitizers
- valgrind
- platform syscall tracing
- fuzzing

Do not add heavyweight tooling without a meaningful target.

### Migration and compatibility policy

Do not create parallel legacy and canonical implementations as part of this work.
If a rename, move, replacement, or contract change becomes necessary, inventory all
references first, keep one canonical path, and retain compatibility only when the
invoking request or an existing external contract requires it.

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


## Verification

After editing:

- Run the nearest hard judge for unsafe blocks/functions, FFI declarations, raw pointers, native handles, manual memory, casts, mmap, syscalls, callbacks, and ABI boundaries: the compiler, type checker, schema/build check, or focused tests that can reject an invalid change.
- Test the observable success behavior, failure behavior, edge cases, and invariants established by the numbered requirements.
- Audit unsafe scope, safety preconditions, safe wrappers, ownership transfer, numeric/pointer conversions, ABI layout, callbacks, native errors, and dynamic-analysis targets; classify every remaining exception rather than assuming it is harmless.
- Broaden checks only when the changed boundary warrants it, and distinguish pre-existing failures from regressions introduced by this work.

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
