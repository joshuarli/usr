---
name: campaign-preflight
description: "Use for /campaign-preflight on a campaign design doc draft: turn it into a final, sequenced plan an agent can execute unattended, with every major decision answered, feature and test parity before optimization, and a fast verification loop. ultrareview for a campaign doc."
disable-model-invocation: true
---

# Campaign Preflight

A campaign doc is the only thing the executing agent has once the owner walks away. Preflight edits the draft in place until that agent can run to the end without asking anything, then reports whether it is ready. It does not start the campaign. Like `ultrareview` it is a router: the method for each design area lives in the skill named for it. For campaign mechanics (workstreams, waves, lane contract) the doc conforms to the Campaigns section of `orchestrate` instead of restating it.

## The bar

- **Unattended.** No question is left for runtime. Every decision is made in the doc, or delegated with a bound and a tie-break, so the executor has judgment inside the bounds and nothing to wait for. It stops only when every deliverable is met or every remaining item is parked behind a hard stop.
- **Parity first, optimization last.** Feature-completeness and test parity come first, because a campaign that polishes before it works is too slow. Optimization, size, and polish items are the final phases, and until then performance budgets are measured and logged, not gating.
- **Autonomy with a floor.** The executor makes the judgment calls and logs each. It also fixes anything egregiously slow or plainly broken that it meets, to thresholds the doc states in numbers.
- **Checkable.** Every deliverable has a proof an agent can run, and "done" never waits on the owner.

## Rules

- **Edit the draft in place,** and nothing else. No second plan file and no preflight commentary in the doc.
- **The code is the truth.** Read it at the current commit and record the SHA. Verify every claim the draft makes about what exists and fix the ones that disagree.
- **The owner owns intent.** Preflight prescribes anything the code, the evidence, or sound practice settles. It asks the owner only for choices that change the product, the contract, or carry real risk, in one batch with a recommendation each, and records the answers as owner decisions with the date.
- **Pre-answer every place the global instructions say ask:** new dependencies, contract changes, anything destructive. The executor cannot ask, so the doc permits it, forbids it, or says exactly how to proceed.
- **Cut.** The executable core (charter, decisions, sequence, acceptance) comes first and fits comfortably in the executor's context. Rationale, history, and design background follow as reference. Delete what only explains how the draft got here.
- **Explicit-only skills are not in your skill list.** Load one by reading `~/.agents/skills/<name>/SKILL.md`.
- **Follow the repo's instructions,** including its verification limits. Time the loop commands; report before running anything expensive. No formatters, no commits, no pushes.

## Steps

1. **Read.** The draft, the repo's AGENTS.md, every document the draft depends on, and the code it names. Record the SHA.
2. **Audit the draft against the bar and the lenses.** Collect every open decision: hedges ("consider", "maybe", "TBD", "if time", "owner to decide"), questions in the doc, and the decisions the lenses below would force the executor to make.
3. **Decide.** Classify each decision and write it into the doc's Decisions section, in three tiers:
   - **Owner-decided:** ask with `AskUserQuestion`, at most four to a call and each with a recommendation, then record the answer and date. Ask only what changes the outcome.
   - **Prescribed:** you settle it from the code or the principles, with the reason and what would reverse it.
   - **Delegated:** the executor decides inside a stated bound, using the smallest reversible assumption, and logs it.
4. **Sequence** (below), then **make the loop fast** and **make acceptance executable**.
5. **Prove the foundation.** Pick the one or two assumptions the whole plan stands on and prove them with `blast-radius`, by running real code, before the plan is called ready.
6. **Compress and write** in the shape below. Verify every `path:line` you kept.
7. **Report** a verdict: `ready`, `ready after the owner answers <list>`, or `not ready` with the reason.

## Lenses

For each area the campaign touches, load the skill and ask what decisions it would make the executor stop on. Answer them in the doc now.

| Area | Skill | Pre-answer |
| --- | --- | --- |
| Lanes, waves, ownership, merges | `orchestrate` | Workstreams, prerequisites across them, files each lane owns, who integrates and verifies |
| Public surface, module layout | `api-surface-and-module-boundaries` | What may be exposed, which direction dependencies run |
| Types and domain model | `make-invalid-states-unrepresentable` | The shapes of the new core types |
| Configuration, defaults | `single-source-of-truth` | Where each new setting and fact lives, and its default |
| Persisted and wire formats | `durable-state` | Format versions, migrations or refusal of old data, transaction boundaries |
| Errors, retries | `error-model` | Error types, exit codes, what is retried |
| Concurrency, lifecycle | `lifecycle-concurrency` | Ownership of tasks, cancellation, shutdown |
| Effects and testability | `isolate-effects` | Which seams tests use |
| Untrusted input, platform code | `os-boundaries` | Path, symlink, temp-file, and platform rules |
| Tests and parity | `test-audit` | The parity oracle, the behavior-to-test register, what counts as a test of a behavior |
| Optimization | `performance-by-mechanism`, `benchmark-checklist` | What is measured, how, against what baseline, and the targets |
| Cleanup | `dead-code-archaeology`, `deslop` | What is deleted at the end and how liveness is proven |
| Repeat failures | `correct` | Guards for mistakes the campaign is likely to repeat |

## Sequence

- **Items** have an ID, a size, prerequisites, the files they own, and an acceptance proof. Prerequisites that cross workstreams are written on the item. An item that shares code with another is in the same workstream.
- **Order the phases:**
  1. *P0, ground:* record the baseline commit, the known failures on it (so the executor never mistakes a pre-existing red for its own), and the loop timings, and repair the loop itself if it is the bottleneck.
  2. *Parity and completeness:* every deliverable works end to end, and every behavior of the reference has a test that fails if it is wrong. The reference is the thing being ported, replaced, or specified, and the doc names it. A parity register maps each behavior to its test.
  3. *Hardening:* the cases found along the way, the contract changes written up, the docs updated.
  4. *Optimization and polish:* only now. An optimization item earlier than this is moved here unless it unblocks a feature.
  5. *Close:* delete what is dead, run `ultrareview`, fix its P1 and P2 findings, write the final report.
- **The loop has two speeds.** An item ends on the narrowest check that covers it. A phase ends on the checks of the areas it touched. The full suite runs at named milestones and at the close, each with the reason. If a command in the loop is slow, the first item is to speed it up, with a number as the target.
- **Time-box a failing item** at a stated number of attempts, then park it with a finding and continue with the next item that does not depend on it.

## Shape of the final doc

1. **Header:** status, the SHA it was written against, the goal in a few lines, and the numbered deliverables.
2. **Charter:** the rules the executor runs by.
   - Decide, log the call, and keep going.
   - Never ask and never wait for approval, and send no check-in or progress report. Run until every deliverable is met or every remaining item is parked.
   - Hard stops are few, and each one parks the item: an irreversible or outside-the-repo action, a boundary the doc forbids, or a loop that cannot check anything. Pushing is always forbidden.
   - Fix on the way what is egregious, in its own commit, to thresholds stated in numbers: a command over N minutes, a regression of more than N times against the baseline, a test red on the baseline that blocks the item. Record anything else seen and leave it.
   - Parity before optimization.
   - Code comments never cite this doc.
3. **Decisions:** the three tiers, each with its reason.
4. **Baseline:** SHA, known failures, loop timings, reference numbers.
5. **Sequence:** the items by phase, with the dependency order.
6. **Acceptance register:** each deliverable, the command or test that proves it, and its status (`met`, `unmet`, `not run`). Nothing waits on a person.
7. **Contract changes:** the classes pre-authorized and the ones forbidden. Each change made is listed for the owner.
8. **Non-goals:** what the campaign does not do, so the executor drops ideas instead of queueing them.
9. **Reference:** the design, the verified code map, and the background.
10. **Decision log and campaign log,** both append-only for the executor: date, question, what was assumed, why, and what would reverse it; then one row per phase end.
11. **For the owner afterwards:** what to read and cherry-pick. It is a list, not a gate.

**The test:** an agent with only this doc and the repo can run from the first item to the last without asking a question, and cannot reach a point where it works on optimization while a feature or a parity test is missing.

**Reply:** the verdict and the SHA; the owner's answers and the decisions you prescribed, so the owner can overrule them; the loop timings; what you cut or moved to optimization; what you could not verify; and the one-line prompt to launch the executor on the doc.
