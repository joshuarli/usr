Prefix: USR
Next: 21

### USR-5 · P2 · Push rules do not require user approval

- **Area:** Security
- **Where:** `dotfiles/base/.codex/config.toml:7-8`, `dotfiles/base/.config/git/hooks/pre-push:3-8`
- **Problem:** The Codex profile sets `approval_policy = "never"` with full filesystem access. `codex execpolicy check` returns no matching rule for `git -C . push`, and the global pre-push hook permits a push whenever stderr is a terminal. A hook reproduction with non-TTY stdin and PTY stderr exited successfully. No push was attempted.
- **Recommendation:** Require an explicit interactive approval at the final push boundary, and fail closed when that approval cannot be obtained.
- **Fix with:** none
- **Effort:** M
- **Design:** [USR-5 RFC](docs/rfc/USR-5-push-approval.md)

### USR-17 · P2 · Memory-use effect on agent behavior is unmeasured

- **Area:** Agent learning
- **Where:** `dotfiles/agent-recall-live.py`, `dotfiles/base/.agents/skills/do/SKILL.md`
- **Problem:** The live baseline, treatment, and control evaluation exists and its scoring and fixtures are tested offline, but it has never run because it makes paid Codex calls. Whether agents call `agent-learn recall` when the `do` rule says to, in each harness, and whether results change outcomes, is unmeasured.
- **Recommendation:** Run `python3 dotfiles/agent-recall-live.py --live --runs 5` once with explicit approval, record the result in `docs/agent-learning.md`, and check recall invocation in Claude, Muse, and Grok transcripts with `agent-sessions search 'agent-learn recall'`.
- **Fix with:** none
- **Effort:** S

### USR-18 · P3 · Unsegmented scripts match only whole runs

- **Area:** Agent learning
- **Where:** `dotfiles/base/.local/bin/agent_session_store.py` (`events_fts`)
- **Problem:** The FTS5 `unicode61` tokenizer treats a run of Chinese or Japanese characters as one token, so a query matches only the exact run.
- **Recommendation:** Measure a trigram index for events containing such scripts against its size cost before adding one.
- **Fix with:** none
- **Effort:** M

### USR-19 · P3 · Muse transcripts lack tool events

- **Area:** Agent learning
- **Where:** `dotfiles/base/.local/bin/agent_transcripts.py` (`_muse_record`)
- **Problem:** Only user messages and skill reads are verified from fixtures, so Muse sessions yield no tool-based experience and Muse ancestry stays unknown.
- **Recommendation:** Capture a real Muse session, add its assistant and tool event shapes and any parent field to the normalizer, and add fixtures.
- **Fix with:** none
- **Effort:** S

### USR-20 · P3 · Pi subagent delegation is unverified against a real run

- **Area:** Agent learning
- **Where:** `dotfiles/base/.local/bin/agent_transcripts.py` (`default_roots`, `read_header`), `dotfiles/base/.local/bin/agent_session_store.py` (`_archive_source`)
- **Problem:** Pi sessions are indexed, archived, and branch-filtered from fixtures shaped like two real single-agent sessions. No parallel-subagent run has been captured, so three assumptions are unproven. Child session files may live outside `~/.pi/agent/sessions` (for example under `$TMPDIR/pi-subagents-uid-N/`), where the index would never see them. They may not match the `<timestamp>_<id>.jsonl` name the adapter requires. Run artifacts under that temp directory are cleaned up (workflow artifacts after 24 hours), so they may need archiving. The capture attempt on 2026-10-25 hit the Gemini free-tier limit of 20 requests per day per model, which the first undirected run used up reading documentation.
- **Recommendation:** After the quota resets, run `cd .work/pi-capture && vault GEMINI_API_KEY -- pi -p --no-approve --no-skills 'Call the subagent tool exactly once, in the foreground, with tasks set to two scout children that run in parallel: the first reads a.txt and reports its line count, the second reads b.txt and reports its line count. Do not read any documentation first.'` (create `a.txt` and `b.txt` first), using the default `TMPDIR`. Diff `$TMPDIR/pi-subagents-uid-*` and `~/.pi/agent/sessions` before and after. Add the child session location as a Pi root if it is outside the sessions directory, check that `parentSession` links the child to the parent in `agent-sessions recent`, and add a sanitized fixture to `dotfiles/agent-sessions-test.py`. Archive the run artifacts only if a consumer needs them.
- **Fix with:** none
- **Effort:** S
