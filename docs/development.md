# Development checks

## Run checks

Run the narrowest check that covers the change. `sh sync check-parallel` runs the Python files in parallel across `tools`, `dotfiles`, and `host/macos` via pytest and joshuarli-pytest-parallel (see `pytest.ini`). The table lists the per-file runner for each area.

| Changed | Run |
| --- | --- |
| `dotfiles/base/.local/bin/sbx` or its policy spec | `TMPDIR="$PWD/.work/tmp" python3 -I dotfiles/sbx-test.py`; on macOS also run `TMPDIR="$PWD/.work/tmp" python3 -I dotfiles/sbx-test.py --live` |
| Python link discovery, planning or apply | `python3 -I tools/sync/test_links.py`, `python3 -I tools/sync/test_main.py`, and `python3 -I tools/sync/test_integration.py` |
| `tools/decide` | `TMPDIR="$PWD/.work/tmp" python3 -I tools/decide/tests/test_decide.py` and `uvx ruff check tools/decide/src/decide.py tools/decide/tests/test_decide.py` |
| `sync doctor` and default tool inventory | `sh dotfiles/doctor-test.sh`, `sh -n dotfiles/doctor`, `sh -n dotfiles/doctor-test.sh`, `dash -n dotfiles/doctor`, and `dash -n dotfiles/doctor-test.sh` |
| Pi Git tool-call guard | `node dotfiles/pi-git-guard-test.mjs` (no Pi login or network) |
| Pi release pin, installer, launcher, or SDK closure | `TMPDIR="$PWD/.work/tmp" python3 -I tools/pi/test_release_install.py` and `TMPDIR="$PWD/.work/tmp" python3 -I tools/pi/test_offline.py`; see [bridge checks](../tools/pi-subagent-bridge/README.md#tests) for affected delegation behavior |
| Pi bridge installation or MCP registration | `python3 -I tools/pi/test_sync_bridge_offline.py` in a disposable checkout, plus the affected `tools/sync/*worker-test.py` cases |
| `sync` DAG/bootstrap | `python3 -I tools/sync/test_dag.py`, `python3 -I tools/sync/test_main.py`, `python3 -I tools/sync/test_integration.py`, `sh -n sync`, and `sh dotfiles/doctor-test.sh` |
| Private tool installer | `python3 -I tools/sync/test_installer.py`, `python3 -I tools/sync/test_ffmpeg_runtime.py`, `sh tools/sync/bootstrap-test.sh`, `sh -n tools/sync/bootstrap.sh`, and `shellcheck -s sh tools/sync/bootstrap.sh` |
| `yt-dlp` shim | `sh dotfiles/yt-dlp-shim-test.sh` and `shellcheck -s sh dotfiles/base/.local/bin/yt-dlp dotfiles/yt-dlp-shim-test.sh` |
| `pk` process picker | `python3 -I dotfiles/pk-test.py`, `sh -n dotfiles/base/.local/bin/pk`, `dash -n dotfiles/base/.local/bin/pk`, and `shellcheck -s sh dotfiles/base/.local/bin/pk` |
| DeepSeek launcher | `sh dotfiles/dsh-launcher-test.sh` and `shellcheck -s sh dotfiles/base/.local/bin/dsh dotfiles/dsh-launcher-test.sh` |
| Claude API launcher | `sh dotfiles/claude-api-test.sh` and `shellcheck -s sh dotfiles/base/.local/bin/claude-api dotfiles/claude-api-test.sh` |
| `ghostty-fda-check` | `sh dotfiles/ghostty-fda-test.sh` and `shellcheck -s sh dotfiles/base/.local/bin/ghostty-fda-check dotfiles/ghostty-fda-test.sh` |
| a skill or agent definition | `sh dotfiles/skills-check.sh dotfiles/base/.agents/skills` (or `.agents/skills` for repo-only skills); use the focused check for other agent configuration |
| model routes, native Pi policy, or generated policy blocks | `make check-generated`, `node --test tools/policy/generate.test.ts`, and the affected [bridge checks](../tools/pi-subagent-bridge/README.md#tests); use `make generate` to refresh projections |
| local workflow composition | Read the directly composed procedures and applicable global rules; check the affected transitions and effects. A short composition instruction is a behavior change, not wording-only. |
| skill invocation or discovery metadata, global instruction adapters, checker behavior, or fixture behavior | Run the named `SkillCampaignTests` cases that cover the changed mechanism, plus relevant metadata and link checks. Do not run the full suite only because a campaign skill changed. |
| a hook or `mdtool` | the matching `tools/mdtool/tests/*-test.sh`, or `python3 -I tools/mdtool/src/mdtool.py selftest` |
| `perf-gate-ready` | `sh dotfiles/perf-gate-ready-test.sh`, and `dash dotfiles/perf-gate-ready-test.sh` |
| `host/setup-linux` | `sh host/setup-linux-test.sh` and `shellcheck -s sh host/setup-linux host/setup-linux-test.sh` |
| macOS sync side effects | `python3 -I host/macos/sync-test.py` |
| Linux `power-policy` or its test harness | `sh dotfiles/power-policy-test.sh`, `dash dotfiles/power-policy-test.sh`, `busybox ash dotfiles/power-policy-test.sh`, and `shellcheck -s sh dotfiles/linux/.local/bin/power-policy dotfiles/power-policy-test.sh` when available |
| a shell script | `shellcheck -s sh FILE` |
| a Python script | `uvx ruff check FILE` and `uvx ty check FILE`, which read `ruff.toml` and `ty.toml` |
| macOS tools | `TMPDIR="$PWD/.work/tmp" python3 -I host/macos/macos-test.py`, `TMPDIR="$PWD/.work/tmp" python3 -I host/macos/lean-test.py`, and `uvx ruff check host/macos/macos host/macos/macos-test.py host/macos/lean.py host/macos/lean-test.py` |

`sh sync check` and `./lint` cover several repository areas. Use them for changes that cross areas; they do not replace checks omitted from `sync`.

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

Keep shell scripts compatible with macOS `/bin/sh` and dash. Python scripts use only the standard library. Add a failing numbered case to `tools/sync/test_links.py` before modifying link reconciliation; run the Python suite and the scratch-home integration tests.

Use `TODO.md` for deferred work and create an RFC under `docs/rfc/` when a design needs a decision. The `todo` skill owns both formats.

`README.md` is a clean, up-to-date end-user guide: what the project is, how to get and use it, configuration and output users need, where to get help, and license. Keep developer setup, architecture, internals, and contributor workflow in `AGENTS.md` or `docs/`.

Use the supported Node version (currently at least 26.12.0) for Pi runtime checks. `test_offline.py` skips its runtime cases when Node is absent or below major 26; a green suite with skips does not verify SDK loading. `test_sync_bridge_offline.py` creates and removes an ignored bridge dependency link and refuses an existing installation, so use a disposable checkout. Live provider checks require local account authentication and remain separate from fixture proof.
