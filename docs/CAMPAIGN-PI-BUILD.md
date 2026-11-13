# Status

- **Goal:** move Pi producer inputs and archives to `pi-build`, preserve full runtime behavior through pinned releases, then deliver explicit `headless-usr` selection.
- **Accepted:** `usr` `cc4963d` (USR-39), `2639eef` (USR-41), `8101cc4` (USR-45), `366fca1` (USR-42/46), `ed3efa0` (supported developer test loader), `f8f99c3` (USR-40/44), `f90d6be` (proven pre-admission model-loss race), `292eaa4` (staged consumer), `f1fd64c` (extracted SDK/broker protocol probes), `1e8b38f` (probe intercom shutdown), `a70a142` (full-profile cutover: sync consumes the pin; vendored tree and old workflows retired), `a227122`/`91bf143`/`50891ba` (cold-cache, macOS path and pinned-Node CI fixes). `pi-build` `9dd4c4c` (preserved sources and old archives), `46885cc` (locked darwin builder), `32694f0`..`db041e6` (pinned toolchain, native Linux locks, CI build/musl/release workflow, provenance merge).
- **Re-released:** the pin now names `pi-build` `release-a17c28f2ebaaac32e8cd1dfb66baa4c1d725a800` (shared build-repository format, `.tar.xz` archives, version 1.5.0). The text below records the earlier `full-1.5.0-1` release.
- **Released:** `pi-build` `full-1.5.0-1` (immutable) at builder `db041e61c504dce53483db1aca69cda53a313312`; provenance `a05f7c03…`. All three archives were repeat-built byte-identically on native runners, Linux archives loaded under Alpine musl Node, the local darwin rebuild matched CI bytes, and independently downloaded assets matched the candidate.
- **Next:** headless work is filed as `pi-build` TODO PIB-1..5 (profile plumbing first). An upgrade simulation from `c05fb47` migrated launcher, bridge and intercom loader, kept the old runtime working when the download was blocked, and passed the bridge suite (76) on the migrated closure. The campaign worktrees are retired.
- **CI:** `Verify Pi offline setup and bridge` passes every Pi suite on both Linux runners; the job still fails in `sh sync check` on the pre-existing `tools/decide` orchestrate-contract test. On macOS, the whole-sync test segfaults (-11) in sync bootstrap after re-signing `jaq`, as it did before the cutover; the same test passes on a local macOS ARM64 host.
- **Parked proof:** live-account entitlement, Linux runs of the `usr` SDK/intercom protocol probes (only the builder loader check ran under glibc and musl), headless acceptance. Headless now reaches the provider and fails correctly: a scoped scout SDK child launches and receives the upstream `429 FreeUsageLimitError`. Free Zen is gated to genuine opencode clients by User-Agent, so the pins moved to `opencode-go/muse-spark-1.3-contributor` (scout/mechanic); a full acceptance proof remains unverified. Performance timing gate deferred while host swap exceeds the gate. No target or release is counted as passed from a skip.

# Authority and execution

The owner's execution grant authorizes implementation, dependency acquisition for explicit maintainer builds, related CI, direct default-branch commits/pushes and verified versioned Pi releases. It supersedes this document's former review-only boundary. The existing empty `/Users/josh/d/pi-build` checkout had no origin. Authenticated access confirmed `joshuarli/pi-build`; its configured SSH origin now hosts `main`.

Use disposable homes and checkouts under each repository's ignored `.work/`. Preserve real credentials, active runtimes, unrelated work and Git history. The owner requires native lanes at expert tier or below because bridge provider quota is exhausted. No bridge delegation or god lane is authorized for this campaign. The coordinator integrates, commits, pushes and owns worktree disposal. Allowance writes remain serial. USR-32/38/43/47/48 are not prerequisites and remain open.

# Decisions

- `pi-build` owns upstream identities, snapshots, local patches, production/build locks, tool pins, packaging, licenses, provenance and archives. `usr` retains first-party bridge code, harness configuration, consumer pins, installation and registration.
- `headless-usr` is the committed default as of 2026-11-13 (owner-granted). `full` remains available by pin selection and preserves bare interactive `pi`. One closure is installed either way.
- Keep tracked `confirmSend: true` and `inboundTrigger: "never"`. Headless sends requiring UI confirmation must fail clearly. Explicit `confirmSend: false` may authorize fixture-proved sends. Scoped SDK children remain without intercom.
- Preserve current versions and provider behavior during the ownership move. Optimize only after accepted full parity, one measured dependency group per slice.
- Maintainer dependency installation is permitted. Routine Pi setup/runtime may fetch pinned release assets only, with a digest-addressed cache and no fetch for an unchanged valid installation. No npm/npx, registry resolution, `pi install/update` or automatic catalog/package updates. Provider requests and configured local intercom traffic remain permitted.
- Node is a separate prerequisite: supported pin 26.13.1, effective minimum 26.12.0. Muse still requires a separately installed executable and login. Use isolated Node for campaign checks.
- Preserve exact tier/model/effort pins, typed descendant ceilings, depth 2, Command Code leaves, owned worktrees, durable leases, result identity and same-scope continuation. Legacy admitted sessions retain their pins.

# Artifact contract

The agreed consumer pin has `schema: 1`, `release_url`, `builder_revision`, `profile`, `version`, `provenance_sha256` and `targets`. Each target binds `archive`, `sha256` and `bytes`. Archives are `pi-<profile>-<version>-<rust triple>.tar.xz` (earlier `full-1.5.0-1` used `<target>-<profile>.tar.gz`) with a single `node_modules/` closure. Targets are keyed `darwin-arm64`, `linux-x64` and `linux-arm64` and map to `aarch64-apple-darwin`, `x86_64-unknown-linux-musl` and `aarch64-unknown-linux-musl`, including advertised Linux musl behavior.

Release assets include `SHA256SUMS` and `provenance.json`. The latter repeats schema, builder revision and target records containing target/profile/archive/hash/size. Its exact bytes must match the committed provenance digest. Downloaded checksums must agree with the pin. Tags locate assets; they never replace committed digest authority. Never resolve latest.

The staged consumer is `tools/sync/pi_release.py`; its acceptance command is `TMPDIR="$PWD/.work/tmp" python3 -I tools/pi/test_release_install.py`. Routine sync uses it with `tools/pi/runtime.pin.json`. It retains verified generations and switches one selection symlink that the launcher and bridge both follow. The previous vendored prefix at `share/pi` is preserved for explicit removal, not adopted. Rollback is a revert of the pin commit; the earlier generation or its immutable release remains available.

# Current baseline

Rechecked source inventories: subagents `52e68e9ef0e563d5c97b28519f9999f1b5fbbbea`, intercom Pi `62ba6985fe77d0f966563d5efd74c47d1c475b83`, intercom core `8316cbab548f422ad11c78ed887fabeef94817c1`, Muse adapter `b83e605e5675429e9d4aaccf13bd73e76575c22c`. Pi is 1.5.0. No opportunistic upgrade is included.

Remeasured current archives by compressed file length and the sum of tar regular-member sizes:

| Target | Compressed bytes | Logical regular-file bytes |
| --- | ---: | ---: |
| darwin-arm64 | 36,958,539 | 155,659,928 |
| linux-x64 | 37,255,814 | 155,887,824 |
| linux-arm64 | 36,887,599 | 155,228,388 |

Total compressed baseline: 111,101,952 bytes. Symlink targets are not counted twice. No accepted headless delta exists.

# Remaining sequence and acceptance

1. **A3 prerequisite acceptance:** USR-40 must preserve previous-version node/npm/npx through failed upgrade and retry. USR-44 must recover a deleted stage with retained journal using exact inode/text ownership, and reject foreign replacements. Use installer, numbered links, main and scratch-home integration suites. Fresh source-preservation review is required for link recovery.
2. **P0-1 builder:** implement `make build`, `verify`, `repro` and `sizes` for all targets/profiles. Lock production and build inputs, preserve source/patch provenance and notices, distinguish source compilation from verified precompiled packages, normalize tar order/ownership/timestamps/compression. Two clean builds of identical inputs must hash identically. Repackaging an imported archive is a separate, narrower result.
3. **P0-2 consumer:** prove pinned acquisition, cache reuse, no-fetch unchanged install, missing/truncated/interrupted assets, wrong hash/size, unsafe paths/chained links, foreign and legacy prefix preservation, concurrent installers, switch failure/retry, upgrade and rollback with local HTTP fixtures. Bind both launcher and bridge to one closure. Preserve credentials and unrelated registrations.
4. **P1-1 exact candidate:** run the behavior matrix below against extracted candidate bytes, then repeat applicable proof against independently downloaded release bytes. Missing platforms or credentials remain unverified.
5. **P1-2 publication/cutover:** publish only the accepted full target set as an immutable versioned release. Commit `tools/pi/runtime.pin.json` and installer wiring together after independent download checks. Preserve a known previous pin and retrievable verified artifact for rollback. Only then remove old snapshots/archives and their live callers.
6. **P2 lifecycle:** repeat release-install, offline Pi, disposable-checkout bridge sync, Pi extensions and affected Claude/Pi/OpenCode registration suites. Prove install, unchanged resync, upgrade, failure, retry and rollback.
7. **P3 headless:** measure retained/reachable groups before editing; declare minimum byte saving and retained behaviors before each removal. Repeat loader/worker/Muse/intercom/platform/repeat-build proof per candidate. If no safe candidate meets its threshold, retain full and report optimization blocked.
8. **P4 closeout:** review changed scope, repair campaign-caused P1/P2 defects, reconcile tickets/docs, dispose only reviewed campaign-owned worktrees and report accepted commits, pins, releases, measured sizes and parked proof.

# Behavior matrix

| Boundary | Required proof |
| --- | --- |
| CLI/loader | Real CLI startup, install/update refusal, SDK module evaluation, resource reload and extension binding, including Muse |
| SDK/detached worker | Deterministic local provider/protocol fixtures covering approved routes/pre-admission fallback, exact ownership, spawn, cancellation with termination, resume, steer, restart recovery, duplicate-admission prevention and nesting ceilings |
| Muse | Registration and real host protocol against fixture; explicit missing executable/auth failures; account entitlement remains separate live proof |
| Intercom | Real local broker and authorized fixture peer send/receive; no automatic model wakeup; absent from scoped SDK children; headless consent behavior |
| Network | Poison npm/npx and block package registries while permitting required local fixture/provider traffic |
| Platforms | Actual execution for all three targets and required libc variants; Ubuntu alone does not establish musl |
| Reproducibility | Two clean builds per target/profile/input set, identical SHA-256; state whether source build or repack |

# Cutover callers

Update or retire `tools/pi` tests, `tools/sync/check.sh`, old `vendor.py`/`build-runtime.sh`, Pi build/verify/Alpine workflows, sync/worker registration, the actual `/pi-update` SKILL.md and its SKILLS.md description, and current operator docs in the same cutover. `/pi-update` must build/verify/publish in the builder and bump the consumer only after compatibility proof. Routine sync consumes the existing pin.

Retain meaningful offline/runtime fixtures. Run `test_sync_bridge_offline.py` only in a disposable checkout. Audit all tracked references to retired paths; historical ticket/plan evidence is not a live caller. `git ls-files vendor/pi` must become empty only after durable provenance preservation and accepted replacement delivery. Never rewrite history to remove old blobs.

Extracted-runtime local proof commands use `node --import RUNTIME/node_modules/tsx/dist/loader.mjs` with `tools/pi/test_sdk_protocol.mjs RUNTIME`, `tools/pi/test_intercom_protocol.mjs RUNTIME`, and `tools/pi/verify-extensions.mjs RUNTIME`. The separate `test_runtime_protocol.mjs RUNTIME [MUSE_EXECUTABLE]` probes the installed Muse host before any model turn. It does not establish account entitlement or close USR-50.
