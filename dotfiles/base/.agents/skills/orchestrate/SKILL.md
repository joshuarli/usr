---
name: orchestrate
description: "Route all coding subagents through the shared Pi SDK bridge, scope and verify delegated work, and run multi-lane campaigns only when useful. Skip work cheaper to do directly."
---

# Orchestrate

**All coding subagents from any harness use `pi-subagent-bridge`**, regardless of which skill initiated delegation. This includes non-orchestrate tools and ordinary review tasks. The only native exception is `god` in Claude Code or Codex, using the existing pinned native model. Never use native Claude `Agent`/`Task`, Codex `spawn_agent`, OpenCode child agents, Command Code `Explore`/`General`, Pi `pi-subagents`, or another harness's native child launcher for `scout`, `mechanic`, `worker`, or `expert`.

The parent keeps task framing, orchestration, integration, and independent verification. Delegate only when context isolation, cost, parallelism, or independent scrutiny beats the overhead. A worker may not delegate or broaden its task.

## Pinned tiers

| Tier | Pi SDK primary on OpenCode Go | Thinking | Command Code fallback | Purpose |
| --- | --- | --- | --- | --- |
| scout | `opencode-go/muse-spark-1.3-contributor` | `medium` | `deepseek/deepseek-v4.1-flash`, `low` | Read-only exploration |
| mechanic | `opencode-go/muse-spark-1.3-contributor` | `high` | `deepseek/deepseek-v4.1-flash`, `high` | Mechanical scoped edits |
| worker | `opencode-go/deepseek-v4.1-flash` | `high` | `deepseek/deepseek-v4.1-flash`, `high` | Implementation, debugging, testing |
| expert | `opencode-go/deepseek-v4.1-flash` | `max` | `deepseek/deepseek-v4.1-flash`, `max` | Difficult architectural or cross-cutting work |

No Pi god tier is available. **Only Claude Code** may spawn a native `god` on `claude-opus-5-5` at `xhigh`; **only Codex** may spawn a native `god` on `gpt-6.1-sol` at `high`. Other harnesses do not have `god`; do not silently substitute another model or map it to `expert`.

**Default to worker** for substantial well-specified tasks; size alone does not justify `expert`. A read-only `scout` gets no `bash`, `edit`, or `write`. No tier grants privilege to change requirements or affect unrelated files.

## The one bridge, everywhere

Prefer MCP `pi-subagent-bridge`: `worker_model_check`, `worker_start`, `worker_status`, `worker_resume`, `worker_cancel`. Every configured host uses the same server implementation. If a harness cannot expose MCP, invoke the `pi-subagent-bridge` CLI shim with the same contract. Neither route uses a native host subagent. See `tools/pi-subagent-bridge/README.md`.

The parent creates a clean, dedicated linked worktree under `.work/wt/<slice>`. Before `worker_start(cwd,title,tier,scope,brief)`, call `worker_model_check(cwd,tier)`. Supply a complete contract:

- `scope.base_revision`: exact 40-character HEAD.
- `scope.writable_paths`: up to 20 specific relative files or directory prefixes; empty for scout.
- `scope.acceptance_proof`: named command with expected result, or a source file:line for research.
- `scope.attempt_limit`: 1 normally; 2 only for one justified same-scope correction.
- `scope.stop_on`: ambiguity, scope expansion, new dependencies, contract changes, unavailable proof.
- `brief`: one outcome, relevant facts, prohibited changes, and no downstream delegation.

**Admission is not completion.** Observe the returned ID using `worker_status` or wait with `worker-watch`, then read its terminal result. It reports the actual backend, model, thinking/effort, changed paths, out-of-scope changes, and whether HEAD stayed pinned. Require exact commands, exit codes and decisive output; prose is only a claim.

The parent independently reviews `git diff --check`, the diff against `base_revision` and untracked paths once. Verify requested behavior, permitted scope, imports and obvious regressions before integrating. An optional single `worker_resume` correction may touch only the same files, without increasing the attempt budget. Otherwise park or reject. Workers never commit, merge, push, switch branches, or clean worktrees.

## Provider fallback and ambiguous runs

The primary executor is an isolated Node process using the **Pi SDK**, pinned to the model above and reusing OpenCode Go credentials. It does not invoke the Pi CLI or start the OpenCode agent/server. Only an unavailable approved model/provider or a recognized quota/usage failure permits a fallback to the separate authenticated Command Code CLI, pinned to DeepSeek V4.1 Flash and effort above.

**Never fallback after any tracked/untracked edit, changed HEAD, uncertain prompt admission, unknown process termination or potentially running worker.** Retain durable leases and inspect uncertain sessions; do not launch a second paid worker. A generic task failure, rejected acceptance check, or changed path is not a provider failure. Command Code has no third fallback. Cancellation acknowledgement alone is not proof of termination. The scope check is Git-based, not an OS sandbox; ignored files and host writes require separate containment.

## Clef-flash advisory routing

Before a nontrivial delegated task with meaningful tier uncertainty, build a bounded, evidence-backed `TaskBrief` from available verified facts and consult `decide route --guide` then `decide route --baseline worker` once, if disclosure is safe. Use Clef-flash advice only to choose among permitted tiers; it cannot override exact provider/model pins, tools, read-only scope, risk, permissions or the `god` rule. On missing evidence, sensitive contents, auth/quota failures, or one obvious tier, choose the deterministic table without retry storms.

## Delegation

Delegate coherent component-sized work. Do not spawn an agent for one command or edit, to restate a plan, or to summarize code the parent must understand anyway. Batch related trivial work into one assignment. When one script or codemod can apply the change to every unit in a single pass, write and run it yourself instead of fanning out children to hand-apply it, and prove it by rerunning it on the unit you did by hand.

Size concurrency for accepted progress. Serial is the default for work that shares files. Give parallel writers disjoint ownership, but also bound shared-service contention, review work, and the verification queue. Resource headroom is a ceiling, not a target. Stagger independent preparation when it helps; reduce or pause writers when acceptance is saturated. Give each child a coherent end-to-end slice, not a fragment requiring another handoff.

When a child reports, a merge lands, or a check fails, reassess ready work and the limiting stage. **Procedural escalation:** diagnose briefing, environment, or verification failures; fix the cause and retry at most once at the same tier with a materially changed approach. **Capability escalation:** use a stronger pinned model only for evidenced reasoning limits. Where tiers reuse a model, use fresh context and independent scrutiny, never a provider switch. Never repeat an unchanged failure. The parent resolves shared prerequisites and obstructive tactics. Owner intent, public contracts, required proof, and permissions stay fixed unless the owner changes them.

Give every parallel writer its own worktree, created by you with `git worktree add .work/wt/<name> -b <branch>` and named in the brief as the only place it may write. `isolation: "worktree"` also lands in `.work/wt/` through the WorktreeCreate hook, but its branch name is generated and the tree outlives the child, so campaigns create their own. A child's final report is not shown to the user: relay what matters. Bridge workers do not deliver native harness notifications; use `worker-watch` where available and inspect `worker_status` when complete. Never restart a worker merely because the parent lost its notification.

Carry forward findings and failed approaches. Every child gets:

- Clear ownership and write boundaries.
- A concrete deliverable with only the needed context.
- Proportionate checks, an attempt limit, and a stopping condition.
- The current campaign ruling, plus a duty to report misleading metrics, repeated gate failures, or shared blockers rather than work around them.
- No further delegation unless the brief grants it; Grok may delegate to lower tiers within its depth cap. Claude-triggered DeepSeek executors never delegate. Codex V2 children never delegate because V1's `agents.max_depth` does not apply.

## Worktree lifecycle

The parent owns each child worktree from creation through removal. Every skill that removes worktrees or branches follows this section. Record its exact path, its branch when it has one, and the integration worktree when you create it or the harness creates it. A child finishing does not remove its worktree. Remove only the recorded path, never every entry under `.work/wt/`.

After a child finishes, review its changes and decide whether to integrate or park them. For accepted changes, inspect the integrated diff and reuse worker evidence unless integration or changed inputs could invalidate it. Remove the child worktree only after applicable proof is complete, the child has stopped, and all work worth keeping is in the integration branch or a preserved branch.

Before removal, run `git -C <child-worktree> status --porcelain --ignored=matching --untracked-files=all`. Keep the worktree if it has modified or untracked files. Review ignored files and preserve any local data worth keeping. Remove the worktree with `git -C <integration-worktree> worktree remove <child-worktree>`. Delete a branch only when `git -C <integration-worktree> merge-base --is-ancestor <branch> HEAD` succeeds, then run `git -C <integration-worktree> branch -d <branch>`. Keep the branch when that check fails, including after squash integration. Never force-delete a branch or worktree.

When you park unfinished work, commit it, remove its clean worktree, and keep its branch.

## Campaigns

For a backlog too large for one session, read [campaign mechanics and lane contract](references/campaigns.md) before preparing or launching work. The default is one writer on one slice until it is accepted. Add lanes only when they own disjoint files.

The parent runs the [steering checkpoint](references/campaigns.md#parent-steering-checkpoint) after each accepted slice, on resume, and after repeated failures, without waiting for the owner to complain.

**The test:** the parent can name the accepted slices that landed and the next one, and the integration branch is green.

**Report:** accepted slices and the checks that proved them, what is open and why, contract changes, and blockers needing the owner. Lane counts, doc commits, and audits are not progress.
