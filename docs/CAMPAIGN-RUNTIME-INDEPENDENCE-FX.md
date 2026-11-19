# Runtime-independent worker bridge and FX migration

## Status

**Decision, November 19, 2026:** qualify FX's pinned native ACP interface inside the existing bridge as the next step toward replacing Pi headless workers. The current FX experiment does **not** satisfy worker parity. Keep Pi available until each required route and lifecycle contract has a qualified replacement.

- **Completed foundation:** runtime independence, optional Pi loading, core-only installation, shared state/owner/lease machinery, and the isolated `fx ask --json` experiment. Preserve the [runtime-independence evidence](verification/runtime-independence.md) and [original CLI spike evidence](verification/runtime-independence-fx.md); do not restart those campaigns.
- **Historical qualification:** native macOS ARM64 deterministic tools, successful continuation, owner controls, isolation probes and quota failover through the approved ladder. A Codex fallback success is not FX inference. No successful live FX task is established by the recorded evidence.
- **Phase 0 recovery and telemetry, November 19, 2026:** a receipt-verified deadline, cancellation, nonzero exit or quota stop now keeps the validated native session token. These outcomes report `timed_out`, `cancelled` or `failed` and resume through `worker_resume`. Missing or invalid receipts, mismatched native sessions, and changed pins or worktrees still block resumption. Each new FX admission persists `wallMs` and `maxSteps`. Admission and status report them as `run_deadline_ms` and `run_step_limit`. Records written before that report `null`. Evidence: `npm run test:fx` on Node 26.13.1 with deterministic fake FX executables.
- **Phase 0 step budgets:** over ACP, step exhaustion is distinguished. FX ends the prompt with `stopReason: "refused"` and logs `outcome_kind=step_limit`. The bridge reports this as `turn_limit` and continues without consuming an attempt. The CLI transport still cannot distinguish it: an empty `final_output` stays `unknown_or_interrupted`. The 15-minute/20-step pilot bounds and the 15-minute `wallMs` cap remain until a production budget is approved.
- **Phase 1 ACP leaf worker, November 19, 2026:** accepted with deterministic proof. `makeFxAdapter({ transport: "acp" })` runs `fx acp` under a detached supervisor (`src/fx-acp-supervisor.ts`):
  - It persists the native session ID at admission and verifies effective pins from `configOptions`.
  - Unexpected permission requests are denied, and the run is reported as blocked.
  - Stops send `session/cancel`, and termination is verified against a snapshot of FX's descendant tree. FX runs shell tools in their own process groups, so a group check alone is insufficient.
  - Resumption validates token, worktree, pins and saved configuration before attempt accounting or transition, through `preflightResume`. FX itself resumes a session for any `cwd`, so the bridge-side workspace binding is required.
- **ACP session-creation blocker resolved:** FX 0.0.17 returns `-32603 Failed to create session` whenever `fx acp --provider <name>` is given. This includes configured custom providers, which `--help` documents as accepted. Built-in providers without credentials fail differently, with `-32600`. Selecting the provider through private `settings.json` works. Reproduction: `fx acp --provider <configured>` followed by `initialize` and `session/new {cwd, mcpServers: []}`.
- **Phase 1 evidence:** `npm run spike:fx -- --local-acp` passes with the pinned 0.0.17 binary (`binary_sha256` in `experiment/fx/pin.json`) on macOS ARM64 and Node 26.13.1 against a loopback provider. It covers:
  - scout evidence, edit and parent check, owner correction with idempotent replay, and steering through interrupt-resume
  - interrupt after edit, deadline then resume, and cancellation during a writing tool (tool killed, no late write) then resume
  - failed-tool recovery, step limit then continuation, changed-configuration refusal, and a hostile read-only scout. The scout ran with committed `.fx.json` (full-access, `max_agent_steps: 0`) and `.mcp.json`: all five escape tools failed, and the ambient MCP server never started.
  - `npm run test:fx` adds binary-free ACP regressions for pin mismatch, permission denial, unverified termination and the preflight ordering.
- **Phase 1 limits:**
  - Steering remains interrupt-resume. The negotiated `_meta.fx.steer` live steering is not used, so delivery states are the bridge's existing pending/completed/failed.
  - A process that detaches and reparents after the descendant snapshot is not detected. This is lifecycle control, not an OS sandbox.
  - ACP is not wired into production routing.
- **Next implementation slice:** Phase 2 live DeepSeek through ACP, with an account-access check first. Phases 3 and 4 can proceed deterministically in parallel.
- **Current boundary:** FX remains experimental. Production routes, public names, ordinary schema-2 writes, experimental schema-3 readers/writes, installer defaults and provider entitlements are unchanged.

This is the authoritative remaining execution plan. The dated audit holds the comparison, pinned references and diagnostic evidence; earlier verification documents hold historical results.

## Charter and working rules

The owner requested an audit and replacement plan, then explicitly authorized integrating and committing that documentation directly to `usr`. This revision records that plan; runtime implementation and production promotion remain future work under their respective launch scope. The earlier CLI-only spike boundary is superseded for planning by the ACP sequence below.

Use the existing [campaign mechanics](../dotfiles/base/.agents/skills/orchestrate/references/campaigns.md) and [worktree lifecycle](../dotfiles/base/.agents/skills/orchestrate/SKILL.md#worktree-lifecycle). One writer owns shared bridge, policy, state and installer changes. Do not delegate through a modified admission/control path until qualified; use a known-good generation or bootstrap directly. Scratch homes, sessions and fixture repositories live under `.work/`, never the real home.

After each accepted slice, record the product improvement, evidence, remaining blocker and smallest useful next slice. At most two materially different repair attempts precede parking an unchanged failure with its cause and retry condition. An environment blocker parks only its dependent proof; an observed foundational defect blocks dependent implementation. Reuse evidence while its inputs remain valid. Keep Git as the change log and update Status instead of appending checkpoint narratives.

## Binding decisions

1. **Keep the shared bridge.** Retain admission, immutable route snapshots, leases, attempts, scope checks, acceptance-claim parsing, observation, owner journals and failover. The parent independently executes or verifies acceptance proof. Adapters own native execution, decoding, session identity and control; the bridge must not become a model loop.
2. **Preserve current policy.** Resolve `ROOT_PLANS` at admission and retain exact routes/pins in saved state. Only scout, mechanic and worker enter the bridge. Experts are native; top-level Antigravity, Command Code, OpenCode and Devin use native children. Claude Code, Codex and Pi parents use the bridge for lower tiers. Earlier campaign instructions about exclusive bridge experts and an Antigravity bridge adapter are obsolete. The [generated architecture](subagents.md) and typed policy are authoritative.
3. **Preserve external compatibility.** Keep `pi-subagent-bridge`, its MCP registration, `worker_*`, `.work/worker-bridge/`, owner v1, job IDs and receipts. An eventual `fx-subagent-bridge` alias/rename is a separate migration, not a second service or state store.
4. **Extend a small typed boundary.** Separate runtime, provider, model/effort, session and run. Add only the asynchronous admission, events and controls ACP needs. Use explicit wiring and discriminated capabilities, not a universal SDK wrapper or plugin framework. Unsupported operations fail before effects.
5. **Separate outcome and continuation identity.** Preserve a validated session after verified timeout/cancellation/failure without claiming success. Unknown termination, changed pins/worktrees or corrupt state block continuation and replay. Legacy readers do not invent missing budgets/identity or convert Pi sessions into FX sessions.
6. **Use native ACP first.** Keep the CLI pilot as a comparison fixture while qualifying ACP's native coding tools. Unrestricted FX fanout stays denied. Controlled children require the parent-bound controller and group-lifetime gates in Phase 4.
7. **Keep selection experimental.** Use explicit typed policy injection and private fixture state. Installing FX cannot reroute production; do not expose runtime/model overrides on public `worker_start`. Promotion is a distinct evidence-backed decision.
8. **Keep Pi and companions intact.** Core execution, inspection and installation must work without Pi imports, binaries or credentials. Optional Pi routes and historical readers remain supported. Intercom stays coordinator-only; preserve worker environment scrubbing and companion files. Worker retirement and whole-distribution removal are separate milestones.
9. **Preserve account semantics.** No paid-provider substitution, premium-tier change, credential scraping or client impersonation. Matching endpoints/model labels do not prove entitlement. Missing credentials/quota are blocked proof, not permission to buy Gateway access.
10. **Pin executable inputs.** Continue with FX 0.0.17 and verified artifact digests unless a recorded defect requires one explicit replacement release and requalification. Never follow `latest` or development HEAD. Disable upgrades only in private experiment configuration. Optional research MCP uses a pinned closure, with no runtime npm/npx resolution.

A demonstrated ACP limitation permits one bounded investigation of pinned libfx with an executable reproduction. The SDK supplies durable engines and controls, but its native backend requires host-provided coding tools; host callbacks do not automatically equip descendants, and published Linux native addons require glibc. Native-musl CLI proof is not SDK/WASM proof. Do not add Vercel infrastructure, a general coding-tool rewrite, a persistent daemon or two production transports without an accepted concrete need.

## Baseline and ownership

The audit inspected `usr` at `5657b60dc57c2d0e8acd1a50ff99fe8c1d55faaf`. Documentation integration refreshed to `41c91c0fff525226407c7f809015f6a29fc0154f`; intervening commits changed only skill/test guidance, leaving the audited bridge inputs unchanged. Refresh relevant inputs at the next launch.

| Input | Audited version / conclusion |
| --- | --- |
| Selected pi-build | `d2f544fdd3ecc54c3809b02cd4f2fd998a2576d7`, headless-usr |
| Latest pi-build inspected | `235d3be03fc03dec6f217a3d9a2ff71a6f200c98`; unchanged upstream snapshots/headless transformation, mainly packaging/release/test changes |
| Pi and extensions | Pi 1.5.0; pi-subagents 0.87.0; Muse 0.1.0; Devin 0.4.2 |
| FX release | 0.0.17, source `d1d4a883382daf8f2e7447dc361978312cf403d2`; newer development code is not released behavior |
| Proposed research dependency | pi-web-access 0.48.0, source `438e58be6307efb7cd539af3806757abe303aa0c`; standalone MCP needs no Pi runtime |

No release-pin update follows merely from a newer pi-build commit. The [audit baseline](verification/fx-subagent-parity-audit-2026-11-19.md#2-audited-baselines) gives pinned references and the full capability comparison.

| Owned surface | Responsibility |
| --- | --- |
| [FX adapter](../tools/pi-subagent-bridge/src/fx.ts), [process supervisor](../tools/pi-subagent-bridge/src/process-supervisor.ts) | Recover native identity independently of final JSON; support bidirectional ACP under owned-process supervision |
| [Lifecycle](../tools/pi-subagent-bridge/src/hybrid.ts), [session state](../tools/pi-subagent-bridge/src/session.ts), [owner controls](../tools/pi-subagent-bridge/src/owner.ts) | Async admission, actual budgets, correlated receipts and restart reconciliation |
| [Tier policy](../tools/pi-subagent-bridge/src/tier-policy.ts), [route policy](../tools/pi-subagent-bridge/src/policy.ts), [lease](../tools/pi-subagent-bridge/src/worktree-lease.ts) | Exact authority, controlled descendants, group quiescence before lease release |
| [Pi port](../tools/pi-subagent-bridge/src/pi-port.ts), [native delegation](../tools/pi-subagent-bridge/src/native-delegation.ts), [nested guard](../tools/pi-subagent-bridge/src/nested-guard.ts) | Behavioral oracles for continuation, controls and consumed nesting semantics |
| [FX runner](../tools/pi-subagent-bridge/experiment/fx/spike.mjs), [live pilot](../tools/pi-subagent-bridge/experiment/fx/live-pilot.mjs), [scripts](../tools/pi-subagent-bridge/package.json) | Real-binary fixtures, exact live-route comparisons and bounded measurement |
| [Installation](sync.md), [Pi integration](pi.md), [Intercom](intercom-tailnet.md) | Core-only install, pinned optional closures and later companion migration |

Fresh audit tests: 24 FX fixtures passed and both recovery gaps reproduced, using Node 24.22.3 below the declared Node 26 minimum. These are diagnostics, not supported-toolchain acceptance. The no-Pi fixture stopped at owner-socket `listen EPERM`. A checksum-verified Linux x86-64 FX binary initialized ACP and rejected unsupported effort, then returned `-32603 Failed to create session`; the cause is unresolved. Neither result establishes ACP lifecycle or native-Alpine qualification.

## Remaining sequence

Phase 0 precedes Phase 1. Phases 2–4 need the accepted ACP lifecycle, but unavailable live access in Phase 2 need not block deterministic research/child work. Independent platform/provider investigation may proceed without concurrent writers on shared files. A route cannot be promoted before its required gates pass.

The scripts `test:core`, `test:no-pi`, `test:runtime-contract`, `test:fx`, `spike:fx` and `bench:runtime` already exist. Extend them rather than reimplementing completed scaffolding. Run package commands from `tools/pi-subagent-bridge`. ACP/child files and modes below are proposed; document their runnable commands with their implementation.

### Phase 0 — Repair recovery and budgets

**Prerequisite:** supported Node/development tooling; owner-RPC cases additionally require Unix sockets. Unavailable sockets park that proof, not the direct lifecycle/supervisor repairs. **Owns:** FX/lifecycle/session fixtures and associated fixes.

Reproduce deadline and cancellation through the real shared lifecycle and supervisor with deterministic executables. Each leaves valid native identity, yet current resume refuses it. Preserve a validated continuation token independently of successful output after verified termination. Cover nonzero failure, corrupt/missing identity, changed scope/pins and unknown termination; retain attempts, steer budgets and no-replay behavior.

Persist/report effective wall and step limits at admission and observation. Distinguish timeout, step exhaustion/incomplete, cancellation, quota, task failure and unknown termination. Keep 15-minute/20-step pilot defaults separate from the admitted production budget. Missing legacy fields stay unknown.

**Exit evidence:** regressions fail before the fix and pass afterward on supported Node; `npm run test:fx` and targeted session cases pass; production policy output is unchanged. Run affected owner cases where sockets are available and record unavailable proof separately. Land fixes and regressions together. Reverify affected independence contracts rather than restarting completed work.

### Phase 1 — One ACP worker through recovery

**Prerequisite:** Phase 0; resolve or reproduce the released-binary session-creation failure on a supported host. **Owns:** proposed ACP adapter, runtime-control boundary, process supervisor and experiment fixtures.

Run one FX process per worker over stdio ACP. The synchronous FX start interface and final-JSON supervisor cannot support this unchanged. Add async session admission, correlated events, prompt/cancel/load/resume and negotiated steering while retaining shared state, leases and owner receipts. Persist native identity as soon as admission is proven; never use newest-session or `last` discovery.

Use private HOME/configuration, fixed cwd and explicit MCP/tool grants. Validate saved provider/model/effort and controls on every continuation; saved settings can differ from launch overrides. Where possible, advertise only the admitted effort in route-specific metadata, and test retry request bodies. Hooks are observation, not enforcement. Disable helper model work or account for its route and usage.

Client-supplied MCP does not by itself exclude approved project MCP merging. Prove that ambient/project settings cannot widen access; stdio server commands use absolute managed paths. Do not enable full-access to suppress permission prompts: allow required operations explicitly and surface unexpected permission/input requests as blocked.

Preserve pending/delivered/dropped steering states; protocol acceptance is not model absorption. Replay cannot duplicate delivery. Verify cancellation and owned tool-process termination before continuation or lease release.

**Exit evidence:** a real pinned binary with a deterministic local provider completes edits, exact-session correction, cancel/resume, timeout/resume, failed-tool recovery and steering during a tool. Hostile read-only calls, changed pins, ambiguous termination and replay have discriminating outcomes. Extend `test:fx`, the FX runtime-contract selection and local spike runner. An unresolved session-creation error prevents accepting this slice.

### Phase 2 — First live Pi-dependent replacement

**Prerequisite:** Phase 1 and authorized OpenCode Go access. **Owns:** live profile and paired evidence.

Start with `opencode-go/deepseek-v4.1-flash` at high effort. Compare Pi and FX through the same bridge, exact route, instructions and tool permissions: investigation, one-file repair, multi-file change and mandatory correction. Cap the batch at six new admissions and two corrections, with explicit wall/step bounds. Exercise pre-edit quota and post-edit failure separately.

Earlier Go runs proved auth, the session header and quota handling, not inference. The reported reset in roughly 14 days was historical; recheck account access once on the execution host. Park unavailable proof without repeated paid retries. The Codex profile may prove other lifecycle behavior but cannot discharge this Pi-dependent gate.

**Exit evidence:** actual FX inference and same-session correction produce useful work with independent parent checks. Exact model/provider/effort is supported by transport fixtures and available runtime evidence. Separate requested and completing backends; Codex fallback proves orchestration continuity only. Partial edits or uncertain termination never authorize another-model replay.

### Phase 3 — Independent research tools

**Prerequisite:** Phase 1 for worker integration; packaging inspection can begin earlier. **Owns:** optional pinned MCP closure, explicit tool policy and evidence persistence.

Configured scoped Pi workers lack pi-web-access, so this is an explicit addition. Package standalone `pi-web-access-mcp` 0.48.0 through the existing managed dependency mechanism. Grant only `web_search`, `fetch_content`, `get_search_content` and `source_check` to approved roles; no Pi SDK, ambient extensions or runtime package download.

Use worker-private configuration/cache and separate search credentials. Standalone mode lacks Pi-login authentication and several Pi UI/generated-content features; recent-result memory disappears at process exit. Persist URLs, passages, retrieval times, errors and citations, or report expired handles explicitly. Coding subscriptions do not automatically entitle search; FX's Gateway/Exa built-in search does not establish search on custom subscription lanes.

**Exit evidence:** offline tests prove dependency isolation, grants, bounded output, cancellation and restart behavior. An authorized live search/fetch/citation task with usable resumed evidence establishes provider usefulness. Missing access is explicit and cannot silently select another billable model or expose Intercom.

### Phase 4 — Controlled child workers

**Prerequisite:** Phase 1 and root recovery/owner controls. **Owns:** minimal child controller, per-parent MCP, durable group accounting and lease changes.

Replace only the consumed pi-subagents contract: async spawn/status/wait/result, errors/usage, steer/cancel/resume and one nested generation. UI, missions, schedules, memory and generic workflows are outside this use case.

Derive parent identity, cwd, scope, provider policy and depth from trusted admission state. Do not expose unrestricted public `worker_start` to the model. Children use the immutable parent policy and equal-or-weaker typed lattice, including provider exceptions. Reject stronger tiers, alternate providers/models, new workspaces, broader tools/extensions and grandchildren before launch. Bound concurrency, inherited remaining time and work.

Keep children under the root lease with deliberate write coordination. Current release observes root termination; extend it to require every descendant capable of writing to be stopped. Persist child/run IDs and deduplicated spawn/control intents. Unknown spawn cannot authorize duplication. Root cancellation propagates to children and owned tools with verified termination; retained sessions support deliberate correction.

**Exit evidence:** a useful parent/child task passes independent combined-diff checks. Authority overrides fail before launch. Root completion/crash/cancel cannot release a writing group; restart/replay have one effect; no descendant escapes scope/accounting. These are authority and lifecycle controls, not an OS sandbox.

### Phase 5 — Remaining routes, platforms and long sessions

**Prerequisite:** accepted lifecycle plus each route's required capabilities. **Owns:** transport tests, platform pins/install and context-pressure qualification.

Qualify Contributor Spark scout/medium and mechanic/high separately from DeepSeek. Muse requires authenticated SDK/`muse serve` subscription transport, parked tool calls, context/prefix handling, fork/continuation and cancellation. Devin SWE-2 Flash medium requires CLI auth/catalog, variant mapping, reasoning replay and tool-result/error semantics. Native CLI/ACP custom protocols and headers do not automatically replace either adapter. Extract necessary transport behavior or qualify a native executor; retain Pi until an equivalent passes or the owner explicitly retires that route.

Qualify macOS ARM64, Linux x86-64 musl and Linux ARM64 musl with verified artifacts. Version output/ACP handshake on this audit host does not prove a native Alpine lifecycle. Test long context/compaction, restoration, auth refresh, research restart and descendant cleanup.

**Exit evidence:** every retained Pi-dependent route has a useful equivalent at its exact effort; each claimed platform passes lifecycle/install gates. A clean installation runs the required matrix with Pi imports/spawns/credentials trapped. Skipped core cases are not no-Pi proof. External consumers require their own available authorized environments.

### Phase 6 — Measure, decide and retire dependencies

**Prerequisite:** required route/capability/platform cells for the intended rollout. **Owns:** matched measurement, promotion proposal, rollback and eventual packaging changes.

Measure accepted tasks through the same bridge with matched model/effort/tools and interleaved runs. Record cold/warm overhead, accepted-task time, full process-tree peak memory, installed bytes, usage, failure rates and recovery. Include Node, tools and research/child sidecars. Unknown usage stays unknown. A native binary size versus a compressed Pi archive proves no resource advantage.

Recommend one-route-at-a-time promotion with rollback to the retained adapter. Remove Pi execution dependencies only when required lanes are replaced or explicitly retired. Migrate Intercom/other distribution consumers separately before uninstalling the distribution. Historical Pi sessions remain inspectable under their original identity.

**Exit evidence:** the intended no-Pi setup is useful, recoverable and compatible with real consumers; measured benefit justifies maintenance. Promotion/removal follow an accepted decision, not a handshake or executable rename.

## Acceptance matrix

Extend existing behavior tests. Separate source support, fake-process proof, real-binary deterministic proof and live intended-provider proof.

| Contract | Required evidence |
| --- | --- |
| Admission/completion | Admitted is not complete; early output cannot hide a live process. Malformed, oversized, truncated or mismatched output never becomes success. |
| Ownership/replay | Reject stale generations/targets. Command IDs have one effect. Crash between intent and receipt stays uncertain; never cancel a reused PID. |
| Leases/descendants | Concurrent roots admit at most one writer per worktree. Unknown/writing descendants retain protection after root completion. Cancellation acknowledgement is insufficient. |
| Scope/acceptance | Preserve clean linked-worktree/base-HEAD checks; detect tracked, untracked, deleted, out-of-scope and HEAD-changing effects. Parent proof is independent; Git checks are not containment. |
| State/budgets | Legacy sessions stay readable; new records persist exact pins and effective bounds. Missing data stays unknown. No silent route/runtime conversion. |
| Continuation/steering | Exact session/worktree/pins, no overlapping turns or scope expansion, preserved attempt/steer accounting and truthful delivery states. |
| Failover | Only approved pre-edit provider-unavailability with verified termination advances along the admitted snapshot; task failure, partial writes and uncertainty do not. |
| Observation | Inspection/watch/campaign and owner reads do not start providers or mutate leases. Missing adapters do not break other history; retain explicit status advancement. |
| Independence | Core installation/public dispatch/non-Pi lifecycle use no Pi. Optional Pi qualification remains usable. Optional MCP closures are pinned without runtime dependency resolution. |
| FX isolation | Verify effective model/provider/effort, retries, saved settings and MCP/tool grants. No ambient widening, coordinator credentials or unrestricted fanout. |
| Read-only work | Attempt alternate writes/shell escapes in disposable fixtures. Distinguish prevention from detection; admit a tier only when required controls hold. |
| Interruption | Stop before response, during a write and after a write before persistence. Preserve identity and partial effects without duplicate work. |
| Consumers/platforms | Preserve CLI/MCP/owner v1 receipts, foreign registrations and companions. Agentctl/Intercom and each native platform have distinct evidence. |

## Blocked proof and retry conditions

| Gate | Current evidence / retry condition |
| --- | --- |
| Supported contracts | Audit used Node 24; rerun affected fixtures on Node 26 with development tools. Reproduce the no-Pi owner case where Unix sockets are permitted. |
| ACP execution | Resolved on macOS ARM64: `-32603` comes from the `--provider` override; select the provider through private settings. Linux ACP still needs native execution proof. |
| Live account/model | Historical Go quota and absent FX-owned Codex login blocked inference. Recheck the selected authorized account once; use the printed login handoff if needed, never unrelated client credentials. |
| Native platforms | Retain historical macOS CLI evidence; new ACP and each Linux musl architecture need native execution/install proof. |
| External consumers | Agentctl/Intercom peers were not exercised in this audit. Preserve local receipt/environment-scrubbing fixtures; integration needs the relevant checkout/authorized host. |
| Provider retirement | Go Spark, Muse and Devin equivalents remain unqualified. DeepSeek/Codex success cannot clear them. |

Update a gate with exact revision, command, result and remaining limit. Do not repeat unchanged failures or broaden unrelated suites. Follow [development checks](development.md) and the affected contract tests.

## Verdict and stop conditions

**Current verdict: limited-go for the next bounded experiment; no Pi replacement claim.** Runtime independence and historical CLI qualification retain value. ACP is the recommended next transport, with a real session-creation blocker still to resolve.

A **go** recommendation requires lifecycle, isolation, exact-route task quality and platform evidence for its scope. A **limited-go** names excluded routes/capabilities/platforms. A **no-go** records the concrete defect or unacceptable implementation cost and preserves the neutral core and reproduction. Stop expanding the project merely to make FX win.

Provider economics, native harness policy, Intercom enrollment and real-home configuration remain outside this documentation change. Whole-distribution removal, broad renaming and deployment are distinct migrations. Use the [dated audit](verification/fx-subagent-parity-audit-2026-11-19.md), [bridge contract](../tools/pi-subagent-bridge/README.md) and pinned source when upstream behavior is uncertain.
