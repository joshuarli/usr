# Feature Flags, Capabilities, and Rollout Lifecycle

You are improving an existing codebase so feature flags and capability gates have explicit ownership, lifecycle, defaults, compatibility, and removal criteria.

The goal is to prevent permanent dual implementations, combinatorial behavior, stale flags, and hidden runtime modes.

Preserve intended rollout behavior unless explicitly changing it.

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

## 1. Classify each gate

Determine whether it is:

- permanent capability
- temporary rollout flag
- experiment
- kill switch
- compatibility mode
- platform capability detection
- build feature

Different classes need different lifecycle policies.

## 2. Give every temporary flag an owner and end state

A rollout flag should specify:

- owner
- default
- intended final behavior
- removal condition
- compatibility implications

Do not create immortal temporary flags.

## 3. Minimize combinations

Be skeptical of nested independent flags that multiply supported states.

Where possible, replace correlated flags with one explicit mode/state.

## 4. Keep defaults authoritative

Do not repeat default state across:

- code
- config
- deployment
- docs
- tests

Use the canonical settings/policy boundary.

## 5. Keep capability detection separate from preference

"Platform supports X" and "user enabled X" are different facts.

Do not conflate them.

## 6. Remove completed rollout branches

Once one behavior is canonical:

- remove old branch
- remove flag
- remove tests/docs/config
- migrate callers

Do not leave permanent dead branch structure.

## 7. Test both sides while both are supported

For active flags, ensure meaningful behavior is covered in each supported state.

Avoid exhaustive Cartesian testing when combinations are independent and low-risk.

## 8. Keep kill switches simple

Emergency disables should be:

- reliable
- easy to locate
- narrow in scope

Do not route ordinary product configuration through "kill switch" machinery.

## 9. Avoid flags deep in domain logic

Resolve rollout/capability decisions near orchestration boundaries when practical.

Pass an explicit mode/capability rather than repeatedly querying a global flag service.

## 10. Make unsupported combinations fail clearly

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
