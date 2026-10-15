# Campaign Preflight Procedure

## Steps

1. **Read.** The draft, the repo's AGENTS.md, every document the draft depends on, and the code it names.
2. **Audit the draft against the bar and the lenses.** Collect every open decision: hedges ("consider", "maybe", "TBD", "if time", "owner to decide"), questions in the doc, and the decisions the skill's lens table would force the executor to make.
3. **Decide.** Classify each decision and write it into the doc's Decisions section, in three tiers:
   - **Owner-decided:** ask with `AskUserQuestion`, at most four to a call and each with a recommendation, then write the answer into the doc. Ask only what changes the outcome.
   - **Prescribed:** you settle it from the code or the principles, with the reason and what would reverse it.
   - **Delegated:** the executor decides inside a stated bound, using the smallest reversible assumption, and logs it.
4. **Sequence** (below), then **make the loop fast** and **make acceptance executable**.
5. **Prove the foundation.** Pick the one or two assumptions the whole plan stands on and prove them with `blast-radius`, by running real code, before the plan is called ready.
6. **Compress and write** in the shape below. Verify every `path:line` you kept.

   - When `mdtool` is installed, check a draft once with `mdtool check --untracked PATH`; it groups all checks and searches source consumers across the repo. Without it, search Markdown links with `rg -n '\[[^]]+\]\(' PATH`, then inspect each target and literal path reference manually.
7. **Report** a verdict: `ready`, `ready after the owner answers <list>`, or `not ready` with the reason.

## Sequence

- **Items** have an ID, a size, prerequisites, the files they own, and an acceptance proof. Prerequisites that cross workstreams are written on the item. An item that shares code with another is in the same workstream.
- **Size for speed.** An item is a capability a lane delivers end to end, not a ticket: merge adjacent increments that touch the same files into one item, and a lane takes several in a go. Draw the workstreams so each phase offers the most disjoint ownership sets, and write down the widest lane count each phase allows. A sequence of many small items over the same files is a defect to fix before the doc is ready.
- **Order the phases:**
  1. *P0, ground:* note the known failures on the baseline (so the executor never mistakes a pre-existing red for its own), and the loop timings, and repair the loop itself if it is the bottleneck.
  2. *Parity and completeness:* every deliverable works end to end, and every behavior of the reference has a test that fails if it is wrong. The reference is the thing being ported, replaced, or specified, and the doc names it. The parity register is built as `reference-parity` describes.
  3. *Hardening:* the cases found along the way, the contract changes written up, the docs updated.
  4. *Optimization and polish:* only now. An optimization item earlier than this is moved here unless it unblocks a feature.
  5. *Close:* delete what is dead, run `ultrareview`, fix its P1 and P2 findings, write the final report.
- **The loop has two speeds.** An item ends on the narrowest check that covers it. A phase ends on the checks of the areas it touched. The full suite runs at named milestones and at the close, each with the reason. If a command in the loop is slow, the first item is to speed it up, with a number as the target.
- **Time-box a failing item** at a stated number of attempts, then park it with a finding and continue with the next item that does not depend on it.

## Shape of the final doc

1. **Header:** status, the goal in a few lines, and the numbered deliverables.
2. **Charter:** the rules the executor runs by.
   - Decide, log the call, and keep going.
   - Within the owner's execution grant, decide and proceed without waiting for approval. A plan does not provide missing permission. Park an item that needs authority outside the grant, and run until every deliverable is met or every remaining item is parked.
   - Hard stops are few, and each one parks the item: an irreversible or outside-the-repo action, a boundary the doc forbids, or a loop that cannot check anything. Pushing is always forbidden.
   - Fix on the way what is egregious, in its own commit, to thresholds stated in numbers: a command over N minutes, a regression of more than N times against the baseline, a test red on the baseline that blocks the item. Record anything else seen and leave it.
   - Parity before optimization.
   - Keep bookkeeping minimal: no provenance, checksums, or pinned hashes unless the campaign delivers something that needs them.
   - Run as wide as ownership and the machine allow, with the largest slices a lane can finish, as `orchestrate` sets out. The doc states the memory budget per lane.
   - Worktrees and all working state live under `.work/` in the repo, never `/tmp`. The doc states the lane worktree path (`.work/wt/<lane>`).
   - Follow [`orchestrate`'s worktree lifecycle](../../orchestrate/SKILL.md#worktree-lifecycle) for each lane. During winddown, retain a worktree only when it is clean, named in the handoff, and explicitly allowed by the closeout guard.
   - Every commit, the executor's and the lanes', is a Conventional Commit, with the area or workstream as its scope. The item ID belongs in the body, never the subject.
   - Code comments never cite this doc.
3. **Decisions:** the three tiers, each with its reason.
4. **Baseline:** known failures, loop timings, and the reference numbers the optimization phase needs.
5. **Sequence:** the items by phase, with the dependency order.
6. **Acceptance:** each deliverable and the command or test that proves it. Nothing waits on a person.
7. **Execution boundary:** the effects the owner authorized and the effects the executor must not take. The campaign doc cannot grant permission. Each contract change made is listed for the owner.
8. **Non-goals:** what the campaign does not do, so the executor drops ideas instead of queueing them.
9. **Reference:** the design, the verified code map, and the background.
10. **Decision log and campaign log,** both append-only for the executor and short: one line per judgment call a reader would otherwise miss (the call and why), and one line per phase end. They are for the owner's read, not proof.
11. **For the owner afterwards:** what to read and cherry-pick. It is a list, not a gate.

