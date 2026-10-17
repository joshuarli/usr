# Development checks

## Run checks

Run the narrowest check that covers the change:

| Changed | Run |
| --- | --- |
| `dotfiles/sym` | `cd dotfiles && sh sym-test.sh`, and `dash sym-test.sh` |
| `dl` | `sh dotfiles/dl-test.sh` and `shellcheck -s sh dl dotfiles/dl-test.sh` |
| a skill or agent definition | `sh dotfiles/skills-check.sh dotfiles/base/.agents/skills` (or `.agents/skills` for the repo-only ones), then `python3 -I dotfiles/skills-campaign-test.py` |
| a hook or `mdtool` | the matching `dotfiles/*-test.sh`, or `python3 -I dotfiles/base/.local/bin/mdtool selftest` and `skill-usage selftest` |
| `perf-gate-ready` | `sh dotfiles/perf-gate-ready-test.sh`, and `dash dotfiles/perf-gate-ready-test.sh` |
| a shell script | `shellcheck -s sh FILE` |
| a Python script | `uvx ruff check FILE`, which reads `ruff.toml` |

`make check` and `make lint` run all of these across the repo. Use them to close a change that crosses several areas, not to iterate.

Run `python3 -I dotfiles/base/.local/bin/mdtool check` after changing repository docs. It checks links, references, consumers, source pointers, duplicate blocks, and the docs router. Warnings and notes do not change its exit status.

## Conventions

Keep shell scripts compatible with macOS `/bin/sh` and dash. Python scripts use only the standard library. Add a failing numbered case to `dotfiles/sym-test.sh` before fixing a `sym` bug, then run the suite under both shells.

Use `TODO.md` for deferred work and `docs/rfc/` when a design needs a decision. The `todo` skill owns both formats.

