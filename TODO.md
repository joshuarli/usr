Prefix: USR
Next: 17

### USR-5 · P2 · Push rules do not require user approval

- **Area:** Security
- **Where:** `dotfiles/base/.codex/config.toml:7-8`, `dotfiles/base/.config/git/hooks/pre-push:3-8`
- **Problem:** The Codex profile sets `approval_policy = "never"` with full filesystem access. `codex execpolicy check` returns no matching rule for `git -C . push`, and the global pre-push hook permits a push whenever stderr is a terminal. A hook reproduction with non-TTY stdin and PTY stderr exited successfully. No push was attempted.
- **Recommendation:** Require an explicit interactive approval at the final push boundary, and fail closed when that approval cannot be obtained.
- **Fix with:** none
- **Effort:** M
- **Design:** [USR-5 RFC](docs/rfc/USR-5-push-approval.md)

### USR-15 · P3 · Failed preserved-service checks still exit successfully

- **Area:** macOS
- **Where:** `macos/lean.py:979-1007`, `macos/lean.py:1322-1330`, `macos/lean.py:1451`
- **Problem:** `ensure_service()` increments `verify_fail` when `launchctl print` fails, but `main()` still returns 0 after printing a warning. Scripts and automation therefore treat an unverified preserved service as a successful apply.
- **Recommendation:** Return a nonzero status when one or more preserved services fail verification.
- **Fix with:** none
- **Effort:** S

### USR-16 · P3 · Claude API logs inherit permissive permissions

- **Area:** Security
- **Where:** `dotfiles/base/.local/bin/claude-api:48-52`, `dotfiles/base/.local/bin/claude-api:105`
- **Problem:** The launcher writes raw prompt and tool events under `.work/logs` without setting directory or file permissions. A synthetic file created under the current shell's `umask 022` had mode `0644`. Any local account that can traverse the repository can read the event stream, which may contain sensitive prompts, tool input, and results.
- **Recommendation:** Set a private umask before creating the log directory and file, then enforce private permissions on existing log paths.
- **Fix with:** `security`
- **Effort:** S
