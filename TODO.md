Prefix: USR
Next: 39

### USR-38 · P1 · Finish self-contained Pi runtime and intercom activation

- **Area:** Dependency packaging / agent coordination
- **Where:** `vendor/pi/`, `tools/sync/{installer,main,pi_extensions,pi-worker,claude-worker,opencode-worker}.py`, `tools/pi-subagent-bridge/`, `dotfiles/base/.pi/agent/settings.json`
- **Problem:** `vendor/pi/` currently contains audited upstream *source* snapshots, not the Pi executable, SDK build, transitive runtime closure, or Claude/Codex/OpenCode intercom adapters. Normal `sh sync` still invokes npm for Pi CLI and bridge dependencies, and `pi install/update` for extensions. The intercom adapter cannot yet be activated offline and should not be confused with working runtime integration.
- **Recommendation:** Use `/pi-update` to vendor/build a complete verified distributable from pinned upstream SHAs, wire local package paths, remove all npm/registry paths from routine Pi setup, and prove Pi CLI, SDK, worker RPC, Muse and intercom via fresh cacheless cross-harness smoke tests. Preserve the typed tier guard, worktree leases and parent-only authority; use intercom for messaging only, and disable unsolicited wakeups by default.
- **Fix with:** `pi-update`
- **Effort:** XL

### USR-5 · P2 · Push rules do not require user approval

- **Area:** Security
- **Where:** `dotfiles/base/.codex/config.toml:7-8`, `dotfiles/base/.config/git/hooks/pre-push:3-8`
- **Problem:** The Codex profile sets `approval_policy = "never"` with full filesystem access. `codex execpolicy check` returns no matching rule for `git -C . push`, and the global pre-push hook permits a push whenever stderr is a terminal. A hook reproduction with non-TTY stdin and PTY stderr exited successfully. No push was attempted.
- **Recommendation:** Require an explicit interactive approval at the final push boundary, and fail closed when that approval cannot be obtained.
- **Fix with:** none
- **Effort:** M
- **Design:** [USR-5 RFC](docs/rfc/USR-5-push-approval.md)

### USR-32 · P3 · Concurrent campaign allowances can overwrite each other

- **Area:** Concurrency
- **Where:** `dotfiles/base/.local/bin/codex-campaign-closeout.py:132-168`, `dotfiles/base/.local/bin/codex-campaign-closeout.py:171-197`, `dotfiles/base/.local/bin/codex-campaign-closeout.py:252-274`, `dotfiles/base/.local/bin/codex-campaign-closeout.py:337-356`
- **Problem:** Two concurrently invoked allow commands both load the current allowed dictionary, add different worktrees locally, then atomically replace the same state file without a lock or generation check. The last writer discards the other's allowance; the Stop hook later blocks on a worktree that was reported as allowed. This is a source-grounded concurrent interleaving, not yet exercised as a two-process fixture.
- **Recommendation:** Serialize allow updates or use a compare-and-retry revision/lock around load-modify-save, and reproduce two processes adding disjoint allowances with a barrier. Keep the existing state validation.
- **Fix with:** `durable-state`
- **Effort:** S
