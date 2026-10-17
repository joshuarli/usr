# Cleanup Skill Sources

## Synthesis

- Class: `workflow-process`; cleanup is a repeatable, safety-sensitive operation.
- Primary shape: `orchestrator-workers`; one worker inventories and removes candidates.
- Secondary shape: plan-validate-execute; Git and campaign evidence validate each removal before execution.
- Simpler shapes rejected: inline-only coordinator work would not provide the requested low-cost worker pass; scripts add no value because ownership and completion require campaign context.
- Portability: prompt-level delegation and standard Git commands; use the agent spawning mechanism available in the current environment.

## Sources

| Source | Trust | Contribution | Use |
|---|---|---|---|
| User request in the current session | Authoritative | Scope: campaign worktrees that are completed and merged; use a cheap worker | Directly shapes the trigger and delegation |
| `../campaign-winddown/SKILL.md` in the same skill tree | Local operational guidance | Preserve useful ignored or untracked data; remove checkouts without force; retain only work with a current consumer | Adapted for active campaign cleanup; full winddown steps excluded |
| `../orchestrate/SKILL.md` in the same skill tree | Local operational guidance | Worker tier mapping and bounded delegation contracts | Adapted to one low-cost worker and coordinator synthesis |
| `skill-writer/references/workflow-orchestrator-workers.md` | Skill authoring guidance | Stable worker scope, output, stopping rule, and synthesis | Worker contract coverage |
| `skill-writer/references/workflow-plan-validate-execute.md` | Skill authoring guidance | Validate the removal plan against live state before acting | Per-checkout evidence gate |
| `skill-creator/SKILL.md` | Skill authoring guidance | Scope, concise runtime instructions, and portable skill layout | Frontmatter and runtime structure |

## Coverage And Gaps

| Dimension | Decision | Evidence |
|---|---|---|
| Happy path | Adopted | Clean, completed checkout with all commits integrated |
| Edge behavior | Adopted | Retain on dirty state, active ownership, lock, ignored-data uncertainty, or failed removal |
| False positives | Adopted | Require campaign membership and affirmative completion evidence |
| Worker contract | Adopted | One bounded worker; coordinator supplies scope and verifies the final list |
| Stop rule | Adopted | No recursion, branch deletion, force removal, or scope expansion |
| Provider-specific behavior | Deferred | No provider-specific spawning syntax is required |

Further source collection is low-yield for this narrow skill: its behavior is defined by the user request, live Git state, and established local campaign guidance.

## Description Check

Should trigger: “clean up the merged worktrees from this campaign”; “remove completed campaign checkouts.”

Should not trigger: “free disk space by deleting build caches”; “remove this unmerged worktree”; “clean up all worktrees on this machine.”

The description identifies campaign scope, confirmed integration, and the common cleanup request while excluding general cleanup.
