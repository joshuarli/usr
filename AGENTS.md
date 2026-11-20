# Dotfiles (`~/usr`)

This repository is the source of truth for my home configuration and machine setup. Edit this tree, never `~`.

Use the [README](README.md) to install.

`sh sync plan` previews home sync. Do not run `sh sync`, `host/macos/*`, `host/setup-*`, or reset scripts unless asked; they can alter the host or remove agent state. Run `sh sync links` only with `TARGET` set to a scratch home under `.work/`, and `sync tools` only with `HOME` set to a scratch directory under `.work/`. For checks, use the narrow commands in [development checks](docs/development.md). Keep scripts POSIX `sh` and use only the Python standard library. Fix a link-reconciliation bug with a failing numbered case in `tools/sync/test_links.py` first.

Each path belongs to one sync layer (see [sync](docs/sync.md)). Do not `cat` or `rg` binaries in `~/.local/bin`; use `git ls-files dotfiles/*/.local/bin` to list repository scripts.

## Where things are

| Topic | Doc |
| --- | --- |
| Home sync, layers, tools, doctor, uninstall | [docs/sync.md](docs/sync.md) |
| Development checks and conventions | [docs/development.md](docs/development.md) |
| Agent setup and harness configuration | [docs/agent-setup.md](docs/agent-setup.md) |
| Lean harness defaults and launch shims | [docs/harness-lean.md](docs/harness-lean.md) |
| Instruction profiles | [docs/model-profiles.md](docs/model-profiles.md) |
| Model policy ownership and generation | [tools/policy/README.md](tools/policy/README.md) |
| Markdown audit | [tools/mdtool/README.md](tools/mdtool/README.md) |
| macOS process sandbox | [docs/sbx-spec.md](docs/sbx-spec.md) |
| Subagent architecture | [docs/subagents.md](docs/subagents.md) |
| Disk pressure, cleanup and worktree CoW | [docs/agent-disk-pressure.md](docs/agent-disk-pressure.md), [docs/worktree-cow.md](docs/worktree-cow.md) |
| Runtime independence and FX migration plan | [docs/CAMPAIGN-RUNTIME-INDEPENDENCE-FX.md](docs/CAMPAIGN-RUNTIME-INDEPENDENCE-FX.md) |
| Runtime independence and FX evidence | [core verification](docs/verification/runtime-independence.md), [CLI spike](docs/verification/runtime-independence-fx.md), [parity audit](docs/verification/fx-subagent-parity-audit-2026-11-19.md) |
| Pi profile | [docs/pi.md](docs/pi.md) |
| Tailnet Intercom coordinators | [docs/intercom-tailnet.md](docs/intercom-tailnet.md) |
| Pi build migration plan | [docs/CAMPAIGN-PI-BUILD.md](docs/CAMPAIGN-PI-BUILD.md) |
| macOS preference management | [docs/macos-preferences.md](docs/macos-preferences.md) |
| Linux CPU power policy | [docs/power-policy.md](docs/power-policy.md) |
| Tailnet hardening runbook | [tailscale/TAILSCALE.md](tailscale/TAILSCALE.md) |
| Alpine provisioner | [host/alpine/README.md](host/alpine/README.md) |
| Skills guide | [SKILLS.md](SKILLS.md) |
| Deferred work | [TODO.md](TODO.md) |
| Backlog commands and record format | [tools/todo/README.md](tools/todo/README.md) |

## Background work

Every 15 minutes, check in on your background shells and processes: still
running as expected, or stuck, spinning, or past its timeout with no output
progress? Kill your own strays promptly; a hung QEMU, test server, or build
watcher left overnight is a bug in your session, not someone else's problem
to discover. Never kill, `pkill`, or `killall` processes you did not start;
if someone else's work saturates the host, report the load and work around
it instead of touching it.

## Verification

Run with `TMPDIR="$PWD/.work/tmp"`, Python 3.10+, and pinned Node 26.13.1 for the offline bridge fixture.
- `make test`: cache-empty 230s, warm 265s and 283s; `make lint`: 12s. Busy-host observations, not performance gates. On macOS the Pi offline SDK binding check fails identically at base `7f9e2af` (DSLP-6).
- `sync` CLI, links and ownership formats: `tools/sync/test_main.py`, `test_links.py`, `test_integration.py`, `test_uninstall.py`.
- `sync` installers, archives and companion configuration: `tools/sync/test_installer.py`, `test_ffmpeg_runtime.py`, `test_companions.py`.
- `pinact` CLI, workflow YAML and action pins: `tools/pinact/test_pinact.py`, `tools/pinact/tests/`.
- `mdtool` CLI and Markdown formats: `tools/mdtool/tests/mdtool-test.sh`; `decide` CLI and JSON: `tools/decide/tests/test_decide.py`.
- `todo` CLI and backlog format: `tools/todo/tests/test_todo.py` (not in `make test`).
- Pi bridge CLI, provider processes and session records: `tools/pi-subagent-bridge/test/`; full suite requires its documented development install.
- Pi release and runtime formats: `tools/pi/test_release_install.py`, `test_offline.py`, `test_runtime_profiles.py`.
- Policy generation and projections: `tools/policy/generate.test.ts`; skills metadata: `tools/skills/skills.test.ts`.
- Alpine provisioner CLI and configuration: `host/alpine/tests/test_provision.py`, `test_tuning.py`; VM journey is separate.
- macOS setup sequence: `host/macos/sync-test.py`; macOS utilities: `host/macos/macos-test.py`, `lean-test.py`.
- `intercom-tailnet` CLI: `tools/intercom-tailnet/test_intercom_tailnet.py`; font utilities, `src/wol.py`, `src/su-exec.c`: none.
- Network endpoints and live provider behavior: none; fixture checks do not establish live service behavior.
- Performance workload: `cd tools/pi-subagent-bridge && npm run bench:runtime` compares local adapter/bridge samples; no repository-wide workload.
- Vendored PyYAML revision and source: `tools/pinact/src/pinact/_vendor/yaml/PROVENANCE.txt`.
- Further component commands, platform prerequisites and fixture limits: `docs/development.md`.
