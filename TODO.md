Prefix: USR
Next: 73







### USR-69 · P1 · Companion upgrades and uninstall delete unowned or modified files

- **Area:** Sync ownership
- **Where:** tools/sync/companions.py:112-123,243-275,517-531; tools/sync/uninstall.py:25-50; tools/sync/test_companions.py:255-279,345-359
- **Problem:** Confirmed with isolated real installer/uninstaller calls: create agent-intercom-codex/foreign.txt under a scratch HOME with no dl-owned record or companion receipt, then call uninstall.uninstall(Context(...)); the directory and file are deleted. Separately install a local fixture companion, add personal.txt, and request a new pin: install_status reports modified for the old pin but stale for the new one, and install_companion replaces the tree and deletes personal.txt. Removal never checks the receipt or inventory, while upgrades check pin mismatch before inventory. The normal ownership preflight does not cover these companion roots, so ordinary sync uninstall or a pin upgrade can lose user files. Intact owned installation/removal controls passed.
- **Recommendation:** Validate receipt shape and companion identity, then compare its recorded inventory with the live tree independently of the desired pin before removal or replacement. Preflight every companion root before changing registrations or deleting anything; preserve or refuse unknown and modified roots and recheck at the destructive step. Add boundary regressions for unrecorded foreign roots, modified installed roots on uninstall, modified roots across a pin bump, and intact owned controls; use only disposable homes and local fixture archives.
- **Fix with:** os-boundaries
- **Effort:** M


### USR-70 · P2 · Fleet apply runs the old checkout after fetching fails

- **Area:** Fleet sync
- **Where:** tools/sync/fleet.py:34-46,119-136; tools/sync/test_fleet.py:88-104
- **Problem:** Confirmed through real fleet.visit and PULL_SCRIPT in a disposable local Git checkout: after a successful-fetch control, point origin at a nonexistent local bare repository and run apply. REPO_SCRIPT prints fetch=failed and exits 0, but visit skips only pull=blocked and still invokes sh sync apply --json; the fixture sync writes its applied marker. The summary later reports the fetch failure, but the stale checkout has already mutated the host, violating the pull-before-apply dependency.
- **Recommendation:** Make apply require a successfully completed repository update phase. Treat fetch failure and unexpected repository-command exits as a per-host failure and skip sync before mutation. Preserve the existing read-only plan/doctor policy. Add a local-Git boundary test proving failed fetch never invokes apply, alongside successful fetch/fast-forward and blocked-pull controls.
- **Fix with:** root-cause
- **Effort:** S


### USR-71 · P2 · Fleet doctor reports success when a host doctor fails

- **Area:** Fleet diagnostics
- **Where:** tools/sync/fleet.py:140-144,183-217,234-245; tools/sync/main.py:450-464; tools/sync/report.py:53-54
- **Problem:** Confirmed using real main.main doctor JSON output and real fleet.main/visit/render with controlled graph probes and the legacy doctor edge. Healthy control returns doctor_exit=0/fleet_exit=0. A missing required probe returns doctor_exit=1/fleet_exit=0 with a green '1 to apply'; a legacy-only diagnostic failure returns doctor_exit=1/fleet_exit=0 with a green '1 up to date'. visit discards nonzero subprocess status whenever JSON parses, healthy treats apply as success, and main emits its JSON before running the legacy doctor. Fleet automation can therefore certify an unhealthy host as healthy and suppress the reason.
- **Recommendation:** Retain the child exit status in each host outcome and make any failed doctor fail the aggregate even when valid JSON was emitted. Treat required apply states as unhealthy for doctor without changing plan semantics, and surface legacy doctor failure details through the structured result or stderr. Add boundary tests for healthy, missing-probe, and legacy-only failure cases using the real doctor and fleet rendering paths.
- **Fix with:** error-model
- **Effort:** S





