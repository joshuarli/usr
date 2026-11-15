Prefix: USR
Next: 73







### USR-69 · P1 · Companion upgrades and uninstall delete unowned or modified files

- **Area:** Sync ownership
- **Where:** tools/sync/companions.py:112-123,243-275,517-531; tools/sync/uninstall.py:25-50; tools/sync/test_companions.py:255-279,345-359
- **Problem:** Confirmed with isolated real installer/uninstaller calls: create agent-intercom-codex/foreign.txt under a scratch HOME with no dl-owned record or companion receipt, then call uninstall.uninstall(Context(...)); the directory and file are deleted. Separately install a local fixture companion, add personal.txt, and request a new pin: install_status reports modified for the old pin but stale for the new one, and install_companion replaces the tree and deletes personal.txt. Removal never checks the receipt or inventory, while upgrades check pin mismatch before inventory. The normal ownership preflight does not cover these companion roots, so ordinary sync uninstall or a pin upgrade can lose user files. Intact owned installation/removal controls passed.
- **Recommendation:** Validate receipt shape and companion identity, then compare its recorded inventory with the live tree independently of the desired pin before removal or replacement. Preflight every companion root before changing registrations or deleting anything; preserve or refuse unknown and modified roots and recheck at the destructive step. Add boundary regressions for unrecorded foreign roots, modified installed roots on uninstall, modified roots across a pin bump, and intact owned controls; use only disposable homes and local fixture archives.
- **Fix with:** os-boundaries
- **Effort:** M









