Prefix: USR
Next: 14

### USR-5 · P2 · Push rules do not require user approval

- **Area:** Security
- **Where:** `dotfiles/base/.codex/config.toml:7-8`, `dotfiles/base/.codex/rules/default.rules:7-13`, `dotfiles/base/.config/git/hooks/pre-push:3-8`
- **Problem:** The Codex profile sets `approval_policy = "never"` with full filesystem access. `codex execpolicy check` returns no matching rule for `git -C . push`, and the global pre-push hook permits a push whenever stderr is a terminal. A hook reproduction with non-TTY stdin and PTY stderr exited successfully. No push was attempted.
- **Recommendation:** Require an explicit interactive approval at the final push boundary, and fail closed when that approval cannot be obtained.
- **Fix with:** none
- **Effort:** M
- **Design:** [USR-5 RFC](docs/rfc/USR-5-push-approval.md)

### USR-12 · P3 · `sym` can loop forever for a root-level target path

- **Area:** Operability
- **Where:** `dotfiles/sym:52-55`
- **Problem:** For a destination such as `/.bashrc`, `${1%/*}` becomes empty. The loop keeps trimming the empty path and never reaches an existing directory. A shell expansion reproduction confirmed the empty ancestor.
- **Recommendation:** Handle `/` explicitly when finding the nearest existing parent.
- **Fix with:** os-boundaries
- **Effort:** S

### USR-13 · P3 · Stale PR cleanup exits successfully after branch deletion errors

- **Area:** Errors
- **Where:** `dotfiles/base/.local/bin/close-stale-prs.py:406-419`
- **Problem:** A failed branch deletion prints an error and continues, but `main()` returns 0 after the loop. Automation can treat a partial cleanup as complete.
- **Recommendation:** Preserve the per-branch attempts and return a nonzero status if any deletion failed.
- **Fix with:** error-model
- **Effort:** S

### USR-3 · P4 · `mdtool` reports false positives on this repo

- **Area:** Docs
- **Where:** `dotfiles/base/.local/bin/mdtool:344`, `dotfiles/base/.local/bin/mdtool:451-452`, `dotfiles/base/.local/bin/mdtool:493-500`, `dotfiles/base/.local/bin/mdtool:702-712`
- **Problem:** `R001` strips a leading dot before checking paths. `P002` flags ordinary section wording and dotted numbers in Python docstrings. A scoped `router` command that selects only a docs file reports `T000` even though the repository has a tracked root `AGENTS.md`; `python3 -I dotfiles/base/.local/bin/mdtool router docs/mdtool.md --quiet --json` reproduces it.
- **Recommendation:** Preserve leading dots during path normalization, narrow `P002` to actual section references, and discover router root files from repository context when a doc path is selected. Add a failing `mdtool selftest` case for each behavior before fixing it.
- **Fix with:** none
- **Effort:** S
