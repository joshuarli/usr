# Repository, Workspace, and Package Structure

You are improving this codebase so package/crate/module boundaries align with ownership, build units, release units, and dependency direction.

The goal is a repository tree where a contributor can infer what belongs together and changes do not require touching unrelated units.

Scope: repository/workspace packages, crates, apps, libraries, tools, tests, fixtures, generated/vendor code, root files, and release units.

Applicability: Apply this prompt only when the repository contains multiple package/build units or a tree whose ownership boundaries have become historically accidental. If the condition is materially absent, report that evidence and make no speculative changes.

Preserve: Existing valid behavior, public contracts, persisted data and formats, output, side effects, permissions, state transitions, and supported-platform semantics unless this request explicitly changes them.

Intentional changes: Only changes explicitly authorized by the invoking request; otherwise none.

If inspection shows that the relevant contract already holds, do not manufacture
changes. Verify it, correct only concrete gaps, and report the evidence.

## First inspect the repository

Before editing:

- inventory packages/crates/workspaces/apps/libs/tools/examples
- identify duplicate package boundaries
- identify tiny packages with no independent reason to exist
- identify giant packages containing unrelated domains
- identify circular package dependencies
- identify packages used only as "shared" dumping grounds
- identify build/release/version boundaries
- identify generated code and vendored code placement
- identify tests/fixtures separated far from owned code
- inspect CI/package build graph
- run baseline checks

- Record failures that predate the work.

## Non-negotiable design

Each numbered requirement defines an invariant or observable behavior, its
authoritative owner or boundary, the shortcut or ambiguous state it prohibits,
and the evidence that proves it. Do not prescribe incidental implementation
structure unless that structure is itself part of the contract.

### 1. Align package boundaries with real ownership and change reasons

#### Align package boundaries with independent reasons to change


A package/crate should usually correspond to at least one:

- reusable capability
- stable API boundary
- independent build/release unit
- platform adapter
- dependency isolation boundary
- substantial domain ownership

Do not create packages simply to shorten files.

#### Merge artificial micro-packages


If several packages:

- always change together
- have no external consumers
- merely forward types/functions
- exist only to satisfy an old architecture

consider merging them.

#### Split real ownership boundaries


Split a package when unrelated domains create:

- dependency bloat
- build coupling
- ownership confusion
- release coupling
- test coupling

Do not split based on LOC thresholds.

### 2. Use workspace dependencies and test locality to reinforce ownership

#### Keep dependency direction coherent


Workspace structure should reinforce architecture rather than permit arbitrary cross-imports.

#### Keep tests/fixtures with owners


A contributor should quickly locate the tests and fixtures for a package/domain.

Shared fixtures should be genuinely shared.

### 3. Separate generated/vendor code and keep the root intentional

#### Separate generated/vendor code clearly


Generated and vendored code should not look hand-owned.

Keep provenance and update mechanics obvious.

#### Avoid root-level clutter


Root files should represent repository-wide concerns.

Move domain-specific scripts/config/docs near their owner where ecosystem conventions permit.

### 4. Make repository commands, release boundaries, and names coherent

#### Make canonical commands repository-wide


Document one obvious path for:

- build
- test
- lint
- generate
- package

Workspace orchestration should not require knowing package internals for common tasks.

#### Keep release boundaries explicit


If packages version/release independently, their dependency and compatibility policy should reflect that.

If they always ship together, do not pretend independence unnecessarily.

#### Audit path/name consistency


Package names, directories, import names, binary names, and documentation should use canonical vocabulary.


## Explicit anti-patterns

Do not:

- create a package per folder
- retain micro-packages with no independent purpose
- create giant "shared" packages
- split by arbitrary line count
- place domain-specific files at repo root by habit
- hide generated/vendor ownership
- pretend packages release independently when they never do


## Verification

After editing:

- Run the nearest hard judge for repository/workspace packages, crates, apps, libraries, tools, tests, fixtures, generated/vendor code, root files, and release units: the compiler, type checker, schema/build check, or focused tests that can reject an invalid change.
- Test the observable success behavior, failure behavior, edge cases, and invariants established by the numbered requirements.
- Audit package purpose, micro/mega packages, dependency direction, test/fixture locality, generated/vendor placement, root clutter, canonical commands, release boundaries, and naming; classify every remaining exception rather than assuming it is harmless.
- Broaden checks only when the changed boundary warrants it, and distinguish pre-existing failures from regressions introduced by this work.

## Acceptance criteria

The work is complete only when:

- package boundaries correspond to real ownership/build/release reasons
- artificial micro-packages are reduced
- unrelated domains are not trapped in giant packages
- dependency direction is reinforced by the workspace
- tests/fixtures are easy to locate
- generated/vendor code is clearly separated
- root structure is intentional
- canonical workspace commands are obvious
- naming is consistent across paths/packages/docs

The architectural principle is: **repository structure should encode ownership and change boundaries, not historical accidents.**
