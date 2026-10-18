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

### USR-10 · P2 · macOS Lean skips later performance defaults

- **Area:** Operability
- **Where:** `macos/macos-lean.py:1120-1142`
- **Problem:** `any(ensure_default(spec) for spec in PERFORMANCE_DEFAULTS)` stops at the first changed setting. Later preferences are skipped, while the script reports the group as applied. A small Python reproduction confirmed generator evaluation stopped at the first true result.
- **Recommendation:** Attempt every preference and accumulate whether any changed.
- **Fix with:** isolate-effects
- **Effort:** S

### USR-1 · P3 · The local DNS cache falls back to Cloudflare in the clear

- **Area:** Security
- **Where:** `macos/setup-macos:223`, `macos/setup-macos:246`, `macos/setup-macos:283`
- **Problem:** The system resolver list is `127.0.0.1 1.1.1.1`, so a stopped unbound sends queries to Cloudflare over plain DNS. unbound also runs as root (`username: ""`, line 169). Both choices are deliberate, but the failure mode has not been revisited.
- **Recommendation:** Choose whether to remove the plain DNS fallback, keep the availability tradeoff, or configure an encrypted upstream. See the RFC.
- **Fix with:** none
- **Effort:** S
- **Design:** [USR-1 RFC](docs/rfc/USR-1-dns-fallback.md)

### USR-2 · P3 · The auto-triggered skills have never been measured

- **Area:** Tests
- **Where:** `.agents/skills/dotfiles-health/SKILL.md:33-35`, `dotfiles/base/.agents/skills/`
- **Problem:** The repository records that auto-triggered skills have not been evaluated against real sessions. Nothing in the repository shows whether they fire at the right times or change behavior. Session data is outside this repository review.
- **Recommendation:** Run `skill-eval` on the auto-triggered skills, inspect loads and misses in real sessions, and retune, demote, or remove each skill based on the results.
- **Fix with:** skill-eval
- **Effort:** M

### USR-11 · P3 · CI cancellation reports success when listing runs fails

- **Area:** Errors
- **Where:** `dotfiles/base/.local/bin/gh-cancel-pr-runs:84-92`
- **Problem:** If `gh run list` fails, command substitution produces an empty `run_ids`. The script then prints `no active runs found` and exits 0, so callers cannot distinguish an API or authentication failure from a successful empty result.
- **Recommendation:** Check the `gh run list` exit status and return a failure before interpreting an empty result.
- **Fix with:** error-model
- **Effort:** S

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
