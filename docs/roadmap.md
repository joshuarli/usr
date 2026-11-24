# Roadmap

This is the single plan for this repository: all current and future work, and the handoff for resuming it. Campaigns are sections below, and their items interleave in **Sequence**. "Resume the roadmap" means continue from **Status**.

## Status

- **State:** idle. No campaign is active and no slice is in progress.
- **Pi build:** released and cut over; remaining proof is parked (see its State). Headless follow-ups live in `pi-build` as PIB-1..5.
- **Runtime-independent bridge and FX:** shelved by owner decision 2026-11-19 (Pi stays). Remaining work is USR-87..93.
- **Next slice:** none ready. New work enters **Sequence** only through `campaign-plan` and `campaign-preflight`, starting from a **Later** entry or a new goal.

## Charter

Each campaign follows the charter in `campaign-preflight`'s final shape. A campaign's own authority section states its departures and wins where it is narrower.

## Sequence

None ready.

## Campaign: Pi build

### State

- **Goal:** move Pi producer inputs and archives to `pi-build`, preserve full runtime behavior through pinned releases, then deliver explicit `headless-usr` selection.
- **Accepted:** `usr` `cc4963d` (USR-39), `2639eef` (USR-41), `8101cc4` (USR-45), `366fca1` (USR-42/46), `ed3efa0` (supported developer test loader), `f8f99c3` (USR-40/44), `f90d6be` (proven pre-admission model-loss race), `292eaa4` (staged consumer), `f1fd64c` (extracted SDK/broker protocol probes), `1e8b38f` (probe intercom shutdown), `a70a142` (full-profile cutover: sync consumes the pin; vendored tree and old workflows retired), `a227122`/`91bf143`/`50891ba` (cold-cache, macOS path and pinned-Node CI fixes). `pi-build` `9dd4c4c` (preserved sources and old archives), `46885cc` (locked darwin builder), `32694f0`..`db041e6` (pinned toolchain, native Linux locks, CI build/musl/release workflow, provenance merge).
- **Re-released:** the pin now names `pi-build` `release-a17c28f2ebaaac32e8cd1dfb66baa4c1d725a800` (shared build-repository format, `.tar.xz` archives, version 1.5.0). The text below records the earlier `full-1.5.0-1` release.
- **Released:** `pi-build` `full-1.5.0-1` (immutable) at builder `db041e61c504dce53483db1aca69cda53a313312`; provenance `a05f7c03…`. All three archives were repeat-built byte-identically on native runners, Linux archives loaded under Alpine musl Node, the local darwin rebuild matched CI bytes, and independently downloaded assets matched the candidate.
- **Next:** headless work is filed as `pi-build` TODO PIB-1..5 (profile plumbing first). An upgrade simulation from `c05fb47` migrated launcher, bridge and intercom loader, kept the old runtime working when the download was blocked, and passed the bridge suite (76) on the migrated closure. The campaign worktrees are retired.
- **CI:** `Verify Pi offline setup and bridge` passes every Pi suite on both Linux runners; the job still fails in `sh sync check` on the pre-existing `tools/decide` orchestrate-contract test. On macOS, the whole-sync test segfaults (-11) in sync bootstrap after re-signing `jaq`, as it did before the cutover; the same test passes on a local macOS ARM64 host.
- **Parked proof:** live-account entitlement, Linux runs of the `usr` SDK/intercom protocol probes (only the builder loader check ran under glibc and musl), headless acceptance. Headless now reaches the provider and fails correctly: a scoped scout SDK child launches and receives the upstream `429 FreeUsageLimitError`. Free Zen is gated to genuine opencode clients by User-Agent, so the pins moved to `opencode-go/muse-spark-1.3-contributor` (scout/mechanic); a full acceptance proof remains unverified. Performance timing gate deferred while host swap exceeds the gate. No target or release is counted as passed from a skip.

### Authority and execution

The owner's execution grant authorizes implementation, dependency acquisition for explicit maintainer builds, related CI, direct default-branch commits/pushes and verified versioned Pi releases. It supersedes this document's former review-only boundary. The existing empty `/Users/josh/d/pi-build` checkout had no origin. Authenticated access confirmed `joshuarli/pi-build`; its configured SSH origin now hosts `main`.

Use disposable homes and checkouts under each repository's ignored `.work/`. Preserve real credentials, active runtimes, unrelated work and Git history. The owner requires native lanes at expert tier or below because bridge provider quota is exhausted. No bridge delegation or god lane is authorized for this campaign. The coordinator integrates, commits, pushes and owns worktree disposal. Allowance writes remain serial. USR-32/38/43/47/48 are not prerequisites and remain open.

### Decisions

- `pi-build` owns upstream identities, snapshots, local patches, production/build locks, tool pins, packaging, licenses, provenance and archives. `usr` retains first-party bridge code, harness configuration, consumer pins, installation and registration.
- `headless-usr` is the committed default as of 2026-11-13 (owner-granted). `full` remains available by pin selection and preserves bare interactive `pi`. One closure is installed either way.
- Keep tracked `confirmSend: true` and `inboundTrigger: "never"`. Headless sends requiring UI confirmation must fail clearly. Explicit `confirmSend: false` may authorize fixture-proved sends. Scoped SDK children remain without intercom.
- Preserve current versions and provider behavior during the ownership move. Optimize only after accepted full parity, one measured dependency group per slice.
- Maintainer dependency installation is permitted. Routine Pi setup/runtime may fetch pinned release assets only, with a digest-addressed cache and no fetch for an unchanged valid installation. No npm/npx, registry resolution, `pi install/update` or automatic catalog/package updates. Provider requests and configured local intercom traffic remain permitted.
- Node is a separate prerequisite: supported pin 26.13.1, effective minimum 26.12.0. Muse still requires a separately installed executable and login. Use isolated Node for campaign checks.
- Preserve exact tier/model/effort pins, typed descendant ceilings, depth 2, Command Code leaves, owned worktrees, durable leases, result identity and same-scope continuation. Legacy admitted sessions retain their pins.

### Artifact contract

The agreed consumer pin has `schema: 1`, `release_url`, `builder_revision`, `profile`, `version`, `provenance_sha256` and `targets`. Each target binds `archive`, `sha256` and `bytes`. Archives are `pi-<profile>-<version>-<rust triple>.tar.xz` (earlier `full-1.5.0-1` used `<target>-<profile>.tar.gz`) with a single `node_modules/` closure. Targets are keyed `darwin-arm64`, `linux-x64` and `linux-arm64` and map to `aarch64-apple-darwin`, `x86_64-unknown-linux-musl` and `aarch64-unknown-linux-musl`, including advertised Linux musl behavior.

Release assets include `SHA256SUMS` and `provenance.json`. The latter repeats schema, builder revision and target records containing target/profile/archive/hash/size. Its exact bytes must match the committed provenance digest. Downloaded checksums must agree with the pin. Tags locate assets; they never replace committed digest authority. Never resolve latest.

The staged consumer is `tools/sync/pi_release.py`; its acceptance command is `TMPDIR="$PWD/.work/tmp" python3 -I tools/pi/test_release_install.py`. Routine sync uses it with `tools/pi/runtime.pin.json`. It retains verified generations and switches one selection symlink that the launcher and bridge both follow. The previous vendored prefix at `share/pi` is preserved for explicit removal, not adopted. Rollback is a revert of the pin commit; the earlier generation or its immutable release remains available.

### Current baseline

Rechecked source inventories: subagents `52e68e9ef0e563d5c97b28519f9999f1b5fbbbea`, intercom Pi `62ba6985fe77d0f966563d5efd74c47d1c475b83`, intercom core `8316cbab548f422ad11c78ed887fabeef94817c1`, Muse adapter `b83e605e5675429e9d4aaccf13bd73e76575c22c`. Pi is 1.5.0. No opportunistic upgrade is included.

Remeasured current archives by compressed file length and the sum of tar regular-member sizes:

| Target | Compressed bytes | Logical regular-file bytes |
| --- | ---: | ---: |
| darwin-arm64 | 36,958,539 | 155,659,928 |
| linux-x64 | 37,255,814 | 155,887,824 |
| linux-arm64 | 36,887,599 | 155,228,388 |

Total compressed baseline: 111,101,952 bytes. Symlink targets are not counted twice. No accepted headless delta exists.

### Remaining sequence and acceptance

1. **A3 prerequisite acceptance:** USR-40 must preserve previous-version node/npm/npx through failed upgrade and retry. USR-44 must recover a deleted stage with retained journal using exact inode/text ownership, and reject foreign replacements. Use installer, numbered links, main and scratch-home integration suites. Fresh source-preservation review is required for link recovery.
2. **P0-1 builder:** implement `make build`, `verify`, `repro` and `sizes` for all targets/profiles. Lock production and build inputs, preserve source/patch provenance and notices, distinguish source compilation from verified precompiled packages, normalize tar order/ownership/timestamps/compression. Two clean builds of identical inputs must hash identically. Repackaging an imported archive is a separate, narrower result.
3. **P0-2 consumer:** prove pinned acquisition, cache reuse, no-fetch unchanged install, missing/truncated/interrupted assets, wrong hash/size, unsafe paths/chained links, foreign and legacy prefix preservation, concurrent installers, switch failure/retry, upgrade and rollback with local HTTP fixtures. Bind both launcher and bridge to one closure. Preserve credentials and unrelated registrations.
4. **P1-1 exact candidate:** run the behavior matrix below against extracted candidate bytes, then repeat applicable proof against independently downloaded release bytes. Missing platforms or credentials remain unverified.
5. **P1-2 publication/cutover:** publish only the accepted full target set as an immutable versioned release. Commit `tools/pi/runtime.pin.json` and installer wiring together after independent download checks. Preserve a known previous pin and retrievable verified artifact for rollback. Only then remove old snapshots/archives and their live callers.
6. **P2 lifecycle:** repeat release-install, offline Pi, disposable-checkout bridge sync, Pi extensions and affected Claude/Pi/OpenCode registration suites. Prove install, unchanged resync, upgrade, failure, retry and rollback.
7. **P3 headless:** measure retained/reachable groups before editing; declare minimum byte saving and retained behaviors before each removal. Repeat loader/worker/Muse/intercom/platform/repeat-build proof per candidate. If no safe candidate meets its threshold, retain full and report optimization blocked.
8. **P4 closeout:** review changed scope, repair campaign-caused P1/P2 defects, reconcile tickets/docs, dispose only reviewed campaign-owned worktrees and report accepted commits, pins, releases, measured sizes and parked proof.

### Behavior matrix

| Boundary | Required proof |
| --- | --- |
| CLI/loader | Real CLI startup, install/update refusal, SDK module evaluation, resource reload and extension binding, including Muse |
| SDK/detached worker | Deterministic local provider/protocol fixtures covering approved routes/pre-admission fallback, exact ownership, spawn, cancellation with termination, resume, steer, restart recovery, duplicate-admission prevention and nesting ceilings |
| Muse | Registration and real host protocol against fixture; explicit missing executable/auth failures; account entitlement remains separate live proof |
| Intercom | Real local broker and authorized fixture peer send/receive; no automatic model wakeup; absent from scoped SDK children; headless consent behavior |
| Network | Poison npm/npx and block package registries while permitting required local fixture/provider traffic |
| Platforms | Actual execution for all three targets and required libc variants; Ubuntu alone does not establish musl |
| Reproducibility | Two clean builds per target/profile/input set, identical SHA-256; state whether source build or repack |

### Cutover callers

Update or retire `tools/pi` tests, `tools/sync/checks.py`, old `vendor.py`/`build-runtime.sh`, Pi build/verify/Alpine workflows, sync/worker registration, the actual `/pi-update` SKILL.md and its SKILLS.md description, and current operator docs in the same cutover. `/pi-update` must build/verify/publish in the builder and bump the consumer only after compatibility proof. Routine sync consumes the existing pin.

Retain meaningful offline/runtime fixtures. Run `test_sync_bridge_offline.py` only in a disposable checkout. Audit all tracked references to retired paths; historical ticket/plan evidence is not a live caller. `git ls-files vendor/pi` must become empty only after durable provenance preservation and accepted replacement delivery. Never rewrite history to remove old blobs.

Extracted-runtime local proof commands use `node --import RUNTIME/node_modules/tsx/dist/loader.mjs` with `tools/pi/test_sdk_protocol.mjs RUNTIME`, `tools/pi/test_intercom_protocol.mjs RUNTIME`, and `tools/pi/verify-extensions.mjs RUNTIME`. The separate `test_runtime_protocol.mjs RUNTIME [MUSE_EXECUTABLE]` probes the installed Muse host before any model turn. It does not establish account entitlement or close USR-50.

## Campaign: Runtime-independent worker bridge and FX

### State

**Owner decision, November 19, 2026: Pi stays.** FX is kept off the active path: production `ROOT_PLANS` route only to Codex, Command Code and Pi, which `test/policy.test.ts` pins, and `server.ts` builds the bridge without an FX adapter. The FX adapter, ACP supervisor, children controller and experiments stay in the tree, so the work can resume as FX develops. Remaining work is tracked in `TODO.md` as USR-87 through USR-93. The owner does not use FX's paid inference or FX as a top-level harness.

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
- **FX 0.0.17 egress defect:** the built-in `web_fetch` cannot be prevented, so the bridge only detects it.
  - **Not prevented by permissions or mode:** it fetches public URLs under `"*": "deny"`, in both `auto` and `ask` modes, and without a client permission request. `web_fetch` rules match only exact canonical domains, so no rule denies every domain.
  - **Not prevented by hiding:** `tool_placement` removes it from the offered tools, yet a direct call still runs, and so does a call through the denied `toolbox`. FX refuses an ungranted MCP tool the same way, but not this built-in.
  - **Mitigation:** both web built-ins are hidden through `tool_placement`. The ACP supervisor stops a run on any `web_fetch`/`web_search` call, and the CLI transport rejects a result that used one. The fetch may already have happened.
  - **Consequence:** read-only FX tiers have a detected public-URL egress channel, not a prevented one. Reproduction: settings `{"permission": {"*": "deny"}}`, then a provider response calling `web_fetch` with `{"url": "https://example.com/"}`.
- **Phase 3 grant shape (probed):** client-supplied ACP MCP servers expose tools as `mcp_<server>_<tool>`. A per-tool `permission` allow offers and runs only that tool. An ungranted tool from the same server is refused before it reaches the server.
- **Phase 2 parked, November 19, 2026:** the one-time account recheck sent a single 1-token `deepseek-v4.1-flash` request to OpenCode Go. It returned HTTP 429 `GoUsageLimitError`: the monthly limit was reached, resetting in about 10 days. Only paid Extra Usage would continue, and binding decision 9 forbids buying access. No pilot jobs were admitted, so no fallback quota was spent. The live pilot now runs over ACP (`LIVE_TRANSPORT` in `experiment/fx/live-pilot.mjs`). Retry `npm run spike:fx -- --live opencode-go` after the reset. The Codex profile still lacks an FX-owned login. Its handoff is `FX_HOME=<usr>/.work/tmp/fx-live/fx-profile <usr>/.work/tmp/fx-spike/installed-home/.local/bin/fx login codex`, and it can prove lifecycle but not this gate.
- **Phase 4 controlled children, November 19, 2026:** accepted with deterministic proof. `makeFxAdapter({ delegation: { maxChildren, maxConcurrent } })` gives each ACP root a per-root controller (`src/fx-children-mcp.ts`). It is a client-supplied MCP server with only `spawn`, `status`, `wait`, `cancel`, `steer` and `resume`, granted per tool as `mcp_children_*`.
  - **Authority:** child pins are snapshotted at root admission from the bridge's own policy for `DELEGATION[tier]`, into `children.json` beside the root's FX home. They are never rewritten, so resumptions keep them. Any other argument (model, cwd, tools and so on) is refused before launch, as are unknown or stronger tiers and tiers without an FX route.
  - **Nesting:** children get no controller, so delegation stops at one generation.
  - **Ledger:** `children-ledger.json` records intents before launch. A replayed `intent_id` has one effect, and an uncertain spawn is recorded, never retried.
  - **Limits:** total and concurrent child counts are bounded, with at most one writing child at a time. A child's wall time is capped at its root's deadline.
  - **Process ownership:** child supervisors launch orphaned, through `src/fx-orphan-launcher.ts`, so the root's termination sweep cannot kill them. They are signaled only by verified process identity.
  - **Lease:** the root's worktree lease is held until every child has a verified terminal state, even after the root succeeds. Cancelling the root cancels its children. Status reports `children_active`.
  - **Steering:** steering a child requires a bound native session.
- **Phase 4 evidence:** `npm run spike:fx -- --local-acp` includes a real-binary root worker that spawns a scout child, then a writing worker child, and waits for each. An authority override is refused there. The root reruns the check, and the combined diff is in scope with both child receipts verified. `npm run test:fx` drives the real controller against a fake ACP runtime. It covers argument and tier refusals, intent replay, writer exclusion, the lease held after root success, steer/resume, and root cancellation reaching every child.
- **Phase 4 limits:** children share the root's worktree, and coordination is limited to one writer at a time. There is no OS containment. A root crash before its controller records an intent leaves nothing to reconcile; a crash after it leaves an `uncertain` entry, which keeps the lease until manual reconciliation.
- **Phase 5 platforms, November 19, 2026:** `npm run spike:fx -- --local-acp` passes against the pinned FX 0.0.17 binary with a loopback provider on three platforms. The run includes the children scenario.
  - **macOS ARM64:** native.
  - **Linux ARM64 musl:** native. Alpine 3.22 in an OrbStack container on Apple Silicon, run with `experiment/fx/linux.sh arm64`.
  - **Linux x86-64 musl:** emulated by the container runtime, run with `experiment/fx/linux.sh amd64`. That proves musl compatibility, not native x86-64 execution.
  - **Pins:** `experiment/fx/pin.json` is now per target, with archive and binary digests for the statically linked Linux assets. Node.js 26.13.1 comes from the checksum-pinned mirror artifact named in `tools/sync/installer.py`. Alpine also needs `libgcc`, `libstdc++`, `libatomic` (x86-64) and `bash`.
- **FX 0.0.17 shell defect on Alpine:** with busybox `ash` as `SHELL`, FX's shell tool fails every command with `shell snapshot unavailable (the login shell exited before reporting its state)`. With `bash` the same pilot passes. The qualified shell is pinned per target, and `makeFxAdapter` now requires an absolute `shell`.
- **Phase 5 long sessions (probed):** with a 4,500-token context window, FX compacted repeatedly and the prompt still reached `end_turn`. Compaction notes are written by extra calls to the admitted model and provider, so there is no route escape. Whether those calls are included in reported usage is unverified.
- **Phase 5 routes, parked:**
  - **Contributor Spark** (scout/medium, mechanic/high) is served by OpenCode Go. It waits for the same quota reset as Phase 2.
  - **Muse** speaks MSP and also serves ACP (`muse acp`). Its route is therefore not an FX provider configuration. Replacing it would mean either extracting the subscription transport or adding a Muse-native ACP executor, which reuses the ACP supervisor but needs a separate design decision plus an authenticated subscription and live quota.
  - **Devin SWE-2 Flash** likewise needs its own CLI authentication and a qualified executor.
  - Pi stays the executor for these routes.
- **Phase 3 research tools, parked:** this is an addition, not Pi parity: scoped Pi workers have no research tools today. It needs `pi-web-access` 0.48.0 in a pinned closure, through a pi-build release, plus separate search-provider credentials. The npm tarball's `gitHead` is `896d75bec55e316726db287a870eb166c4e3f40c`, not the `438e58be…` recorded above, so re-verify the source revision when packaging. The grant shape is already proven (see Phase 3 grant shape).
- **Phase 6, not started:** matched measurement needs live inference on the intended routes, blocked as in Phase 2. Promotion and retirement are owner decisions. The current verdict stays limited-go: FX over ACP is qualified deterministically for leaf workers and one-generation children on three platforms. It has no live-inference proof and no Spark, Muse or Devin replacement.
- **Next:** after the Go quota reset, run `npm run spike:fx -- --live opencode-go` for Phase 2, then the Spark cells. Decide whether to pursue Muse and Devin native ACP executors, or to keep Pi for those routes.
- **Current boundary:** FX remains experimental. Production routes, public names, ordinary schema-2 writes, experimental schema-3 readers/writes, installer defaults and provider entitlements are unchanged.

This is the authoritative remaining execution plan. The dated audit holds the comparison, pinned references and diagnostic evidence; earlier verification documents hold historical results.

### Charter and working rules

The owner requested an audit and replacement plan, then explicitly authorized integrating and committing that documentation directly to `usr`. This revision records that plan; runtime implementation and production promotion remain future work under their respective launch scope. The earlier CLI-only spike boundary is superseded for planning by the ACP sequence below.

Use the existing [campaign mechanics](../dotfiles/base/.agents/skills/orchestrate/references/campaigns.md) and [worktree lifecycle](../dotfiles/base/.agents/skills/orchestrate/SKILL.md#worktree-lifecycle). One writer owns shared bridge, policy, state and installer changes. Do not delegate through a modified admission/control path until qualified; use a known-good generation or bootstrap directly. Scratch homes, sessions and fixture repositories live under `.work/`, never the real home.

After each accepted slice, record the product improvement, evidence, remaining blocker and smallest useful next slice. At most two materially different repair attempts precede parking an unchanged failure with its cause and retry condition. An environment blocker parks only its dependent proof; an observed foundational defect blocks dependent implementation. Reuse evidence while its inputs remain valid. Keep Git as the change log and update Status instead of appending checkpoint narratives.

### Binding decisions

1. **Keep the shared bridge.** Retain admission, immutable route snapshots, leases, attempts, scope checks, acceptance-claim parsing, observation, owner journals and failover. The parent independently executes or verifies acceptance proof. Adapters own native execution, decoding, session identity and control; the bridge must not become a model loop.
2. **Preserve current policy.** Resolve `ROOT_PLANS` at admission and retain exact routes/pins in saved state. Only scout, mechanic and worker enter the bridge. Experts are native; top-level Antigravity, Command Code, OpenCode and Devin use native children. Claude Code, Codex and Pi parents use the bridge for lower tiers. Earlier campaign instructions about exclusive bridge experts and an Antigravity bridge adapter are obsolete. The [generated architecture](subagents.html) and typed policy are authoritative.
3. **Preserve external compatibility.** Keep `pi-subagent-bridge`, its MCP registration, `worker_*`, `.work/worker-bridge/`, owner v1, job IDs and receipts. An eventual `fx-subagent-bridge` alias/rename is a separate migration, not a second service or state store.
4. **Extend a small typed boundary.** Separate runtime, provider, model/effort, session and run. Add only the asynchronous admission, events and controls ACP needs. Use explicit wiring and discriminated capabilities, not a universal SDK wrapper or plugin framework. Unsupported operations fail before effects.
5. **Separate outcome and continuation identity.** Preserve a validated session after verified timeout/cancellation/failure without claiming success. Unknown termination, changed pins/worktrees or corrupt state block continuation and replay. Legacy readers do not invent missing budgets/identity or convert Pi sessions into FX sessions.
6. **Use native ACP first.** Keep the CLI pilot as a comparison fixture while qualifying ACP's native coding tools. Unrestricted FX fanout stays denied. Controlled children require the parent-bound controller and group-lifetime gates in Phase 4.
7. **Keep selection experimental.** Use explicit typed policy injection and private fixture state. Installing FX cannot reroute production; do not expose runtime/model overrides on public `worker_start`. Promotion is a distinct evidence-backed decision.
8. **Keep Pi and companions intact.** Core execution, inspection and installation must work without Pi imports, binaries or credentials. Optional Pi routes and historical readers remain supported. Intercom stays coordinator-only; preserve worker environment scrubbing and companion files. Worker retirement and whole-distribution removal are separate milestones.
9. **Preserve account semantics.** No paid-provider substitution, premium-tier change, credential scraping or client impersonation. Matching endpoints/model labels do not prove entitlement. Missing credentials/quota are blocked proof, not permission to buy Gateway access.
10. **Pin executable inputs.** Continue with FX 0.0.17 and verified artifact digests unless a recorded defect requires one explicit replacement release and requalification. Never follow `latest` or development HEAD. Disable upgrades only in private experiment configuration. Optional research MCP uses a pinned closure, with no runtime npm/npx resolution.

A demonstrated ACP limitation permits one bounded investigation of pinned libfx with an executable reproduction. The SDK supplies durable engines and controls, but its native backend requires host-provided coding tools; host callbacks do not automatically equip descendants, and published Linux native addons require glibc. Native-musl CLI proof is not SDK/WASM proof. Do not add Vercel infrastructure, a general coding-tool rewrite, a persistent daemon or two production transports without an accepted concrete need.

### Baseline and ownership

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

### Remaining sequence

Phase 0 precedes Phase 1. Phases 2–4 need the accepted ACP lifecycle, but unavailable live access in Phase 2 need not block deterministic research/child work. Independent platform/provider investigation may proceed without concurrent writers on shared files. A route cannot be promoted before its required gates pass.

The scripts `test:core`, `test:no-pi`, `test:runtime-contract`, `test:fx`, `spike:fx` and `bench:runtime` already exist. Extend them rather than reimplementing completed scaffolding. Run package commands from `tools/pi-subagent-bridge`. ACP/child files and modes below are proposed; document their runnable commands with their implementation.

#### Phase 0 — Repair recovery and budgets

**Prerequisite:** supported Node/development tooling; owner-RPC cases additionally require Unix sockets. Unavailable sockets park that proof, not the direct lifecycle/supervisor repairs. **Owns:** FX/lifecycle/session fixtures and associated fixes.

Reproduce deadline and cancellation through the real shared lifecycle and supervisor with deterministic executables. Each leaves valid native identity, yet current resume refuses it. Preserve a validated continuation token independently of successful output after verified termination. Cover nonzero failure, corrupt/missing identity, changed scope/pins and unknown termination; retain attempts, steer budgets and no-replay behavior.

Persist/report effective wall and step limits at admission and observation. Distinguish timeout, step exhaustion/incomplete, cancellation, quota, task failure and unknown termination. Keep 15-minute/20-step pilot defaults separate from the admitted production budget. Missing legacy fields stay unknown.

**Exit evidence:** regressions fail before the fix and pass afterward on supported Node; `npm run test:fx` and targeted session cases pass; production policy output is unchanged. Run affected owner cases where sockets are available and record unavailable proof separately. Land fixes and regressions together. Reverify affected independence contracts rather than restarting completed work.

#### Phase 1 — One ACP worker through recovery

**Prerequisite:** Phase 0; resolve or reproduce the released-binary session-creation failure on a supported host. **Owns:** proposed ACP adapter, runtime-control boundary, process supervisor and experiment fixtures.

Run one FX process per worker over stdio ACP. The synchronous FX start interface and final-JSON supervisor cannot support this unchanged. Add async session admission, correlated events, prompt/cancel/load/resume and negotiated steering while retaining shared state, leases and owner receipts. Persist native identity as soon as admission is proven; never use newest-session or `last` discovery.

Use private HOME/configuration, fixed cwd and explicit MCP/tool grants. Validate saved provider/model/effort and controls on every continuation; saved settings can differ from launch overrides. Where possible, advertise only the admitted effort in route-specific metadata, and test retry request bodies. Hooks are observation, not enforcement. Disable helper model work or account for its route and usage.

Client-supplied MCP does not by itself exclude approved project MCP merging. Prove that ambient/project settings cannot widen access; stdio server commands use absolute managed paths. Do not enable full-access to suppress permission prompts: allow required operations explicitly and surface unexpected permission/input requests as blocked.

Preserve pending/delivered/dropped steering states; protocol acceptance is not model absorption. Replay cannot duplicate delivery. Verify cancellation and owned tool-process termination before continuation or lease release.

**Exit evidence:** a real pinned binary with a deterministic local provider completes edits, exact-session correction, cancel/resume, timeout/resume, failed-tool recovery and steering during a tool. Hostile read-only calls, changed pins, ambiguous termination and replay have discriminating outcomes. Extend `test:fx`, the FX runtime-contract selection and local spike runner. An unresolved session-creation error prevents accepting this slice.

#### Phase 2 — First live Pi-dependent replacement

**Prerequisite:** Phase 1 and authorized OpenCode Go access. **Owns:** live profile and paired evidence.

Start with `opencode-go/deepseek-v4.1-flash` at high effort. Compare Pi and FX through the same bridge, exact route, instructions and tool permissions: investigation, one-file repair, multi-file change and mandatory correction. Cap the batch at six new admissions and two corrections, with explicit wall/step bounds. Exercise pre-edit quota and post-edit failure separately.

Earlier Go runs proved auth, the session header and quota handling, not inference. The reported reset in roughly 14 days was historical; recheck account access once on the execution host. Park unavailable proof without repeated paid retries. The Codex profile may prove other lifecycle behavior but cannot discharge this Pi-dependent gate.

**Exit evidence:** actual FX inference and same-session correction produce useful work with independent parent checks. Exact model/provider/effort is supported by transport fixtures and available runtime evidence. Separate requested and completing backends; Codex fallback proves orchestration continuity only. Partial edits or uncertain termination never authorize another-model replay.

#### Phase 3 — Independent research tools

**Prerequisite:** Phase 1 for worker integration; packaging inspection can begin earlier. **Owns:** optional pinned MCP closure, explicit tool policy and evidence persistence.

Configured scoped Pi workers lack pi-web-access, so this is an explicit addition. Package standalone `pi-web-access-mcp` 0.48.0 through the existing managed dependency mechanism. Grant only `web_search`, `fetch_content`, `get_search_content` and `source_check` to approved roles; no Pi SDK, ambient extensions or runtime package download.

Use worker-private configuration/cache and separate search credentials. Standalone mode lacks Pi-login authentication and several Pi UI/generated-content features; recent-result memory disappears at process exit. Persist URLs, passages, retrieval times, errors and citations, or report expired handles explicitly. Coding subscriptions do not automatically entitle search; FX's Gateway/Exa built-in search does not establish search on custom subscription lanes.

**Exit evidence:** offline tests prove dependency isolation, grants, bounded output, cancellation and restart behavior. An authorized live search/fetch/citation task with usable resumed evidence establishes provider usefulness. Missing access is explicit and cannot silently select another billable model or expose Intercom.

#### Phase 4 — Controlled child workers

**Prerequisite:** Phase 1 and root recovery/owner controls. **Owns:** minimal child controller, per-parent MCP, durable group accounting and lease changes.

Replace only the consumed pi-subagents contract: async spawn/status/wait/result, errors/usage, steer/cancel/resume and one nested generation. UI, missions, schedules, memory and generic workflows are outside this use case.

Derive parent identity, cwd, scope, provider policy and depth from trusted admission state. Do not expose unrestricted public `worker_start` to the model. Children use the immutable parent policy and equal-or-weaker typed lattice, including provider exceptions. Reject stronger tiers, alternate providers/models, new workspaces, broader tools/extensions and grandchildren before launch. Bound concurrency, inherited remaining time and work.

Keep children under the root lease with deliberate write coordination. Current release observes root termination; extend it to require every descendant capable of writing to be stopped. Persist child/run IDs and deduplicated spawn/control intents. Unknown spawn cannot authorize duplication. Root cancellation propagates to children and owned tools with verified termination; retained sessions support deliberate correction.

**Exit evidence:** a useful parent/child task passes independent combined-diff checks. Authority overrides fail before launch. Root completion/crash/cancel cannot release a writing group; restart/replay have one effect; no descendant escapes scope/accounting. These are authority and lifecycle controls, not an OS sandbox.

#### Phase 5 — Remaining routes, platforms and long sessions

**Prerequisite:** accepted lifecycle plus each route's required capabilities. **Owns:** transport tests, platform pins/install and context-pressure qualification.

Qualify Contributor Spark scout/medium and mechanic/high separately from DeepSeek. Muse requires authenticated SDK/`muse serve` subscription transport, parked tool calls, context/prefix handling, fork/continuation and cancellation. Devin SWE-2 Flash medium requires CLI auth/catalog, variant mapping, reasoning replay and tool-result/error semantics. Native CLI/ACP custom protocols and headers do not automatically replace either adapter. Extract necessary transport behavior or qualify a native executor; retain Pi until an equivalent passes or the owner explicitly retires that route.

Qualify macOS ARM64, Linux x86-64 musl and Linux ARM64 musl with verified artifacts. Version output/ACP handshake on this audit host does not prove a native Alpine lifecycle. Test long context/compaction, restoration, auth refresh, research restart and descendant cleanup.

**Exit evidence:** every retained Pi-dependent route has a useful equivalent at its exact effort; each claimed platform passes lifecycle/install gates. A clean installation runs the required matrix with Pi imports/spawns/credentials trapped. Skipped core cases are not no-Pi proof. External consumers require their own available authorized environments.

#### Phase 6 — Measure, decide and retire dependencies

**Prerequisite:** required route/capability/platform cells for the intended rollout. **Owns:** matched measurement, promotion proposal, rollback and eventual packaging changes.

Measure accepted tasks through the same bridge with matched model/effort/tools and interleaved runs. Record cold/warm overhead, accepted-task time, full process-tree peak memory, installed bytes, usage, failure rates and recovery. Include Node, tools and research/child sidecars. Unknown usage stays unknown. A native binary size versus a compressed Pi archive proves no resource advantage.

Recommend one-route-at-a-time promotion with rollback to the retained adapter. Remove Pi execution dependencies only when required lanes are replaced or explicitly retired. Migrate Intercom/other distribution consumers separately before uninstalling the distribution. Historical Pi sessions remain inspectable under their original identity.

**Exit evidence:** the intended no-Pi setup is useful, recoverable and compatible with real consumers; measured benefit justifies maintenance. Promotion/removal follow an accepted decision, not a handshake or executable rename.

### Acceptance matrix

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

### Blocked proof and retry conditions

| Gate | Current evidence / retry condition |
| --- | --- |
| Supported contracts | Audit used Node 24; rerun affected fixtures on Node 26 with development tools. Reproduce the no-Pi owner case where Unix sockets are permitted. |
| ACP execution | Resolved on macOS ARM64: `-32603` comes from the `--provider` override; select the provider through private settings. Linux ACP still needs native execution proof. |
| Live account/model | Rechecked November 19, 2026: Go returned 429 `GoUsageLimitError` (monthly, about 10 days to reset); no FX-owned Codex login. Retry after the reset; use the printed login handoff, never unrelated client credentials. |
| Native platforms | ACP pilot passes natively on macOS ARM64 and Linux ARM64 musl (container), and on Linux x86-64 musl under emulation; native x86-64 hardware and a full Alpine install via the provisioner remain unproven. |
| External consumers | Agentctl/Intercom peers were not exercised in this audit. Preserve local receipt/environment-scrubbing fixtures; integration needs the relevant checkout/authorized host. |
| Provider retirement | Go Spark, Muse and Devin equivalents remain unqualified. DeepSeek/Codex success cannot clear them. |

Update a gate with exact revision, command, result and remaining limit. Do not repeat unchanged failures or broaden unrelated suites. Follow [development checks](development.md) and the affected contract tests.

### Verdict and stop conditions

**Current verdict: limited-go for the next bounded experiment; no Pi replacement claim.** Runtime independence and historical CLI qualification retain value. ACP is the recommended next transport, with a real session-creation blocker still to resolve.

A **go** recommendation requires lifecycle, isolation, exact-route task quality and platform evidence for its scope. A **limited-go** names excluded routes/capabilities/platforms. A **no-go** records the concrete defect or unacceptable implementation cost and preserves the neutral core and reproduction. Stop expanding the project merely to make FX win.

Provider economics, native harness policy, Intercom enrollment and real-home configuration remain outside this documentation change. Whole-distribution removal, broad renaming and deployment are distinct migrations. Use the [dated audit](verification/fx-subagent-parity-audit-2026-11-19.md), [bridge contract](../tools/pi-subagent-bridge/README.md) and pinned source when upstream behavior is uncertain.

## Later

- **Transfer the web-UI design method** (USR-73): on separate requests, apply `refactor-web-ui` to stats (with `refactor-dashboard-ui` owning metrics and trends; keep useful analytical charts), stuff (dependency visualization, catalog and forge workflows; keep canvas rendering and its performance invariants), and discover (search and research results, evidence and provenance hierarchy, mobile reading; invent no data relationships to fill a screen). After a second product, decide per rule whether it belongs in the shared skill, the Laputa component library, or a product test, and delete agentctl-specific rules. The agentctl redesign evidence is in agentctl `docs/ui/redesign.md`.
