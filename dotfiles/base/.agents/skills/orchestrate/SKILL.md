---
name: orchestrate
description: "Route coding subagents through the Pi SDK bridge (OpenCode: native subagents only); scope and verify; campaigns only when useful. Skip work cheaper to do directly."
---

# Orchestrate

**All coding subagents from any harness use `pi-subagent-bridge`**, including `expert` and `god`. New expert/god jobs MUST use the bridge's pinned Antigravity CLI `gemini-4-carbon-high` backend. Do not spawn native Claude/Codex `god`, or use native subagents while an approved lower-tier bridge backend is available. Exceptions: the OpenCode path below and the lower-tier quota fallback.

**OpenCode exception:** A top-level OpenCode session never uses `pi-subagent-bridge` — any tier, including expert/god, never as a fallback. Delegate only through OpenCode native subagents: the configured `scout`/`mechanic`/`worker`/`expert` agents, or built-in `general`/`explore`. `god` has no OpenCode lane. If the top-level model is free (zero cost, e.g. `opencode/*-free`), every tier must run a free model; never substitute a paid one. All tiers pin `opencode/inkling-2-small-free`:

| Tier | Effort |
| --- | --- |
| scout (read-only: no `shell`, no `edit`) | low |
| mechanic | medium |
| worker | high |
| expert | max |

These pins hold regardless of the top-level model. Bridge pins, fallbacks, and nesting rules below do not apply on this path.

**Quota fallback for scout/mechanic/worker only:** When the bridge cannot run any pinned backend, use harness-native subagents with the same brief, isolated worktree, scope, and verification. In Claude Code use `haiku` for scout and `sonnet` for mechanic/worker. Preserve any partial work before relaunch. Never use this fallback for expert or god: Carbon unavailable or exhausted is a blocker, not permission to use Argon, native Opus/Sol, or a cheaper model. No hook gates native subagents. Return to the bridge when it has capacity.

**Host-access exception for scout/mechanic/worker:** a slice whose acceptance proof needs host access that Codex's sandbox cannot grant, such as Docker, booting VMs, `taskpolicy`, or hardware, runs on a native subagent at the same tier mapping (`haiku` scout, `sonnet` mechanic/worker), with the same brief, worktree, scope, and parent verification. Fetching dependencies is not such a slice: use scope `network: true`.

The parent keeps task framing, orchestration, integration, and independent verification. Delegate only when context isolation, cost, parallelism, or independent scrutiny beats the overhead. No worker may broaden its scope.

## Pinned tiers

| Tier | Primary executor/model | Effort | Provider fallback |
| --- | --- | --- | --- |
| scout | Codex `gpt-6-luna` | medium | Command Code `meta/muse-ember` (medium); Pi `opencode-go/muse-spark-1.3-contributor` (medium) |
| mechanic | Codex `gpt-6-luna` | high | Command Code `meta/muse-ember` (xhigh); Pi `opencode-go/muse-spark-1.3-contributor` (high) |
| worker | Codex `gpt-6.1-terra` | medium | Command Code `deepseek/deepseek-v4.1-flash` (high); Pi `muse-sdk/muse-spark-1.3` (xhigh), then `opencode-go/deepseek-v4.1-flash` (high) |
| expert | Antigravity CLI `gemini-4-carbon-high` | high | **None. Fail closed.** |
| god | Antigravity CLI `gemini-4-carbon-high` | high | **None. Fail closed.** |

**Model prohibition:** Gemini 4 Argon is banned from routing, fallback, and substitutions. Antigravity CLI's `--model` is pinned and verified against `agy models`. No implicit or automatic downgrade. Carbon currently needs Google AI Ultra or eligible enterprise Antigravity access; the bridge never buys API credits.

**Hydrogen succession:** When a task would previously select Gemini 3.8 Flash, prefer the available `gemini-4-hydrogen-high` or `gemini-4-hydrogen-medium` in Antigravity. Documented CLI slugs are `gemini-4-hydrogen-{low,medium,high,xhigh}`. Existing Codex/Command/Pi pins are not Gemini 3.8 and must not be relabeled. Hydrogen is not a configured bridge backend; use it directly only with an explicit pin and a successful `agy models` check. Never fall back to Gemini 3.8 or Argon.

**Pi OpenCode Go boundary:** scout and mechanic pin `opencode-go/muse-spark-1.3-contributor`; Zen models are unusable from headless SDK workers (the gateway rejects non-opencode-client User-Agents with `429 FreeUsageLimitError` — see `docs/pi.md#why-zen-is-not-a-pin`). Other OpenCode Go models and custom endpoints are forbidden. The existing Pi expert profile remains only for already-admitted legacy sessions, not new expert dispatches.

No Pi `god` tier exists. Root `god` is a terminal Carbon lane; no native child fanout. Reserve it for exceptional architectural decisions and independent adversarial review. Expert/god differ by brief and acceptance proof, not by model.

**Default to worker** for substantial well-specified tasks; size alone does not justify `expert`. A read-only `scout` gets no `bash`, `edit`, or `write`. No tier grants privilege to change requirements or affect unrelated files.

## The bridge, except OpenCode

Use the MCP tools `worker_model_check`, `worker_start`, `worker_status`, `worker_resume`, `worker_cancel`, or the `pi-subagent-bridge` CLI shim where a harness has no MCP (see `tools/pi-subagent-bridge/README.md`).

Create a clean worktree under `.work/wt/<slice>`, call `worker_model_check`, then `worker_start`. Set scope `network: true` when the slice adds or fetches dependencies; Codex's sandbox otherwise has no network and cannot write the Cargo home. The schema enforces the scope's shape; the judgment is yours: `acceptance_proof` is a named command with its expected result (or a source file:line for research), `attempt_limit` is 1 unless one same-scope correction is justified, and `stop_on` covers ambiguity, scope expansion, new dependencies, contract changes, and unavailable proof. The `brief` states one outcome, the relevant facts, prohibited changes, and whether one level of Pi fanout is justified.

**Admission is not completion.** Run the `watch` command that `worker_start` returns as a background task, so the harness wakes you when the worker ends; never end a turn on an admitted worker without one. Then read `worker_status`. State `incomplete` means the worker exited without a final `ACCEPTANCE: met`; treat it as unaccepted work, not success. It reports the actual backend, model, thinking/effort, changed paths, out-of-scope changes, and whether HEAD stayed pinned. Require exact commands, exit codes and decisive output; prose is only a claim.

The parent independently reviews `git diff --check`, the diff against `base_revision` and untracked paths once. Verify requested behavior, permitted scope, imports and obvious regressions before integrating. An optional single `worker_resume` correction may touch only the same files, without increasing the attempt budget. Otherwise park or reject. Workers never commit, merge, push, switch branches, or clean worktrees.

## Provider fallback and ambiguous runs

**Codex subscription is first for scout/mechanic/worker**, followed by Command Code, then Pi. Expert and god route straight to Carbon; neither has fallback. Only an unavailable executor or a confirmed provider/model/usage failure may switch, before any edits and with unambiguous termination. Never switch after Go, and never return to Command Code. Legacy sessions keep their admitted backend and models, including prior Pi/Command/Codex expert sessions.

**Nesting:** a Pi SDK child may delegate one more generation, at an equal-or-weaker tier, only when its brief calls for it; the bridge's guard rejects anything else (deeper nesting, `god`, model or worktree overrides). Descendants share the original worktree and write budget, and the outer parent still owns acceptance and review. Codex and Command Code workers are leaves: no bridge CLI children, no host-native agents.

**Never fallback after any tracked/untracked edit, changed HEAD, uncertain prompt admission, unknown process termination or potentially running worker.** Retain durable leases and inspect uncertain sessions; do not launch a second paid worker. A generic task failure, rejected acceptance check, or changed path is not a provider failure. Cancellation acknowledgement alone is not proof of termination. The scope check is Git-based, not an OS sandbox; ignored files and host writes require separate containment.

**Clef-flash advice** (per the global contract): build the `TaskBrief` from verified facts and call `decide route --guide`, then `decide route --baseline worker` once. On any failure, choose from the table without retrying.

## Delegation

Delegate coherent component-sized work. Do not spawn an agent for one command or edit, to restate a plan, or to summarize code the parent must understand anyway. Batch related trivial work into one assignment. When one script or codemod can apply the change to every unit in a single pass, write and run it yourself instead of fanning out children to hand-apply it, and prove it by rerunning it on the unit you did by hand.

Size concurrency for accepted progress, not resource headroom. Serial is the default for work that shares files; parallel writers get disjoint ownership, bounded by shared services, review, and the verification queue. Pause writers when acceptance is saturated. Each child gets a coherent end-to-end slice, not a fragment needing another handoff.

When a child reports, a merge lands, or a check fails, reassess ready work and the limiting stage. A briefing, environment, or verification failure gets its cause fixed and at most one retry at the same tier with a materially changed approach. Escalate to a stronger tier only for evidenced reasoning limits; where tiers share a model, use fresh context, never a provider switch. Never repeat an unchanged failure. Owner intent, public contracts, required proof, and permissions stay fixed unless the owner changes them.

Give every parallel writer its own worktree, created by you with `git worktree add .work/wt/<name> -b <branch>` and named in the brief as the only place it may write. A child's final report is not shown to the user: relay what matters. Bridge workers do not deliver native harness notifications; use `worker-watch` where available and inspect `worker_status` when complete. Never restart a worker merely because the parent lost its notification.

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
