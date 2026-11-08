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
| Markdown audit | [tools/mdtool/README.md](tools/mdtool/README.md) |
| macOS process sandbox | [docs/sbx-spec.md](docs/sbx-spec.md) |
| Pi profile | [docs/pi.md](docs/pi.md) |
| macOS preference management | [docs/macos-preferences.md](docs/macos-preferences.md) |
| Alpine provisioner | [host/alpine/README.md](host/alpine/README.md) |
| Skills guide | [SKILLS.md](SKILLS.md) |
| Deferred work and RFCs | [TODO.md](TODO.md), [docs/rfc/](docs/rfc/) |

## Background work

Every 15 minutes, check in on your background shells and processes: still
running as expected, or stuck, spinning, or past its timeout with no output
progress? Kill your own strays promptly; a hung QEMU, test server, or build
watcher left overnight is a bug in your session, not someone else's problem
to discover. Never kill, `pkill`, or `killall` processes you did not start;
if someone else's work saturates the host, report the load and work around
it instead of touching it.
