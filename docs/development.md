# Development checks

## Run checks

Run the narrowest check that covers the change. `make check-parallel` runs the Python files in parallel across `dotfiles` and `macos` via pytest and joshuarli-pytest-parallel (see `pytest.ini`). The table lists the per-file runner for each area.

| Changed | Run |
| --- | --- |
| `dotfiles/base/.local/bin/sbx` or its policy spec | `TMPDIR="$PWD/.work/tmp" python3 -I dotfiles/sbx-test.py`; on each actual target OS also run `TMPDIR="$PWD/.work/tmp" python3 -I dotfiles/sbx-test.py --live` |
| `dotfiles/sym` | `cd dotfiles && sh sym-test.sh`, and `dash sym-test.sh` |
| `tools/decide` | `TMPDIR="$PWD/.work/tmp" python3 -I tools/decide/tests/test_decide.py` and `uvx ruff check tools/decide/src/decide.py tools/decide/tests/test_decide.py` |
| Session search, transcript adapters, and normalization | `TMPDIR="$PWD/.work/tmp" uv run --no-project --python '>=3.15' python -I tools/agent-memory/tests/test_sessions.py` and `TMPDIR="$PWD/.work/tmp" python3 -I dotfiles/base/.local/bin/skill-usage selftest` |
| Agent learning | `TMPDIR="$PWD/.work/tmp" uv run --no-project --python '>=3.15' python -I tools/agent-memory/tests/test_learning.py`, `TMPDIR="$PWD/.work/tmp" uv run --no-project --python '>=3.15' python -I tools/agent-memory/tests/test_learning_review.py`, `TMPDIR="$PWD/.work/tmp" uv run --no-project --python '>=3.15' python -I tools/agent-memory/tests/test_learning_promote.py`, and `TMPDIR="$PWD/.work/tmp" uv run --no-project --python '>=3.15' python -I tools/agent-memory/tests/test_learning_ops.py` |
| Recall, experience capture, and lifecycle | `TMPDIR="$PWD/.work/tmp" uv run --no-project --python '>=3.15' python -I tools/agent-memory/tests/test_recall.py` |
| Retrieval benchmark | `uv run --no-project --python '>=3.15' python -I tools/agent-memory/eval/bench_recall.py validate`, then `TMPDIR="$PWD/.work/tmp" uv run --no-project --python '>=3.15' python -I tools/agent-memory/eval/bench_recall.py run --split dev` (offline; see [agent learning](../tools/agent-memory/README.md#evaluation)) |
| Live evaluation fixtures | `TMPDIR="$PWD/.work/tmp" uv run --no-project --python '>=3.15' python -I tools/agent-memory/eval/test_live_learning.py` and `TMPDIR="$PWD/.work/tmp" uv run --no-project --python '>=3.15' python -I tools/agent-memory/eval/test_live_recall.py` (no inference) |
| `dl` | `sh dotfiles/dl-test.sh` and `shellcheck -s sh dl dotfiles/dl-test.sh` |
| DeepSeek launcher | `sh dotfiles/dsh-launcher-test.sh` and `shellcheck -s sh dotfiles/base/.local/bin/dsh dotfiles/dsh-launcher-test.sh` |
| Claude API launcher | `sh dotfiles/claude-api-test.sh` and `shellcheck -s sh dotfiles/base/.local/bin/claude-api dotfiles/claude-api-test.sh` |
| a skill or agent definition | `sh dotfiles/skills-check.sh dotfiles/base/.agents/skills` (or `.agents/skills` for repo-only skills); use the focused check for other agent configuration |
| local workflow composition | Read the directly composed procedures and applicable global rules; check the affected transitions and effects. A short composition instruction is a behavior change, not wording-only. |
| skill invocation or discovery metadata, global instruction adapters, checker behavior, or fixture behavior | Run the named `SkillCampaignTests` cases that cover the changed mechanism, plus relevant metadata and link checks. Do not run the full suite only because a campaign skill changed. |
| a hook or `mdtool` | the matching `tools/mdtool/tests/*-test.sh`, or `python3 -I tools/mdtool/src/mdtool.py selftest` and `skill-usage selftest` |
| `perf-gate-ready` | `sh dotfiles/perf-gate-ready-test.sh`, and `dash dotfiles/perf-gate-ready-test.sh` |
| `setup-linux` | `sh setup-linux-test.sh` and `shellcheck -s sh setup-linux setup-linux-test.sh` |
| macOS sync side effects | `python3 -I macos/make-sync-test.py` |
| a shell script | `shellcheck -s sh FILE` |
| a Python script | `uvx ruff check FILE` and `uvx ty check FILE`, which read `ruff.toml` and `ty.toml` |
| macOS tools | `TMPDIR="$PWD/.work/tmp" python3 -I macos/macos-test.py`, `TMPDIR="$PWD/.work/tmp" python3 -I macos/lean-test.py`, and `uvx ruff check macos/macos macos/macos-test.py macos/lean.py macos/lean-test.py` |

`make check` and `make lint` cover several repository areas. Use them for changes that cross areas; they do not replace checks omitted from the Makefile.

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

