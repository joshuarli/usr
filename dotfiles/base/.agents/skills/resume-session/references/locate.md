# Locate the exact session

Read this before reading any transcript for `resume-session` or `session-handoff`.

Normalize the agent name, but never guess the session ID:

<!-- policy:begin resume-locations -->
<!-- Generated from tools/pi-subagent-bridge/src/policy.ts; run make generate. -->
| Agent | Names accepted | Transcript files and ID |
| --- | --- | --- |
| Codex | `codex` | `$CODEX_HOME/sessions` and `$CODEX_HOME/archived_sessions` (default `~/.codex/`). The session is `rollout-*.jsonl`; its ID is the first record's `payload.id` or `payload.session_id`, written bare. |
| Claude Code | `claude`, `claude-code` | `$CLAUDE_CONFIG_DIR/projects` (default `~/.claude/projects`). The ID is `sessionId` in the transcript records; a subagent sidechain under `subagents` uses its file stem. |
| Muse Code | `muse`, `muse-code` | `$XDG_DATA_HOME/muse/sessions` (default `~/.local/share/muse/sessions`). Each session is a directory holding `session.jsonl`; the ID is the directory name. |
| OpenCode | `opencode` | `$XDG_DATA_HOME/opencode` (default `~/.local/share/opencode`) holds the SQLite database `opencode.db`. The session is a `session_v2` row, its ID is that row's `id`, and its messages are `session_message` rows ordered by `seq`. |
| Pi | `pi` | `$PI_CODING_AGENT_SESSION_DIR` (default under `$PI_CODING_AGENT_DIR/sessions`, then `~/.pi/agent/sessions`). Files are `<timestamp>_<id>.jsonl`; the ID is the first session record's `id`, or the filename suffix. |
| Antigravity CLI | `agy`, `antigravity` | `$ANTIGRAVITY_HOME/brain` (default `~/.gemini/antigravity-cli/brain`). A conversation's transcript is `transcript.jsonl` or `transcript_full.jsonl`; the ID is the conversation directory three levels above the file. |
| Devin | `devin`, `devin-cli` | `$XDG_DATA_HOME/devin/cli/transcripts/<ID>.json` (default `~/.local/share/devin/cli/transcripts`), or under `DEVIN_SESSIONS_DIR` when set. The ID is the root `session_id` and the file stem. |
<!-- policy:end resume-locations -->

Accept an ID only when it matches the requested harness and the exact file. A supplied `harness:ID` prefix must agree with the requested agent; use the source format's exact session ID. A missing or mismatched ID is a failure, not permission to substitute a similarly named session.

<!-- policy:begin resume-details -->
<!-- Generated from tools/pi-subagent-bridge/src/policy.ts; run make generate. -->
Read only the exact local session's files:

- **fx:** read the exact `~/.fx/sessions/<ID>/session.json` manifest and its `events.jsonl` append-only log, read-only. Validate the manifest's session ID, workspace and committed log extent; treat `history_turn_committed` records as conversation evidence and ignore uncommitted trailing events. fx's log envelope differs from the other harnesses. Do not attribute a subagent's turns to the parent without explicit lineage. If the session or its committed history is missing, report the gap.
- **Devin:** read the exact `.../transcripts/<ID>.json` read-only and match its root `session_id` to the requested ID. It is an ATIF JSON document: `steps` is the ordered conversation as `{step_id, timestamp, source, message, ...}`, where `source` is `user`, `agent` or `system`; assistant steps carry `reasoning_content`, `tool_calls` (`function_name`, `arguments`, `tool_call_id`) and `observation.results` (`source_call_id`, `content`), and the root `final_metrics` aggregates usage. `~/.local/share/devin/cli/sessions.db` (or `DEVIN_SESSIONS_DIR/sessions.db`) supplies workspace/title/model/timestamp metadata when the transcript alone is ambiguous; `summaries/history_*.md` are prior-thread compaction summaries, useful as navigation but not primary evidence. Verify claims against the actual steps and current workspace, and do not attribute a delegated subagent's turns to the parent without explicit lineage.
<!-- policy:end resume-details -->

Do not run a source CLI or install a new decoder just to extract context. For a missing log, an ambiguous prefix, a corrupted or unsupported event format, or inaccessible data, report precisely what could not be recovered and offer the native command below. Never claim a complete handoff from only a title or summary.
