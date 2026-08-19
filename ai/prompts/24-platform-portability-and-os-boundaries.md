# Platform Portability and OS Boundary Audit

You are improving an existing multi-platform codebase so platform differences are isolated, explicit, and tested instead of leaking through scattered conditionals.

The goal is not universal portability. The goal is clean, deliberate support for the platforms the project actually claims to support.

Preserve supported-platform behavior and contracts unless explicitly changing support policy.

## First inspect the repository

Before editing:

- inventory platform conditionals, `cfg` blocks, build tags, preprocessor conditionals, OS checks, architecture checks, syscall wrappers, path assumptions, process semantics, terminal behavior, filesystem behavior, networking differences, and packaging differences
- identify repeated platform conditionals across unrelated modules
- identify platform-specific constants scattered through business logic
- identify fallback code paths that are rarely tested
- identify unsupported platforms accidentally compiling partially
- inspect CI matrix and platform-specific tests
- run baseline checks on available supported targets

## 1. State the support matrix

Make explicit which combinations are supported:

```text
OS
architecture
runtime/library version
filesystem/terminal assumptions where material
```

Do not imply support merely because code happens to compile.

## 2. Isolate platform mechanisms

Prefer:

```text
platform/
  unix
  macos
  linux
  windows
```

or the repository's equivalent where meaningful.

Keep high-level domain logic platform-neutral when semantics are actually shared.

## 3. Keep platform policy separate from platform mechanism

A macOS implementation may use a different syscall than Linux while preserving the same application-level contract.

Do not duplicate entire workflows when only one mechanism differs.

## 4. Avoid scattered conditional compilation

If the same platform distinction appears in many files, establish a narrow platform abstraction.

Do not create an elaborate portability layer for one tiny conditional.

## 5. Fail unsupported combinations clearly

If a target is unsupported, prefer an explicit compile/configuration failure over a partially working binary with hidden missing behavior.

## 6. Normalize semantics at the boundary

Where platforms expose different mechanism-level behavior, define the application contract explicitly.

Examples:

- process signals
- file replacement
- terminal modes
- permissions
- path encoding
- clock behavior

## 7. Preserve platform-native values

Do not force Unix paths, process arguments, identifiers, or metadata through portable-looking UTF-8/string abstractions when that loses information.

## 8. Test platform-specific behavior

Use real platform integration tests for semantics that cannot be faithfully mocked.

CI should exercise every claimed supported platform when practical.

## 9. Keep fallback behavior intentional

Fallbacks should identify:

- why the preferred mechanism is unavailable
- semantic differences
- supported platforms
- test coverage

Do not silently fall back to weaker correctness semantics.

## 10. Audit architecture assumptions

Look for:

- pointer width
- endianness
- alignment
- page size
- CPU features
- atomic support

when low-level code depends on them.

## 11. Keep conditional dependency graphs coherent

Platform-specific dependencies should be scoped to relevant targets/features.

Avoid pulling every platform backend into every build.

## Explicit anti-patterns

Do not:

- claim portability because compilation succeeds
- scatter identical OS checks everywhere
- duplicate whole workflows for tiny mechanism differences
- erase native path/argument semantics for portability
- silently downgrade correctness on fallback paths
- keep unsupported targets half-working
- add a portability framework for one simple branch

## Verification

After editing:

- inspect all remaining platform conditionals
- test every claimed supported target available in CI
- verify unsupported combinations fail clearly
- verify platform-specific dependencies are properly scoped
- test semantics rather than only compilation
- document unavoidable platform differences

## Acceptance criteria

The work is complete only when:

- support policy is explicit
- platform-specific mechanisms are isolated
- shared application semantics remain centralized
- scattered conditionals are reduced
- unsupported combinations fail clearly
- native path/process/filesystem semantics are preserved
- fallbacks have deliberate semantics
- claimed platforms have real integration coverage
- target-specific dependencies are scoped correctly

The architectural principle is: **portability means one explicit contract implemented by platform-specific mechanisms—not pretending operating systems are identical.**
