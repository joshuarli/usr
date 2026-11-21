---
name: orchestrate
description: "Route coding subagents through native Command Code/OpenCode/Devin lanes or the Pi bridge; scope and verify; campaigns only when useful. Skip work cheaper to do directly."
---

# Orchestrate

<!-- policy:begin routing-intro -->
<!-- Generated from tools/pi-subagent-bridge/src/policy.ts; run make generate. -->
**All scout/mechanic/worker coding subagents use `pi-subagent-bridge` by default**, except top-level OpenCode, Devin, Command Code and Antigravity native parents described below. Bridge tiers: `scout`, `mechanic`, `worker`. Native-only tier: `expert`, which always runs as a harness-native subagent and never through the bridge. There is no `god` tier. The model families `gemini-3.8` and `gemini-4-argon` and `gemini-4-carbon` and `gpt-6-astra` and `gpt-6.1-astra` and `gpt-6.2-astra` and `claude-fable` and `fable` are prohibited, including every effort variant.
<!-- policy:end routing-intro -->

<!-- policy:begin opencode -->
<!-- Generated from tools/pi-subagent-bridge/src/policy.ts; run make generate. -->
**OpenCode exception:** A top-level OpenCode session never uses `pi-subagent-bridge`, at any tier or as a fallback. Delegate only through its configured native agents or built-in `general`/`explore`. When the top-level model is free, every tier must run a free model. The configured tier agents use `opencode/hy4-flash-free` regardless of the top-level model:

| Tier | Effort |
| --- | --- |
| scout (read-only: no `shell`, no `edit`) | high |
| mechanic | high |
| worker | high |
| expert | high |

Bridge pins, fallbacks, and nesting rules do not apply on this path.
<!-- policy:end opencode -->

<!-- policy:begin devin -->
<!-- Generated from tools/pi-subagent-bridge/src/policy.ts; run make generate. -->
**Devin exception:** A top-level Devin session never uses `pi-subagent-bridge`, at any tier or as a fallback. Delegate only through native `run_subagent` subagents (`subagent_explore` for read-only research, `subagent_general` for changes). Devin subagents run on the models the session provides, so there is no per-tier pinning on this path. Bridge pins, fallbacks, and nesting rules do not apply.
<!-- policy:end devin -->

<!-- policy:begin command-code -->
<!-- Generated from tools/pi-subagent-bridge/src/policy.ts; run make generate. -->
**Command Code exception:** A top-level Command Code session delegates through native `agent` subagents only; never invoke `pi-subagent-bridge` from that parent. Use the named agents below, never the unpinned built-in General/Explore for tiered work. The pilot requires an explicit comparison task; it is not the default worker.

| Tier | Native agent | Model | Effort |
| --- | --- | --- | --- |
| scout | `usr-scout` | `thinkingmachines/inkling-2-small:free` | model default |
| mechanic | `usr-mechanic` | `tencent/hy4-flash` | `high` |
| worker | `usr-worker` | `deepseek/deepseek-v4.1-flash` | `high` |
| expert | `usr-expert` | `tencent/hy4` | `high` |
| worker pilot (explicit only) | `usr-worker-hy4` | `tencent/hy4` | `medium` |

Native agents have separate contexts and cannot spawn another agent. They do not provide bridge admission or Git worktree containment: the parent owns isolation, scope, review, tests and integration. Agent frontmatter pins are not hard enforcement: a per-call model override takes precedence, and unsupported effort silently reverts to model default. Check `cmd --list-models` and the `/model` effort picker on each host before trusting a lane; block it rather than silently substituting. Collect detached results with `agent_output` and run `scope-check --lane` on native writer lanes.
<!-- policy:end command-code -->

<!-- policy:begin antigravity -->
<!-- Generated from tools/pi-subagent-bridge/src/policy.ts; run make generate. -->
**Antigravity CLI exception:** A top-level `agy` session delegates only through native `invoke_subagent`. Never invoke the Pi bridge or use another harness as fallback. The `god` label is a direct parent-session mode, not a bridge tier. Native `usr-*` definitions live under `~/.gemini/config/agents/`.

| Tier | Native agent | Target model | Target effort | CLI selector |
| --- | --- | --- | --- | --- |
| scout | `usr-scout` | `gemini-4-hydrogen-low` | `low` | `flash` |
| mechanic | `usr-mechanic` | `gemini-4-hydrogen-low` | `low` | `flash` |
| worker | `usr-worker` | `gemini-4-hydrogen-high` | `high` | `flash` |
| expert | `usr-expert` | `gemini-4-neon-high` | `high` | `pro` |

The CLI's documented agent schema accepts `model: flash/pro` selectors, not exact model IDs or effort pins. Treat these as target allocations, check actual child model and effort on first use, and block any lane resolving to Gemini 3.8, Carbon, Argon or an unexpected model. Carbon may only be selected manually by the owner, outside delegation. See `docs/antigravity-native.md`.
<!-- policy:end antigravity -->

<!-- policy:begin native-fallback -->
<!-- Generated from tools/pi-subagent-bridge/src/policy.ts; run make generate. -->
**Claude Code native subagents:** `expert` assignments always use native subagents pinned to `opus` with `xhigh` effort. If that pinned model is unavailable, the expert lane is blocked; never substitute another model. When no approved bridge backend can run because it is unavailable or exhausted, scout/mechanic/worker use tier-matched native subagents with the same brief, worktree, scope, and independent verification: scout: `haiku`; mechanic: `sonnet`; worker: `sonnet`. A host or session whose environment sets `USR_DELEGATION=native`, such as a cloud environment without bridge providers, uses these native subagents directly and does not start the bridge. Preserve partial work before relaunch. Register native lanes with `scope-check --register` and record their final check with `scope-check --lane`. No hook gates native subagents. Return to the bridge when capacity recovers, unless `USR_DELEGATION=native` is set.
<!-- policy:end native-fallback -->

The parent keeps task framing, orchestration, integration, and independent verification. Delegate only when context isolation, cost, parallelism, or independent scrutiny beats the overhead. No worker may broaden its scope.

## Pinned tiers

On the bridge path, call `worker_model_check` for the tier you are about to assign: it returns the exact pins, efforts, fallback order and availability. The full table is in `tools/pi-subagent-bridge/README.md`.

**Pi OpenCode Go boundary:** scout and mechanic Pi fallbacks use pinned OpenCode Go models; Zen models are unusable from headless SDK workers (the gateway rejects non-opencode-client User-Agents with `429 FreeUsageLimitError` — see `docs/pi.md#why-zen-is-not-a-pin`). Other OpenCode Go models and custom endpoints are forbidden. The native Pi `expert` profile is the Pi-native expert lane; it authorizes new expert dispatches from Pi sessions through the native subagent tool.

Expert assignments use harness-native subagents (Command Code's `usr-expert`, OpenCode's `expert` agent, Devin's `run_subagent`, Codex's native subagents, Pi's native `expert` profile, Claude Code's `opus` at `xhigh` effort); nothing routes to the bridge. Codex expert runs like Devin's: on the model its session config provides, with no per-tier pin. Reserve the lane for exceptional architectural decisions and independent adversarial review. There is no higher tier above expert. If the harness's expert model is unavailable, the lane is blocked; never substitute a weaker model.

**Native expert lanes get the bridge's guarantees by hand.** Nothing enforces scope on a native subagent, so the parent supplies what admission would:

- Create its worktree and branch, and name that worktree in the brief as the only place it may write. Write the scope as a bridge scope JSON (`base_revision`, `writable_paths`, `acceptance_proof`, `stop_on`).
- Put the bridge's worker contract in the brief: commit only on the lane branch, never amend pre-existing commits, merge, rebase, switch branches or push; keep working until the acceptance proof is met or a listed stop condition applies; end with a proof record of exact commands, exit codes and decisive output, and a final `ACCEPTANCE: met` or `ACCEPTANCE: not met` line.
- Register it with `pi-subagent-bridge scope-check CWD SCOPE_JSON_FILE BRANCH --register TITLE` and retain the returned lane ID. When it finishes, from the repository run `pi-subagent-bridge scope-check --lane ID`. It reports changed and out-of-scope paths since `base_revision` and whether HEAD stayed on the lane, and exits 1 when either fails. Then review the diff as for any worker.

**Default to worker** for substantial well-specified tasks; size alone does not justify a native `expert` subagent. A read-only `scout` gets no `bash`, `edit`, or `write`. No tier grants privilege to change requirements or affect unrelated files.

## The bridge, except Command Code, OpenCode and Devin

Use the MCP tools `worker_model_check`, `worker_start`, `worker_status`, `worker_resume`, `worker_cancel`, or the `pi-subagent-bridge` CLI shim where a harness has no MCP (see `tools/pi-subagent-bridge/README.md`).

Create a clean worktree under `.work/wt/<slice>`, call `worker_model_check`, then `worker_start`. The schema enforces the scope's shape; the judgment is yours: `acceptance_proof` is a named command with its expected result (or a source file:line for research), `attempt_limit` is 1 unless one same-scope correction is justified, and `stop_on` covers ambiguity, scope expansion, new dependencies, contract changes, and unavailable proof. The `brief` states one outcome, the relevant facts, prohibited changes, and whether one level of Pi fanout is justified.

**Admission is not completion.** Run the `watch` command that `worker_start` returns as a background task, so the harness wakes you when the worker ends; never end a turn on an admitted worker without one. The default idle threshold is 45 minutes. Then read `worker_status`. For a reviewed same-scope correction, `worker_resume` may add up to two lifetime attempts with `extend_attempts` and `extension_reason`. State `incomplete` means the worker exited without a final `ACCEPTANCE: met`; treat it as unaccepted work, not success. For unmet acceptance, check `stopped_on` and `stop_condition_valid` against the assigned stop conditions. It reports the actual backend, model, thinking/effort, changed paths, out-of-scope changes, and whether HEAD stayed pinned. Require exact commands, exit codes and decisive output; prose is only a claim.

The parent independently reviews `git diff --check`, the diff against `base_revision` (including commits) and untracked paths once. Verify requested behavior, permitted scope, imports and obvious regressions before integrating. An optional single `worker_resume` correction may touch only the same files, without increasing the attempt budget. Otherwise park or reject. Scouts never commit; other workers may commit on their lane branch. Workers never merge, push, switch branches, or clean worktrees.

## Provider fallback and ambiguous runs

**The bridge owns provider fallback on bridge-path parents only.** `worker_status` switches only along the tier's admitted routes, only before edits and with unambiguous termination, and admitted sessions keep their recorded models. Never start a replacement worker yourself: a task failure, rejected acceptance check, or changed path is not a provider failure. A session whose `attention` is `needs_attention` (any `blocked_*` state) or `unknown` needs you to inspect the session and worktree before deciding anything; do not launch a second paid worker over it. Check `pending_steer` and `last_steer` before retrying steering. Cancellation acknowledgement is not proof of termination; wait until `watch` or `inspect` shows the run gone. The scope check is Git-based; ignored files and host writes are not contained.

**Nesting:** Command Code native children cannot launch subagents. On the bridge path, grant one level of Pi fanout in the brief only when the slice needs it; the bridge's guard enforces the rest. Codex and Command Code workers are leaves.

**Clef-flash advice** (per the global contract): build the `TaskBrief` from verified facts and call `decide route --guide`, then `decide route --baseline worker` once. On any failure, choose the tier yourself without retrying.

## Delegation

Delegate coherent component-sized work. Do not spawn an agent for one command or edit, to restate a plan, or to summarize code the parent must understand anyway. Batch related trivial work into one assignment. When one script or codemod can apply the change to every unit in a single pass, write and run it yourself instead of fanning out children to hand-apply it, and prove it by rerunning it on the unit you did by hand.

Size concurrency for accepted progress, not resource headroom. Serial is the default for work that shares files; parallel writers get disjoint ownership, bounded by shared services, review, and the verification queue. Pause writers when acceptance is saturated. Each child gets a coherent end-to-end slice, not a fragment needing another handoff.

When a child reports, a merge lands, or a check fails, reassess ready work and the limiting stage. A briefing, environment, or verification failure gets its cause fixed and at most one retry at the same tier with a materially changed approach. Escalate to a stronger tier only for evidenced reasoning limits; where tiers share a model, use fresh context, never a provider switch. Never repeat an unchanged failure. Owner intent, public contracts, required proof, and permissions stay fixed unless the owner changes them.

Give every parallel writer its own worktree, created by you with `git worktree add .work/wt/<name> -b <branch>` and named in the brief as the only place it may write. A child's final report is not shown to the user: relay what matters. Bridge workers do not deliver native harness notifications; use `pi-subagent-bridge watch` where available and inspect `worker_status` when complete. Never restart a worker merely because the parent lost its notification.

Carry forward findings and failed approaches. Every child gets:

- Clear ownership and write boundaries.
- A concrete deliverable with only the needed context.
- Proportionate checks, an attempt limit, and a stopping condition.
- The current campaign ruling, plus a duty to report misleading metrics, repeated gate failures, or shared blockers rather than work around them.

## Worktree lifecycle

The parent owns each child worktree from creation through removal. Every skill that removes worktrees or branches follows this section. Record its exact path, its branch when it has one, and the integration worktree when you create it or the harness creates it. A child finishing does not remove its worktree. Remove only the recorded path, never every entry under `.work/wt/`.

Treat retirement as part of accepting the lane, regardless of free disk space. Claude's `WorktreeRemove` hook does not run when a hook-created subagent finishes: the parent must explicitly retire that lane. Separately, unsolicited cleanup sweeps require an `agent-disk-pressure` notice and a fresh reading strictly below 16 GiB; use `cleanup`, never periodic model polling. Workers report pressure to their parent and keep their assigned scope.

After a child finishes, review its changes and decide whether to integrate or park them. For accepted changes, inspect the integrated diff and reuse worker evidence unless integration or changed inputs could invalidate it. Remove the child worktree only after applicable proof is complete, the child has stopped, and all work worth keeping is in the integration branch or a preserved branch.

Retire it with `worktree-retire <child-worktree> --into <integration-head>`. The tool keeps the worktree when it is locked, dirty, or not integrated, and lists ignored files: preserve any worth keeping, then rerun with `--discard-ignored`. It deletes the branch only when it is an ancestor, so a squash-integrated branch survives. Use `--dry-run` to preview. Never force-delete a branch or worktree.

When you park unfinished work, commit it on a named branch and record its exact path and resume conditions. Keep the checkout while it has a consumer or is not safely integrated; a pressure sweep cannot decide to discard a parked lane. Do not point `--into` at the lane's own HEAD or branch to make retirement pass.

## Campaigns

For a backlog too large for one session, read [campaign mechanics and lane contract](references/campaigns.md) before preparing or launching work. By default, ready slices that own disjoint files run in parallel; slices that share files run serially.

The parent runs the [steering checkpoint](references/campaigns.md#parent-steering-checkpoint) after each accepted slice, on resume, and after repeated failures, without waiting for the owner to complain.

**The test:** the parent can name the accepted slices that landed and the next one, and the integration branch is green.

**Report:** accepted slices and the checks that proved them, what is open and why, contract changes, and blockers needing the owner. Lane counts, doc commits, and audits are not progress.
