---
name: orchestrate
description: "Route coding subagents through the Pi SDK bridge (OpenCode: native subagents only); scope and verify; campaigns only when useful. Skip work cheaper to do directly."
---

# Orchestrate

<!-- policy:begin routing-intro -->
<!-- Generated from tools/pi-subagent-bridge/src/policy.ts; run make generate. -->
**All coding subagents from any harness use `pi-subagent-bridge`**, subject to the OpenCode and native exceptions below. New `expert` assignments use Antigravity CLI `gemini-4-hydrogen-xhigh` (`xhigh`) exclusively, with no fallback. The available tiers are `scout`, `mechanic`, `worker`, `expert`; there is no `god` tier. The model families `gemini-4-argon` and `gemini-4-carbon` are prohibited, including every effort variant. Already-admitted sessions retain their recorded models and routes.
<!-- policy:end routing-intro -->

<!-- policy:begin opencode -->
<!-- Generated from tools/pi-subagent-bridge/src/policy.ts; run make generate. -->
**OpenCode exception:** A top-level OpenCode session never uses `pi-subagent-bridge`, at any tier or as a fallback. Delegate only through its configured native agents or built-in `general`/`explore`. When the top-level model is free, every tier must run a free model. The configured tier agents use `opencode/inkling-2-small-free` regardless of the top-level model:

| Tier | Effort |
| --- | --- |
| scout (read-only: no `shell`, no `edit`) | low |
| mechanic | medium |
| worker | high |
| expert | max |

Bridge pins, fallbacks, and nesting rules do not apply on this path.
<!-- policy:end opencode -->

<!-- policy:begin native-fallback -->
<!-- Generated from tools/pi-subagent-bridge/src/policy.ts; run make generate. -->
**Quota fallback for scout/mechanic/worker only:** When no approved bridge backend can run because it is unavailable or exhausted, use tier-matched native subagents with the same brief, worktree, scope, and independent verification. In Claude Code use scout: `haiku`; mechanic: `sonnet`; worker: `sonnet`. Preserve partial work before relaunch. Expert unavailability or quota exhaustion is a blocker; never substitute another model. No hook gates native subagents. Return to the bridge when capacity recovers.

**Host-access exception for scout/mechanic/worker:** use the same native mapping when the slice's proof needs host access Codex's sandbox cannot grant (Docker, VMs, `taskpolicy`, hardware), with unchanged scope and parent review. Dependency fetching uses scope `network: true` and does not qualify.
<!-- policy:end native-fallback -->

The parent keeps task framing, orchestration, integration, and independent verification. Delegate only when context isolation, cost, parallelism, or independent scrutiny beats the overhead. No worker may broaden its scope.

## Pinned tiers

<!-- policy:begin routing-table -->
<!-- Generated from tools/pi-subagent-bridge/src/policy.ts; run make generate. -->
| Tier | Primary | Fallback (in order) |
| --- | --- | --- |
| scout | Codex `gpt-6-luna` (`medium`) | Command Code `meta/muse-ember` (`medium`); Pi `opencode-go/muse-spark-1.3-contributor` (`medium`) |
| mechanic | Codex `gpt-6-luna` (`high`) | Command Code `meta/muse-ember` (`xhigh`); Pi `opencode-go/muse-spark-1.3-contributor` (`high`) |
| worker | Codex `gpt-6.1-terra` (`medium`) | Command Code `deepseek/deepseek-v4.1-flash` (`high`); Pi `muse-sdk/muse-spark-1.3` (`xhigh`); Pi `opencode-go/deepseek-v4.1-flash` (`high`) |
| expert | Antigravity CLI `gemini-4-hydrogen-xhigh` (`xhigh`) | **None. Fail closed.** |
<!-- policy:end routing-table -->

<!-- policy:begin direct-models -->
<!-- Generated from tools/pi-subagent-bridge/src/policy.ts; run make generate. -->
Antigravity main sessions replacing Gemini 3.8 Flash must explicitly select an available approved model: `gemini-4-hydrogen-high` or `gemini-4-hydrogen-medium`. Verify it with `agy models`; never silently substitute a model or purchase API credits. Delegated expert assignments use the exact root pin above.
<!-- policy:end direct-models -->

**Pi OpenCode Go boundary:** scout and mechanic use the pinned OpenCode Go models in the routing table; Zen models are unusable from headless SDK workers (the gateway rejects non-opencode-client User-Agents with `429 FreeUsageLimitError` — see `docs/pi.md#why-zen-is-not-a-pin`). Other OpenCode Go models and custom endpoints are forbidden. The Pi expert profile belongs to the native/nested domain and supports already-admitted legacy sessions; it does not authorize new root expert dispatches.

Expert is a terminal Antigravity lane; no native child fanout beyond the typed ceilings. Reserve it for exceptional architectural decisions and independent adversarial review. There is no higher tier above expert.

**Default to worker** for substantial well-specified tasks; size alone does not justify `expert`. A read-only `scout` gets no `bash`, `edit`, or `write`. No tier grants privilege to change requirements or affect unrelated files.

## The bridge, except OpenCode

Use the MCP tools `worker_model_check`, `worker_start`, `worker_status`, `worker_resume`, `worker_cancel`, or the `pi-subagent-bridge` CLI shim where a harness has no MCP (see `tools/pi-subagent-bridge/README.md`).

Create a clean worktree under `.work/wt/<slice>`, call `worker_model_check`, then `worker_start`. Set scope `network: true` when the slice adds or fetches dependencies; Codex's sandbox otherwise has no network and cannot write the Cargo home. The schema enforces the scope's shape; the judgment is yours: `acceptance_proof` is a named command with its expected result (or a source file:line for research), `attempt_limit` is 1 unless one same-scope correction is justified, and `stop_on` covers ambiguity, scope expansion, new dependencies, contract changes, and unavailable proof. The `brief` states one outcome, the relevant facts, prohibited changes, and whether one level of Pi fanout is justified.

**Admission is not completion.** Run the `watch` command that `worker_start` returns as a background task, so the harness wakes you when the worker ends; never end a turn on an admitted worker without one. Then read `worker_status`. State `incomplete` means the worker exited without a final `ACCEPTANCE: met`; treat it as unaccepted work, not success. It reports the actual backend, model, thinking/effort, changed paths, out-of-scope changes, and whether HEAD stayed pinned. Require exact commands, exit codes and decisive output; prose is only a claim.

The parent independently reviews `git diff --check`, the diff against `base_revision` and untracked paths once. Verify requested behavior, permitted scope, imports and obvious regressions before integrating. An optional single `worker_resume` correction may touch only the same files, without increasing the attempt budget. Otherwise park or reject. Workers never commit, merge, push, switch branches, or clean worktrees.

## Provider fallback and ambiguous runs

**Follow the ordered routing table.** Expert has no fallback. Only an unavailable executor or a confirmed provider/model/usage failure may switch, before any edits and with unambiguous termination. Never switch after Go, and never return to Command Code. Legacy sessions keep their admitted backend and models, including prior Pi/Command/Codex expert sessions.

**Nesting:** a Pi SDK child may delegate one more generation, at an equal-or-weaker tier, only when its brief calls for it; the bridge's guard rejects anything else (deeper nesting, model or worktree overrides). Descendants share the original worktree and write budget, and the outer parent still owns acceptance and review. Codex and Command Code workers are leaves: no bridge CLI children, no host-native agents.

**Never fallback after any tracked/untracked edit, changed HEAD, uncertain prompt admission, unknown process termination or potentially running worker.** Retain durable leases and inspect uncertain sessions; do not launch a second paid worker. A generic task failure, rejected acceptance check, or changed path is not a provider failure. Cancellation acknowledgement alone is not proof of termination. The scope check is Git-based, not an OS sandbox; ignored files and host writes require separate containment.

**Clef-flash advice** (per the global contract): build the `TaskBrief` from verified facts and call `decide route --guide`, then `decide route --baseline worker` once. On any failure, choose from the table without retrying.

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

After a child finishes, review its changes and decide whether to integrate or park them. For accepted changes, inspect the integrated diff and reuse worker evidence unless integration or changed inputs could invalidate it. Remove the child worktree only after applicable proof is complete, the child has stopped, and all work worth keeping is in the integration branch or a preserved branch.

Retire it with `worktree-retire <child-worktree> --into <integration-head>`. The tool keeps the worktree when it is locked, dirty, or not integrated, and lists ignored files: preserve any worth keeping, then rerun with `--discard-ignored`. It deletes the branch only when it is an ancestor, so a squash-integrated branch survives. Use `--dry-run` to preview. Never force-delete a branch or worktree.

When you park unfinished work, commit it, remove its clean worktree, and keep its branch.

## Campaigns

For a backlog too large for one session, read [campaign mechanics and lane contract](references/campaigns.md) before preparing or launching work. The default is one writer on one slice until it is accepted. Add lanes only when they own disjoint files.

The parent runs the [steering checkpoint](references/campaigns.md#parent-steering-checkpoint) after each accepted slice, on resume, and after repeated failures, without waiting for the owner to complain.

**The test:** the parent can name the accepted slices that landed and the next one, and the integration branch is green.

**Report:** accepted slices and the checks that proved them, what is open and why, contract changes, and blockers needing the owner. Lane counts, doc commits, and audits are not progress.
