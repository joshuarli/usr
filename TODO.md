Prefix: USR
Next: 68




### USR-66 · P3 · Run cwd-relative shell tests from dotfiles in sync check

- **Area:** development checks
- **Where:** tools/sync/checks.py perf-gate-ready, perf-gate-ready-dash, ghostty-fda
- **Problem:** sh sync check runs dotfiles/perf-gate-ready-test.sh and dotfiles/ghostty-fda-test.sh from the repository root, but both resolve the script under test as $PWD/base/.local/bin/..., so every case fails with exit 127 on origin/main; from dotfiles/ they pass.
- **Recommendation:** Give these Check entries a dotfiles working directory (or make the tests resolve the script from their own location, like owned-help-test.sh does).
- **Fix with:** sh sync check --changed selects and passes perf-gate-ready, perf-gate-ready-dash, and ghostty-fda after touching dotfiles/base/.local/bin/perf-gate-ready and ghostty-fda-check.
- **Effort:** S


### USR-67 · P3 · Interactive Pi writes lastChangelogVersion into the tracked settings.json

- **Area:** Pi
- **Where:** `dotfiles/base/.pi/agent/settings.json` (linked as `~/.pi/agent/settings.json`)
- **Problem:** The first interactive Pi start after a runtime change appends `"lastChangelogVersion": "1.5.0"` to the settings file, which is a link into the checkout; observed on mac and lisa on 2026-11-14 after adopting release-headless-usr-f6fc723. The checkout becomes dirty, which blocks fast-forward pulls on hosts and risks committing machine state.
- **Recommendation:** Keep Pi's mutable state out of the tracked file: give Pi a tracked read-only base plus an untracked local override if Pi supports one, or seed lastChangelogVersion in the tracked file from the runtime pin so the write is a no-op.
- **Fix with:** Start interactive Pi with a fresh agent dir linked to the tracked settings and assert git status stays clean
- **Effort:** S

