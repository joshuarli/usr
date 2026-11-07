Prefix: USR
Next: 38

### USR-5 · P2 · Push rules do not require user approval

- **Area:** Security
- **Where:** `dotfiles/base/.codex/config.toml:7-8`, `dotfiles/base/.config/git/hooks/pre-push:3-8`
- **Problem:** The Codex profile sets `approval_policy = "never"` with full filesystem access. `codex execpolicy check` returns no matching rule for `git -C . push`, and the global pre-push hook permits a push whenever stderr is a terminal. A hook reproduction with non-TTY stdin and PTY stderr exited successfully. No push was attempted.
- **Recommendation:** Require an explicit interactive approval at the final push boundary, and fail closed when that approval cannot be obtained.
- **Fix with:** none
- **Effort:** M
- **Design:** [USR-5 RFC](docs/rfc/USR-5-push-approval.md)

### USR-24 · P2 · Bootstrap pinned Python on minimal Alpine before the sync DAG

- **Area:** Sync / portability
- **Where:** `sync` POSIX bootstrap, `tools/sync/main.py`, `tools/sync/bootstrap.sh`, `host/setup-linux`
- **Problem:** The Python DAG runner needs Python 3.9+ before it can execute. macOS can use the existing shell-based `python-build` installer to install the managed runtime, but Alpine currently needs an already runnable Python. Production `python-build` Linux artifacts still list `libgcc` in their runtime requirements; automatically fetching those binaries would introduce an unwanted system dependency. Alpine provisioning and fresh `sh sync` therefore do not yet have a self-contained bootstrap guarantee.
- **Recommendation:** After `laputa-systems/python-build` removes the actual `libgcc_s.so.1` dependency from both Linux musl archives and proves it in minimal-container smoke tests, implement a minimal POSIX-shell bootstrap for Alpine x86_64 and aarch64. Pin the release artifact identity and SHA-256 independently of release metadata, verify before extraction, reject unsafe archive paths, stage and atomically switch the Python runtime, and smoke-test `sqlite3`/`ssl` before invoking the Python DAG. Avoid adding `libgcc`, a package-manager Python, or a second installer engine. Test fresh Alpine without Python or libgcc, interrupted download, existing installations, and second-run idempotency.
- **Fix with:** `sync` bootstrap and python-build release qualification
- **Effort:** M

### USR-32 · P3 · Concurrent campaign allowances can overwrite each other

- **Area:** Concurrency
- **Where:** `dotfiles/base/.local/bin/codex-campaign-closeout.py:132-168`, `dotfiles/base/.local/bin/codex-campaign-closeout.py:171-197`, `dotfiles/base/.local/bin/codex-campaign-closeout.py:252-274`, `dotfiles/base/.local/bin/codex-campaign-closeout.py:337-356`
- **Problem:** Two concurrently invoked allow commands both load the current allowed dictionary, add different worktrees locally, then atomically replace the same state file without a lock or generation check. The last writer discards the other's allowance; the Stop hook later blocks on a worktree that was reported as allowed. This is a source-grounded concurrent interleaving, not yet exercised as a two-process fixture.
- **Recommendation:** Serialize allow updates or use a compare-and-retry revision/lock around load-modify-save, and reproduce two processes adding disjoint allowances with a barrier. Keep the existing state validation.
- **Fix with:** `durable-state`
- **Effort:** S
