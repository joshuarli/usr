# Status

- **Goal:** Replace in-repo vendored Pi runtime archives in `usr` with pinned, checksum-verified prebuilt artifacts built and released from `~/d/pi-build`, and deliver a debloated headless-only Pi runtime profile for `usr` (headless CLI/SDK, bridge, subagents, Muse, intercom) without changing its offline-at-runtime/no-npm guarantees.
- **Last accepted revision:** none (planning draft; campaign not started).
- **Slices accepted/red/parked:** none.
- **Next slice:** P0-1 (after owner answers owner-decided items D1-D4) — bootstrap `~/d/pi-build` with equivalent reproducible build/provenance pipeline and publish a behavior-equivalent release for all supported targets.
- **Verdict:** `ready after the owner answers D1-D4`.
- **Resume prompt / first command:** n/a.

# Charter

- Decide and keep going. Record a decision only when a later slice depends on it.
- Within the owner's execution grant, proceed without waiting for approval. A plan does not provide missing permission. Park an item that needs authority outside the grant.
- Hard stops are few, and each one parks the item: an irreversible or outside-the-repo action, a boundary the doc forbids, or a loop that cannot check anything. Pushing is always forbidden.
- Fix egregious problems met on the way, in their own commit, to thresholds stated in numbers: a check loop taking >120s for an item-level acceptance is split or narrowed when feasible; a step adding >10% to an item’s measured baseline without justification is treated as a regression to investigate before acceptance. Record anything else and leave it.
- Parity before optimization. Behavior-equivalent external artifact consumption and headless parity land before debloat/size optimization phases.
- One writer by default. Parallel lanes only for the disjoint pairs named in **Sequence**, in worktrees at `.work/wt/<lane>`, never `/tmp`, following `orchestrate`’s worktree lifecycle.
- Every commit is a Conventional Commit with the workstream as its scope. The item ID belongs in the body. Code comments never cite this doc.

# Decisions

## Owner-decided (pending; one batch)

- **D1 Release source and pinning (owner, pending).** Where `pi-build` publishes release artifacts consumed by `usr`, and how `usr` pins them. **Recommendation:** publish from `~/d/pi-build` as GitHub releases under `joshuarli/pi-build` (current owner/repo of the local workdir), and have `usr` pin an exact release tag plus per-asset SHA256s (or a pinned digest verified against release `SHA256SUMS`) for `darwin-arm64`, `linux-x64`, `linux-arm64`. **Reason:** matches git-build’s verifiable release pattern and keeps installs reproducible/deterministic. **Reverses if:** owner prefers `laputa-systems/*` hosting or a different pin format.
- **D2 Headless debloat compatibility floor (owner, pending).** Which capabilities/providers must remain in the `headless-usr` profile and what may be removed (e.g. `@silvia-odwyer/photon-node`, TUI/image helpers, unused provider SDKs). **Recommendation:** preserve current `usr` headless behavior: managed `pi` wrapper/CLI entry, `pi-subagents`, `pi-muse-subscription`, `agent-intercom-pi`/core, `tsx` broker loader, `pi-subagent-bridge` SDK/worker paths, and all model providers currently required by those paths; permit removing `photon-node` and other modules only when unreachable/unused by these paths and proven by item acceptance smokes. **Reason:** debloat must not break headless automation/bridge/intercom; photon/TUI are plausible exclusions for headless-only use. **Reverses if:** owner names a narrower required provider/capability set or approves aggressive removals.
- **D3 Provenance/source snapshot location (owner, pending).** Whether `usr` keeps `vendor/pi/{pi-subagents,agent-intercom-*,pi-muse-subscription}` and `vendor/pi/upstreams.json` or moves build-time provenance to `pi-build` and keeps only a lightweight consumed-pin/provenance record in `usr`. **Recommendation:** move runtime build inputs and authoritative provenance to `pi-build`; remove `vendor/pi/runtime` blobs and bulky source snapshots from `usr`, keeping only a small pinned reference (release tag, asset names, SHA256s, upstream commit/version refs as needed) so `usr` drops ~100+ MB of vendored weight while remaining auditable. **Reason:** goal is to stop maintaining large Pi artifacts in `usr`; provenance belongs with the builder. **Reverses if:** owner requires full source snapshots to remain vendored in `usr`.
- **D4 Sync/install network contract (owner, pending).** Whether `sh sync tools pi` may download a pinned release artifact when installing/updating (runtime remains extracted and offline). **Recommendation:** yes—allow pinned, checksum-verified artifact download only on install/update of the `pi` tool (and cache/reuse verified artifacts), while the installed closure and wrapper remain strictly offline (`PI_OFFLINE=1`, no npm/npx/registry/`pi install|update` fetches at runtime). Update docs to state “no npm/registry; pinned release download only for install/update.” **Reason:** matches existing bundle tools (e.g. git-build) and removes in-repo blobs; preserving runtime no-fetch behavior is the important safety property. **Reverses if:** owner requires zero network access during sync/install for Pi.

## Prescribed

- **P1 Parity before debloat.** A behavior-equivalent `pi-build` artifact consumed by `usr` (same effective runtime contents/behavior as current pinned closure for headless paths) is proven before any size-reduction removals land. **Reason:** isolates build/distribution changes from compatibility changes. **Reverses if:** D2 explicitly authorizes a slimmer initial profile and acceptance proves it sufficient.
- **P2 Deterministic pinning and verification.** Every consumed artifact is identified by immutable release/tag + asset name and verified by SHA256 (and byte size) before extraction; installer refuses mismatches, unsafe tar members/links, and foreign/unmanaged install prefixes/symlinks (preserve current `pi_offline.py` safety checks). **Reason:** supply-chain and reproducibility parity with current committed hashes. **Reverses if:** never for normal sync.
- **P3 Runtime/offline invariants preserved.** Installed `~/.local/bin/pi` wrapper continues to enforce `PI_OFFLINE=1`, `PI_SKIP_VERSION_CHECK=1`, block `install|update`, and load bundled extensions from the installed closure; bridge links to the same installed `node_modules`; intercom loader remains bundled/local. **Reason:** existing security/operability contract (`docs/pi.md:7,9`, `docs/sync.md:46`, `tools/sync/pi_offline.py:138-147,191-214`). **Reverses if:** owner explicitly changes contract.
- **P4 Supported targets unchanged initially.** Maintain `darwin-arm64`, `linux-x64`, `linux-arm64` artifacts and Node minimum/pinned Pi family as today unless D1-D4 require otherwise. **Reason:** avoid platform regressions during migration. **Reverses if:** owner narrows support.
- **P5 Debloat evidence gate.** No dependency/module removal without (a) a named headless codepath justification, (b) before/after size measurement, and (c) passing headless smokes for wrapper/CLI, bridge/subagent SDK paths, Muse, and intercom relevant to `usr`. **Reason:** prevents breaking non-obvious runtime paths. **Reverses if:** never.
- **P6 Contract/documentation updates in same slice.** Any change to install-time network behavior, provenance layout, or update workflow updates `docs/pi.md`, `docs/sync.md`, `vendor/pi/README.md` (or replacement), `SKILLS.md` `/pi-update` description, and user-facing sync messages together. **Reason:** docs are part of the contract for this repo.

## Delegated (bounded)

- **G1 Artifact naming/packaging details** (asset names, archive format tar.gz/zip, manifest filename, cache location under XDG dirs) — executor chooses the smallest change compatible with existing installer primitives and P2/P3, logs choice in commit body.
- **G2 CI/build implementation in `pi-build`** (runner matrix, Docker/build tooling, script layout) — executor chooses standard, reproducible approach modeled on `~/d/git-build`; must emit checksums and per-target smokes.
- **G3 Order of specific debloat removals** within D2/P5 — executor prioritizes largest safe wins for headless profile, logs measurements and rationale per slice.
- **G4 Exact test narrowing** — executor uses narrowest checks proving changed behavior; widens only for uncovered integration risk (repo AGENTS).

# Baseline

## Measured (2026-11-11, local repo state)

- Vendored Pi footprint: `vendor/pi` 114 MB total; `vendor/pi/runtime` 106 MB (`vendor/pi/runtime/darwin-arm64.tar.gz` 36,958,539 B, `linux-x64.tar.gz` 37,255,814 B, `linux-arm64.tar.gz` 36,887,599 B, `artifacts.json` 606 B); source snapshots ~7.9 MB (`pi-subagents` 6.6 MB, others smaller). (`du -sh`, `wc -c`)
- `darwin-arm64.tar.gz`: 35.2 MB compressed / 148.4 MB uncompressed, 19,889 files, all under `node_modules/`. Largest packages by uncompressed size: `@earendil-works/pi-coding-agent` 23.6 MB, `openai` 17.6 MB, `@google/genai` 10.8 MB, `@esbuild/darwin-arm64` 9.5 MB, `@anthropic-ai/sdk` 9.1 MB, `web-streams-polyfill` 8.6 MB, `zod` 5.9 MB, `pi-subagents` 5.8 MB, `@modelcontextprotocol/sdk` 4.3 MB, `@earendil-works/pi-ai` 4.2 MB, … `@silvia-odwyer/photon-node` 2.2 MB (tar analysis, 2026-11-11).
- Current runtime metadata: `pi_version` 1.5.0, `node_minimum` 26.0.0, per-platform SHA256 pinned in `vendor/pi/runtime/artifacts.json`.
- Foundation proof: `tools/sync/pi_offline.verify_archive()` successfully verified committed `darwin-arm64` artifact in ~0.20s real (`0285bdad384a…`, 36,958,539 B). (`python3 -I` import/run)
- Loop timings (narrow, local): `python3 -I -m py_compile tools/sync/pi_offline.py tools/sync/installer.py tools/pi/vendor.py` ~0.10s real; `sh -n tools/pi/build-runtime.sh sync lint` ~0.01s real.
- Known red on baseline: not established by full test run in this planning pass (no repo-wide tests executed). Any pre-existing failures discovered during execution must be recorded in Status and not attributed to campaign slices.

## Current integration points (verified)

- Local archive verification/install/wrapper/bridge/intercom: `tools/sync/pi_offline.py` (`ARCHIVES = ROOT/"vendor/pi/runtime"`, `verify_archive`, `install`, `wrapper` enforces `PI_OFFLINE=1`, `bridge_current/link_bridge`).
- Sync tool install and ownership: `tools/sync/installer.py` (`install_pi`, state/launcher wiring).
- Worker bridge linking: `tools/sync/pi-worker.py`, `tools/sync/claude-worker.py`, `tools/sync/opencode-worker.py` and corresponding `*-test.py`.
- Maintainer build/provenance: `tools/pi/build-runtime.sh`, `tools/pi/vendor.py`, `vendor/pi/upstreams.json`, `vendor/pi/README.md`.
- Docs/skills: `docs/pi.md`, `docs/sync.md`, `SKILLS.md` (`pi-update`).

# Sequence

Workstreams: **B** = `~/d/pi-build` (build/release), **U** = `usr` (consumer/sync/docs), **D** = debloat profile (primarily B, validated in U). Default one writer. **Disjoint parallel pairs allowed only when stated:** none by default; B and U slices touching the same contract must be sequenced (B publishes/defines artifact, U consumes pin). Optimization (D) begins only after parity slices P2-* are accepted.

## P0 ground

- **P0-1 (B, parity foundation, blocked on D1,D3,D4)** — Bootstrap `pi-build` build/provenance and publish a behavior-equivalent release.
  - **Owns:** `~/d/pi-build` (new scripts, manifests/pins, CI workflow, packaging/smoke tooling, release metadata); no `usr` edits.
  - **Prereqs:** D1-D4 answered (at least D1,D3,D4). Records baseline-equivalent runtime contents for headless contract.
  - **Acceptance:** for each target (`darwin-arm64`, `linux-x64`, `linux-arm64`) CI/local build produces a verified archive with checksums and a smoke proving `node .../cli.js --version` (or equivalent), required extension entrypoints resolve, and wrapper/offline invariants are representable; release (or draft release artifact set) includes `SHA256SUMS` and provenance (Pi/extension versions, source SHAs). Local proof command: `cd ~/d/pi-build && <documented build+smoke command>` completes exit 0 and prints per-target sha256/size. Time-box: 3 failed attempts then park with cause.

- **P0-2 (U, ground, can run after P0-1 artifact contract known)** — Introduce pinned remote-artifact consumption path in `usr` without behavior regression.
  - **Owns:** `tools/sync/pi_offline.py`, `tools/sync/installer.py`, new pin/config file for pi runtime (exact path delegated, G1), minimal sync wiring; tests for download/verify/extract logic using local fixtures.
  - **Prereqs:** P0-1 artifact naming/checksum contract; D1,D4.
  - **Acceptance:** `python3 -I -m py_compile tools/sync/pi_offline.py tools/sync/installer.py` exits 0; new/updated narrow tests for pin resolution + checksum verification + safe extraction pass (exact command recorded at implementation, e.g. `python3 -I -m pytest <new test file> -q`); installing from a locally served/fixture release archive yields a runtime passing `pi_offline.current()` and wrapper contains `PI_OFFLINE=1` and `install|update` guard.

## P1 parity and completeness

- **P1-1 (U, migration)** — Switch `usr` default `pi` install to pinned `pi-build` release and remove in-repo runtime blobs.
  - **Owns:** `vendor/pi/runtime/*` (delete blobs/manifests as applicable per D3), `tools/sync/{pi-worker.py,claude-worker.py,opencode-worker.py}` and `*-test.py`, `tools/pi/*` (retire or repoint maintainer/build tooling per D3), `docs/pi.md`, `docs/sync.md`, `vendor/pi/README.md`, `SKILLS.md`, `TODO.md`.
  - **Prereqs:** P0-2 accepted; D3,D4.
  - **Acceptance:** `git ls-files vendor/pi/runtime` empty (or contains no large binary archives; exact end-state per D3) and `du -sh vendor/pi` reduced accordingly; `python3 -I -m py_compile` on touched sync/worker modules exits 0; `rg -n "vendor/pi/runtime" tools/sync docs SKILLS.md tools/pi` returns only intentional historical/reference-free matches (none expected) or documented pointers; updated docs state pinned-release install/update behavior and preserved runtime-offline/no-npm contract.

- **P1-2 (U/B, parity proof)** — Prove headless parity on supported host(s) with installed closure and bridge.
  - **Owns:** test/fixture scripts or documented proof steps in `pi-build` and/or `usr` as needed; no functional code changes except test harness.
  - **Prereqs:** P1-1 accepted; access to at least one supported environment.
  - **Acceptance:** on darwin-arm64 (and linux targets when available): `pi --version` (or wrapper smoke) exits 0; `node --input-type=module` resolves required `pi-subagents`, `pi-muse-subscription/src/index.ts`, intercom entrypoints from installed closure; `pi-subagent-bridge` link/current checks pass (`bridge_current` true) and a minimal headless worker/SDK smoke used by `usr` completes. Commands recorded with outputs in commit/PR evidence (not in doc). Unavailable targets/platform checks listed under **Needs environment**.

## P2 hardening

- **P2-1 (U)** — Harden download/cache/error paths and operational UX.
  - **Owns:** `tools/sync/pi_offline.py`, `tools/sync/installer.py`, related tests/docs.
  - **Prereqs:** P1-2.
  - **Acceptance:** tests cover checksum mismatch, missing asset, unsafe member/symlink rejection, stale pin/state recovery, and idempotent install; `python3 -I -m pytest <touched tests> -q` exits 0.

## P3 optimization and debloat (only after P1/P2 parity)

- **P3-1 (B, measure & candidates, blocked on D2)** — Establish headless size budget and removal candidates from dependency/runtime trace.
  - **Owns:** `~/d/pi-build` profiling/budget scripts, `headless-usr` profile definition, CI size report.
  - **Prereqs:** P1-2 parity evidence; D2.
  - **Acceptance:** documented module reachability/need analysis for headless entrypoints; baseline vs headless-profile size report per target generated by `cd ~/d/pi-build && <budget command>`; candidate removal list includes measured bytes and risk notes (must evaluate `@silvia-odwyer/photon-node` explicitly).

- **P3-2..P3-N (B, incremental debloat slices)** — Remove/exclude approved unused deps in small, proven slices.
  - **Owns:** `~/d/pi-build` build/profile/patch/override files per slice (disjoint by dependency area when possible).
  - **Prereqs:** P3-1; each prior debloat slice accepted.
  - **Acceptance (each slice):** target artifact size decreases by measured amount vs prior accepted headless build (report bytes/%); all P1-2 headless smokes and D2-required provider/feature checks still pass; no npm/registry fetch introduced in runtime/install contract. One slice per coherent removal set; time-box 3 attempts.

- **P3-U (U)** — Bump `usr` pin to debloated `pi-build` release after accepted debloat milestones.
  - **Owns:** `usr` pi pin/checksum/state expectations and docs as needed.
  - **Prereqs:** selected P3-x slices released in `pi-build`.
  - **Acceptance:** `usr` installs pinned debloated artifacts with verification; P1-2 smokes pass on available hosts; `du -sh` of installed runtime recorded and reduced vs 148.4 MB uncompressed darwin baseline (target threshold set in P3-1, recorded as a number).

## P4 close

- **P4-1 (U/B)** — Cleanup and final verification.
  - **Owns:** dead maintainer paths in `usr` replaced by `pi-build` references (per D3), stale TODO/docs, final reports.
  - **Prereqs:** all accepted slices; no red/parked items except **Needs environment**.
  - **Acceptance:** `python3 -I -m py_compile` on touched Python files exits 0; touched shell scripts pass `sh -n`; narrow tests added/modified for this campaign pass; `git grep -n 'vendor/pi/runtime'` (and obsolete local-build assumptions) clean per D3/P1-1; final size/parity summary recorded.

## Milestones (full/narrow suite points)

- M1 after P0-2: fixture-based install/verify tests green.
- M2 after P1-2: headless parity smokes green on available targets.
- M3 after each debloat pin bump (P3-U): parity smokes + size report.
- M4 close: narrow affected checks + documentation consistency sweep.

# Acceptance

| Deliverable | Proof / command | Threshold |
| --- | --- | --- |
| `pi-build` produces verified per-target artifacts | `cd ~/d/pi-build && <documented build command>`; inspect emitted `SHA256SUMS`/manifest | Exit 0; assets for `darwin-arm64,linux-x64,linux-arm64`; each SHA256 and byte size recorded and internally consistent |
| `pi-build` headless/runtime smoke (parity build) | `cd ~/d/pi-build && <documented smoke command>` against built artifact(s) | Exit 0; CLI/version/required entrypoints resolve; no npm/registry fetch during smoke |
| `usr` consumes pinned release artifact safely | `python3 -I -m pytest <pi offline/install tests> -q` (fixtures) | Exit 0; valid download/install passes; checksum/tamper/unsafe-archive cases fail with explicit errors |
| `usr` sync installs Pi without in-repo runtime blobs | `sh sync tools pi` (or documented equivalent) in a controlled environment with pinned release reachable; `python3 -I -m py_compile tools/sync/pi_offline.py tools/sync/installer.py` | Exit 0; installed stamp/current checks pass; wrapper has `PI_OFFLINE=1`, `PI_SKIP_VERSION_CHECK=1`, blocks `install|update`; no `vendor/pi/runtime/*.tar.gz` required in `usr` |
| Bridge/headless parity | `pi --version` (installed); `node --input-type=module -e '...'` resolution/import smoke for required packages; bridge `current`/link checks and minimal worker smoke used by `usr` | Exit 0 on available targets; required subagents/muse/intercom/SDK paths functional |
| Debloated headless profile (post-parity) | `cd ~/d/pi-build && <budget command>`; parity smoke suite above | Uncompressed installed/runtime closure reduced vs darwin 148.4 MB baseline by >= the threshold set and recorded in P3-1; all D2-required capabilities pass |
| Docs/contracts updated | `rg -n "vendor/pi/runtime|no npm or package registry|/pi-update" docs/pi.md docs/sync.md SKILLS.md vendor/pi/README.md tools` (adjusted for final design) | No stale claims; install/update/runtime-offline contract accurately described |

# Needs environment

- **Linux x64 / Linux arm64 build and runtime parity:** validate `linux-x64` and `linux-arm64` artifact build, install, and headless/bridge smokes on matching hosts or CI runners. Command (owner/CI): run `pi-build` target build+smoke and `usr` `sh sync tools pi` + headless smoke on each platform. Required when local host cannot execute that target.
- **GitHub release publishing/access (per D1):** create/publish releases and verify `usr` can download pinned assets (auth/public access as applicable). Command: publish tagged release in chosen repo and run `usr` pinned install from a clean environment.
- **Any model/provider credentials needed for end-to-end headless provider smokes:** if D2 requires live provider verification beyond import/startup, run provider-specific headless checks with configured credentials. Command: documented per-provider smoke in `pi-build`/`usr`.
- **Full `./lint` or repo-wide test suites:** run only if an accepted slice’s touched scope requires them or owner requests; otherwise narrow checks are used per repo guidance. Command: `cd /Users/josh/usr && ./lint` and/or targeted `python3 -I -m pytest ...` as applicable.

# Execution boundary and non-goals

## Authorized effects

- Create/edit files and commits in `~/d/pi-build` and `/Users/josh/usr` as needed for the campaign slices (including new build scripts, CI config, docs, tests, pin files).
- Run local build/test/smoke/package commands, including network/npm use **only inside explicit maintainer/build flows in `pi-build`** (and fixture/local servers for tests) consistent with current policy.
- Download pinned, checksum-verified `pi-build` release artifacts during `usr` install/update flows when implementing/testing D4-approved behavior.
- Delete or replace in-repo `vendor/pi/runtime` binaries and, if D3 approves, move/remove bulky Pi provenance snapshots from `usr` with documented replacement.

## Forbidden effects

- Pushing branches, publishing releases/tags, or modifying remote repositories/services without explicit owner action/authorization (release publication is **Needs environment/owner action** unless separately authorized).
- `pi install`, `pi update`, npm/npx/registry fetches in normal `usr` sync/runtime paths beyond the explicitly approved pinned artifact download mechanism.
- Rewriting git history to shrink existing blobs unless explicitly requested.
- Destructive host changes outside repo/worktree scopes; no `/tmp`/`$TMPDIR` worktrees or scratch (use `.work/`).
- Weakening or deleting tests to pass; changing unrelated user work.

## Contract changes (surface to owner)

- **Install-time network behavior for Pi in `usr` (D4):** from “vendored local archive in repo, no network for Pi during sync” to “download pinned, checksum-verified release artifact on install/update; runtime remains offline/no npm/no registry.” Requires doc and UX updates.
- **Provenance/layout (D3):** removal/migration of `vendor/pi/runtime` and possibly `vendor/pi` source snapshots/upstreams from `usr` to `pi-build`, replaced by a pin/provenance pointer.
- **Update workflow:** `/pi-update` moves from in-repo runtime rebuild/commit to `pi-build` release + `usr` pin bump (skill/docs update).
- **Runtime contents/profile (D2):** debloated headless profile may remove modules/providers not required by approved headless `usr` use; observable behavior for excluded capabilities changes by design if approved.

## Non-goals

- Changing Pi’s upstream feature set beyond packaging/profiling/debloating for headless `usr` use.
- Redesigning `pi-subagent-bridge` behavior, orchestration policy, or non-Pi sync tools except where required to consume the new artifact source.
- Supporting platforms/Node versions beyond the currently supported matrix unless explicitly added.
- Making interactive Pi UI/TUI/media features work in the headless-debloated profile unless D2 requires them.
- CI workflow changes in `usr` unrelated to this campaign.

# Reference

- `~/d/git-build/README.md`, `~/d/git-build/Makefile`, `~/d/git-build/scripts/package.sh`, `~/d/git-build/.github/workflows/release.yml` — release-artifact pattern (per-target build/package, manifests, consolidated `SHA256SUMS`, tagged releases, consumer download+verify).
- `tools/sync/pi_offline.py:1` — current verified local install, safety checks, wrapper/offline guards, bridge/intercom integration.
- `tools/sync/installer.py:1215` — `install_pi` ownership/state/install flow; `tools/sync/installer.py:1856` shows git-build bundle consumption pattern.
- `tools/pi/build-runtime.sh:1` — current maintainer build/pack/smoke/archive flow and pinned dependency set.
- `tools/pi/vendor.py:1` — upstream source snapshot/provenance audit mechanism.
- `vendor/pi/upstreams.json:1`, `vendor/pi/runtime/artifacts.json:1`, `vendor/pi/README.md:1` — current provenance and artifact metadata.
- `docs/pi.md:7`, `docs/sync.md:46`, `tools/pi-subagent-bridge/README.md:16` — user-visible contracts to preserve/update.
- `~/d/pi-build` — empty git repo initialized for new build/release pipeline (no commits at planning time).
