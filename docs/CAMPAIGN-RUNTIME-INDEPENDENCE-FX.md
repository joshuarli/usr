# Runtime-independent worker bridge, then an FX spike

## Status

- **Goal:** make usr's worker orchestration independent of Pi, then establish whether a pinned FX runtime can replace a useful execution lane without weakening its contracts.
- **State:** FX spike implemented and locally qualified on macOS ARM64; the live pilot path is implemented and was executed against real accounts. Verdict: **limited-go for deterministic qualification only**. Live model usefulness and Pi-route replacement remain unproven behind reproduced account blockers. No production promotion, Pi removal or remote update.
- **Accepted implementation:** runtime independence through `2025e04`; FX CLI/bridge qualification `91642ad`; cancellation identity guard `6dd9583`; unavailable-control guard `c6f94ad`; qualification evidence through `d986a7f`; credential-safe live provisioning `c19b2f3`; opt-in live pilot runner `cdda03b`; pilot bounds/contract fixes `12df815`.
- **Evidence:** pinned real FX 0.0.17 and matching source; real tools and exact-session continuation; hostile read-only/fanout/MCP probes; interruption before response, during a tool and after a write; shared owner correction, steering, replay and interruption; unchanged production policy JSON; live pilot reached the real OpenCode Go endpoint through the bridge with credentials confined to 0600 secret files. See [spike verification](verification/runtime-independence-fx.md).
- **Compatibility:** production routes and schema-2 writes remain unchanged. Experimental leaf records use schema 3 with explicit version-1/2 readers. No production npm dependency was added.
- **External gates:** live account/model qualification is parked on two reproduced blockers: no FX-owned Codex login (`fx login codex` handoff printed by `--live codex`) and an exhausted OpenCode Go monthly quota (provider reports reset in ~14 days; the incumbent Pi CLI fails identically). Native musl hosts, real agentctl/Intercom peers, production resource/task quality and one qualified Pi-dependent route remain unqualified.
- **Next:** rerun `npm run spike:fx -- --live codex` after the printed login, or `npm run spike:fx -- --live opencode-go` after the quota reset, then qualify one existing Pi-dependent route through FX. No SDK rewrite or rollout follows from the current evidence.

## Charter

The order is binding: **runtime independence -> existing-backend parity -> no-Pi installation/execution proof -> FX protocol pilot -> FX integration and qualification**. A generic interface or a renamed directory is not runtime independence. FX is a test of the boundary, not the new foundation of usr.

This document's creation authorizes no implementation. On a separate launch, work in `joshuarli/usr`, make focused verified commits, and follow the launch's explicit push grant. Without one, keep implementation commits local; do not infer permission to publish, deploy, alter the real home directory or modify other repositories. The planning request authorized committing the campaign only. Later owner launches authorized runtime independence and then this isolated FX spike. Neither launch grants production promotion or a push.

Use the existing [campaign mechanics](../dotfiles/base/.agents/skills/orchestrate/references/campaigns.md) and [worktree lifecycle](../dotfiles/base/.agents/skills/orchestrate/SKILL.md#worktree-lifecycle). One writer owns shared bridge, policy, state and installer changes. Do not delegate through the modified bridge while its admission/control path is unqualified. Use a separate known-good installed generation or do the bootstrap directly. Scratch homes, sessions, fixture repositories and worktrees live under `.work/`, never the real home or `/tmp`.

After each accepted slice, perform the parent steering checkpoint: identify the product improvement, its evidence, the next blocked invariant and the smallest useful next slice. At most two materially different repair attempts per failing slice before parking it with the cause and retry condition. Never spin on an unchanged failure. An environment blocker parks only its dependent proof; a broken foundational contract blocks dependent implementation. No formatters, CI changes, new daemon, cloud deployment, dashboard redesign or unrelated cleanup.

## Binding decisions

### Owner-decided

1. Runtime independence comes first; FX is a subsequent spike, not an immediate Pi replacement.
2. The work belongs in usr. The later owner launches authorize executing runtime independence and the isolated FX spike.

### Prescribed

1. **Keep the orchestrator.** Retain scoped admission, exact route snapshots, worktree leases, attempts/continuations, ownership, acceptance checks, campaign observation and MCP/CLI in usr. Adapters own runtime-specific execution, native IDs, event decoding, provider preflight and continuation semantics. Do not reimplement a model loop in the bridge.
2. **Preserve defaults.** Read `ROOT_PLANS` at execution start; retain its exact model/provider/effort pins, route order, terminal expert behavior and OpenCode exception. Do not copy a historical routing table into new code. A missing optional adapter is observable unavailability, not permission to change the approved plan.
3. **Preserve external names for this campaign.** Keep `pi-subagent-bridge`, its MCP registration, `worker_*`, `.work/worker-bridge/`, owner protocol v1, job IDs and existing command receipts compatible. Internals can become neutral in place. A cosmetic public rename or state-directory move is a separate migration, not an independence gate.
4. **Use a small typed boundary.** Separate executor/runtime, provider, model/effort, session identity and run identity. Use a closed discriminated union plus explicit adapter wiring, not a dynamically loaded plugin marketplace, service locator or universal SDK wrapper. Validate untrusted adapter data once; do not export `unknown`-shaped OpenCode responses as the domain model.
5. **Declare differences rather than flattening them.** Capabilities distinguish live steering, interrupt-and-resume steering and unsupported steering; resumption requirements; native nesting; and tool-level read-only controls versus after-the-fact Git checks. An unsupported operation must fail before effects. Never label a restart as live steering or Git checks as an OS sandbox.
6. **Pi remains a supported optional adapter.** Keep its native nesting ceilings, provider extensions, offline behavior and historical-session readers. Shared policy may describe Pi routes as data; core execution, inspection, installation and core tests must not load Pi packages or acquire Pi credentials to run another adapter.
7. **Intercom stays separate.** Preserve coordinator-only messaging, companion installations and worker environment scrubbing. Do not delete pi-build or its Intercom artifacts. Removing the entire Pi distribution requires a later packaging migration; running the worker bridge without Pi must not silently uninstall unrelated companions.
8. **FX starts as a CLI leaf.** Prefer a pinned `fx ask --json` subprocess adapter in a parent-owned worktree. Disable native fanout through a proven capability/tool boundary, not just a prompt. The first spike does not port Pi nesting or claim its parity.
9. **No production promotion.** FX is selected only in a checked-in experimental qualification entrypoint using explicit typed policy injection and private fixture state. Installing FX alone must never alter production routing. Do not add an arbitrary runtime/model override to `worker_start`.
10. **No paid-provider substitution.** Existing approved subscription/account routes may be exercised only under the later execution grant. Do not purchase credits, add Gateway billing, turn on premium speed tiers, scrape unrelated credentials or impersonate official clients. Endpoint compatibility does not prove subscription entitlement.

### Delegated within bounds

Choose internal module names and the minimum adapter operations from existing callers. Keep admission and state transitions under one owner; keep CLI/MCP consumers on one implementation. Preserve the serialized schema where practical. A necessary schema revision needs explicit legacy decoders and fixtures, not a bulk migration or reinterpretation using today's policy. Resume tokens are opaque, runtime-tagged and bound to the recorded worktree; they are not interchangeable session IDs.

Start the FX pilot against documented `0.0.17`, but verify the release, binary version, platform artifact and source before use. If it cannot be obtained, record one exact replacement release and requalify its contracts; never follow `latest` or `dev` during the experiment. Use existing installation/pinning machinery rather than creating fx-build. Disable automatic upgrades only inside the experiment's private configuration.

A CLI protocol gap permits one bounded investigation of the pinned libfx API, with one executable minimal reproduction of the missing capability. It does not authorize replacing the bridge with libfx, adding Vercel infrastructure, or building a new coding-tool suite. If resolving the gap requires those, finish with no-go and the concrete blocker. No speculative second adapter before an observed CLI limitation.

## Baseline and source map

At the survey revision, `package.json` declares four production dependencies: Pi coding-agent, pi-subagents, yaml and pi-muse-subscription. `dev-install.sh` combines production and development dependencies, so even developer installation currently pulls the Pi set. `tools/sync/pi-worker.py` links the bridge to the installed Pi closure. These are independent coupling points; lazy-importing one SDK is insufficient.

| Existing surface | Verified coupling / responsibility | Treatment |
| --- | --- | --- |
| `tools/pi-subagent-bridge/src/bridge.ts` | `OpenCodePort`, `ModelRef`, response unboxing and ownership checks | Extract neutral contracts; keep backend wire decoding in the adapter. |
| `src/server.ts`, `src/cli.ts` under that directory | `connect()` and inspection composition construct `piPort()` | Select/load only the adapter needed; preserve public dispatch. |
| `src/hybrid.ts`, `src/policy.ts`, `src/session.ts` | Root plans, Pi/process branches, transitions and admitted snapshots | Reuse state machine and policy; separate backend-specific operations without changing semantics. |
| `src/pi-port.ts`, `src/sdk-worker.ts`, `src/native-delegation.ts`, `src/nested-guard.ts` | Pi SDK host, native RPC, detached children and nesting restrictions | Keep behind the Pi boundary, with provider extensions and guards. |
| `src/codex.ts`, `src/command.ts`, `src/antigravity.ts`, `src/launch.ts` | Existing subprocess executors and launch selection | Adapt these first; do not rewrite their proven protocol handling. |
| `src/inspect.ts`, `src/owner.ts`, `src/worktree-lease.ts`, `src/worker-env.ts` | Observation, owner receipts, leases and coordinator credential exclusion | Preserve behavior and verify through real public entrypoints. |
| `tools/sync/pi-worker.py`, `tools/pi/test_sync_bridge_offline.py`, `tools/pi/test_offline.py` | Pi closure installation and offline consumer checks | Separate core install/development dependencies from optional runtime qualification. |
| `tools/policy/generate.ts`, `dotfiles/orchestrate-test.py` | Generated policy and harness contract checks | Keep one source of truth; regenerate, never hand-edit projections. |
| `docs/intercom-tailnet.md`, `docs/pi.md` | Coordinator packaging and operator semantics | Preserve; document independence without claiming Intercom has migrated. |

Paths beginning `src/` above are relative to `tools/pi-subagent-bridge/`. Recheck symbols and callers at HEAD; this map is not a mandate to retain obsolete code. Use `git grep` to locate all imports, installer prerequisites and agentctl-facing protocol consumers before moving a boundary.

**Measured execution baseline:** none in this planning session. No fixture suite, live provider, musl binary or FX worker was executed. Startup/RSS and loop timings are unknown. RI-0 must establish them on the executor host; source inspection is not a passing runtime gate. Consult [development checks](development.md) for supported Node/tooling and expected skips. Do not carry earlier campaigns' reported failures forward without reproducing them.

## Sequence

All items below run serially because they share contracts or depend on acceptance. Each item owns its named surfaces plus directly affected tests. Split an item into smaller end-to-end commits when necessary; do not interleave writers in the same state/adapter/installer files.

The new `test:runtime-contract`, `test:no-pi`, `test:fx`, `spike:fx` and `bench:runtime` package scripts below are **deliverables to implement**, not existing commands. Define them in `tools/pi-subagent-bridge/package.json`, document their exact behavior, and keep fixture commands offline by default. They must run actual bridge entrypoints and owned child processes where lifecycle behavior is at issue, not only assert exported types or grep source text.

### RI-0 — Ground and one discriminating test (S)

**Prerequisite:** none. **Owns:** baseline evidence in this document; the smallest new contract fixture under the bridge's existing `test/` directory.

Record the execution revision, clean/dirty state, supported toolchain, available platform and whether optional runtimes are installed. Time the narrow baseline bridge tests and policy-generation check, recording exit codes and skips separately. Reproduce known red before assigning it to this work. Use a disposable checkout for tests that manipulate the runtime symlink; do not run home sync.

Build one substantive failing test: with Pi packages unavailable and Pi paths/credentials trapped, start a non-Pi worker through the public bridge in a clean linked fixture worktree, observe its result, resume it and exercise owner control. The executor may be a deterministic fake CLI initially; the bridge, persistence, leases and IPC must be real. A missing installed CLI is a separate unavailable route, not permission to skip the case. Start with this pilot, not a general evaluator project.

**Proof:** record baseline `(cd tools/pi-subagent-bridge && npm test)` and `node tools/policy/generate.ts --check`; run the new focused boundary test and record its specific failure. A failing test may exist on the work branch but must land together with its fix in RI-1. No fake-CLI result is described as live provider proof.

### RI-1 — Neutral boundary with a non-Pi vertical slice (M)

**Prerequisite:** RI-0. **Owns:** bridge contracts, composition roots, one existing subprocess adapter and its tests.

Route the Codex path through the small typed boundary. Make the RI-0 test pass from MCP/CLI admission through persisted inspection and a controlled continuation, including meaningful failure behavior. Domain types must not import Pi SDK types. Load optional adapters on selection, not simply when the server starts or a campaign is listed. Inject dependencies using explicit constructors/factories already justified by tests; do not introduce global mutable runtime selection.

**Proof:** `(cd tools/pi-subagent-bridge && npm run test:runtime-contract -- --adapter codex)` passes; targeted server/CLI/owner tests pass. Deliberately break the adapter result/session association once and confirm the test rejects it, then restore the implementation. This gate must prove an observable contract, not merely instantiate an interface.

### RI-2 — Existing-adapter and durable-state parity (M)

**Prerequisite:** RI-1. **Owns:** remaining adapters, policy/session/inspection/owner integration and associated fixtures.

Move Command Code, Antigravity and Pi behind the same boundary without merging their native semantics. Remove provider-shaped response interpretation from the shared lifecycle path. Preserve current production plan output, exclusive expert routing, scope/attempt/continuation/steer budgets and allowed Pi nesting. Keep direct OpenCode harness routing outside this bridge.

Golden fixtures cover supported historical session versions and plans, including interrupted transitions, retired pins and unresolved legacy destinations. They must stay readable or fail with the existing actionable reconciliation boundary, never be silently rerouted. Missing Pi must not crash observation of other jobs or discard Pi records. Preserve known on-disk evidence; report genuinely uninspectable live adapter state as unknown, not succeeded or failed.

**Proof:** `npm run test:runtime-contract` and `npm test` in the bridge directory; `node tools/policy/generate.ts --check`, `node --test tools/policy/generate.test.ts`, and `python3 -I dotfiles/orchestrate-test.py` from the repository root. Capture production-policy JSON before and after and require semantic equality. Run the real pinned Pi offline protocol checks on an available supported runtime; inability to run them is an explicit compatibility gap, not a passing Pi gate.

### RI-3 — Prove runtime independence, including installation (M)

**Prerequisite:** RI-2. **Owns:** bridge dependency/build wiring, sync bridge registration/install path, documentation and install tests.

A core-only install/development path must work without pi-build artifacts. Separate optional Pi SDK/extension dependencies and typechecking from core dependencies; keep Pi qualification available as a separate explicit suite. Existing full installations and the selected Pi release must remain intact. Do not use npm at production runtime or introduce an unpinned download to replace the existing closure. Reuse the repository's reviewed dependency mechanism for anything the neutral core genuinely needs.

In a disposable checkout and scratch home, physically omit Pi packages, binaries, runtime symlinks, `~/.pi`, provider caches and credentials. Trap attempts to resolve/import Pi packages, spawn Pi/npm/npx during runtime, fetch Pi releases or read Pi credentials. Exercise core installation and the real MCP/CLI paths: policy, model check, start/status/resume/steer/cancel, inspect/watch/campaign and owner RPC against deterministic non-Pi executors. Probe approved optional routes without discovering unrelated credentials or starting them. Preserve foreign MCP registrations and existing companion files.

**Proof:** `(cd tools/pi-subagent-bridge && npm run test:no-pi)` passes with zero trapped accesses and zero skipped core cases. Run affected scratch-home sync/registration tests listed in development.md. Reinstall the Pi adapter in a separate fixture and pass its contract/offline qualification. **Milestone A:** all available existing-backend contract gates pass and core operation is demonstrably Pi-free. Do not implement the FX adapter before this milestone. Unavailable host/account/Pi-runtime proof goes to Needs environment: it prevents a full-parity or production-readiness claim, but does not block the isolated FX experiment after the local gates pass. An observed regression is not an environment exemption.

### FX-0 — Pin and test the real CLI protocol (S/M)

**Prerequisite:** Milestone A. **Owns:** experimental runner, pinned FX fixture setup and protocol evidence; no production routing changes.

Read the candidate binary's help, matching source and current primary docs. Verify provider/model/effort selection, saved session identity, noninteractive permissions, tool/profile controls, cancellation and exit/result shape. Establish private configuration and state directories using supported mechanisms, not guessed environment variables. No package may auto-update or inherit an unrelated coordinator MCP configuration.

Use the actual pinned binary with a loopback-only deterministic provider fixture where the supported custom connection permits it. Make it read a fixture file, change one allowed file, invoke a passing check and continue the same saved session. Fake stdout transcripts alone do not qualify the real CLI. Fix the fixture at the protocol boundary if it exposes a real integration mismatch; do not invent successful provider/tool events.

**Proof:** `(cd tools/pi-subagent-bridge && npm run spike:fx -- --local-protocol)` produces observed binary identity, arguments/settings with secrets removed, session/run correlation, tool results and exit evidence. A protocol failure has an executable reproduction. The binary passing `--version` or producing assistant text is insufficient. Record leaf/read-only/steering capability results before proceeding.

### FX-1 — Add the opt-in FX executor (M)

**Prerequisite:** FX-0's required protocol capabilities proven. **Owns:** FX adapter, adapter registration/typed selection, experiment runner and FX contract fixtures.

Use the same scope, lease, command-dispatch, owner and observation machinery as existing executors. The experimental runner injects an explicit FX-only route for the chosen test tier; it must not consult a mutable production default or add FX to `ROOT_PLANS`. The public worker request schema stays unchanged. A small registry/selection-union addition is expected; a new orchestration state machine or FX branches throughout campaign/owner code means the runtime boundary failed and must be repaired first.

Record process identity before trusting termination. Persist admission intent before dispatch and the bound native session identity as soon as supported evidence establishes it. Never use `--resume last`, choose the newest ambient session or scrape a TUI. If identity cannot be recovered unambiguously after a crash, mark the run unknown and retain its lease; do not start a duplicate or synthesize a result.

Use bounded process supervision, bounded log/result sizes and actual exit evidence. Qualifier jobs have a 15-minute wall limit and a 20-model-step limit where the pinned runtime supports it; a shell-command timeout is not a whole-run budget. Stop owned processes on exceeded budgets, preserve evidence and distinguish interruption from successful completion. If needed, implement the deadline in the existing subprocess supervisor, not by relying on an invented FX flag.

Same-session correction and interrupt/resume steering require a proven terminal prior run and the bound session ID. If only that steering mode works, expose it honestly. Live steering is not mandatory for a limited-go CLI result; unsafe or ambiguous resume is a blocker. Test all required restrictions against project configuration overrides and hostile instructions rather than trusting the profile name.

**Proof:** `(cd tools/pi-subagent-bridge && npm run test:fx)` plus `npm run test:runtime-contract -- --adapter fx`; rerun `npm run test:no-pi`. The real-binary local protocol pilot must now run through the experimental entrypoint and shared bridge, not around it.

### FX-2 — Qualify realistic behavior and resource cost (M)

**Prerequisite:** FX-1. **Owns:** executable qualification corpus and one concise result document, proposed `docs/verification/runtime-independence-fx.md`.

Run the acceptance matrix below. Add two small, reproducible end-to-end workloads in disposable fixture repositories: a read-only scout that locates a real behavioral issue with file/line evidence, and a one-file bug fix with a failing-then-passing acceptance test and same-session correction. Require independent parent verification of the diff and test output. Do not benchmark only greetings, `--help` or empty sessions.

Where a permitted account is already available, compare the incumbent and FX using the same supported exact model/provider/effort, instructions, tools needed and workload. Do not equate matching model labels across different endpoints with equal billing or entitlement. Cap the live batch at six new admitted jobs and two same-scope corrections total; each is bounded as above. No automatic retries for missing quota/credentials, and no fallback into metered Gateway. Missing access parks live proof while deterministic work continues.

Measure cold/warm launch overhead, idle and peak RSS, installed dependency footprint, end-to-end accepted-task duration, reported tokens/usage and recovery results. Measure harness overhead separately with deterministic local provider responses. Run timing checks only around a passing `perf-gate-ready`/`perf-gate-ready -1` window; interleave baseline/candidate runs, report medians and spread, and discard contaminated timing runs. Missing usage is unknown, not zero. No speedup claim from binary size or different models. Optimization follows parity and is limited to regressions caused by this work.

**Proof:** `npm run spike:fx -- --local` is credential-free and repeatable; `npm run spike:fx -- --live` requires explicit opt-in and prints its bounded scope before starting. `npm run bench:runtime` produces comparable measurements or an explicit busy-host deferral. Run these from the bridge directory. Live, macOS and musl results are reported separately.

### CLOSE — Review and stop (S)

**Prerequisite:** all unblocked slices accepted; blocked proof classified. **Owns:** narrow cleanup, final evidence and this Status block.

Run the focused ultrareview of changed boundaries; fix P1/P2 defects introduced by this work. Delete superseded internal glue only after caller and parity proof, not useful optional adapters. Rerun the full bridge suite, runtime-contract/no-Pi/FX fixtures, policy generation and affected installer checks at this final milestone. Do not run unrelated repository-wide suites.

Close with accepted commit IDs, exact commands/results/skips, supported capabilities, provider/account compatibility, measured costs, missing environment proof and one verdict below. Keep Git as the change log; rewrite Status instead of appending checkpoint narratives. Stop without removing Pi, promoting FX or starting an SDK rewrite.

## Acceptance matrix

Each row must have at least one behaviorally discriminating fixture. Existing tests should be extended instead of duplicated. Production invariants do not become optional merely because FX lacks a feature.

| Contract | Required evidence / rejection behavior |
| --- | --- |
| Admission and terminal evidence | Admitted is not complete; a live process remains running despite an early receipt; exit zero without acceptable final proof is incomplete. Malformed, truncated, oversized or mismatched results never become success. |
| Ownership and replay | A stale owner generation/run target is rejected. Repeating a command ID causes no second effect. Crash after intent but before receipt stays uncertain; no blind replay, backend switch or cancellation of a reused PID. |
| Concurrency and leases | Two concurrent starts for one worktree admit at most one. Unknown or possibly writing runs retain protection. No released lease while an owned child can still mutate the worktree. Cancellation acknowledgement alone proves nothing. |
| Scope and verification | Clean linked worktree and exact base HEAD required. Detect tracked, untracked, deleted, out-of-scope and HEAD-changing edits. Preserve existing ignored-file/host-access limitations rather than calling them containment. Parent independently verifies acceptance. |
| Saved state | Legacy records retain admitted pins, budgets and identity. Current policy changes cannot reroute them. Unknown adapter versions or missing native identity fail explicitly without rewriting history. |
| Continuation and steering | Same session, unchanged scope and correct budget accounting; supported live versus interrupt/resume behavior distinguished. No overlapping continuation, `last` shortcut or scope expansion. Unsupported operations fail before effects. |
| Fallback | Only the existing approved pre-edit, unambiguously terminated provider-unavailability cases switch routes. Task failure, partial edits, uncertain admission or missing receipts do not. Expert remains exclusive. |
| Observation | Inspect/watch/campaign and owner read methods neither start providers nor mutate job/lease state; missing optional adapters do not prevent other jobs being inspected. Preserve the existing explicit status-advancement boundary. |
| Runtime independence | Real core installation, startup, public dispatch and non-Pi lifecycle pass with zero Pi package/credential/runtime access; optional Pi qualification still works when installed. No new production npm/network dependency. |
| FX isolation | Exact provider/model/effort and saved identity established; project config cannot widen tools/routes. Native fanout, bridge recursion and coordinator Intercom capabilities are disabled. No auto-upgrade or ambient MCP inheritance. |
| Read-only capability | Intentionally attempt file edits, shell escape paths and alternate write tools in the disposable scout fixture. Record prevention versus post-run detection accurately. FX cannot be admitted to a tier whose required control it cannot enforce. |
| Interruption and retry | Stop before first provider response, during a tool write and after a write before result persistence. Bound retries/wall time, establish child termination and retain ambiguous state without duplicate paid work. |
| Consumer compatibility | Existing CLI/MCP schemas and owner v1 client fixtures remain compatible. Agentctl job/control receipts are unchanged; a real agentctl integration test is separate proof, not inferred from compilation. |
| Installation and platform | Scratch-home install is repeatable; foreign registrations/companions survive; exact pins and rollback work. macOS ARM64 and each Linux musl architecture have distinct real-binary results. A glibc or WASM success is not native-musl proof. |

## Needs environment

Record unavailable proofs here during execution with their exact rerun command and prerequisite. Initially all execution results are pending, not failures.

- **Supported Node/development tooling and pinned Pi runtime:** run RI-0 through RI-3 plus the offline tests from development.md on a disposable checkout. A suite skipping SDK cases because Node/runtime is missing does not prove adapter parity.
- **Real FX binary and local protocol support:** `npm run spike:fx -- --local-protocol`. If the pinned binary cannot express a locked-down local provider/tool setup, retain the reproduction and classify the capability gap; fake executables do not clear it.
- **Existing authorized account:** executed once via `npm run spike:fx -- --live opencode-go` (report `.work/tmp/fx-live.json`). FX reached the real provider but retried `429 GoUsageLimitError` until each 15-minute deadline; the incumbent Pi CLI on the same account failed in ~1 s with the identical quota error (monthly limit, provider-stated reset ~14 days). Rerun `npm run spike:fx -- --live opencode-go` after the reset. For the subscription route, run the printed `FX_HOME=<profile> fx login codex` handoff, then `npm run spike:fx -- --live codex`. Do not prompt for, print, copy into evidence or commit credentials. Absent auth/entitlement is a parked live gate, not authorization to change providers.
- **Native hosts:** run the fixture and real-binary qualification commands on macOS ARM64, Linux x86-64 musl and Linux ARM64 musl when available. Do not broaden to emulation or glibc-only shipping. Unavailable Linux proof need not prevent a macOS-only spike verdict; it blocks fleet-wide replacement claims.
- **Agentctl and Intercom peers:** run existing integration/companion tests when their checkouts and authorized hosts are available. Do not mutate those repositories or real tailnet infrastructure under this campaign. Preserve worker credential-scrubbing tests locally regardless.

## Verdict and execution boundary

**Runtime-independence success:** the core works without Pi, existing adapters preserve their tested contracts and production routing, and the shared bridge does not acquire FX coupling. This is valuable even if FX is rejected.

**FX go:** the pinned candidate passes required lifecycle/isolation/control and intended-tier workloads on the reported platform and authorized provider. It is a recommendation for a separately approved rollout, not a rollout itself.

**FX limited-go:** useful, verified capabilities have explicit limits, such as macOS only, worker only, no native nesting, interrupt/resume instead of live steering, or deterministic transport proof without live account qualification. Name which production use remains prohibited. In particular, fixture-only proof is not unattended production readiness.

**FX no-go:** an observed protocol, scope, provider-entitlement, identity, recovery or platform gap prevents safe intended use within this spike's bounds. Preserve the independent core, tests and minimal reproduction; do not invent parity or keep expanding the project until FX wins.

No change to production route selection, model entitlement, fallback economics, owner authorization, Intercom enrollment or native Pi nesting is granted. No Pi uninstall, pi-build archival/deletion, companion repackaging, session deletion, broad renaming, new service/queue, Vercel deployment or SDK/tool-suite rewrite. Newly necessary effects outside this boundary are parked, not silently performed. The eventual removal of Pi, including its packaging tie to Intercom, requires a separate accepted decision and migration.

## Primary references and version-sensitive pitfalls

Recheck these against the pinned binary/source at FX-0:

- [FX noninteractive execution](https://fx.sh/docs/using-fx/fx-ask): JSON is a final object, not an event stream; interrupted requests can exit without that result. The documented shell timeout does not bound a complete agent job, and transient retries can continue indefinitely. Use exact session IDs for continuation. Main-agent usage does not cover every helper/subagent cost.
- [FX stability](https://fx.sh/docs/stability): the 0.0.x CLI, saved formats and library API are experimental; automatic upgrades and permissive default tools require deliberate isolation.
- [FX subagents](https://fx.sh/docs/capabilities/subagents): native agents share the workspace. Their existence does not supply usr's cross-harness ownership, admission or scoped tier policy.
- [libfx overview](https://fx.sh/docs/lib) and [API](https://fx.sh/docs/lib/api): the documented guide currently targets 0.0.17. The host supplies tools. Verify actual session/engine methods; do not assume a `session.resume()` method or a public Pi-equivalent subagent RPC. Durable checkpoint recovery is not proof that external filesystem effects execute exactly once.
- [Current bridge contract](../tools/pi-subagent-bridge/README.md), [Pi integration](pi.md), [Intercom boundary](intercom-tailnet.md) and [development checks](development.md) are the behavior baseline, reconciled with source at execution HEAD.
