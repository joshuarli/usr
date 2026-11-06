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
- **Where:** `sync` POSIX bootstrap, `tools/sync/main.py`, `tools/sync/install.sh`, `host/setup-linux`
- **Problem:** The Python DAG runner needs Python 3.9+ before it can execute. macOS can use the existing shell-based `python-build` installer to install the managed runtime, but Alpine currently needs an already runnable Python. Production `python-build` Linux artifacts still list `libgcc` in their runtime requirements; automatically fetching those binaries would introduce an unwanted system dependency. Alpine provisioning and fresh `sh sync` therefore do not yet have a self-contained bootstrap guarantee.
- **Recommendation:** After `laputa-systems/python-build` removes the actual `libgcc_s.so.1` dependency from both Linux musl archives and proves it in minimal-container smoke tests, implement a minimal POSIX-shell bootstrap for Alpine x86_64 and aarch64. Pin the release artifact identity and SHA-256 independently of release metadata, verify before extraction, reject unsafe archive paths, stage and atomically switch the Python runtime, and smoke-test `sqlite3`/`ssl` before invoking the Python DAG. Avoid adding `libgcc`, a package-manager Python, or a second installer engine. Test fresh Alpine without Python or libgcc, interrupted download, existing installations, and second-run idempotency.
- **Fix with:** `sync` bootstrap and python-build release qualification
- **Effort:** M

### USR-34 · P2 · Link creation can converge without ever persisting ownership

- **Area:** Data
- **Where:** `tools/sync/link_apply.py:49-57`, `tools/sync/link_apply.py:118-161`, `tools/sync/link_plan.py:100-115`, `tools/sync/link_plan.py:122-163`, `tools/sync/main.py:84-107`, `dotfiles/doctor:35-53`
- **Problem:** Reachable, reproduced by raising OSError during `_save_records` after `os.symlink` succeeds: (1) a new `LinkAction` is planned; (2) `link_apply.py:157` creates the symlink; (3) `Ownership.add` fails persisting ownership or its second fingerprint manifest; (4) the first run fails but leaves the symlink; (5) a retry sees `path.samefile(spec.source)` and returns a converged plan, so no code repairs the missing/incomplete F+fingerprint ownership. The doctor checks path presence, not the full owned-versus-verified lifecycle. The link is effectively orphaned, and uninstall cannot safely reclaim it. A process interruption in the same write window produces the same state.
- **Recommendation:** Represent link creation as recoverable intent→exclusive create→record+verify with a narrowly scoped durable journal or equivalent restart reconciliation. On retry, repair a proven incomplete own operation without claiming a pre-existing foreign correct symlink. Add fault-injection tests after the link, after the path record and before the fingerprint write.
- **Fix with:** `durable-state`
- **Effort:** M

### USR-35 · P2 · Concurrent link and tool sync silently discard ownership claims

- **Area:** Concurrency
- **Where:** `tools/sync/link_apply.py:41-47`, `tools/sync/link_apply.py:66-73`, `tools/sync/link_apply.py:24-35`, `tools/sync/ownership.py:77-104`, `tools/sync/main.py:119-136`, `tools/sync/dag.py:81-128`
- **Problem:** Reachable, reproduced by injecting a second writer's F-record append between the Python link manager's initial `records()` read and `_save_records()` atomic replacement. The link manager writes its earlier in-memory set and erases the new tool record, leaving the installed tool untracked. Two independent CLI invocations, `sync links` and `sync tools NAME`, have no common interprocess lock. The DAG's in-process resource exclusions do not serialize separate sync processes; the JSON fingerprint manifest has an analogous read/modify/replace race. The loss affects safe uninstall and repair after a later sync.
- **Recommendation:** Use one interprocess ownership-state lock and a single transaction boundary around reading, updating and committing both the path records and fingerprint manifest (or migrate to per-object atomic records). Preserve old on-disk state and ensure shell leaf installers participate in the same locking protocol. Exercise two competing processes with a barrier and assert no claims disappear.
- **Fix with:** `durable-state`
- **Effort:** M

### USR-36 · P2 · Successful kache setup never transitions into managed ownership

- **Area:** Operability
- **Where:** `tools/sync/main.py:172-180`, `tools/sync/main.py:238-243`, `tools/sync/uninstall.py:19-38`, `tools/sync/uninstall.py:50-60`, `dotfiles/base/.local/bin/setup-kache:163-214`, `tools/sync/test_uninstall.py:36-101`
- **Problem:** Reachable, reproduced with a stubbed setup-kache command and disposable HOME: `kache_apply` successfully installs a `~/.cargo/bin/kache` executable but does not write any K ownership record or verified provenance; `sync uninstall` sees no K entry, never invokes `setup-kache uninstall --purge`, and leaves the binary plus kache-managed Cargo state. The inverse case, an old path-only K record without a fingerprint, causes the uninstall preflight to refuse the entire operation. Neither state has a completed managed-install→managed-uninstall transition.
- **Recommendation:** Treat kache as a first-class typed managed resource: record verifiable provenance on a new installation (never adopt a pre-existing foreign executable), and call the dedicated reversible setup-kache uninstaller only for a still-proven owned installation. Add fresh install, pre-existing kache, legacy K record and uninstall round-trip fixtures.
- **Fix with:** `durable-state`
- **Effort:** S

### USR-37 · P2 · Concurrent worker starts can claim the same clean worktree

- **Area:** Concurrency
- **Where:** `tools/opencode-worker/src/bridge.ts:58-76`, `tools/opencode-worker/src/hybrid.ts:101-117`, `tools/opencode-worker/src/hybrid.ts:178-211`, `tools/opencode-worker/test/hybrid.test.ts:74-235`
- **Problem:** Source-grounded reachable interleaving (unproven against a live backend): two simultaneous `worker_start` calls pass `checkedWorktree(...,true)` and the clean `git status` guard (`hybrid.ts:178-185`) before either performs work. Both then await `modelCheck` (`:188`), create different session IDs and can admit concurrent OpenCode prompts to the same worktree (`:198-203`). The exclusive locks cover only later status/resume/cancel operations keyed by session ID (`:101-117`), so they do not exclude two starts on the same checkout. Both workers can write the same allowed paths and invalidate each other's acceptance proof. Current tests cover overlapping status/resume requests, not starts.
- **Recommendation:** Introduce a per-worktree admission/active lease acquired before the first asynchronous model check; release or transition it explicitly when an executor reaches a verified terminal state. If concurrent scouts are allowed, encode that as a separate read-only admission mode. Add `Promise.all` tests that overlap two writer starts, plus restart/recovery and separate-worktree concurrency tests.
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
