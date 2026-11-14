Prefix: USR
Next: 67




### USR-66 · P3 · Run cwd-relative shell tests from dotfiles in sync check

- **Area:** development checks
- **Where:** tools/sync/checks.py perf-gate-ready, perf-gate-ready-dash, ghostty-fda
- **Problem:** sh sync check runs dotfiles/perf-gate-ready-test.sh and dotfiles/ghostty-fda-test.sh from the repository root, but both resolve the script under test as $PWD/base/.local/bin/..., so every case fails with exit 127 on origin/main; from dotfiles/ they pass.
- **Recommendation:** Give these Check entries a dotfiles working directory (or make the tests resolve the script from their own location, like owned-help-test.sh does).
- **Fix with:** sh sync check --changed selects and passes perf-gate-ready, perf-gate-ready-dash, and ghostty-fda after touching dotfiles/base/.local/bin/perf-gate-ready and ghostty-fda-check.
- **Effort:** S

