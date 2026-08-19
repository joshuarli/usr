# Build, Release, and Code Generation Hygiene

You are improving an existing codebase so builds, generated artifacts, version metadata, feature combinations, and release outputs are reproducible, inspectable, and owned by clear inputs.

The goal is to eliminate build-script magic, stale generated files, hidden environment dependencies, and release-only behavior that ordinary development does not exercise.

Preserve artifact compatibility unless explicitly changing release behavior.

## First inspect the repository

Before editing:

- inspect build scripts, Makefiles, task runners, package scripts, CI build commands, code generation, bindgen/protobuf/OpenAPI/schema generation, embedded assets, version stamping, feature flags, release profiles, linker flags, and packaging
- identify generated files checked into source
- identify generated files with unclear source commands
- identify build behavior dependent on undeclared environment variables
- identify network access during builds
- identify build scripts with broad rerun triggers
- identify release-only conditional code
- identify differences between local and CI/release builds
- run representative baseline builds

## 1. Make build inputs explicit

A build should depend on identifiable inputs:

- source
- lockfile
- compiler/toolchain
- features
- environment variables
- generated sources
- platform

Avoid ambient machine state.

## 2. Keep builds offline-capable where practical

Do not fetch arbitrary network resources during compilation unless the build contract explicitly requires it.

Prefer vendored/pinned/generated inputs established before compile time.

## 3. Make code generation reproducible

For every generated artifact, define:

- authoritative source
- generator/tool version
- exact command
- destination
- whether output is checked in
- how drift is detected

Generated files should say they are generated and where from.

## 4. Detect stale generated output

If generated files are committed, CI should be able to regenerate and detect diffs.

Do not rely on maintainers remembering to rerun generators.

## 5. Keep build scripts narrow

Build scripts should perform only tasks that genuinely belong at build time.

Avoid turning build scripts into general-purpose orchestration engines.

For Rust, use precise Cargo rerun directives rather than rerunning on every build.

## 6. Make version metadata deterministic

Define policy for:

- package version
- git SHA
- dirty state
- release tag
- build timestamp

Do not execute source-control commands at runtime merely to report version.

Avoid nondeterministic timestamps unless intentionally part of the artifact.

## 7. Audit feature combinations

For feature-gated builds:

- define supported combinations
- avoid accidental mutually incompatible states
- test representative/minimal/maximal sets
- avoid features silently changing unrelated semantics

## 8. Keep release behavior close to development behavior

Release builds may optimize differently, but should not enable major untested logic paths solely in release environments.

## 9. Make artifacts inspectable

A release artifact should make it possible to determine:

- version
- source revision
- target/platform
- enabled significant features where relevant

without relying on network access.

## 10. Minimize toolchain sprawl

Avoid requiring multiple overlapping build orchestrators for ordinary workflows.

Document one canonical path for:

- build
- test
- generate
- package/release

## 11. Keep secrets out of build artifacts

Audit environment substitution and generated files to ensure CI secrets are not embedded accidentally.

## 12. Test clean builds

Validate from a clean checkout/worktree or equivalent to catch hidden generated/local dependencies.

## Explicit anti-patterns

Do not:

- fetch mutable remote content during compilation
- hide generator provenance
- commit generated files without a drift check
- put broad unrelated orchestration in build scripts
- depend on undeclared environment state
- stamp nondeterministic metadata without reason
- create release-only logic that ordinary tests never exercise
- require multiple task runners for the same operation
- embed CI secrets

## Verification

After editing:

- perform a clean build
- regenerate committed artifacts and confirm no diff
- test supported feature sets
- inspect embedded version metadata
- verify precise build-script rerun behavior
- verify offline build assumptions where applicable
- inspect artifacts for accidental secrets/host paths

## Acceptance criteria

The work is complete only when:

- build inputs are explicit
- codegen is reproducible and traceable
- stale generated output is mechanically detectable
- build scripts are narrow
- version metadata is deterministic and compile-time where appropriate
- supported feature combinations are clear and tested
- release behavior does not hide untested logic
- canonical build/test/generate/release commands are documented
- clean builds succeed without accidental local state
- secrets and host-specific data are not embedded unintentionally

The architectural principle is: **a build should be a deterministic transformation of declared inputs into inspectable artifacts.**
