# Campaign Preflight Procedure

## Steps

1. **Read.** The draft, the repo's AGENTS.md, every document the draft depends on, and the code it names.
2. **Audit the draft against the bar and the lenses.** Collect every open decision: hedges ("consider", "maybe", "TBD", "if time", "owner to decide"), questions in the doc, and the decisions the skill's lens table would force the executor to make.
3. **Decide.** Classify each decision and write it into the doc's Decisions section, in three tiers:
   - **Owner-decided:** ask in one batch of at most four, recommend each answer, then write the answers into the doc. Ask only what changes the outcome.
   - **Prescribed:** you settle it from the code or the principles, with the reason and what would reverse it.
   - **Delegated:** the executor decides inside a stated bound, using the smallest reversible assumption, and logs it.
4. **Sequence** (below), then **make the loop fast** and **make acceptance executable**. Check the proposed gate against a real improvement, a genuine regression, newly exposed existing debt, and a change benefiting unchanged consumers. Plan a substantive pilot, not a complete new evaluator as the entry fee for every kind of work.
5. **Prove the foundation.** Pick the one or two assumptions the whole plan stands on and prove them with `blast-radius`, by running real code, before the plan is called ready.
6. **Compress and write** in the shape below. Verify every `path:line` you kept. Then compare the final plan against the source draft per the bar: every material requirement stays actionable, moves to a reference the executor is directed to use, or is explicitly superseded with a reason. This is a review pass, not a second register to maintain.

   - When `mdtool` is installed, check a draft once with `mdtool check --untracked PATH`; it groups all checks and searches source consumers across the repo. Without it, search Markdown links with `rg -n '\[[^]]+\]\(' PATH`, then inspect each target and literal path reference manually.
7. **Report** a verdict: `ready`, `ready after the owner answers <list>`, or `not ready` with the reason.

## Sequence

- **Items** have an ID, a size, prerequisites, the files they own, and an acceptance proof. Prerequisites that cross workstreams are written on the item. An item that shares code with another is in the same workstream.
- **Size for speed.** An item is a slice: a capability a lane delivers end to end, with one local acceptance command that runs in minutes. Merge adjacent increments that touch the same files into one item. Items sharing files run serially. Allow parallel lanes only between disjoint ownership sets, and state which pairs qualify.
- **Order the phases:**
  1. *P0, ground:* note the known failures on the baseline (so the executor never mistakes a pre-existing red for its own), and the loop timings, and repair the loop itself if it is the bottleneck.
  2. *Parity and completeness:* every deliverable works end to end, and every behavior of the reference has a test that fails if it is wrong. The reference is the thing being ported, replaced, or specified, and the doc names it. The parity register is built as `reference-parity` describes.
  3. *Hardening:* the cases found along the way, the contract changes written up, the docs updated.
  4. *Optimization and polish:* only now. An optimization item earlier than this is moved here unless it unblocks a feature.
  5. *Close:* delete what is dead, run `ultrareview`, fix its P1 and P2 findings, write the final report.
- **The loop has two speeds.** An item ends on its acceptance command and the narrowest affected suite, run on the integrated tree. The full suite runs at named milestones and at the close. Red work never lands on the integration branch.
- **Time-box a failing item** at a stated number of attempts, then park it on its branch with the cause and a retry condition. A shared environment blocker gets one owner.
- **Split out unavailable proof.** Anything needing hardware, a second host, or a service the executor lacks goes on **Needs environment** with the command the owner would run.

## Shape of the final doc

Length follows the work: keep the executable core and its proof, never cut a decision, scenario, or acceptance check to reach a line count, and never pad with repetition, history, or rationale the code or a linked reference already states. Rewrite sections in place; never append dated checkpoints, handoffs, or logs. Git history keeps the past.

1. **Status** (a short at-a-glance block): the goal; the last accepted revision; slices accepted, red, or parked (with branch and cause); the next slice; and, when paused, the resume prompt and first command.
2. **Charter:** the rules the executor runs by.
   - Decide and keep going. Record a decision only when a later slice depends on it.
   - Within the owner's execution grant, proceed without waiting for approval. A plan does not provide missing permission. Park an item that needs authority outside the grant.
   - Hard stops are few, and each one parks the item: an irreversible or outside-the-repo action, a boundary the doc forbids, or a loop that cannot check anything. Pushing is always forbidden.
   - Fix egregious problems met on the way, in their own commit, to thresholds stated in numbers. Record anything else and leave it.
   - Parity before optimization.
   - One writer by default. Parallel lanes only for the disjoint pairs named in **Sequence**, in worktrees at `.work/wt/<lane>`, never `/tmp`, following [`orchestrate`'s worktree lifecycle](../../orchestrate/SKILL.md#worktree-lifecycle).
   - Every commit is a Conventional Commit with the workstream as its scope. The item ID belongs in the body. Code comments never cite this doc.
3. **Decisions:** only binding ones, each with its reason, marked owner, prescribed, or delegated with a bound.
4. **Baseline:** known red and loop timings.
5. **Sequence:** the items in order, each with ID, owned files, prerequisites, and acceptance command.
6. **Acceptance:** each deliverable and its command, keeping the distinct success and failure conditions.
7. **Needs environment:** proof that cannot run here, with the command the owner would run.
8. **Execution boundary and non-goals:** authorized effects, forbidden effects, and what the campaign does not do. List each contract change for the owner.
9. **Reference** (optional, short): a verified code map. Link longer design material in `docs/` instead of inlining it.
