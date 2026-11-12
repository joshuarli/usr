# Status

- **Goal:** Move Pi build inputs, vendored sources, and runtime archives out of `usr` into `pi-build`. First preserve the existing runtime through pinned release artifacts, then produce a smaller `headless-usr` profile.
- **Last accepted revision / slices:** none; planning revised, campaign not started.
- **Verdict:** ready for a local implementation pilot after an execution request. Release activation still requires the gates below; the headless default has an explicit product decision.
- **Next slice:** P0-1. Locate the actual `pi-build` checkout and inspect its Git remote before using a proposed repository URL. Local preparation does not depend on publishing a release.
- **Resume:** read `AGENTS.md`, this plan, and `TODO.md`; run `python3 -I tools/pi/vendor.py check` in `usr` while the current vendor tree exists. Do not execute the campaign merely because this document is committed.

# Charter

- Work within the owner's execution grant. This review authorizes the requested `usr` review/plan commit; it does not create or publish `pi-build`. Honor existing permission to push verified work instead of imposing a blanket no-push rule.
- Preserve behavior before reducing dependencies. Packaging equivalence does not excuse the known bridge defects listed below.
- Use one writer per repository by default. P0-1 builder work and independent bridge repairs may run concurrently only with disjoint ownership; changes to the shared artifact contract are serial.
- Keep scratch and worktrees under each repository's ignored `.work/`, following `orchestrate`. Run installs only in disposable homes/checkouts, never the operator's real home.
- Each slice names its proof before implementation. If a check exceeds 120 seconds, narrow its fixture or separate build preparation without dropping required cases. Park after three materially different failed attempts; never repeat an unchanged failure.
- Use Conventional Commits with the workstream scope and slice ID in the body. Record results in commit evidence; rewrite Status in place rather than appending campaign logs.

# Decisions

## Owner decisions at the affected boundary

- **D1 Release destination:** verify the local `pi-build` origin when execution starts. `joshuarli/pi-build` is the original draft's proposal, not a verified remote. If no destination is configured, resolve the namespace and publication grant before publishing. This does not block building local candidates.
- **D2 Headless entrypoint:** the smaller profile must preserve the required headless CLI/SDK, subagents, Muse adapter, and intercom behavior. Before making it the default, decide whether bare interactive `pi` remains available through a full profile or explicitly reports unsupported mode. Preserve today's full profile until then. Headless intercom sending also needs an explicit noninteractive authorization contract: keeping `confirmSend: true` is insufficient because the current adapter prompts only when `ctx.hasUI`. Keep scoped SDK children without intercom during this migration.

## Prescribed

- **D3 Ownership:** the requested move settles the provenance location. `pi-build` owns upstream revisions, source snapshots, local build patches, transitive locks, artifact production, and build provenance. `usr` owns the consumed pin, installation, launcher, harness registration, agent profiles, and first-party `tools/pi-subagent-bridge` source. Remove the old vendor sources and blobs only after replacement delivery is verified.
- **D4 Network contract:** explicit maintainer builds in `pi-build` may use npm/network. Pi install/update in `usr` may fetch only the already pinned release artifact, with verified-cache reuse and no fetch for an unchanged valid installation. Runtime must perform no dependency acquisition, npm/npx/registry resolution, `pi install/update`, or automatic package/catalog updates. Model requests and configured local intercom traffic remain permitted; this is not offline inference.
- **D5 Trusted pin:** commit the release locator, profile, builder revision, provenance digest, and each target's archive name, SHA-256, and byte size in a small consumer manifest. A release tag is a locator, not immutable authority. Cross-check release `SHA256SUMS` against the committed expectation; never replace the trusted digest from a newly downloaded checksum file or resolve `latest` during sync.
- **D6 Reproducibility:** lock production and build dependency versions/integrities, including packages currently installed from registry tarballs. Pin the builder tools, record local patches, and normalize archive ordering, ownership, timestamps, and compression metadata. Two clean builds of the same target/profile/inputs must have identical digests before claiming reproducibility. Record whether each component is built from source or incorporated as a verified precompiled package.
- **D7 Platforms and prerequisites:** initially retain `darwin-arm64`, `linux-x64`, and `linux-arm64`, including advertised Linux musl behavior. Ubuntu execution alone does not prove musl compatibility. Node remains a separate `usr` tool; use the effective current minimum 26.12.0 and pinned builder Node 26.13.0 consistently. The old artifact manifest's 26.0.0 is weaker than the installer requirement. Muse still needs its separately installed executable and login; the archive supplies the adapter, not that account or executable.
- **D8 Boundaries:** preserve exact model pins, typed tier/depth ceilings, Command Code leaf behavior, owned worktrees, leases, result identity, and same-scope continuation. The launcher retains `PI_OFFLINE=1`, `PI_SKIP_VERSION_CHECK=1`, its install/update refusal, and local extension paths. The bridge uses the same installed closure. Preserve existing credentials/configuration, disabled unsolicited intercom wakeups, retained licenses, and notices.

## Delegated within those bounds

- Use one versioned tar.gz/manifest format and a digest-addressed cache. The proposed consumer manifest is `tools/pi/runtime.pin.json`; settle its schema before producer and consumer implementations diverge.
- Choose small build scripts and native target runners appropriate to the actual `pi-build` repository. Keep source and patch provenance there; do not create a second dependency resolver in `usr`.
- Order debloat candidates by measured retained bytes and reachable code. A package's name is not evidence that it is unused. Set a candidate's expected byte reduction before its edit, then keep it only when the measured reduction and behavior gates hold.

# Baseline and review reconciliation

The reviewed implementation is `19997ea5c91abcbb21d6543b2efc044280b22258`; the original plan landed in `ea8351531072f176f36f9e95cd6319e7d0f37782`. No campaign implementation has landed.

- The three committed runtime archives total **111,101,952 bytes**. Darwin has **36,958,539 compressed bytes**, **19,889 regular files**, and **155,659,928 regular-file payload bytes** (35.246 and 148.449 MiB). Compare these logical byte counts with the same calculation later, not filesystem `du` allocation.
- The current builder uses `--no-package-lock` and ordinary `tar -czf`. Its committed hashes pin distributed bytes; they do not prove repeatable source builds. Pi's recorded upstream source SHA also does not establish that the registry package was compiled from that tree.
- Largest Darwin payload groups include Pi coding agent (24,727,422 B), OpenAI (18,477,473 B), Google GenAI (11,277,335 B), esbuild (9,935,362 B), and Anthropic SDK (9,503,985 B). Investigate required provider paths before removing any group.
- Review checks passed: skill metadata, 56 link cases, and 13 instruction-profile cases. The offline Pi suite passed seven cases and skipped three runtime cases on Node 24.22.1. Those skips are not supported-runtime proof. Record actual build/acceptance timings on the executor rather than reusing the draft's syntax-check timings.
- Both subagents and intercom statically import `@earendil-works/pi-tui`. `--version` and `import.meta.resolve()` alone cannot justify removing TUI/image packages. Exercise module evaluation, extension binding, and detached execution.

| Finding | Owner | Campaign relationship |
| --- | --- | --- |
| USR-39, wrong worker proof | `usr` bridge | Repair before detached-worker success is trusted as acceptance evidence. |
| USR-41, duplicate uncertain admission | `usr` bridge | Repair before claiming safe admission/fallback. |
| USR-45, Muse-to-Go selection | `usr` bridge | Repair before claiming the advertised provider progression. |
| USR-40, failed Node upgrade | `usr` installer | Repair before using an upgrade of the managed Node prerequisite in migration acceptance. |
| USR-38, companion intercom/consultation | Builder packaging plus `usr` registration | Separate feature work; moving archives does not complete it. |

Packaging and fixture work may proceed while these repairs are separate slices. Moving source locations never closes a defect by itself. Other review tickets remain outside this campaign unless its changed behavior depends on them.

# Sequence

**B** means the verified `pi-build` checkout; **U** means `usr`. The following Make targets are proposed interfaces to implement in P0-1, not claims that an empty builder already provides them. Once introduced, the commands and outputs form the slice gates.

## P0 ground and safe acquisition

- **P0-1 (B, M): build an equivalent local candidate.** Own builder source/import manifests, dependency locks, patches, packaging, and the `build`, `verify`, `repro`, and `sizes` Make targets. Preserve the current complete profile before debloat. Implement `make build TARGET=darwin-arm64 PROFILE=full`, with the same interface for both Linux targets; `make verify TARGET=darwin-arm64 PROFILE=full` verifies the actual produced archive; `make repro TARGET=darwin-arm64 PROFILE=full` compares two clean rebuilds. Emit a schema-versioned provenance manifest, checksums, byte counts, and per-package inventory. Publication is a separate later step, not this local slice's acceptance.
- **P0-2 (U, M; after the artifact schema is fixed): implement candidate acquisition and migration fixtures.** Own `tools/sync/pi_offline.py`, `tools/sync/installer.py`, the consumer pin, and a new `tools/pi/test_release_install.py`. Keep the current default distribution until P1-2. Acceptance: `python3 -I tools/pi/test_release_install.py`. Use a local HTTP fixture and disposable homes to prove valid install, verified-cache reuse, no fetch when current, missing asset, truncated/interrupted download, digest/size mismatch, unsafe members and chained links, foreign paths, legacy local-archive state, concurrent installers, failure preservation, and retry after interruption. Invalid input must leave the previous runtime usable and credentials/configuration untouched; no package-manager fallback is allowed.

## P1 runtime proof and consumer cutover

- **P1-1 (B/U, M; after P0 and the relevant review repairs): verify the exact candidate.** Builder owns `verify`/protocol fixtures; `usr` owns compatibility assertions and its bridge. Download or serve the candidate by its proposed release path, verify its committed digest, and exercise the extracted bytes in isolated homes before deleting anything. Run the behavior matrix in Acceptance on every required target/libc. A missing environment can park that proof while local work continues; it cannot count as a passed target or permit a partial supported release.
- **P1-2 (B/U, M; after P1-1 and publication authority): publish, pin, and remove the superseded delivery path.** Publish the already verified complete target set from the verified remote, then independently download and verify those assets. Change the `usr` consumer pin and installer together. Preserve rollback through the previous pin and verified artifact, not a mutable cache alone. Only after the consumer checks pass, remove `vendor/pi/runtime` and the bulky vendor source snapshots, move the build/provenance authority to B, and retire the old build callers.
  - **U owns:** the pin and sync/worker registration modules; applicable `tools/pi` consumer tests; retirement of `tools/pi/vendor.py` and `tools/pi/build-runtime.sh`; `tools/sync/check.sh`; existing `.github/workflows/pi-offline-build.yml`, `pi-offline-build-arm.yml`, `pi-offline-verify.yml`, and `pi-alpine-smoke.yml`; the actual `dotfiles/base/.agents/skills/pi-update/SKILL.md`, its catalog description in `SKILLS.md`, `docs/pi.md`, `docs/sync.md`, and the superseded vendor README.
  - **Acceptance:** `python3 -I tools/pi/test_release_install.py`, `python3 -I tools/pi/test_offline.py`, and `python3 -I tools/pi/test_sync_bridge_offline.py` pass in a disposable checkout. Keep offline/runtime tests meaningful with cached release fixtures; do not replace them with package-presence assertions. `git ls-files vendor/pi` becomes empty after durable provenance/docs move. Search all tracked callers of retired paths and classify every remaining match; this plan and historical ticket evidence are not live consumers.
  - Retire/repoint the existing archive-producing workflows in the same cutover; they currently commit `vendor/pi/runtime` back into `usr`. `/pi-update` must build and verify in B, publish under the grant, then bump U's pin after compatibility proof. Routine sync consumes the existing pin only.

## P2 recovery and operational completion

- **P2-1 (U, S; after P1-2): prove the installed release lifecycle.** Own remaining acquisition/state error handling and operator docs. The essential failure checks already belong to P0-2. Run its suite plus `python3 -I tools/sync/test_pi_extensions.py`, `python3 -I tools/sync/pi-worker-test.py`, `python3 -I tools/sync/claude-worker-test.py`, and `python3 -I tools/sync/opencode-worker-test.py`. Verify an install, unchanged resync, pin upgrade, failure, retry, and rollback against the same manifest/ownership rules. Keep `plan` and `doctor` read-only and preserve unrelated MCP registrations.

## P3 headless optimization

- **P3-1 (B, S; after P1/P2): define `headless-usr` and measure candidates.** Own profile entrypoints, dependency reachability, and `make sizes PROFILE=full` / `make sizes PROFILE=headless-usr`. Report compressed archive bytes and logical regular-file bytes per target/profile. Preserve all required provider/SDK/subagent/Muse/intercom paths; explicitly evaluate photon, TUI and image handling without assuming headless means text-only. Record a minimum expected byte saving for each proposed removal and the exact behavior it must retain before editing it.
- **P3-2..P3-N (B, S each; serial): remove one coherent dependency group.** Own its build transform or source patch and provenance. Required proof is the same target's prior accepted artifact versus the candidate, `make verify TARGET=darwin-arm64 PROFILE=headless-usr` (and both Linux targets), and `make repro` for that profile. Keep only a demonstrated byte reduction that meets the declared candidate threshold and all behavior checks. If no candidate is safe, report the blocked optimization rather than weakening the gate or claiming the debloat goal complete.
- **P3-U (U, S; after accepted/released headless artifacts and D2): select the profile explicitly.** Own only the consumed pin/profile, compatibility expectations, and user docs. Repeat the installed-archive checks and verify the defined behavior of bare `pi` and interactive flags. An unsupported mode must fail deliberately with an actionable message, not a missing-module exception. The full migration remains usable while this product choice is unresolved.

## P4 close

- **P4-1 (B/U, S): retire dead paths and report delivered capabilities.** Run the narrow affected suites, target behavior matrix, source/provenance checks, and documentation consistency. Check Bash builders with `bash -n` and POSIX scripts with `sh -n`; syntax success is supplemental. Report compressed and payload deltas per target, repeat-build results, exact pins, and unverified live-account checks. Removing current-tree blobs does not shrink existing Git history; do not rewrite history.
- Local implementation can finish with named environment-dependent checks parked. The release, all-target parity, and headless deliverables stay explicitly incomplete until their own mandatory gates pass. Roll completed design facts into durable docs only when those deliverables are in the code.

# Acceptance

Producer `make verify TARGET=... PROFILE=...` must test the extracted candidate, and consumer tests must repeat the applicable boundary checks against the downloaded artifact. A successful process exit or a self-reported worker success is insufficient.

| Boundary | Required result |
| --- | --- |
| Artifact identity | Pin/schema, target, profile, byte size, archive digest, provenance digest, source/patch identities, and package integrity data agree. Same-input clean rebuild digests match for each target/profile. |
| Acquisition and switch | All P0-2 success/failure cases pass. The prior runtime survives failures; retry and rollback converge; foreign paths and credentials are preserved. |
| CLI and loader | Managed CLI starts, install/update remain refused, and the real SDK imports, reloads resources, and binds extensions. Adapt `tools/pi/verify-extensions.mjs` as the existing loader baseline and add Muse registration; resolution alone does not pass. |
| Detached workers | Real SDK/native RPC and detached-child bootstrap execute with a deterministic provider/protocol fixture. Assert the approved provider routes and pre-admission fallback progression, exact run/result ownership, spawn, cancellation/termination, same-session resume and steer, no duplicate admission, and permitted/forbidden nesting. USR-39/41/45 must be repaired for these assertions to be trusted. |
| Muse | Required provider registers, its host protocol works against a fixture, and missing executable/login remains explicit. Live subscription entitlement is a separate canary; an import does not prove account access. |
| Intercom | The bundled loader starts the local broker; an authorized fixture peer sends and receives a real message; receipt does not wake a model by default. The full-profile migration preserves and verifies current behavior; the headless profile must also verify D2's chosen noninteractive send contract. Keep scoped SDK children free of intercom in both profiles. |
| Package acquisition | Poison npm/npx, block package-registry egress, and assert no dependency fetch during startup, broker use, or detached execution. Permit only the local fixture/provider traffic needed by the test. |
| Platforms and size | Execute the target artifact on macOS ARM64 and Linux x64/ARM64, including musl cases. Record compressed and logical payload bytes separately; each accepted removal meets its predeclared saving without losing required behavior. |

# Needs environment

- **Builder checkout and remote:** the draft reported an empty `~/d/pi-build`; this review did not inspect that machine. At launch, locate it and run `git remote -v`. Confirm destination and permitted remote effects before publication.
- **Native targets/libc:** run `make build`, `make verify`, and `make repro` with the required `TARGET`/`PROFILE` on matching builders. For Linux, run the produced runtime under musl as well as the builder environment. Do not label missing target evidence passed.
- **Published-asset access:** after authorized publication, run the same candidate verification against the downloaded release bytes, then the consumer installation suites in a fresh disposable checkout/home.
- **Live accounts:** use one bounded canary per required provider when credentials are available. Record entitlement/auth and real tool-call results separately from deterministic local protocol proof. Never spend quota merely to replace an adequate fixture check.

# Execution boundary and non-goals

The current request is to reconcile the review and edit this plan, then commit those `usr` changes. A later campaign execution grant covers implementation in both repositories and must identify any permitted creation/publication effects. Existing authorization is not revoked or requested twice.

Within that grant, source/build changes belong to B and consumer/bridge changes to U. Install-time pinned artifact downloads are the declared replacement for in-repository archives. npm and package-registry access are restricted to explicit builder work; ordinary Pi setup never gains an npm fallback. Headless default selection is an observable contract change governed by D2.

Do not rewrite Git history, modify the real host home, delete unrelated work, weaken tests, introduce fleet orchestration, complete USR-38 implicitly, change model/provider policy, or redesign unrelated sync tools. Limit `usr` workflow edits to callers affected by this migration. Never delete provenance or license material without its durable replacement.

# Reference

- [Current Pi integration](pi.md), [sync implementation](sync.md), and [bridge contract](../tools/pi-subagent-bridge/README.md).
- [Review tickets](../TODO.md): independent defects remain owned and tracked when distribution moves.
- `tools/sync/pi_offline.py`, `tools/sync/installer.py`, `tools/pi/build-runtime.sh`, and `tools/pi/vendor.py` are the current producer/consumer boundaries. Follow their callers before retirement.
- `vendor/pi/upstreams.json` and `vendor/pi/runtime/artifacts.json` are migration inputs, not the future provenance authority.
- `vendor/pi/agent-intercom-pi/index.ts:2148` contains the UI-dependent send confirmation. `vendor/pi/pi-subagents/src/extension/index.ts:7` and the intercom entrypoint import TUI code on headless load.
