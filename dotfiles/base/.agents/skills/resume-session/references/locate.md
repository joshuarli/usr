# Locate the exact session

Read this before reading any transcript for `resume-session` or `session-handoff`.

Normalize the agent name, but never guess the session ID:

| Agent | Names accepted | Transcript files and ID |
| --- | --- | --- |
| Codex | `codex` | `$CODEX_HOME/sessions` and `$CODEX_HOME/archived_sessions` (default `~/.codex/`). The session is `rollout-*.jsonl`; its ID is the first record's `payload.id` or `payload.session_id`, written bare. |
| Claude Code | `claude`, `claude-code` | `$CLAUDE_CONFIG_DIR/projects` (default `~/.claude/projects`). The ID is `sessionId` in the transcript records; a subagent sidechain under `subagents` uses its file stem. |
| Muse Code | `muse`, `muse-code` | `$XDG_DATA_HOME/muse/sessions` (default `~/.local/share/muse/sessions`). Each session is a directory holding `session.jsonl`; the ID is the directory name. |
| OpenCode | `opencode` | `$XDG_DATA_HOME/opencode` (default `~/.local/share/opencode`) holds the SQLite database `opencode.db`. The session is a `session_v2` row, its ID is that row's `id`, and its messages are `session_message` rows ordered by `seq`. |
| Pi | `pi` | `$PI_CODING_AGENT_SESSION_DIR` (default under `$PI_CODING_AGENT_DIR/sessions`, then `~/.pi/agent/sessions`). Files are `<timestamp>_<id>.jsonl`; the ID is the first session record's `id`, or the filename suffix. |
| Command Code | `cmd`, `command`, `command-code` | `$COMMANDCODE_HOME/projects` (default `~/.commandcode/projects`). Session files are `.jsonl`, excluding `.checkpoints.jsonl`; the ID is the first record's `session.id`, falling back to the file stem. |
| Antigravity CLI | `agy`, `antigravity` | `$ANTIGRAVITY_HOME/brain` (default `~/.gemini/antigravity-cli/brain`). A conversation's transcript is `transcript.jsonl` or `transcript_full.jsonl`; the ID is the conversation directory three levels above the file. |

Accept an ID only when it matches the requested harness and the exact file. Codex IDs are bare; the others may be written `harness:ID`, and the prefix must agree with the requested agent. A missing or mismatched ID is a failure, not permission to substitute a similarly named session.

For DeepSeek TUI and fx, inspect only the exact local session's files, read-only:

- **DeepSeek TUI:** look for the exact ID under `~/.dsh/sessions/` (or `DSH_HOME` when set; commonly compressed JSONL). Decode with an already installed reader, if available, and inspect the event structure before deriving any conclusion. Do not treat binary or compressed bytes as text.
- **fx:** read the exact `~/.fx/sessions/<ID>/session.json` manifest and its `events.jsonl` append-only log, read-only. Validate the manifest's session ID, workspace and committed log extent; treat `history_turn_committed` records as conversation evidence and ignore uncommitted trailing events. fx's log envelope differs from the other harnesses. Do not attribute a subagent's turns to the parent without explicit lineage. If the session or its committed history is missing, report the gap.

Do not run a source CLI or install a new decoder just to extract context. For a missing log, an ambiguous prefix, a corrupted or unsupported event format, or inaccessible data, report precisely what could not be recovered and offer the native command below. Never claim a complete handoff from only a title or summary.
