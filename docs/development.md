# Development checks

## Run checks

Run the narrowest check that covers the change. `sh sync check-parallel` runs the Python files in parallel across `tools`, `dotfiles`, and `host/macos` via pytest and joshuarli-pytest-parallel (see `pytest.ini`). The table lists the per-file runner for each area.

`sh sync check --plan` lists the checks that cover your uncommitted changes (add `--base REV` to include commits since REV), why each was selected, which cannot run on this host, and which changed paths no check covers; `sh sync check --changed` runs them and reports each exit code. The table is generated from `tools/sync/checks.py`; run `python3 -I tools/sync/checks.py docs` after editing the registry.

`--changed --json` records a `tree_fingerprint` for each executed check. It covers HEAD, staged and unstaged tracked changes, and untracked non-ignored files; it excludes ignored files, dependencies, and the environment.

<!-- checks:begin -->
| Changed | Run |
| --- | --- |
| `dotfiles/base/.local/bin/sbx` or its policy spec | `TMPDIR="$PWD/.work/tmp" python3 -I dotfiles/sbx-test.py` and on macOS `TMPDIR="$PWD/.work/tmp" python3 -I dotfiles/sbx-test.py --live` |
| Python link discovery, planning or apply | `python3 -I tools/sync/test_links.py`, `python3 -I tools/sync/test_main.py`, and `python3 -I tools/sync/test_integration.py` |
| `sync` DAG/bootstrap | `python3 -I tools/sync/test_main.py`, `python3 -I tools/sync/test_integration.py`, `sh dotfiles/doctor-test.sh`, `python3 -I tools/sync/test_dag.py`, `sh -n sync`, and `python3 -I tools/sync/test_launcher.py` |
| `tools/decide` | `TMPDIR="$PWD/.work/tmp" python3 -I tools/decide/tests/test_decide.py` and `uvx ruff check tools/decide/src/decide.py tools/decide/tests/test_decide.py` |
| `sync doctor` and default tool inventory | `sh dotfiles/doctor-test.sh`, `sh -n dotfiles/doctor`, `sh -n dotfiles/doctor-test.sh`, `dash -n dotfiles/doctor`, and `dash -n dotfiles/doctor-test.sh` |
| Pi Git tool-call guard | `node dotfiles/pi-git-guard-test.mjs` (no Pi login or network) |
| Pi release pin, installer, launcher, or SDK closure | `TMPDIR="$PWD/.work/tmp" python3 -I tools/pi/test_release_install.py` and `TMPDIR="$PWD/.work/tmp" python3 -I tools/pi/test_offline.py` |
| Pi bridge installation or MCP registration | `python3 -I tools/pi/test_sync_bridge_offline.py` (in a disposable checkout), `python3 -I tools/sync/claude-worker-test.py`, `python3 -I tools/sync/pi-worker-test.py`, and `python3 -I tools/sync/opencode-worker-test.py` |
| Intercom companion installation or MCP/plugin registration | `TMPDIR="$PWD/.work/tmp" python3 -I tools/sync/test_companions.py` |
| `tools/pi-subagent-bridge` | `(export TMPDIR="$PWD/.work/tmp"; cd tools/pi-subagent-bridge && npm test)`; run `./dev-install.sh` once first |
| Pi profile and extensions | `python3 -I dotfiles/pi-test.py` and `python3 -I tools/sync/test_pi_extensions.py` |
| Private tool installer | `python3 -I tools/sync/test_installer.py`, `python3 -I tools/sync/test_ffmpeg_runtime.py`, `sh tools/sync/bootstrap-test.sh`, `sh -n tools/sync/bootstrap.sh`, and `shellcheck -s sh tools/sync/bootstrap.sh` |
| `sync uninstall` | `python3 -I tools/sync/test_uninstall.py` |
| `kache` setup | `python3 -I tools/sync/test_kache.py` |
| `pinact` and workflow pins | `TMPDIR="$PWD/.work/tmp" python3 -I tools/pinact/test_pinact.py`, `TMPDIR="$PWD/.work/tmp" python3 -I tools/pinact/tests/test_yaml.py`, `TMPDIR="$PWD/.work/tmp" python3 -I tools/pinact/tests/test_lint_rules.py`, `TMPDIR="$PWD/.work/tmp" python3 -I tools/pinact/tests/test_expressions.py`, `TMPDIR="$PWD/.work/tmp" python3 -I tools/pinact/tests/test_security.py`, `TMPDIR="$PWD/.work/tmp" python3 -I tools/pinact/tests/test_fix.py`, and `python3 -I dotfiles/base/.local/bin/pinact --check` |
| `yt-dlp` shim | `sh dotfiles/yt-dlp-shim-test.sh` and `shellcheck -s sh dotfiles/base/.local/bin/yt-dlp dotfiles/yt-dlp-shim-test.sh` |
| `pk` process picker | `python3 -I dotfiles/pk-test.py`, `sh -n dotfiles/base/.local/bin/pk`, `dash -n dotfiles/base/.local/bin/pk`, and `shellcheck -s sh dotfiles/base/.local/bin/pk` |
| DeepSeek launcher | `sh dotfiles/dsh-launcher-test.sh` and `shellcheck -s sh dotfiles/base/.local/bin/dsh dotfiles/dsh-launcher-test.sh` |
| Claude API launcher | `sh dotfiles/claude-api-test.sh` and `shellcheck -s sh dotfiles/base/.local/bin/claude-api dotfiles/claude-api-test.sh` |
| `ghostty-fda-check` | `sh dotfiles/ghostty-fda-test.sh` and `shellcheck -s sh dotfiles/base/.local/bin/ghostty-fda-check dotfiles/ghostty-fda-test.sh` |
| a skill or agent definition | `node tools/skills/skills.ts check`, `node tools/skills/skills.ts check --root .agents/skills`, `node --test tools/skills/skills.test.ts`, and `python3 -I dotfiles/skills-campaign-test.py`; `node tools/skills/skills.ts generate` refreshes invocation adapters; use the focused check for other agent configuration |
| model routes, native Pi policy, or generated policy blocks | `node tools/policy/generate.ts --check` and `node --test tools/policy/generate.test.ts`; use `make generate` to refresh projections |
| `orchestrate` skill | `python3 -I dotfiles/orchestrate-test.py` |
| instruction profiles and their harness adapters | `TMPDIR="$PWD/.work/tmp" python3 -I dotfiles/instructions-test.py` |
| git hooks and worktree helpers | `sh dotfiles/reset-agents-test.sh`, `(cd dotfiles && sh pre-push-test.sh)`, `(cd dotfiles && sh worktree-remove-test.sh)`, and `python3 -I dotfiles/worktree-retire-test.py` |
| zsh shim | `(cd dotfiles && sh zsh-shim-test.sh)` |
| a hook or `mdtool` | `python3 -I tools/mdtool/src/mdtool.py selftest`, `sh tools/mdtool/tests/mdtool-test.sh`, and `sh FILE` for each changed match |
| `perf-gate-ready` | `sh dotfiles/perf-gate-ready-test.sh` and `dash dotfiles/perf-gate-ready-test.sh` |
| `host/setup-linux` | `sh host/setup-linux-test.sh` and `shellcheck -s sh host/setup-linux host/setup-linux-test.sh` |
| macOS sync side effects | `python3 -I host/macos/sync-test.py` |
| Linux `power-policy` or its test harness | `sh dotfiles/power-policy-test.sh`, `dash dotfiles/power-policy-test.sh`, `busybox ash dotfiles/power-policy-test.sh`, and `shellcheck -s sh dotfiles/linux/.local/bin/power-policy dotfiles/power-policy-test.sh` |
| a shell script | `shellcheck -s sh FILE` for each changed match and `shellcheck -s sh FILE` for each changed match |
| a Python script | `uvx ruff check FILE` for each changed match and `uvx ty check FILE` for each changed match; both read `ruff.toml` and `ty.toml` |
| Markdown | `python3 -I dotfiles/base/.local/bin/mdtool links --untracked FILE` for each changed match; see below for `mdtool refs`, `router`, and `check` |
| macOS tools | `TMPDIR="$PWD/.work/tmp" python3 -I host/macos/macos-test.py`, `TMPDIR="$PWD/.work/tmp" python3 -I host/macos/lean-test.py`, and `uvx ruff check host/macos/macos host/macos/macos-test.py host/macos/lean.py host/macos/lean-test.py` |
<!-- checks:end -->

`sh sync check` and `./lint` cover several repository areas. Use them for changes that cross areas; they do not replace checks omitted from `sync`.

The [Alpine VM journey](../host/alpine/tests/vm.sh) requires `qemu-system-aarch64`, `qemu-img`, and AArch64 UEFI firmware on the test host. It provisions the committed HEAD in a disposable VM and requires a clean checkout.

## Agent setup changes

| Change | Default proof |
| --- | --- |
| Skill invocation or discovery metadata, global instruction adapters, checker behavior, or fixture behavior | Run the named `SkillCampaignTests` cases that cover the changed mechanism, plus relevant metadata and link checks. Do not run the full suite only because a campaign skill changed. |
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
