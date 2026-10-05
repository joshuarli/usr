---
name: orchestrate
description: Route substantial, routine, mechanical, exploratory, or context-heavy work across subagents to control cost, isolate context, and parallelize independent work, and run a multi-lane campaign over a backlog. Delegate whenever the work is economical to specify and verify.
---

# Orchestrate

Delegate when specification and verification cost less than doing the work locally. Keep the parent responsive and responsible for integration and final verification.

## Routing

Route by difficulty, uncertainty, and risk. Use the column for the harness you are running in.

| Work | Codex | Claude |
| --- | --- | --- |
| Read-only scouting, searches, inventories, documentation lookup, log triage, straightforward fact gathering | `gpt-6-luna`, `low` | `haiku`, or the `Explore` agent type |
| Mechanical edits, routine implementation, straightforward documentation, crisp acceptance criteria | `gpt-6-luna`, `xhigh` | `sonnet`, `xhigh` |
| Normal implementation, debugging, tests, ordinary review | `gpt-6.1-sol`, `medium` | `opus`, `medium` |
| Difficult debugging, cross-cutting implementation, architecture, integration, demanding review | `gpt-6.1-sol`, `high` | `opus`, `high` |

If work exceeds the parent's delegation ceiling, keep it local at the highest suitable effort rather than spawning above the parent. If a selected model is unavailable, use a suitable allowed model at the same or lower tier or report the limitation. A failed command, missing dependency, or unavailable environment does not by itself justify model escalation.

### Codex

Allowed child models, highest to lowest: `gpt-6.1-sol` > `gpt-6-luna`.

Never assign a child `gpt-6-astra` or `gpt-6-sol`. GPT-5.x and Terra are also banned. Never use `ultra` effort; its automatic delegation conflicts with this skill.

Always specify `model`, `reasoning_effort`, and `fork_turns`. Prefer `fork_turns: "none"` with a self-contained brief; otherwise use the smallest positive turn count needed.

### Claude

Allowed child models, highest to lowest: `opus` > `sonnet` > `haiku`.

A subagent's reasoning effort comes from its agent definition (`.claude/agents/NAME.md` frontmatter: `model`, `effort`), not from the call; the call can override only the model. When the model and effort a task needs have no definition, add one to the project instead of settling for the nearest. Prefer a fresh agent with a self-contained brief over a fork; fork only when the child needs the conversation itself.

Give every parallel writer `isolation: "worktree"`. A child's final report is not shown to the user: relay what matters. Background children notify on completion, so do not poll them, and send a running child a message when the rules change instead of restarting it.

## Delegation

Delegate coherent component-sized work; do not delegate a one-command or one-edit task when the handoff costs more than doing it locally. Batch related trivial work into one assignment.

Parallelize only independent ownership. Avoid overlapping writes, and use the smallest useful fan-out; concurrency is a ceiling, not a target.

Every child gets:

- Clear ownership and write boundaries.
- A concrete deliverable with only the needed context.
- Proportionate checks and a stopping condition.
- No further delegation unless explicitly given a nested budget and scope.

Carry forward findings and failed approaches.

## Campaigns

A campaign is a backlog too large for one session, run as parallel lanes over several waves. The parent is the integrator: it selects, briefs, reviews, merges, verifies, and reports to the owner. It writes no feature code while lanes are running.

### Prepare

- Group the backlog into workstreams by the code they share, so that work likely to conflict is serialized inside one lane. Order the items in each workstream, give each a stable ID, and write prerequisites that cross workstreams on the item.
- Close design decisions with the owner before assigning. An item with an open decision is not assigned; a lane that meets one stops on it and reports options.
- Before the first wave, measure the tools every lane will run many times and fix what is slow, and make shared architecture changes yourself or in one dedicated lane. Lanes should add to a structure, not invent it in parallel.
- Write the workflow and the lane contract into the repository, and give lanes an agent definition that points at them, so a brief only has to say what is specific to the lane.

### Run a wave

1. **Select.** For each workstream take the next items whose prerequisites have merged. One to three items per lane, sized for one session. A workstream with nothing ready sits out.
2. **Brief.** Item IDs, files the lane owns and files it must not touch, what earlier waves learned, and the report format. The brief is the lane's only context beyond the repository.
3. **Launch** the wave together, each lane in its own worktree, committing on its own branch and never pushing. Start below the fan-out limit and widen once the load on the machine is known.
4. **Review, merge, then verify**, one lane at a time as they report. Read the diff, rebase the lane onto the campaign branch, fast-forward, then run the checks for the areas it touched on the merged tree. Send a failure back to the lane with the command and its output.
5. **Close** with every lane merged and none running: the full checks, the performance measurements against the baseline, and any repository-wide rewrite the wave made possible. Such rewrites run only here, because they change the files lanes read.
6. **Record.** Delete finished items, add the defects found, and report to the owner: what merged, every contract change, measurements, and the decisions the next wave needs.

### Lane contract

- Lanes never coordinate with each other. A lane that needs something from another workstream reports it; the integrator sequences it.
- Verification belongs to the integrator. A lane uses the cheapest build that compiles its change and runs only the tests it wrote or changed, by name. It does not run suites, slow or repository-wide checks, or optimized builds; those run once, after the merge, on the code that will ship. A lane's report names what the integrator's checks should exercise and what it left unverified.
- Shared files are append-only for a lane: add to a registry at the end of its group, put a new unit in its own file, and do not reorganize, rename, or reformat.
- A change in the behavior of existing code is named in the report and ships with whatever makes old code explicit first.
- A lane does not rewrite the corpus, settle an open decision, add a dependency, or fix another workstream's defect. It reports them.
