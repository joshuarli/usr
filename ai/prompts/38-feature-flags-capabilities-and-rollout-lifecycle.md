# Feature Flags, Capabilities, and Rollout Lifecycle

You are improving this codebase so feature flags and capability gates have explicit ownership, lifecycle, defaults, compatibility, and removal criteria.

The goal is to prevent permanent dual implementations, combinatorial behavior, stale flags, and hidden runtime modes.

Scope: compile-time/runtime feature flags, rollout gates, experiments, kill switches, compatibility modes, capability detection, defaults, and flag combinations.

Applicability: Apply this prompt only when the repository contains feature/capability gates or rollout branches. If the condition is materially absent, report that evidence and make no speculative changes.

Preserve: Existing valid behavior, public contracts, persisted data and formats, output, side effects, permissions, state transitions, and supported-platform semantics unless this request explicitly changes them.

Intentional changes: Only changes explicitly authorized by the invoking request; otherwise none.

If inspection shows that the relevant contract already holds, do not manufacture
changes. Verify it, correct only concrete gaps, and report the evidence.

## First inspect the repository

Before editing:

- inventory compile-time features
- runtime flags
- environment toggles
- account/tenant gates
- experiments
- rollout percentages
- kill switches
- compatibility modes
- deprecated flags
- capability detection
- identify flags that gate the same behavior
- identify nested flag combinations
- identify flags whose rollout has completed
- inspect tests for on/off paths
- run baseline checks

- Record failures that predate the work.

## Non-negotiable design

Each numbered requirement defines an invariant or observable behavior, its
authoritative owner or boundary, the shortcut or ambiguous state it prohibits,
and the evidence that proves it. Do not prescribe incidental implementation
structure unless that structure is itself part of the contract.

### 1. Classify gates, give temporary flags a lifecycle, and minimize combinations

#### Classify each gate


Determine whether it is:

- permanent capability
- temporary rollout flag
- experiment
- kill switch
- compatibility mode
- platform capability detection
- build feature

Different classes need different lifecycle policies.

#### Give every temporary flag an owner and end state


A rollout flag should specify:

- owner
- default
- intended final behavior
- removal condition
- compatibility implications

Do not create immortal temporary flags.

#### Minimize combinations


Be skeptical of nested independent flags that multiply supported states.

Where possible, replace correlated flags with one explicit mode/state.

### 2. Keep defaults authoritative and capability distinct from preference

#### Keep defaults authoritative


Do not repeat default state across:

- code
- config
- deployment
- docs
- tests

Use the canonical settings/policy boundary.

#### Keep capability detection separate from preference


"Platform supports X" and "user enabled X" are different facts.

Do not conflate them.

### 3. Remove completed branches while testing every still-supported side

#### Remove completed rollout branches


Once one behavior is canonical:

- remove old branch
- remove flag
- remove tests/docs/config
- migrate callers

Do not leave permanent dead branch structure.

#### Test both sides while both are supported


For active flags, ensure meaningful behavior is covered in each supported state.

Avoid exhaustive Cartesian testing when combinations are independent and low-risk.

### 4. Keep kill switches narrow and flag resolution out of deep domain logic

#### Keep kill switches simple


Emergency disables should be:

- reliable
- easy to locate
- narrow in scope

Do not route ordinary product configuration through "kill switch" machinery.

#### Avoid flags deep in domain logic


Resolve rollout/capability decisions near orchestration boundaries when practical.

Pass an explicit mode/capability rather than repeatedly querying a global flag service.

### 5. Reject unsupported combinations explicitly


If two features conflict, encode and test that constraint.


## Explicit anti-patterns

Do not:

- create flags without removal criteria
- leave completed rollouts in dual-path state
- scatter global flag lookups through business logic
- conflate capability with preference
- create boolean combinations representing a hidden enum
- duplicate defaults
- test every Cartesian feature combination blindly


## Verification

After editing:

- Run the nearest hard judge for compile-time/runtime feature flags, rollout gates, experiments, kill switches, compatibility modes, capability detection, defaults, and flag combinations: the compiler, type checker, schema/build check, or focused tests that can reject an invalid change.
- Test the observable success behavior, failure behavior, edge cases, and invariants established by the numbered requirements.
- Audit gate classification, temporary lifecycle, combinations, defaults, capability vs preference, completed rollout removal, supported paths, kill switches, flag lookup location, and conflicts; classify every remaining exception rather than assuming it is harmless.
- Broaden checks only when the changed boundary warrants it, and distinguish pre-existing failures from regressions introduced by this work.

## Acceptance criteria

The work is complete only when:

- every feature gate has a clear class
- temporary flags have owners and end states
- completed flags are removed
- combinations are minimized
- defaults are canonical
- capability detection and preference are distinct
- active supported paths are tested
- global flag lookups do not permeate domain logic
- conflicting combinations are rejected clearly

The architectural principle is: **a feature flag is a temporary branch in reality; give it a lifecycle before it becomes permanent architecture.**
