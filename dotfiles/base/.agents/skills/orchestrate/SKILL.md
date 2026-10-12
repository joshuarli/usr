---
name: orchestrate
description: "Route substantial, routine, mechanical, exploratory, or context-heavy work across subagents to control cost, isolate context, and parallelize independent work, and run a multi-lane campaign over a backlog. Delegate whenever the work is economical to specify and verify. Skip a task cheaper to do directly."
---

# Orchestrate

Delegate when specification and verification cost less than doing the work locally. Keep the parent responsive and responsible for integration and final verification.

## Routing

Route by difficulty, uncertainty, and risk. Use the column for the harness you are running in.

| Work | Codex | Claude |
| --- | --- | --- |
| Read-only scouting, searches, inventories, documentation lookup, log triage, straightforward fact gathering | `gpt-6-luna`, `xhigh` | `scout` |
| Mechanical edits, routine implementation, straightforward documentation, crisp acceptance criteria | `gpt-6-luna`, `xhigh` | `mechanic` |
| Normal implementation, debugging, tests, ordinary review | `gpt-6-luna`, `xhigh` | `worker` |
| Difficult debugging, cross-cutting implementation, architecture, integration, demanding review | `gpt-6-luna`, `xhigh` | `expert` |
| The hardest work: a failure an `expert` could not explain, a design others will build on, the final adversarial review before landing | `gpt-6-luna`, `xhigh` | `god` |

**Default to `worker`.** Size is not difficulty. A big lane with a clear method and acceptance (a profiled optimization, a port with a reference, a mock built from a design doc, an investigation with a known procedure, a bug fix with a reproduction) is a `worker` task, and so is most campaign lane work. Use `expert` only when the path is unknown and a wrong turn is costly: a cross-cutting design, a failure with no hypothesis, an integration that spans owners. If the brief can name the steps and the acceptance check, it is not an `expert` brief. Start with `worker` and escalate on evidence that the work was harder than briefed.

If work exceeds the parent's delegation ceiling, keep it local at the highest suitable effort rather than spawning above the parent, except for the Codex child profile specified below. If a selected model is unavailable, use a suitable allowed model at the same or lower tier or report the limitation. A failed command, missing dependency, or unavailable environment does not by itself justify model escalation.

### Codex

Use `gpt-6-luna` at `xhigh` effort for every Codex child, including scouts. This profile overrides the parent's effort ceiling; if Luna is unavailable, report the limitation instead of substituting a model.

Never assign a child `gpt-6-astra` or `gpt-6-sol`. GPT-5.x and Terra are also banned. Never use `ultra`: its automatic delegation conflicts with this skill.

Always specify `model`, `reasoning_effort`, and `fork_turns`. Prefer `fork_turns: "none"` with a self-contained brief; otherwise use the smallest positive turn count needed.

### Claude

Spawn children only as `scout`, `mechanic`, `worker`, `expert`, or `god`, never a built-in type. They rank `scout` < `mechanic` < `worker` < `expert` < `god`, and an agent spawns only tiers strictly below its own (`scout` spawns nothing). Claude cannot restrict spawn types per nested subagent in a definition, so the `agent-tier-gate` PreToolUse hook enforces the order on every spawn, and `CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH` caps nesting at 3. A subagent's model and reasoning effort come from its agent definition in `~/.claude/agents` (frontmatter `model`, `effort`), not from the call, which can override only the model. Those definitions are the single source of truth: change a type's model or effort there, not here. Built-in agent types do not pin effort. Reserve `expert` for the difficult row, and `god` for work an `expert` has failed on with evidence of the difficulty, or for a decision others build on. When a task needs a model and effort none of the five provide, add a definition instead of settling for the nearest. Prefer a fresh agent with a self-contained brief over a fork; fork only when the child needs the conversation itself.

Give every parallel writer its own worktree, created by you with `git worktree add .work/wt/<name> -b <branch>` and named in the brief as the only place it may write. `isolation: "worktree"` also lands in `.work/wt/` through the WorktreeCreate hook, but its branch name is generated and the tree outlives the child, so campaigns create their own. A child's final report is not shown to the user: relay what matters. Background children notify on completion, so do not poll them, and send a running child a message when the rules change instead of restarting it.

## Delegation

Delegate coherent component-sized work; do not delegate a one-command or one-edit task when the handoff costs more than doing it locally. Batch related trivial work into one assignment.

Maximize parallel work without overlap. Split the task by what each piece owns, and run one child per disjoint ownership set, as wide as the machine's headroom allows. Width follows the task: one child for a single coupled change, many for a wide one. Overlapping writes are the only limit on width, so serialize them inside one child. Give each child the largest coherent slice it can finish end to end, not a fragment that needs a second handoff.

Idle capacity is a defect. Whenever a child reports, a merge lands, a check finishes, or the owner asks, list the ready work that has no owner and launch it before starting anything slow yourself. Stagger rather than wait: a child may start on the current base while other children are unmerged, when the files it owns are disjoint from theirs; the parent merges and resolves conflicts later, which costs less than an idle child.

Every child gets:

- Clear ownership and write boundaries.
- A concrete deliverable with only the needed context.
- Proportionate checks and a stopping condition.
- No further delegation unless the brief grants it, and then only to lower tiers (Claude) within the depth cap. Codex children are all one tier, so `agents.max_depth` is the only limit.

Carry forward findings and failed approaches.

## Campaigns

A campaign is a backlog too large for one session, run as parallel lanes in rolling tranches: a wave is a selection of ready work, not a barrier, and later tranches start as soon as their prerequisites allow. The parent is the integrator: it selects, briefs, reviews, merges, verifies, and reports to the owner. It writes no feature code while lanes are running.

### Prepare

- Group the backlog into workstreams by the code they share, so that work likely to conflict is serialized inside one lane. Order the items in each workstream, give each a stable ID, and write prerequisites that cross workstreams on the item.
- State each prerequisite as the narrowest thing the dependent item needs (a store, a type, one call site), and split an item into the part that does not need it and the part that does. The first part starts now and leaves a named seam; the second is a follow-up to the same lane once the prerequisite merges.
- Close design decisions with the owner before assigning. An item with an open decision is not assigned; a lane that meets one stops on it and reports options.
- Before the first wave, measure the tools every lane will run many times and fix what is slow, and make shared architecture changes yourself or in one dedicated lane. Lanes should add to a structure, not invent it in parallel.
- Write the workflow and the lane contract into the repository, and give lanes an agent definition that points at them, so a brief only has to say what is specific to the lane.

### Run a wave

1. **Select.** For each workstream take every ready item whose prerequisites have merged (or whose independent part can start, see Prepare) and that shares its files, as one slice the lane delivers end to end: code, tests, and docs, with what it obsoletes removed. Make the slice as large as one session can finish, so a few big lanes beat many small ones over the same files. Split a workstream across lanes only when its items own disjoint files. A workstream with nothing ready sits out. The wave has one lane per workstream with ready work, plus the lanes for work that does not touch the workstreams at all: docs for what has landed, read-side tooling, experiment plans and measurement harnesses for the close.
2. **Brief.** Item IDs, files the lane owns and files it must not touch, what earlier waves learned, and the report format. The brief is the lane's only context beyond the repository.
3. **Launch** the wave together, each lane in its own worktree under `.work/wt/`, committing on its own branch as Conventional Commits and never pushing. Size the wave by the machine: launch the first lanes, read their peak memory and load once they build, then set the width from the available memory with a margin, so the next wave runs as wide as is safe and the machine never swaps or OOMs. Do not hold a launch for the previous wave to finish: tranches overlap.
4. **Review, merge, then verify**, one lane at a time as they report. Read the diff, rebase the lane onto the campaign branch, fast-forward, then run the checks for the areas it touched on the merged tree. Run them from a scratch worktree at the merged commit, never in the integration tree, so a slow suite does not block the next merge or change the files under it. Send a failure back to the lane with the command and its output; send a follow-up in the same files to the lane that holds the context (resume it) rather than starting a new one. Do not hold a merged lane for the slowest one: if its workstream has ready items, brief it again at once on the updated campaign branch.
5. **Close** with every lane merged and none running: the full checks, the performance measurements against the baseline, and any repository-wide rewrite the wave made possible. Such rewrites run only here, because they change the files lanes read. Hold for the close only what depends on the final state (full checks, baselines, held-out runs, the final report); everything else runs when it is ready.
6. **Record.** Delete finished items, add the defects found, and report to the owner: what merged, every contract change, measurements, and the decisions the next wave needs.

### Lane contract

- A lane owns the design of its slice inside its files: it chooses the structure, writes the tests the slice needs, and settles details itself, logging each call. It stops only on a decision the doc leaves open.
- Lanes never coordinate with each other. A lane that needs something from another workstream reports it; the integrator sequences it.
- Verification belongs to the integrator. A lane uses the cheapest build that compiles its change and runs only the tests it wrote or changed, by name. It does not run suites, slow or repository-wide checks, or optimized builds; those run once, after the merge, on the code that will ship. A lane's report names what the integrator's checks should exercise and what it left unverified.
- Shared files are append-only for a lane: add to a registry at the end of its group, put a new unit in its own file, and do not reorganize, rename, or reformat. Registries and lists that every lane appends to (switch overlays, format constants, lock files) take one entry per line, so concurrent lanes merge cleanly; the integrator renumbers format constants at merge.
- A brief may grant a bounded exception to the no-suites rule when the item is judged by a measurement (a batch, a benchmark): the number of attempts, the command, and the scratch output path. Anything not granted stays the integrator's.
- A change in the behavior of existing code is named in the report and ships with whatever makes old code explicit first.
- A lane does not rewrite the corpus, settle an open decision, or fix another workstream's defect. It reports them. It adds a dependency only when the brief names it, because manifests and lockfiles are shared files and the performance-gate measurement is the integrator's check after the merge.
