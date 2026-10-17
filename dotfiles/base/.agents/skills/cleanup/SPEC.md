# Cleanup Specification

## Intent

Remove completed campaign worktrees only after confirming that their changes are integrated and their checkout data is safe to discard. Keep the coordinator in control of scope and final verification while delegating the inventory and removal pass to one inexpensive worker.

## Scope

In scope: worktrees belonging to the current campaign in the supplied repository.

Out of scope: branches, other repositories, active or parked work, broad disk cleanup, and campaign winddown.

## Users And Trigger Context

- Primary users: campaign coordinators.
- Common requests: clean up merged worktrees; remove completed campaign checkouts.
- Should not trigger for general disk cleanup or worktree cleanup without a named campaign and repository.

## Runtime Contract

- Required first actions: provide the campaign branch and head, scope, and known active worktrees to one low-cost worker.
- Required outputs: removed paths and retained paths with evidence or a reason.
- Non-negotiable constraints: clean checkout, confirmed completion, proven integration, no active owner, no force removal, no branch deletion. A non-ancestor checkout is eligible only if it has no extra merge commits and `git cherry` finds no unmatched commits.
- Expected bundled files loaded at runtime: `SKILL.md` only.

## Source And Evidence Model

Authoritative sources: the user's cleanup request, current campaign record, live Git worktree and status output, and the repository's active-agent state.

Useful improvement sources: cleanup outcomes, removal refusals, and cases retained for uncertainty.

Do not store customer data, secrets, or per-run worktree inventories in the skill.

## Reference Architecture

- `SKILL.md` contains the runtime workflow and safety checks.
- No runtime references, scripts, or assets are needed.
- `SOURCES.md` records authoring provenance and design decisions.

## Validation

- Lightweight validation: skill structure validator and a manual review of trigger scope and removal criteria.
- Deeper validation: review a real cleanup worker's classifications and verify the remaining worktree list.
- Acceptance gates: no checkout is removed unless completion, ownership, cleanliness, and integration are all verified.

## Known Limitations

Patch equivalence does not prove campaign completion by itself; the coordinator must confirm the lane is complete. Unknown or uninspectable ignored data keeps a checkout in place.

## Maintenance Notes

- Update `SKILL.md` when worktree ownership or integration checks change.
- Update `SOURCES.md` when new evidence changes the criteria or trigger.
- Keep run-specific inventories out of the skill directory.
