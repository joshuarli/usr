# Repository, Workspace, and Package Structure

You are improving an existing repository so package/crate/module boundaries align with ownership, build units, release units, and dependency direction.

The goal is not more packages. The goal is a repository tree where a contributor can infer what belongs together and changes do not require touching unrelated units.

Preserve public/package contracts unless explicitly changing them.

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

## 1. Align package boundaries with independent reasons to change

A package/crate should usually correspond to at least one:

- reusable capability
- stable API boundary
- independent build/release unit
- platform adapter
- dependency isolation boundary
- substantial domain ownership

Do not create packages simply to shorten files.

## 2. Merge artificial micro-packages

If several packages:

- always change together
- have no external consumers
- merely forward types/functions
- exist only to satisfy an old architecture

consider merging them.

## 3. Split real ownership boundaries

Split a package when unrelated domains create:

- dependency bloat
- build coupling
- ownership confusion
- release coupling
- test coupling

Do not split based on LOC thresholds.

## 4. Keep dependency direction coherent

Workspace structure should reinforce architecture rather than permit arbitrary cross-imports.

## 5. Keep tests/fixtures with owners

A contributor should quickly locate the tests and fixtures for a package/domain.

Shared fixtures should be genuinely shared.

## 6. Separate generated/vendor code clearly

Generated and vendored code should not look hand-owned.

Keep provenance and update mechanics obvious.

## 7. Avoid root-level clutter

Root files should represent repository-wide concerns.

Move domain-specific scripts/config/docs near their owner where ecosystem conventions permit.

## 8. Make canonical commands repository-wide

Document one obvious path for:

- build
- test
- lint
- generate
- package

Workspace orchestration should not require knowing package internals for common tasks.

## 9. Keep release boundaries explicit

If packages version/release independently, their dependency and compatibility policy should reflect that.

If they always ship together, do not pretend independence unnecessarily.

## 10. Audit path/name consistency

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
