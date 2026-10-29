# Dotfiles (`~/usr`)

This repository is the source of truth for my home configuration and machine setup. Edit this tree, never `~`.

Use the [README](README.md) to install. See [sync](docs/sync.md), [development checks](docs/development.md), [agent learning](docs/agent-learning.md), [macOS preferences](docs/macos-preferences.md), [agent setup](docs/agent-setup.md), the [skills guide](SKILLS.md), the [mdtool reference](docs/mdtool.md), [deferred work](TODO.md), and [RFCs](docs/rfc/).

`sh sync plan` previews home sync. Do not run `sh sync`, `host/macos/*`, `host/setup-*`, or reset scripts unless asked; they can alter the host or remove agent state. Run `sym` only with `-t <tmpdir>` and `dl` only with `HOME` set to a scratch directory under `.work/`. For checks, use the narrow commands in [development checks](docs/development.md). Keep scripts POSIX `sh` and use only the Python standard library. Fix a `sym` bug with a failing numbered case in `dotfiles/sym-test.sh` first.

Each path belongs to one sync layer (see [sync](docs/sync.md)). Do not `cat` or `rg` binaries in `~/.local/bin`; use `git ls-files dotfiles/*/.local/bin` to list repository scripts.

## Background work

Every 15 minutes, check in on your background shells and processes: still
running as expected, or stuck, spinning, or past its timeout with no output
progress? Kill your own strays promptly; a hung QEMU, test server, or build
watcher left overnight is a bug in your session, not someone else's problem
to discover. Never kill, `pkill`, or `killall` processes you did not start;
if someone else's work saturates the host, report the load and work around
it instead of touching it.
