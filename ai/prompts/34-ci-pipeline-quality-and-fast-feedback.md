# CI Pipeline Quality and Fast Feedback

You are improving an existing CI system so failures are fast, deterministic, attributable, and representative of real release quality.

The goal is not more CI jobs. The goal is a pipeline that gives developers and coding agents the earliest useful signal with minimal redundant work.

Preserve required quality gates and release semantics.

## First inspect the repository

Before editing:

- inventory CI workflows/jobs/steps
- identify duplicate setup/build/test work
- identify cache behavior
- identify flaky jobs
- identify long serial critical paths
- identify jobs that test the same thing repeatedly
- identify release-only checks
- identify platform/toolchain matrices
- identify artifact handoff
- identify secrets/permissions
- identify conditional/skipped behavior
- inspect historical durations/failure modes when available
- run/validate workflow syntax

## 1. Order checks by signal-per-time

Run cheap high-signal failures early:

```text
format/lint/typecheck
focused compile
unit tests
integration tests
platform/end-to-end
packaging/release
```

Adapt to the repository; do not enforce this exact sequence mechanically.

## 2. Avoid repeated work

Reuse:

- built artifacts
- dependency caches
- generated outputs
- test discovery

when safe.

Do not cache nondeterministic or incorrectly keyed outputs.

## 3. Make failures attributable

A failing job should identify the contract that failed.

Avoid giant jobs containing unrelated checks whose logs are difficult to navigate.

## 4. Keep jobs cohesive

Split by meaningful failure domain, not arbitrary file count.

Avoid hundreds of tiny jobs whose scheduling overhead dominates.

## 5. Make matrices intentional

Test only supported:

- OS
- architecture
- toolchain
- feature combinations

Use representative coverage rather than combinatorial explosion unless compatibility requires it.

## 6. Attack flakiness as a correctness bug

Do not add retries around flaky tests as the primary fix.

Identify nondeterminism, environment leakage, timing races, and shared-resource collisions.

## 7. Keep CI close to local workflows

A developer should be able to reproduce important CI checks locally with canonical commands.

Avoid CI-only magic.

## 8. Use cache keys from real inputs

Cache keys should account for:

- lockfiles
- toolchain
- target
- features
- relevant config

Do not cache stale outputs under broad branch-only keys.

## 9. Bound permissions

Jobs should receive only required credentials and repository permissions.

Untrusted code paths should not inherit release secrets.

## 10. Make artifacts explicit

When jobs pass artifacts, define:

- producer
- consumer
- retention
- provenance
- integrity expectations

## 11. Separate merge confidence from release assurance

Some expensive checks may run post-merge/nightly/release if they do not materially improve PR feedback.

Do not defer essential correctness checks merely to make PR CI fast.

## 12. Track pipeline health

Where useful, observe:

- duration
- queue time
- flake rate
- cache hit rate
- failure frequency by job

## Explicit anti-patterns

Do not:

- add retries to hide flakiness
- run identical builds in every job
- create huge combinatorial matrices by default
- cache without correct invalidation keys
- make CI impossible to reproduce locally
- expose broad secrets/permissions
- split into tiny jobs solely for visual parallelism
- optimize duration by removing meaningful quality gates

## Acceptance criteria

The work is complete only when:

- cheap high-signal failures occur early
- redundant work is reduced
- jobs have clear semantic ownership
- supported-platform matrices are intentional
- flaky behavior is fixed rather than masked
- important checks reproduce locally
- caches are keyed correctly
- permissions are minimal
- artifact flow is explicit
- release assurance remains intact
- pipeline duration and failure signal improve or remain justified

The architectural principle is: **CI should minimize time-to-trust, not maximize the number of green boxes.**
