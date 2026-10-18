Prefix: USR
Next: 16

### USR-5 · P2 · Push rules do not require user approval

- **Area:** Security
- **Where:** `dotfiles/base/.codex/config.toml:7-8`, `dotfiles/base/.codex/rules/default.rules:7-13`, `dotfiles/base/.config/git/hooks/pre-push:3-8`
- **Problem:** The Codex profile sets `approval_policy = "never"` with full filesystem access. `codex execpolicy check` returns no matching rule for `git -C . push`, and the global pre-push hook permits a push whenever stderr is a terminal. A hook reproduction with non-TTY stdin and PTY stderr exited successfully. No push was attempted.
- **Recommendation:** Require an explicit interactive approval at the final push boundary, and fail closed when that approval cannot be obtained.
- **Fix with:** none
- **Effort:** M
- **Design:** [USR-5 RFC](docs/rfc/USR-5-push-approval.md)

### USR-14 · P3 · PR lookup errors look like missing pull requests

- **Area:** CLI
- **Where:** `dotfiles/base/.local/bin/gh-cancel-pr-runs:60-80`
- **Problem:** `gh pr view` stderr is discarded and its failure is treated as an empty head SHA. Authentication and API failures are reported as “no PR found,” hiding the cause from the caller.
- **Recommendation:** Preserve the `gh pr view` status and diagnostic; report a missing PR only when the lookup succeeds without a result.
- **Fix with:** none
- **Effort:** S

### USR-15 · P3 · Failed preserved-service checks still exit successfully

- **Area:** macOS
- **Where:** `macos/macos-lean.py:955-960`, `macos/macos-lean.py:1295-1298`, `macos/macos-lean.py:1420`
- **Problem:** `ensure_service()` increments `verify_fail` when `launchctl print` fails, but `main()` still returns 0 after printing a warning. Scripts and automation therefore treat an unverified preserved service as a successful apply.
- **Recommendation:** Return a nonzero status when one or more preserved services fail verification.
- **Fix with:** none
- **Effort:** S
