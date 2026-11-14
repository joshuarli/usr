Prefix: USR
Next: 67
### USR-64 · P2 · Install rimage from its renamed joshuarli/img repository

- **Area:** sync installer
- **Where:** tools/sync/installer.py install_rimage
- **Problem:** install_rimage still reads releases from joshuarli/rimage, which GitHub now redirects to the public joshuarli/img; the code requires authenticated gh for a private repository and expects rimage-<triple>.zip assets. repomod owned-tool-support reports: installs joshuarli/rimage, which has no owned-tools producer.
- **Recommendation:** Point install_rimage at joshuarli/img, match its current release asset names, decide whether the installed command stays rimage or becomes img, and drop the private-repository gh requirement if img releases are public.
- **Fix with:** uv run --project ~/repos/laputa-systems/stuff repomod lint --repo joshuarli/usr --rule owned-tool-support reports no joshuarli/rimage finding, and python3 -I tools/sync/test_installer.py passes with an img release fixture.
- **Effort:** S


### USR-65 · P3 · Stop installing fs from the archived laputa-systems/fs

- **Area:** sync installer
- **Where:** tools/sync/installer.py install_release owners table
- **Problem:** install_release still installs fs from laputa-systems/fs, which is archived and absent from the stuff fleet catalog, so no maintained repository can receive its bugs or fixes. repomod owned-tool-support reports: installs laputa-systems/fs, which has no owned-tools producer.
- **Recommendation:** Decide whether fs is retired (remove it from the installer, default tool list, and docs) or revived (unarchive it and add it to the stuff fleet catalog and owned-tools policy).
- **Fix with:** repomod lint --repo joshuarli/usr --rule owned-tool-support reports no laputa-systems/fs finding.
- **Effort:** S


### USR-66 · P3 · Run cwd-relative shell tests from dotfiles in sync check

- **Area:** development checks
- **Where:** tools/sync/checks.py perf-gate-ready, perf-gate-ready-dash, ghostty-fda
- **Problem:** sh sync check runs dotfiles/perf-gate-ready-test.sh and dotfiles/ghostty-fda-test.sh from the repository root, but both resolve the script under test as $PWD/base/.local/bin/..., so every case fails with exit 127 on origin/main; from dotfiles/ they pass.
- **Recommendation:** Give these Check entries a dotfiles working directory (or make the tests resolve the script from their own location, like owned-help-test.sh does).
- **Fix with:** sh sync check --changed selects and passes perf-gate-ready, perf-gate-ready-dash, and ghostty-fda after touching dotfiles/base/.local/bin/perf-gate-ready and ghostty-fda-check.
- **Effort:** S

