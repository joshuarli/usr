---
name: orchestrate
description: "Route all coding subagents through the shared Pi SDK bridge, scope and verify delegated work, and run multi-lane campaigns only when useful. Skip work cheaper to do directly."
---

# Orchestrate

**All coding subagents from any harness use `pi-subagent-bridge`**, regardless of which skill initiated delegation. This includes non-orchestrate tools and ordinary review tasks. The only native exception is `god` in Claude Code or Codex, using the existing pinned native model. Never use native Claude `Agent`/`Task`, Codex `spawn_agent`, OpenCode child agents, Command Code `Explore`/`General`, Pi's native `subagent` tool outside the bridge, or another harness's native child launcher for `scout`, `mechanic`, `worker`, or `expert`.

The parent keeps task framing, orchestration, integration, and independent verification. Delegate only when context isolation, cost, parallelism, or independent scrutiny beats the overhead. A native Pi child may delegate one additional generation to equal-or-weaker tiers, only when its assigned task calls for it; no worker may broaden its scope. Command Code workers are still leaves.

## Pinned tiers

| Tier | Command Code first | Effort | Muse SDK middle | OpenCode Go fallback via Pi | Purpose |
| --- | --- | --- | --- | --- | --- |
| scout | `meta/muse-ember` | `medium` | `muse-sdk/muse-ember-1.0` (`medium`) | `opencode-go/muse-spark-1.3-contributor` (`medium`) | Read-only exploration |
| mechanic | `meta/muse-ember` | `xhigh` | `muse-sdk/muse-ember-1.0` (`xhigh`) | `opencode-go/muse-spark-1.3-contributor` (`high`) | Mechanical scoped edits |
| worker | `deepseek/deepseek-v4.1-flash` | `high` | `muse-sdk/muse-spark-1.3` (`xhigh`) | `opencode-go/deepseek-v4.1-flash` (`high`) | Implementation, debugging, testing |
| expert | `deepseek/deepseek-v4.1-flash` | `max` | — | `opencode-go/deepseek-v4.1-flash` (`max`) | Difficult architectural or cross-cutting work |

**Hard OpenCode boundary:** only models actually available through the `opencode-go` provider may be delegated via the OpenCode Go fallback. Never use `opencode/*` (Zen), other metered OpenCode models, or custom model endpoints. Availability in standard OpenCode does **not** imply OpenCode Go eligibility. If a desired model is not on Go, keep it exclusive to another approved provider (Muse Ember on Command Code or the Muse SDK), or choose a supported Go model. Do not automatically substitute Zen.

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
- `brief`: one outcome, relevant facts, prohibited changes, and whether one-level Pi fanout is justified; never delegate beyond the assigned scope.

**Admission is not completion.** Observe the returned ID using `worker_status` or wait with `worker-watch`, then read its terminal result. It reports the actual backend, model, thinking/effort, changed paths, out-of-scope changes, and whether HEAD stayed pinned. Require exact commands, exit codes and decisive output; prose is only a claim.

The parent independently reviews `git diff --check`, the diff against `base_revision` and untracked paths once. Verify requested behavior, permitted scope, imports and obvious regressions before integrating. An optional single `worker_resume` correction may touch only the same files, without increasing the attempt budget. Otherwise park or reject. Workers never commit, merge, push, switch branches, or clean worktrees.

## Provider fallback and ambiguous runs

**Command Code is the first executor for every non-god tier**, pinned to Muse Ember for scout/mechanic and DeepSeek V4.1 Flash for worker/expert. The exact-pinned Muse SDK subscription is **second** for scout/mechanic/worker, and OpenCode Go is **third** and final: the bridge embeds Pi SDK + pi-subagents and invokes its exact pinned model through the extension RPC, without starting OpenCode or the Pi CLI. Only a missing Command Code executable or a confirmed provider/model/usage failure may switch, before any edits and with unambiguous termination. No fallback after Muse/Go, no third provider, and no return to Command Code. Legacy sessions retain their admitted backend and pinned models rather than being restarted.

**Native Pi nested delegation, enforced by code:** Root Pi children (depth 1) have the native `subagent` tool and may make at most one more generation (depth 2). The typed tier lattice is scout → scout; mechanic → scout/mechanic; worker → scout/mechanic/worker; expert → any of those four. God is never allowed. The SDK pins a required per-tier guard extension into every child and descendant; it registers a monotonic `allowedAgents` ceiling, rejects model/cwd/worktree overrides and workflow launches, and upstream enforces `maxSubagentDepth = 2`. Profile parsing and the exact modelScope are checked before first admission. A nested child cannot delegate again. All descendants share the original worktree/write budget; acceptance, conflict avoidance, and review remain the outer parent's responsibility. **Command Code executions do not gain native Pi nesting**; they must not start bridge CLI children or host-native agents. A separate typed delegation interface would be required for Command Code parity.

**Never fallback after any tracked/untracked edit, changed HEAD, uncertain prompt admission, unknown process termination or potentially running worker.** Retain durable leases and inspect uncertain sessions; do not launch a second paid worker. A generic task failure, rejected acceptance check, or changed path is not a provider failure. OpenCode Go is the final fallback after Muse: no third provider, no return to Command Code. Cancellation acknowledgement alone is not proof of termination. The scope check is Git-based, not an OS sandbox; ignored files and host writes require separate containment.

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
- Only Pi SDK workers may delegate one native child generation, at equal-or-weaker tier and within their original brief; the code-owned ceiling/depth guard makes escalation an error. Command Code workers do not nest. Host-native child launches remain forbidden outside the bridge.

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
