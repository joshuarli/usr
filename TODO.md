Prefix: USR
Next: 33

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
- **Where:** `sync` POSIX bootstrap, `tools/sync/main.py`, `tools/sync/install.sh`, `host/setup-linux`
- **Problem:** The Python DAG runner needs Python 3.9+ before it can execute. macOS can use the existing shell-based `python-build` installer to install the managed runtime, but Alpine currently needs an already runnable Python. Production `python-build` Linux artifacts still list `libgcc` in their runtime requirements; automatically fetching those binaries would introduce an unwanted system dependency. Alpine provisioning and fresh `sh sync` therefore do not yet have a self-contained bootstrap guarantee.
- **Recommendation:** After `laputa-systems/python-build` removes the actual `libgcc_s.so.1` dependency from both Linux musl archives and proves it in minimal-container smoke tests, implement a minimal POSIX-shell bootstrap for Alpine x86_64 and aarch64. Pin the release artifact identity and SHA-256 independently of release metadata, verify before extraction, reject unsafe archive paths, stage and atomically switch the Python runtime, and smoke-test `sqlite3`/`ssl` before invoking the Python DAG. Avoid adding `libgcc`, a package-manager Python, or a second installer engine. Test fresh Alpine without Python or libgcc, interrupted download, existing installations, and second-run idempotency.
- **Fix with:** `sync` bootstrap and python-build release qualification
- **Effort:** M

### USR-26 · P2 · Concurrent DeepSeek status/resume calls can double-spawn workers and lose session transitions

- **Area:** Concurrency
- **Where:** `tools/opencode-worker/src/hybrid.ts:16-20`, `tools/opencode-worker/src/hybrid.ts:78-89`, `tools/opencode-worker/src/hybrid.ts:120-132`, `tools/opencode-worker/src/hybrid.ts:178-240`, `tools/opencode-worker/src/server.ts:151-155`
- **Problem:** A persisted Session uses backend plus optional opencode_id/command_run/attempts. The MCP server executes requests concurrently. Two status calls can both load the OpenCode state before awaiting API status, both observe the same terminal quota failure and untouched worktree, then each spawn a Command Code worker. Both write the same ID.json.tmp, and concurrent resumes can lose attempt-count updates. This is a source-grounded reachable interleaving; the existing tests exercise only sequential transitions.
- **Recommendation:** Use a tagged persisted session lifecycle with a single transition owner; serialize each session's status/fallback/resume/cancel through a per-session lock or atomic claim/revision before external side effects. Re-read state under that guard, use unique temporary files and atomic persistence, and add Promise.all overlap tests.
- **Fix with:** `lifecycle-concurrency`
- **Effort:** M

### USR-18 · P3 · Unsegmented scripts match only whole runs

- **Area:** Agent learning
- **Where:** `~/d/agent-memory/src/agent_memory/store.py` (`events_fts`)
- **Problem:** The FTS5 `unicode61` tokenizer treats a run of Chinese or Japanese characters as one token, so a query matches only the exact run.
- **Recommendation:** Measure a trigram index for events containing such scripts against its size cost before adding one.
- **Fix with:** none
- **Effort:** M

### USR-19 · P3 · Muse transcripts lack tool events

- **Area:** Agent learning
- **Where:** `~/d/agent-memory/src/agent_memory/transcripts.py` (`_muse_record`)
- **Problem:** Only user messages and skill reads are verified from fixtures, so Muse sessions yield no tool-based experience and Muse ancestry stays unknown.
- **Recommendation:** Capture a real Muse session, add its assistant and tool event shapes and any parent field to the normalizer, and add fixtures.
- **Fix with:** none
- **Effort:** S

### USR-20 · P3 · Pi subagent delegation is unverified against a real run

- **Area:** Agent learning
- **Where:** `~/d/agent-memory/src/agent_memory/transcripts.py` (`default_roots`, `read_header`), `~/d/agent-memory/src/agent_memory/store.py` (`_archive_source`)
- **Problem:** Pi sessions are indexed, archived, and branch-filtered from fixtures shaped like two real single-agent sessions. No parallel-subagent run has been captured, so three assumptions are unproven. Child session files may live outside `~/.pi/agent/sessions` (for example under `$TMPDIR/pi-subagents-uid-N/`), where the index would never see them. They may not match the `<timestamp>_<id>.jsonl` name the adapter requires. Run artifacts under that temp directory are cleaned up (workflow artifacts after 24 hours), so they may need archiving. The capture attempt on 2026-10-25 hit the Gemini free-tier limit of 20 requests per day per model, which the first undirected run used up reading documentation.
- **Recommendation:** After the quota resets, run `cd .work/pi-capture && vault GEMINI_API_KEY -- pi -p --no-approve --no-skills 'Call the subagent tool exactly once, in the foreground, with tasks set to two scout children that run in parallel: the first reads a.txt and reports its line count, the second reads b.txt and reports its line count. Do not read any documentation first.'` (create `a.txt` and `b.txt` first), using the default `TMPDIR`. Diff `$TMPDIR/pi-subagents-uid-*` and `~/.pi/agent/sessions` before and after. Add the child session location as a Pi root if it is outside the sessions directory, check that `parentSession` links the child to the parent in `agent-sessions recent`, and add a sanitized fixture to `~/d/agent-memory/tests/test_sessions.py`. Archive the run artifacts only if a consumer needs them.
- **Fix with:** none
- **Effort:** S

### USR-22 · P3 · Mirror durability is bounded by the 15-minute capture interval

- **Area:** Operability
- **Where:** `~/d/agent-memory/src/agent_memory/mirror.py` (`sync` calls `refresh` before upload, `pending_report`), `~/d/agent-memory/src/agent_memory/store.py` (`pending_generations`, `transfer_generation`), `dotfiles/launchd/com.josh.agent-sessions-mirror.plist.in:25`
- **Problem:** Reads and writes are local-first, but remote durability is eventual. The scheduled sync captures first and uploads second every 3600 seconds, so a session written just after a run can stay local-only for about an hour plus upload time. If the host is lost in that window, the remote has no copy. Durability is visible only as aggregate pending generations, objects, and bytes in `mirror status`, not per session. Shortening the interval also shortens the capture interval, and each changed session creates an immutable generation with new 64 KiB chunks, so busy sessions multiply generations, objects, and mirror storage; event-driven capture at session end avoids that churn but hooks are per-harness and unreliable. Synchronous acknowledgement would close the window but couple local writes to Cloudflare latency and availability, contrary to local-first.
- **Recommendation:** Choose an RPO target, then make the smallest matching change. For about five minutes, shorten the scheduled interval and keep uploads asynchronous. For seconds, add a debounced end-of-turn capture-and-sync trigger while retaining the periodic backstop. Add per-session durable and pending reporting by joining `sessions`, `archive_generation`, and `transfer_generation`, and keep synchronous acknowledgement only behind an explicit `--wait` or `--durable` path. Account for generation and object growth before shortening capture itself.
- **Fix with:** do
- **Effort:** M

### USR-32 · P3 · Concurrent campaign allowances can overwrite each other

- **Area:** Concurrency
- **Where:** `dotfiles/base/.local/bin/codex-campaign-closeout.py:132-168`, `dotfiles/base/.local/bin/codex-campaign-closeout.py:171-197`, `dotfiles/base/.local/bin/codex-campaign-closeout.py:252-274`, `dotfiles/base/.local/bin/codex-campaign-closeout.py:337-356`
- **Problem:** Two concurrently invoked allow commands both load the current allowed dictionary, add different worktrees locally, then atomically replace the same state file without a lock or generation check. The last writer discards the other's allowance; the Stop hook later blocks on a worktree that was reported as allowed. This is a source-grounded concurrent interleaving, not yet exercised as a two-process fixture.
- **Recommendation:** Serialize allow updates or use a compare-and-retry revision/lock around load-modify-save, and reproduce two processes adding disjoint allowances with a barrier. Keep the existing state validation.
- **Fix with:** `durable-state`
- **Effort:** S
