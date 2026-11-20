# Deslop test inventory

This inventory covers the owned tooling in `tools/`, `src/`, `host/`, `sync`, `lint`, and `tailscale/`. It records fixture boundaries, not live-service coverage. Commands and platform limits are in [development checks](../development.md) and [AGENTS.md](../../AGENTS.md).

| Area | Guarding tests | Gap and disposition |
| --- | --- | --- |
| close-stale-prs | `tools/close-stale-prs/tests/test_close_stale_prs.py` | GitHub actions use mocks. Live service behavior is unverified. |
| decide | `tools/decide/tests/test_decide.py` | Live provider behavior is unverified. |
| intercom-tailnet | `tools/intercom-tailnet/test_intercom_tailnet.py` | Live tailnet behavior is unverified. |
| mdtool | `tools/mdtool/tests/mdtool-test.sh` | Markdown format fixtures cover local CLI behavior. |
| Pi release and offline runtime | `tools/pi/test_release_install.py`, `test_offline.py`, `test_sync_bridge_offline.py`, `test_runtime_profiles.py` | The SDK check now supplies a worker marker to prove coordinator fixture isolation. Live providers and a missing Muse executable remain unverified. |
| Pi bridge | `tools/pi-subagent-bridge/test/` | Full suite needs the documented development install. Live provider behavior is unverified. |
| pinact | `tools/pinact/test_pinact.py`, `tools/pinact/tests/` | Workflow and action pins use fixtures; remote endpoints are unverified. |
| policy | `tools/policy/generate.test.ts` | Generation and projections are covered. |
| skills tooling | `tools/skills/skills.test.ts`, `tools/skills/test_usage.py` | Agent content is outside this pass. |
| sync | `tools/sync/test_main.py`, `test_links.py`, `test_integration.py`, `test_uninstall.py`, `test_installer.py`, `test_companions.py` | Link ownership, CLI and installer fixtures cover local paths. Live downloads are unverified. |
| todo | `tools/todo/tests/test_todo.py` | Lifecycle, concurrency and backlog format are covered. This suite is outside `make test`. |
| usage | `tools/usage/tests/test_usage.py` | Provider integrations use fixtures. Live account data is unverified. |
| host Alpine | `host/alpine/tests/test_provision.py`, `test_tuning.py` | The VM journey is separate and requires QEMU and firmware. |
| host macOS | `host/macos/sync-test.py`, `macos-test.py`, `lean-test.py` | Actual host mutations are not exercised by these fixture checks. |
| src | none for `src/wol.py` | Compact MAC file input is a demonstrated gap recorded as DSLP-8. |
| lint | `make lint` | The entrypoint is exercised by lint itself. |
| tailscale | none | Live network and host changes require a separate environment. |
| C utility | none for `src/su-exec.c` | Privileged runtime behavior is unverified. |

The suite consists of parser and state unit tests, subprocess CLI and filesystem integration tests, and the separate Alpine VM journey. The documented warm `make test` observations are 265 and 283 seconds. These are busy-host observations, not a timing gate. A comprehensive branch coverage measurement and a repeat flake baseline were not run in this pass.
