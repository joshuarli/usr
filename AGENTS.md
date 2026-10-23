# Dotfiles (`~/usr`)

This repository is the source of truth for my home configuration and machine setup. Edit this tree, never `~`.

Use the [README](README.md) to install. See [sync](docs/sync.md), [development checks](docs/development.md), [agent learning](docs/agent-learning.md), [agent VM](docs/agent-vm.md), [macOS preferences](docs/macos-preferences.md), [agent setup](docs/agent-setup.md), the [skills guide](SKILLS.md), the [mdtool reference](docs/mdtool.md), [deferred work](TODO.md), and [RFCs](docs/rfc/).

`make plan` previews home sync. `make check` and `make lint` cover selected checks across several areas; see [development checks](docs/development.md) for narrow commands. Do not run `make`, `dl`, `macos/*`, `setup-*`, or reset scripts unless asked. They can alter the host or remove agent state.

Test `sym` only with `-t <tmpdir>` and `dl` only with `HOME` pointed at a scratch directory under `.work/`. Keep scripts POSIX `sh` and use only the Python standard library. Fix a `sym` bug with a failing numbered case in `dotfiles/sym-test.sh` first.

Each path belongs to one sync layer. Do not `cat` or `rg` binaries in `~/.local/bin`; use `git ls-files dotfiles/*/.local/bin` to list repository scripts.
