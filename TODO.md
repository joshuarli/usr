Prefix: USR
Next: 66
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

