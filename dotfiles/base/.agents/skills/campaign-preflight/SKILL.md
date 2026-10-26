---
name: campaign-preflight
description: "Use for /campaign-preflight on a campaign design doc draft: turn it into a final, sequenced plan an agent can execute unattended, with every major decision answered, feature and test parity before optimization, and a fast verification loop. ultrareview for a campaign doc."
disable-model-invocation: true
metadata:
  opencode/autoinvoke: "false"
---

# Campaign Preflight

A campaign doc is the only thing the executing agent has once the owner walks away. Preflight edits the draft in place until that agent can run to the end without asking anything, then reports whether it is ready. It does not start the campaign. Like `ultrareview` it is a router: the method for each design area lives in the skill named for it. For campaign mechanics (workstreams, waves, lane contract) the doc conforms to the campaign reference linked by `orchestrate` instead of restating it.

An execution-ready plan records an authority boundary; it does not authorize the effects it describes.

## The bar

- **Unattended.** No question is left for runtime. Every decision is made in the doc, or delegated with a bound and a tie-break, so the executor has judgment inside the bounds and nothing to wait for. It stops only when every local deliverable is met or every remaining item is parked behind a hard stop. Proof that needs hardware, hosts, or services the executor lacks goes on a **Needs environment** list and does not hold the campaign open.
- **Parity first, optimization last.** Feature-completeness and test parity come first, because a campaign that polishes before it works is too slow. Optimization, size, and polish items are the final phases, and until then product-performance budgets are measured and logged, not gating unless the owner requires them. Repairs to the execution loop may happen earlier when needed for useful delivery, with a bounded exit test.
- **Autonomy with a floor.** The executor makes the judgment calls and records only those a later slice depends on. It also fixes anything egregiously slow or plainly broken that it meets, to thresholds the doc states in numbers.
- **Checkable.** Every deliverable has a proof an agent can run, and "done" never waits on the owner.
- **Delivered in slices.** Each item is a slice with one local acceptance command that runs in minutes. The default is one writer at a time, with parallel lanes only for disjoint files. The doc invokes the [parent steering checkpoint](../orchestrate/references/campaigns.md#parent-steering-checkpoint) after each accepted slice.
- **Short.** The whole doc stays under 300 lines, and **Status** under 20. Git history is the log. A doc that needs history to be read correctly is not ready.

## Rules

- **Edit the draft in place,** and nothing else. No second plan file and no preflight commentary in the doc.
- **The code is the truth.** Read it at the current commit. Verify every claim the draft makes about what exists and fix the ones that disagree.
- **The owner owns intent.** Preflight prescribes anything the code, the evidence, or sound practice settles. It asks the owner only for choices that change the product, the contract, or carry real risk, in one batch with a recommendation each, and records the answers as owner decisions with the date.
- **Pre-answer every place the global instructions say ask:** contract changes and anything destructive. For dependencies, name the performance gates they must stay within. The executor cannot ask, so the doc permits it, forbids it, or says exactly how to proceed.
- **No `/tmp`.** Move any worktree, scratch, or state path the draft puts in `/tmp` or `$TMPDIR` to `.work/` in the repo, so a reboot or an OOM-killed tmpfs cannot take the campaign with it.
- **Cut repetition, not requirements.** The executable core (charter, decisions, sequence, acceptance) comes first and fits comfortably in the executor's context. Rationale, history, and research detail that does not affect execution follow as reference. Preserve every meaningful deliverable, success criterion, scenario, boundary, and constraint from the draft by mapping it to work and proof, a recorded decision, a non-goal with reason, or an explicitly superseded requirement. Keep measurable qualifiers and scope intact: for example, a goal of one authorization per invocation must not become a generic authentication-context test. Delete what only explains how the draft got here, along with superseded handoffs, checkpoints, and logs.
- **Follow the repo's instructions,** including its verification limits. Time the loop commands; report before running anything expensive. No formatters, no commits, no pushes.

Read the [procedure, sequencing rules, and final document shape](references/procedure.md) before editing the draft.

## Lenses

For each area the campaign touches, load the skill and ask what decisions it would make the executor stop on. Answer them in the doc now. The design areas are the rows of the `ultrareview` lens table (boundaries, types, config, effects, errors, concurrency, persisted state, untrusted input, tests, navigability), asked of the planned work instead of the existing repo. These rows are specific to a campaign:

| Area | Skill | Pre-answer |
| --- | --- | --- |
| Slices, ownership, steering | `orchestrate` | Slice order, owned files, which slices may run in parallel, and who may revise methods |
| Parity with a reference | `reference-parity` | The reference, and the behaviors and corpus that cover it |
| Failures | `root-cause` | The executor's rule for a failing item: cause before retry |
| Optimization | `make-it-fast`, `benchmark-checklist` | What is measured, how, against what baseline, and the targets |
| Cleanup | `dead-code-archaeology` | What is deleted at the end and how liveness is proven |
| Repeat failures | `correct` | Guards for mistakes the campaign is likely to repeat |

**The test:** an agent with only this doc and the repo can land the first slice without asking anything, and can tell from **Status** alone what is accepted, what is red, and what is next.

**Report:** the verdict; the owner's answers and the decisions you prescribed, so the owner can overrule them; the loop timings; what you cut or moved to optimization; any material source requirement you superseded and why; what you could not verify; and the one-line prompt to launch the executor on the doc.
