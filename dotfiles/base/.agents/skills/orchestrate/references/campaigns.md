# Campaigns

A campaign is a backlog too large for one session, run in rolling tranches. A wave is a bounded selection of ready work, not a barrier for unrelated work. The parent owns direction as well as integration: it selects, briefs, reviews, verifies, and changes the method when evidence shows drift. Keeping a queue busy is not the goal.

Lane commits and closeout require owner authorization. Without it, use serial work or disjoint patch handoffs and do not claim a committed handoff. Campaign mechanics never expand the authority grant.

## Prepare

- **Separate ends from means.** Record owner deliverables, contracts, required proof, and allowed effects separately from agent-chosen ordering, lane width, batching, and scoring. Methods are revisable within the grant; explicit owner requirements are not tactics to waive.
- **Define substantive progress.** Name the outcome and remaining obligations. Report metadata cleanup, tooling, investigation, and newly discovered debt separately from delivered capability or repaired contracts. Commits, changed lines, and busy agents are not the objective.
- **Bound ownership.** Group shared code into workstreams with item IDs and cross-stream prerequisites. Split independent work from its smallest coupled repair. Limit edit scope, not how many unchanged consumers may benefit. Do not force misleading contracts or temporary shims just to obey an arbitrary one-file rule.
- **Prove one useful path.** Measure a representative edit-to-acceptance loop and reuse existing checks. Build only the missing proof for the first edit class, then accept a real pilot before expanding infrastructure. Missing required evidence blocks affected acceptance, not independently verifiable work.
- **Set operating bounds.** Name the next substantive milestone, attempt limits, shared prerequisites, initial width, provisional-work cap, and validation-wave limit. Use measured memory and acceptance capacity. Keep the upstream base and tool policy stable during a wave; refresh for a named need, not routine churn.
- **Use one artifact.** Keep the accepted checkpoint, provisional work, current ruling, and next steering checkpoint near the campaign doc's top. Keep history short and point briefs at this workflow. Do not build a supervisor service, dashboard, or second ledger merely to manage the campaign.

## Parent steering checkpoint

Review after each validation wave, on resume or context recovery, and before further dispatch after a recurring rejection or bottleneck. If no wave completes, review after five attempted items, including failed and parked attempts; the campaign may choose a tighter cadence. Use existing evidence for a brief decision, not another global audit or routine user check-in.

1. **Reconcile with the goal.** Compare accepted results on the same scope and policy. What substantive obligation disappeared? What limits delivery now? Separate preparation, verification wait, infrastructure repair, and baseline changes. Commit timestamps do not establish active working time.
2. **Inspect outcomes.** Review a representative accepted diff and rejected or parked proposal against implementation, consumers, and decisive checks. Look for false contracts, lost coverage, misleading credit, and good changes rejected by a proxy metric. This sampling supplements required checks, never replaces them. Independent review may help; the parent retains judgment.
3. **Classify the obstruction.** Distinguish a regression, newly exposed existing debt, invalid measurement, an agent-authored rule defect, an environment prerequisite, and an owner-only decision. Check false acceptance as well as false rejection. Matching error counts or locations alone does not establish unchanged failures.
4. **Apply a ruling.** Continue, reorder, batch, reduce width, repair one prerequisite, or pause affected work. Benefits to multiple consumers are not scope violations. Investigate newly exposed debt instead of hiding truthful information. Correct a proxy gate with a reproducer, positive and negative checks, and a separately reviewable policy change; re-evaluate affected candidates. Preserve actual non-regression and completion requirements. A candidate cannot silently redefine its own acceptance.
5. **Close the loop.** Record the evidence, ruling, and next substantive delivery in the existing artifact. Update active instructions, not only an append-only history, and notify affected lanes. Ask or park only what requires new authority, a public-contract decision, or unavailable evidence; continue independent authorized work.

Intervene before the owner has to notice these signals:

| Signal | Parent response |
| --- | --- |
| Review or verification queues grow | Cap provisional work, stop adding writers, and improve grouping or safe reuse. Idle preparation capacity can be correct. |
| Successive checkpoints deliver tooling but no substantive result | Bound the minimum repair and require a real accepted pilot next; freeze optional infrastructure. |
| Easy metadata wins dominate while shared blockers persist | Finish the cheap sweep as a bounded group, then prioritize the dependency or coherent contract repair. |
| A sound repair fails because several consumers improve or old debt becomes visible | Inspect and correct the proxy within authority; do not weaken truthful contracts to satisfy bookkeeping. |
| Lanes rediscover the same unavailable prerequisite | Give it one owner and retry only when conditions change. Stronger models do not supply missing services or credentials. |
| Rebases, rescans, or terminal checks replace delivery | Preserve comparable baselines and reuse complete compatible evidence; rerun when inputs or relevant completion state change. |

Continue a healthy method without inventing process changes. If two checkpoints repeat the same obstruction, change the approach or narrow the blocked scope instead of relaunching identical attempts.

## Run a wave

1. **Select and brief.** Assign coherent, reviewable slices with item IDs, base revision, owned and forbidden files, dependencies, expected outcome, focused checks, attempt limit, and failed approaches. Make unmerged dependencies explicit: disjoint files alone do not establish semantic independence.
2. **Launch within capacity.** Parallel writers get parent-owned worktrees under `.work/wt/`. Run `perf-gate-ready -s` before a launch round, using measured peak memory for `PERF_GATE_LANE_GIB`; exit 75 means add no width. Headroom is a ceiling, not a utilization target. Respect review capacity and shared services too. Plain `perf-gate-ready` governs timing claims, not unrelated correctness work.
3. **Review and integrate provisionally.** Inspect diffs and evidence, reconcile onto the integration branch, and preserve owner work. Run focused checks on the exact integrated revision in an isolated scratch worktree, never a changing checkout. Keep a named last accepted checkpoint; later local commits are provisional until required wave checks pass. Preparation may overlap within the cap, but do not propagate unexplained failures into dependent lanes.
4. **Validate the bounded group.** Small commits need not each receive an independent cold global audit. Group compatible low-risk candidates under full-scope acceptance on the exact combined tree unless owner or repository rules require per-commit proof. Use smaller dedicated groups for shared or high-risk contracts. If a group fails, isolate or bisect, repair or exclude the culprit, then validate the resulting tree. Do not claim intermediate commits were independently globally verified.
5. **Accept and steer.** Advance the accepted checkpoint only with complete, matching evidence. Follow the [worktree lifecycle](../SKILL.md#worktree-lifecycle) after preserving useful work and evidence. Perform the steering checkpoint before replenishing; report substantive delivery, metadata cleanup, contract changes, and blockers separately.

### Proportionate verification

Choose checks from the actual diff and affected consumers. Prove metadata-only edits change no executable behavior before waiving behavior tests solely for those edits; policy, schema, and coverage checks still apply. Import, registration, initialization, generated-interface, and runtime-metadata changes need relevant execution checks. Static success is not runtime proof.

Use narrow incremental feedback, bounded full-scope acceptance, and independent cold audits where required. Full scope and cold execution are different properties. Do not blindly enable caching in an audit requiring fresh retained internals. Reuse completed evidence only when source revision, effective policy, tool/dependency/environment inputs, scope, and required artifacts match. Verify origins and invalidation; partial, stale, or contaminated evidence is never reusable. Record reuse in existing results, not a new provenance platform.

Test gates against a real improvement, genuine regression, harmless relocation, and newly discovered existing debt. Preserve diagnostic identity and multiplicity enough to detect substitution; adjudicate ambiguous changes explicitly. Do not add broad ignores, shrink coverage, erase contracts, or relabel incomplete runs to make a metric pass. Policy changes and rebases require comparable remeasurement where relevant, not erasure of earlier regressions.

## Keep work flowing

The parent supplies useful parallelism and corrects drift unprompted. When asked to speed up, use [accelerate](../../accelerate/SKILL.md), starting with the limiting stage rather than a predetermined lane count.

- **Replenish deliberately.** After reports, compare ready work with acceptance capacity. Resume useful context or replace stale context. Overlap independent work when it shortens the critical path; reduce or pause writers when the queue is saturated.
- **Resolve shared blockers once.** Assign technical repairs within authority, including cross-boundary ownership when needed. Owner decisions remain with the owner. Park with cause, evidence, prerequisite, and retry condition; no automatic requeue or model escalation for an unchanged external failure.
- **Bound infrastructure.** A loop-speed lane gets a measured bottleneck, minimal repair, exit test, and real candidate to unblock. Return capacity to delivery after it passes. Tool replacements and research remain separate bounded experiments unless necessary for acceptance, not new prerequisite campaigns.
- **Share resources safely.** Disjoint code does not imply independent databases, services, caches, or outputs. Serialize conflicts; parallel validation requires immutable inputs and measured headroom. Keep the parent available for review and rulings; a bounded unblocking edit in unowned files may be cheaper than another handoff.
- **Wait on evidence.** Use completion notifications or supported scheduling with a named next action. Do not promise background follow-up without that mechanism or poll unchanged state. Failed integration pauses dependent acceptance, not every independent investigation.

## Lane contract

- Own the slice's design within the brief and current ruling, not acceptance policy or broader authority. Report contradictions, misleading metrics, repeated gate failures, and shared blockers rather than working around them. Coordinate through the parent.
- Report changed content, substantive outcome, exact commands/results, uncertainty, and checks left to integration. The parent checks supporting evidence rather than trusting a completion claim.
- Run the cheapest sufficient build and named new and existing regression tests. Slow/global suites and optimized builds belong to the integrator unless the brief grants a bounded command and attempt budget. Broader checks run at risk-based milestones, not automatically per tiny commit or only at the end.
- Shared files have one writer or an explicit conflict-safe edit contract. Do not opportunistically reorganize, rename, or reformat them. Manifests, lockfiles, registries, and generated lists need coordinator review even when append-only. Dependencies require authorization.
- Name behavior and public-contract changes. Declarations, stubs, mocks, and assertions must describe real implementations and consumers, not merely silence a selected checker.

## Close or pause

Close only when deliverables and required proof pass, including applicable full checks and baseline performance comparisons. Complete measurement is not campaign completion. Keep deferred checks and parked work explicit; do not rerun terminal audits merely to rediscover known unfinished obligations.

With authorized commits, stop lanes and run `codex-campaign-closeout.py begin` from the integration worktree. Run final repository-wide rewrites only after their readers/writers stop. Preserve useful local data, resolve worktrees with the [general lifecycle](../SKILL.md#worktree-lifecycle), and name retained paths and consumers in the handoff. Allow only those trees with `codex-campaign-closeout.py allow --path <path> --reason <reason>`. If work resumes, run `codex-campaign-closeout.py cancel`, perform the steering checkpoint, and begin closeout again at the next stop.

A pause uses `campaign-winddown`. Preserve the accepted revision, provisional or parked branches, current ruling, remaining obligations, and next substantive milestone so a resumed agent does not replay stale instructions or needlessly rebaseline. Parked work is not completed work.
