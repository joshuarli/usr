---
name: pi-update
description: "Explicitly refresh usr's Pi, Pi SDK and vendored Pi extensions against upstream Git commits, preserve provenance, and prove the offline installation contract."
disable-model-invocation: true
metadata:
  opencode/autoinvoke: "false"
---

# Pi update

Update **Pi itself, the Pi SDK, pi-subagents, intercom and its shared core, Muse adapter, and applicable harness intercom adapters** in one controlled campaign. This is explicit-only. Do not let routine `sh sync` auto-upgrade the agent stack.

## Provenance and preparation

1. Read `AGENTS.md`, `vendor/pi/README.md`, `vendor/pi/upstreams.json`, `tools/pi/vendor.py`, `docs/pi.md`, `tools/pi-subagent-bridge/README.md`, and the sync installers/tests.
2. Run `python3 -I tools/pi/vendor.py check` before doing anything else. Refuse drift or undocumented modifications to vendor code.
3. Run `python3 -I tools/pi/vendor.py plan` and inspect upstream release tags/changelogs/commit diffs. Select the latest **compatible stable release**, not necessarily HEAD. For intercom components sharing a protocol, verify their matched core and adapter revisions. Check license changes.
4. Record **full 40-character commit SHA**, upstream repository/ref, and upstream package version for *every* component. The source snapshot's blob map must match Git object content exactly. The compiled CLI and SDK have their own verified upstream tag/commit provenance, and the final runtime archives have an independent SHA-256 inventory. Keep local adaptations outside vendor directories wherever possible.

## Apply only after assessing compatibility

5. Use `python3 -I tools/pi/vendor.py update` for selected source imports. It updates the source snapshots and `upstreams.json`; do not equate that with a runnable SDK upgrade. Update/record the Pi monorepo **core and SDK** at the same release, the Pi CLI, bridge imports and model API, extension RPC/required-child-extensions, Muse provider, and intercom adapters as one compatibility unit. In particular, ensure the worker bridge's exact pins/manifest reflect the version actually executed.
6. Update **all version surfaces together**: the Pi CLI/SDK pin and tracked-only commit in `vendor/pi/upstreams.json`, `tools/pi/build-runtime.sh`, `tools/sync/pi_offline.py` (manifest and package-version assertions), `tools/pi-subagent-bridge/package.json`, and any affected Pi bridge tests. Rebuild the complete production closure with `bash tools/pi/build-runtime.sh` on **Linux x64, Linux ARM64 and macOS ARM64**, using the explicit GitHub Actions builders or equivalent trusted hosts. npm is permitted only in this isolated **maintainer build**, never ordinary `sh sync`. Check in all three complete `vendor/pi/runtime/<platform>.tar.gz` files with updated SHA-256/byte-count `artifacts.json`. Cross-check all three closures with the selected upstream source and SDK SHAs. Do not publish a partial or unpinned runtime.
7. Keep the existing `pi-subagent-bridge` ownership and typed tier/depth limits. Intercom must not bypass admission, worktree leases, authority, or acceptance proof. Turn off unsolicited model wakeups by default; test explicit messaging and opt-in replies, including cross-harness behavior. Do not import the companion fleet orchestrator.
8. Make `sh sync` and `sh sync bridge` idempotently load only repository-local files. Scan `tools/sync/installer.py`, `tools/sync/pi_extensions.py`, `tools/sync/{pi,claude,opencode}-worker.py`, and `tools/pi-subagent-bridge` for npm install/view/update, `pi install/update`, and runtime fetch paths. If **any** ordinary Pi setup path still downloads from npm, the no-npm requirement is unfulfilled. Fail closed; no hidden online fallback.

## Verification before integration

- Run `python3 -I tools/pi/vendor.py check`, `python3 -I tools/pi/test_offline.py`, bridge tests, all sync tests, `sh sync check`, and local smoke tests for each permitted model/tier.
- Prove `sh sync tools pi` and `sh sync bridge` from a fresh HOME with empty `~/.npm` and blocked npm registry egress: **no Pi dependency downloads**, Pi CLI launches, Pi SDK imports, `pi-subagents` RPC spawn/resume/steer works, Muse provider loads, intercom broker sends/receives, and the CLI/MCP entries agree.
- Verify nested equal-or-weaker one-generation cap, no God, Command Code leaf-only, unchanged HEAD/write boundary, sandbox assumptions, and supervisor messaging that cannot grant new scope.
- Check intercom protocol compatibility from Pi to Claude Code/Codex/OpenCode and vice versa if those adapters are enabled; test no unexpected auto wakeups.
- Use dedicated disposable worktrees; do not claim account/model access from unit tests. Run only the cheapest necessary online provider canaries.
- Commit the updated upstream manifest, source/dist artifacts, integration changes, tests and docs together. Report each old → new SHA, version and validation result. If a required closure/artifact/gate is missing, **do not activate** the new runtime; leave it staged and report incomplete.

The current `usr` distribution includes checksum-pinned full runtime archives for Linux x64/ARM64 and macOS ARM64. Keep that contract: upgrades must refresh the runtime closure and all SHA manifests **atomically**. Do not fall back to npm, npx, `pi install`, or `pi update` during sync or Pi startup. Other unrelated `usr` tools may still use npm.

**Report:** List the old and new version and full Git SHA for every component, all tests run and their results, the exact offline-install proof, any licensing changes, and any incomplete runtime/adapter work. An update without these proofs remains unactivated.
