# Dotfiles (`~/usr`)

This repository is the source of truth for my home configuration and machine setup. Edit this tree, never `~`.

Use the [README](README.md) to install. See [sync](docs/sync.md), [development](docs/development.md), [agent setup](docs/agent-setup.md), the [mdtool reference](docs/mdtool.md), [deferred work](TODO.md), and [RFCs](docs/rfc/) for repository details.

## Commands

- `make plan` previews the home sync. Run the narrowest check that covers the change, listed in [development](docs/development.md); `make check` and `make lint` run every check across the repo.
- Do not run `make`, `dl`, `macos/*`, `setup-*`, or reset scripts unless asked. They can download tools, change `~`, install system services, or delete agent state.
- Test `sym` only with `-t <tmpdir>`; its default target is `$HOME`.
- Test `dl` only with `HOME` pointed at a scratch directory under `.work/`.
- Do not `cat` or `rg` the binaries in `~/.local/bin`; `git ls-files dotfiles/*/.local/bin` lists the scripts that are mine.

## Invariants

- Each path belongs to one layer. Do not create a second claim.
- Keep scripts POSIX `sh`; use only the Python standard library.
- Fix a `sym` bug with a failing numbered test in `dotfiles/sym-test.sh` first.
- Changes to agent setup require `dotfiles-health` and the narrowest check that covers the change.
- File deferred work in `TODO.md` and designs in `docs/rfc/` using the `todo` skill.
- Do not format, commit, or push unless asked.
