# Campaigns

A campaign is a backlog too large for one session. It succeeds by landing accepted product slices on the integration branch, one after another. Busy agents, doc commits, audits, and steering notes are not progress. Only one measure counts: product changes whose named acceptance checks pass on the integration branch.

Lane commits and closeout require owner authorization. Without it, work serially or hand off disjoint patches. Campaign mechanics never expand the authority grant.

## Default shape: one slice at a time

Run one writer on one slice until it is accepted, then pick the next. Add a second writer only when both slices own disjoint files, including shared contracts, schemas, indexes, and lockfiles, and the integration branch is green. Work that shares core files is serial, however large the backlog. Integration cost grows faster than lane count, and a slice parked unaccepted is worth nothing.

A slice is one capability with one acceptance command that runs locally in minutes. If a deliverable's proof needs hardware, hosts, or services that are not available, split it. The local part is a slice. The rest goes on the doc's **Needs environment** list, which never blocks local work or the campaign's local completion.

## Prepare

- **Owner requirements versus tactics.** Record deliverables, contracts, required proof, and allowed effects. Ordering, width, and batching are the agent's to revise.
- **Measure the loop once.** Time the acceptance commands for the first slice. Build missing proof only for that slice, and expand only after a real slice has passed.
- **One short artifact.** The campaign doc follows [preflight's shape](../../campaign-preflight/references/procedure.md#shape-of-the-final-doc) and its size limits. Git history is the log. Never append checkpoints, handoffs, or rulings as new sections: rewrite **Status** in place.

## Parent steering checkpoint

Run this after each accepted slice, on resume, and whenever a slice fails twice. It is a short decision, not an audit. Write it down only when the ruling changes, and then only by rewriting **Status**.

1. **What landed?** Name the accepted slices since the last checkpoint. If the answer is none, the method is wrong. Change it now instead of adding lanes or process.
2. **What limits delivery?** Pick one: implementation, a red check, integration conflicts, an unavailable environment, or an owner decision. Agent turn latency counts as implementation. Many small turns at a high reasoning effort can cost more wall time than every test run combined.
3. **Ruling.** Continue, narrow the slice, serialize lanes, fix one prerequisite, or park the slice with its cause and retry condition. Ask the owner only for authority or a contract decision.

| Signal | Response |
| --- | --- |
| No accepted slice in the last two checkpoints | Stop lanes. Finish the smallest open slice serially. |
| Lanes touch the same files | Serialize them. |
| Tests red on the integration branch | Fix them before any new slice. |
| Doc or tooling commits outnumber product commits | Freeze the doc and tooling. Deliver. |
| A slice needs an unavailable environment | Move it to **Needs environment**. Keep going. |
| The owner asks about progress | Report landed slices only. |

## Run a slice

1. **Brief.** Give the item ID, base revision, owned and forbidden files, expected outcome, acceptance command, attempt limit, and known failed approaches. Include any `agent-learn recall` results you verified.
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

With authorized commits, stop lanes and run `codex-campaign-closeout.py begin` from the integration worktree. Resolve worktrees with the [general lifecycle](../SKILL.md#worktree-lifecycle). Allow only retained trees, with `codex-campaign-closeout.py allow --path <path> --reason <reason>`. If work resumes, run `codex-campaign-closeout.py cancel`.

To pause, use `campaign-winddown`.
