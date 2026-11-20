# Campaigns

A campaign is a backlog too large for one session. It succeeds by completing features: deliverables that work end to end with their named acceptance checks passing on the integration branch. Accepted product slices, landed one after another, are how it gets there. Busy agents, doc commits, audits, diagnostics, and steering notes are not progress.

Campaign mechanics never expand the authority grant.

## Default shape: parallel where files are disjoint

Run every ready slice that owns disjoint files at once, each writer in its own worktree, up to `perf-gate-ready -s` headroom and what the parent can review and integrate. Slices that share files, including shared contracts, schemas, indexes, and lockfiles, run serially, however large the backlog. A red integration branch pauses new lanes until it is green. Review and integration bound the width, and a slice parked unaccepted is worth nothing. Finish a started feature before starting another; three half-done features are worth less than one done.

A slice is one capability with one acceptance command that runs locally in minutes. If a deliverable's proof needs hardware, hosts, or services that are not available, split it. The local part is a slice. The rest goes on the doc's **Needs environment** list, which never blocks local work or the campaign's local completion.

## Prepare

- **Owner requirements versus tactics.** Record deliverables, contracts, required proof, and allowed effects. Ordering, width, and batching are the agent's to revise.
- **Measure the loop once.** Time the acceptance commands for the first slice. Build missing proof only for that slice, and expand only after a real slice has passed.
- **One short artifact.** The campaign doc follows [preflight's shape](../../campaign-preflight/references/procedure.md#shape-of-the-final-doc) and its size limits. Git history is the log. Never append checkpoints, handoffs, or rulings as new sections: rewrite **Status** in place.

## Parent steering checkpoint

Run this after each accepted slice, on resume, and whenever a slice fails twice. It is a short decision, not an audit. Write it down only when the ruling changes, and then only by rewriting **Status**.

1. **What landed?** Name the accepted slices and finished features since the last checkpoint. If the answer is none, the method is wrong. Change it now instead of adding lanes or process.
2. **What limits delivery?** Pick one: implementation, a red check, integration conflicts, an unavailable environment, or an owner decision. Agent turn latency counts as implementation. Many small turns at a high reasoning effort can cost more wall time than every test run combined.
3. **Ruling.** Continue, narrow the slice, serialize lanes, fix one prerequisite, or park the slice with its cause and retry condition. Ask the owner only for authority or a contract decision.

| Signal | Response |
| --- | --- |
| No accepted slice in the last two checkpoints | Stop lanes. Finish the smallest open slice serially. |
| Lanes touch the same files | Serialize them. |
| Tests red on the integration branch | Fix them before any new slice. |
| Doc or tooling commits outnumber product commits | Freeze the doc and tooling. Deliver. |
| A slice needs an unavailable environment | Move it to **Needs environment**. Keep going. |
| Diagnosis, instrumentation, or profiling spans a checkpoint with no fix landed | Narrow to the smallest fix that passes acceptance, or park the slice with its evidence and move to the next feature. |
| A slice waits on a long build, transfer, or remote job | Work independent ready slices meanwhile. Check the job at the next checkpoint. |
| A reply would end with a known next step and nothing needed from the owner | Take the step if the campaign's authority covers it. |
| Many short turns, long time to first token | Batch reads, searches, and edits per turn, lower the child's reasoning effort for routine work, and give lanes larger, fully specified briefs. |
| Audits, checkpoints, handoffs, or doc rewrites dominate | Stop them. Rewrite **Status** once and deliver. |
| Checks dominate wall time | Run the narrowest acceptance command per slice, reuse evidence whose inputs are unchanged, and group wider suites at milestones. |
| Ready slices own disjoint files and headroom remains | Launch them now. |
| The owner asks about progress | Report finished features and landed slices only. |

## Run a slice

1. **Brief.** Give the item ID, base revision, owned and forbidden files, expected outcome, acceptance command, attempt limit, and known failed approaches.
2. **Launch.** A parallel writer gets a parent-owned worktree under `.work/wt/`. Run `perf-gate-ready -s` before adding width.
3. **Integrate only green work.** Review the diff, merge it, and run the slice's acceptance command and the narrowest affected suite on the integrated tree. Reuse a child's evidence only when integration changed none of its inputs. Red work stays on its branch. It never lands on the integration branch as "provisional".
4. **Validate in groups when it is cheaper.** Compatible accepted slices can share one wider-suite run at a milestone. If the group fails, bisect, fix or revert the culprit, and rerun.
5. **Steer, then pick the next slice.** Follow the [worktree lifecycle](../SKILL.md#worktree-lifecycle).

### Proportionate verification

Choose checks from the diff and the affected consumers. Import, registration, schema, and generated-interface changes need execution checks; static success is not runtime proof. Reuse evidence only when the source revision, policy, dependencies, environment, and scope all match. Never add broad ignores, shrink coverage, or relabel an incomplete run to make a gate pass.

## Lane contract

- Own the slice's design within the brief, not acceptance policy. Report contradictions, misleading metrics, and shared blockers instead of working around them.
- Batch independent reads, searches, and edits into one turn. A slice that takes over a hundred turns is mis-sized or mis-briefed. Stop and report.
- Report the changed files, the exact commands and their results, and what is left for integration. The parent checks the evidence, not the claim.
- Shared files have one writer. Manifests, lockfiles, and registries need coordinator review. Dependencies need authorization.

## Close or pause

Close when every local deliverable's acceptance passes. **Needs environment** items stay listed for the owner and do not hold the campaign open.

To close, stop lanes and run `codex-campaign-closeout.py begin --path <owned-lane>` from the integration worktree, repeating `--path` for each recorded campaign lane. An empty path list tracks nothing; it never infers ownership from all repository worktrees. Resolve named lanes with the [general lifecycle](../SKILL.md#worktree-lifecycle). Allow only retained trees, with `codex-campaign-closeout.py allow --path <path> --reason <reason>`. Retained lanes stay clean at their recorded HEAD and branch. If work resumes or the scope changes, run `codex-campaign-closeout.py cancel` before beginning again.

The Stop hook may request one continuation to account for unresolved named lanes. If `stop_hook_active` is already true, it reports a nonblocking warning and preserves the marker for later resumption. A legacy marker without explicit ownership asks for review and restart with named paths; it never authorizes sweeping other worktrees. This closeout accounting is separate from opportunistic disk-pressure cleanup.

To pause, use `campaign-winddown`.
