Prefix: USR
Next: 24

### USR-5 · P2 · Push rules do not require user approval

- **Area:** Security
- **Where:** `dotfiles/base/.codex/config.toml:7-8`, `dotfiles/base/.config/git/hooks/pre-push:3-8`
- **Problem:** The Codex profile sets `approval_policy = "never"` with full filesystem access. `codex execpolicy check` returns no matching rule for `git -C . push`, and the global pre-push hook permits a push whenever stderr is a terminal. A hook reproduction with non-TTY stdin and PTY stderr exited successfully. No push was attempted.
- **Recommendation:** Require an explicit interactive approval at the final push boundary, and fail closed when that approval cannot be obtained.
- **Fix with:** none
- **Effort:** M
- **Design:** [USR-5 RFC](docs/rfc/USR-5-push-approval.md)

### USR-18 · P3 · Unsegmented scripts match only whole runs

- **Area:** Agent learning
- **Where:** `agent-memory/src/agent_memory/store.py` (`events_fts`)
- **Problem:** The FTS5 `unicode61` tokenizer treats a run of Chinese or Japanese characters as one token, so a query matches only the exact run.
- **Recommendation:** Measure a trigram index for events containing such scripts against its size cost before adding one.
- **Fix with:** none
- **Effort:** M

### USR-19 · P3 · Muse transcripts lack tool events

- **Area:** Agent learning
- **Where:** `agent-memory/src/agent_memory/transcripts.py` (`_muse_record`)
- **Problem:** Only user messages and skill reads are verified from fixtures, so Muse sessions yield no tool-based experience and Muse ancestry stays unknown.
- **Recommendation:** Capture a real Muse session, add its assistant and tool event shapes and any parent field to the normalizer, and add fixtures.
- **Fix with:** none
- **Effort:** S

### USR-20 · P3 · Pi subagent delegation is unverified against a real run

- **Area:** Agent learning
- **Where:** `agent-memory/src/agent_memory/transcripts.py` (`default_roots`, `read_header`), `agent-memory/src/agent_memory/store.py` (`_archive_source`)
- **Problem:** Pi sessions are indexed, archived, and branch-filtered from fixtures shaped like two real single-agent sessions. No parallel-subagent run has been captured, so three assumptions are unproven. Child session files may live outside `~/.pi/agent/sessions` (for example under `$TMPDIR/pi-subagents-uid-N/`), where the index would never see them. They may not match the `<timestamp>_<id>.jsonl` name the adapter requires. Run artifacts under that temp directory are cleaned up (workflow artifacts after 24 hours), so they may need archiving. The capture attempt on 2026-10-25 hit the Gemini free-tier limit of 20 requests per day per model, which the first undirected run used up reading documentation.
- **Recommendation:** After the quota resets, run `cd .work/pi-capture && vault GEMINI_API_KEY -- pi -p --no-approve --no-skills 'Call the subagent tool exactly once, in the foreground, with tasks set to two scout children that run in parallel: the first reads a.txt and reports its line count, the second reads b.txt and reports its line count. Do not read any documentation first.'` (create `a.txt` and `b.txt` first), using the default `TMPDIR`. Diff `$TMPDIR/pi-subagents-uid-*` and `~/.pi/agent/sessions` before and after. Add the child session location as a Pi root if it is outside the sessions directory, check that `parentSession` links the child to the parent in `agent-sessions recent`, and add a sanitized fixture to `agent-memory/tests/test_sessions.py`. Archive the run artifacts only if a consumer needs them.
- **Fix with:** none
- **Effort:** S

### USR-22 · P3 · Mirror durability is bounded by the 15-minute capture interval

- **Area:** Operability
- **Where:** `agent-memory/src/agent_memory/mirror.py` (`sync` calls `refresh` before upload, `pending_report`), `agent-memory/src/agent_memory/store.py` (`pending_generations`, `transfer_generation`), `dotfiles/launchd/com.josh.agent-sessions-mirror.plist.in:25`
- **Problem:** Reads and writes are local-first, but remote durability is eventual. The scheduled sync captures first and uploads second every 3600 seconds, so a session written just after a run can stay local-only for about an hour plus upload time. If the host is lost in that window, the remote has no copy. Durability is visible only as aggregate pending generations, objects, and bytes in `mirror status`, not per session. Shortening the interval also shortens the capture interval, and each changed session creates an immutable generation with new 64 KiB chunks, so busy sessions multiply generations, objects, and mirror storage; event-driven capture at session end avoids that churn but hooks are per-harness and unreliable. Synchronous acknowledgement would close the window but couple local writes to Cloudflare latency and availability, contrary to local-first.
- **Recommendation:** Choose an RPO target, then make the smallest matching change. For about five minutes, shorten the scheduled interval and keep uploads asynchronous. For seconds, add a debounced end-of-turn capture-and-sync trigger while retaining the periodic backstop. Add per-session durable and pending reporting by joining `sessions`, `archive_generation`, and `transfer_generation`, and keep synchronous acknowledgement only behind an explicit `--wait` or `--durable` path. Account for generation and object growth before shortening capture itself.
- **Fix with:** do
- **Effort:** M

### USR-23 · P3 · Mirror encryption depends on unprovisioned age binary

- **Area:** Dependencies
- **Where:** `agent-memory/src/agent_memory/mirror_crypto.py:23-48`
- **Problem:** `mirror_crypto` requires `rage` or `age` (and `rage-keygen`/`age-keygen`) to encrypt session mirror backups, but no `age` implementation is packaged or installed by `usr`.
- **Recommendation:** Set up the fork at https://github.com/laputa-systems/rage to publish release binaries, and package `rage` under `dl`.
- **Fix with:** none
- **Effort:** S
