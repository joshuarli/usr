---
name: pi-update
description: "Explicitly update Pi, the Pi SDK and Pi extensions in pi-build, publish a verified immutable release, then bump usr's runtime pin after proving the offline installation contract."
disable-model-invocation: true
metadata:
  opencode/autoinvoke: "false"
---

# Pi update

Update **Pi itself, the Pi SDK, pi-subagents, intercom and its shared core, Muse adapter, and applicable harness intercom adapters** in one controlled campaign. This is explicit-only. Do not let routine `sh sync` auto-upgrade the agent stack: sync only installs the release already named by `tools/pi/runtime.pin.json`.

Ownership is split. The [`pi-build`](https://github.com/joshuarli/pi-build) checkout owns upstream identities, source snapshots (`sources/`), local patches (`patches/`), locks (`locks/`), tool pins, packaging, provenance and release archives. `usr` owns the first-party bridge, harness configuration, the consumer pin, installation and registration.

## Provenance and preparation

1. Read both repositories' `AGENTS.md`, `pi-build/README.md`, `pi-build/sources/upstreams.json`, `pi-build/tools/vendor.py`, `usr/docs/pi.md`, `usr/tools/pi-subagent-bridge/README.md`, `usr/tools/sync/pi_release.py` and its tests.
2. In `pi-build`, run `python3 -I tools/vendor.py check` before doing anything else. Refuse drift or unrecorded modifications to source snapshots.
3. Run `python3 -I tools/vendor.py plan` and inspect upstream release tags, changelogs and commit diffs. Select the latest **compatible stable release**, not necessarily HEAD. For intercom components sharing a protocol, verify their matched core and adapter revisions. Check license changes.
4. Record the **full 40-character commit SHA**, upstream repository/ref and package version for *every* component. The snapshot's blob map must match Git object content exactly. Keep local adaptations in `pi-build/patches/`, never in `sources/`.

## Build and publish in pi-build

5. Use `python3 -I tools/vendor.py update` for selected source imports. It updates the snapshots and `upstreams.json`; that alone is not a runnable SDK upgrade. Update the Pi core, SDK and CLI at one release, plus bridge imports and model API, extension RPC, the Muse provider and intercom adapters, as one compatibility unit.
6. Update **all version surfaces together**: `pi-build/tools/build.sh` (runtime `package.json`), `pi-build/tools/verify.mjs` if behavior changed, `usr/tools/sync/pi_offline.py` (`PACKAGES`), `usr/tools/pi-subagent-bridge/package.json`, and affected bridge tests. Refresh locks with the `Build Pi runtime` workflow in `prepare` mode for Linux and `make prepare TARGET=darwin-arm64` on a macOS ARM64 host, using `sh tools/toolchain.sh TARGET` tools. Review and commit the lock artifacts. npm is permitted only in this maintainer build, never in ordinary `sh sync`.
7. Run the workflow in `build` mode without a tag. It must repeat-build byte-identically and verify on darwin-arm64, linux-x64 and linux-arm64, then load the Linux archives under Alpine musl. Download the candidate archives and run the `usr` extracted-runtime probes against them (`tools/pi/test_sdk_protocol.mjs`, `test_intercom_protocol.mjs`, `verify-extensions.mjs`). Only then rerun `build` mode with a new `release_tag` (`full-<pi version>-<n>`). Releases are immutable; never reuse or move a tag, and never resolve "latest".
8. Keep the existing `pi-subagent-bridge` ownership and typed tier/depth limits. Intercom must not bypass admission, worktree leases, authority, or acceptance proof. Keep unsolicited model wakeups disabled by default (`inboundTrigger: "never"`, `confirmSend: true`). Do not import the companion fleet orchestrator.

## Bump the usr consumer

9. Download the published assets independently (not from the workflow's artifacts). Check `SHA256SUMS`, every archive digest and size, and the `provenance.json` digest and identity. Write `tools/pi/runtime.pin.json` from those values: `release_url`, `builder_revision`, `profile`, `provenance_sha256`, and each target's `archive`, `sha256` and `bytes`.
10. Scan `tools/sync/installer.py`, `tools/sync/pi_release.py`, `tools/sync/pi_extensions.py`, `tools/sync/{pi,claude,opencode}-worker.py` and `tools/pi-subagent-bridge` for npm install/view/update, `pi install/update`, or any fetch beyond the pinned release assets. Any other Pi download path breaks the contract. Fail closed with no hidden online fallback.

## Verification before integration

- Run `TMPDIR="$PWD/.work/tmp" python3 -I tools/pi/test_release_install.py`, `TMPDIR="$PWD/.work/tmp" python3 -I tools/pi/test_offline.py`, the worker and installer tests, `tools/pi/test_sync_bridge_offline.py` in a disposable checkout, the bridge tests, and `sh sync check`. Clear `.work/cache/pi-releases` first so the runtime suite fetches and verifies the new pin.
- Prove `sh sync tools pi` and `sh sync bridge` from a fresh HOME with an empty `~/.npm` and blocked npm registry. Only the pinned release assets may be downloaded. The Pi CLI must launch, the SDK must import, `pi-subagents` RPC spawn/resume/steer must work, the Muse provider must load, the intercom broker must send and receive, and the CLI and MCP entries must agree. An unchanged rerun must make no request.
- Verify the nested equal-or-weaker one-generation cap, no God, Command Code leaf-only, unchanged HEAD/write boundary, sandbox assumptions, and supervisor messaging that cannot grant new scope.
- Use dedicated disposable worktrees. Do not claim account or model access from unit tests. Run only the cheapest necessary online provider canaries.
- Commit the `pi-build` sources, locks and tooling there. Commit the `usr` pin, version surfaces, tests and docs together. The previous pin stays in `usr` history and its release stays published, so reverting the pin commit is the rollback. If a required target, archive or gate is missing, do not publish or bump the pin; report the update as incomplete.

**Report:** List the old and new version and full Git SHA for every component, the release tag, builder revision and archive digests, all tests run and their results, the exact offline-install proof, any licensing changes, and any incomplete runtime or adapter work. An update without these proofs remains unactivated.
