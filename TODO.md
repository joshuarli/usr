Prefix: USR
Next: 39

### USR-38 · P2 · Complete companion intercom adapters and supervisor consultation

- **Area:** Cross-harness agent communication
- **Where:** `vendor/pi/`, `tools/pi-subagent-bridge/`, `docs/pi.md`
- **Delivered:** Pi 1.5.0 CLI, SDK, pi-subagents, Muse SDK adapter, intercom Pi/core plus their entire installed JS closure are bundled as SHA-256-verified platform archives (macOS ARM64, Linux x64/ARM64). `sh sync tools pi`, `sh sync bridge` and the Pi launcher never download npm dependencies or run `pi install/update`. Interactive Pi loads local intercom with `inboundTrigger: "never"` and `confirmSend: true`.
- **Remaining:** Claude/Codex/OpenCode *companion intercom adapters* are not yet vendored/registered. Scoped Pi SDK child workers deliberately do not load intercom, so `contact_supervisor` is not exposed inside child sessions. These are **communications features**, separate from the now-offline Pi installation, and must not bypass existing typed tier restrictions, worktree ownership, and acceptance proof.
- **Recommendation:** Vendor compatible companion adapters and core protocol revisions, track each upstream commit SHA, register only required MCP hooks/wrappers, and add cross-harness send/ask/reply tests plus bounded child-supervisor consultation with strict admission/permission gates. Do not add the intercom fleet orchestrator or enable unsolicited model wakeups.
- **Fix with:** `pi-update`
- **Effort:** L

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
