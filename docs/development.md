# Development checks

## Run checks

Run the narrowest check that covers the change:

| Changed | Run |
| --- | --- |
| `dotfiles/sym` | `cd dotfiles && sh sym-test.sh`, and `dash sym-test.sh` |
| `dotfiles/base/.local/bin/decide` | `TMPDIR="$PWD/.work/tmp" python3 -I dotfiles/base/.local/bin/decide-test.py` and `uvx ruff check dotfiles/base/.local/bin/decide dotfiles/base/.local/bin/decide-test.py` |
| `dotfiles/base/.local/bin/agent-vm` | `python3 -I dotfiles/agent-vm-test.py`; on macOS with smolvm, `python3 -I dotfiles/agent-vm-test.py --live` for mount/symlink integration |
| `dl` | `sh dotfiles/dl-test.sh` and `shellcheck -s sh dl dotfiles/dl-test.sh` |
| DeepSeek launcher | `sh dotfiles/dsh-launcher-test.sh` and `shellcheck -s sh dotfiles/base/.local/bin/dsh dotfiles/dsh-launcher-test.sh` |
| Claude API launcher | `sh dotfiles/claude-api-test.sh` and `shellcheck -s sh dotfiles/base/.local/bin/claude-api dotfiles/claude-api-test.sh` |
| a skill or agent definition | `sh dotfiles/skills-check.sh dotfiles/base/.agents/skills` (or `.agents/skills` for repo-only skills); use the focused check for other agent configuration |
| local workflow composition | Read the directly composed procedures and applicable global rules; check the affected transitions and effects. A short composition instruction is a behavior change, not wording-only. |
| skill invocation or discovery metadata, global instruction adapters, checker behavior, or fixture behavior | Run the named `SkillCampaignTests` cases that cover the changed mechanism, plus relevant metadata and link checks. Do not run the full suite only because a campaign skill changed. |
| a hook or `mdtool` | the matching `dotfiles/*-test.sh`, or `python3 -I dotfiles/base/.local/bin/mdtool selftest` and `skill-usage selftest` |
| `perf-gate-ready` | `sh dotfiles/perf-gate-ready-test.sh`, and `dash dotfiles/perf-gate-ready-test.sh` |
| `setup-linux` | `sh setup-linux-test.sh` and `shellcheck -s sh setup-linux setup-linux-test.sh` |
| macOS sync side effects | `python3 -I macos/make-sync-test.py` |
| a shell script | `shellcheck -s sh FILE` |
| a Python script | `uvx ruff check FILE`, which reads `ruff.toml` |
| macOS tools | `TMPDIR="$PWD/.work/tmp" python3 -I macos/macos-test.py`, `TMPDIR="$PWD/.work/tmp" python3 -I macos/lean-test.py`, and `uvx ruff check macos/macos macos/macos-test.py macos/lean.py macos/lean-test.py` |

`make check` and `make lint` run all of these across the repo. Use them to close a change that crosses several areas, not to iterate.

## Agent setup changes

| Change | Default proof |
| --- | --- |
| Wording with unchanged meaning | Inspect the diff and relevant references; stop when checked. |
| Rename, removal, or heading/anchor change | Check the changed files and inbound references, including `mdtool links` where links or anchors changed. |
| Local workflow composition | Read the directly composed procedures and applicable global rules; check the specific transitions and effects. A short composition instruction is a behavior change, not wording-only. |
| Invocation metadata, discovery adapter, checker, or fixture code | Run the corresponding named structural tests and relevant metadata or link checks. |
| Broad shared policy, authority, or consequential uncertain behavior | Get one focused independent consistency review and run the smallest behavioral scenario that can resolve the uncertainty. |

Do not run an entire campaign suite only because a campaign skill changed. Reuse successful evidence while its relevant inputs and assumptions remain valid. Do not stack reviews for the same uncertainty or create a process artifact just to report that checking is complete.

After changing Markdown, choose the `mdtool` check that matches the edit: use `links PATH...` for links, headings, or anchors; `refs PATH...` for command and path references; and `router PATH...` for changes to the documentation router. Use `check PATH...` when the change can affect several of those checks. Add `--untracked` for new files. `check` and `consumers` read all tracked text files; path filters limit reported findings, not the files read. Stop once the relevant checks pass and references are current.

## Conventions

Keep shell scripts compatible with macOS `/bin/sh` and dash. Python scripts use only the standard library. Add a failing numbered case to `dotfiles/sym-test.sh` before fixing a `sym` bug, then run the suite under both shells.

Use `TODO.md` for deferred work and `docs/rfc/` when a design needs a decision. The `todo` skill owns both formats.

