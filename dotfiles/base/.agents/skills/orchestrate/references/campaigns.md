# Campaigns

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
   Treat the serialized verification queue as a workstream. Track the targets,
   test counts, and unrelated work selected by each focused command. If queue
   wait or verification becomes the campaign's critical path, give loop speed a
   dedicated owner before widening implementation further. Fix selectors,
   expose named tests, split oversized harnesses, or improve revision-safe
   artifact reuse. A broad gate that eventually finishes does not excuse a
   missing focused check; retain the broad gate for the integration risk it
   actually covers.
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
