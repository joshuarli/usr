# CI Pipeline Quality and Fast Feedback

You are improving this codebase so failures are fast, deterministic, attributable, and representative of real release quality.

The goal is a pipeline that gives developers and coding agents the earliest useful signal with minimal redundant work.

Scope: CI workflows/jobs/steps, matrices, caches, artifacts, permissions, flaky checks, critical path, release gates, and local reproducibility.

Applicability: Apply this prompt only when the repository uses CI and its feedback latency, determinism, attribution, or release confidence can be materially improved. If the condition is materially absent, report that evidence and make no speculative changes.

Preserve: Existing valid behavior, public contracts, persisted data and formats, output, side effects, permissions, state transitions, and supported-platform semantics unless this request explicitly changes them.

Intentional changes: Only changes explicitly authorized by the invoking request; otherwise none.

If inspection shows that the relevant contract already holds, do not manufacture
changes. Verify it, correct only concrete gaps, and report the evidence.

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

- Record failures that predate the work.

## Non-negotiable design

Each numbered requirement defines an invariant or observable behavior, its
authoritative owner or boundary, the shortcut or ambiguous state it prohibits,
and the evidence that proves it. Do not prescribe incidental implementation
structure unless that structure is itself part of the contract.

### 1. Order checks for fast signal and avoid redundant work

#### Order checks by signal-per-time


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

#### Avoid repeated work


Reuse:

- built artifacts
- dependency caches
- generated outputs
- test discovery

when safe.

Do not cache nondeterministic or incorrectly keyed outputs.

### 2. Make failures attributable through cohesive jobs

#### Make failures attributable


A failing job should identify the contract that failed.

Avoid giant jobs containing unrelated checks whose logs are difficult to navigate.

#### Keep jobs cohesive


Split by meaningful failure domain, not arbitrary file count.

Avoid hundreds of tiny jobs whose scheduling overhead dominates.

### 3. Keep matrices intentional and treat flakiness as correctness

#### Make matrices intentional


Test only supported:

- OS
- architecture
- toolchain
- feature combinations

Use representative coverage rather than combinatorial explosion unless compatibility requires it.

#### Attack flakiness as a correctness bug


Do not add retries around flaky tests as the primary fix.

Identify nondeterminism, environment leakage, timing races, and shared-resource collisions.

### 4. Keep CI reproducible locally with correctly keyed caches

#### Keep CI close to local workflows


A developer should be able to reproduce important CI checks locally with canonical commands.

Avoid CI-only magic.

#### Use cache keys from real inputs


Cache keys should account for:

- lockfiles
- toolchain
- target
- features
- relevant config

Do not cache stale outputs under broad branch-only keys.

### 5. Minimize permissions and make artifact flow explicit

#### Bound permissions


Jobs should receive only required credentials and repository permissions.

Untrusted code paths should not inherit release secrets.

#### Make artifacts explicit


When jobs pass artifacts, define:

- producer
- consumer
- retention
- provenance
- integrity expectations

### 6. Separate merge/release assurance and observe pipeline health

#### Separate merge confidence from release assurance


Some expensive checks may run post-merge/nightly/release if they do not materially improve PR feedback.

Do not defer essential correctness checks merely to make PR CI fast.

#### Track pipeline health


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


## Verification

After editing:

- Run the nearest hard judge for CI workflows/jobs/steps, matrices, caches, artifacts, permissions, flaky checks, critical path, release gates, and local reproducibility: the compiler, type checker, schema/build check, or focused tests that can reject an invalid change.
- Test the observable success behavior, failure behavior, edge cases, and invariants established by the numbered requirements.
- Audit signal ordering, duplicate work, job cohesion, matrices, flakiness, local parity, cache keys, permissions, artifact flow, and pipeline health; classify every remaining exception rather than assuming it is harmless.
- Broaden checks only when the changed boundary warrants it, and distinguish pre-existing failures from regressions introduced by this work.

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
