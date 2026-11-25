import { harnessEnabled, type HarnessId, type HarnessSwitches } from "../pi-subagent-bridge/src/harnesses.ts"

type Entry = readonly [HarnessId, string]

const COMMANDS: readonly Entry[] = [
  ["codex", "| Codex | `codex resume <ID>` |"],
  ["claude", "| Claude Code | `claude --resume <ID>` |"],
  ["muse", "| Muse Code | `muse resume <ID>` |"],
  ["opencode", "| OpenCode | `opencode --session <ID>` |"],
  ["pi", "| Pi | `pi --session <ID>` |"],
  ["command-code", "| Command Code | `cmd --session <ID>` |"],
  ["antigravity", "| Antigravity CLI | `agy --conversation <ID>` |"],
  ["deepseek", "| DeepSeek Harness | `dsh tui --resume <ID>` |"],
  ["fx", "| fx | `fx resume <ID>` |"],
  ["devin", "| Devin | `devin --resume <ID>` |"],
]

const LOCATIONS: readonly Entry[] = [
  ["codex", "| Codex | `codex` | `$CODEX_HOME/sessions` and `$CODEX_HOME/archived_sessions` (default `~/.codex/`). The session is `rollout-*.jsonl`; its ID is the first record's `payload.id` or `payload.session_id`, written bare. |"],
  ["claude", "| Claude Code | `claude`, `claude-code` | `$CLAUDE_CONFIG_DIR/projects` (default `~/.claude/projects`). The ID is `sessionId` in the transcript records; a subagent sidechain under `subagents` uses its file stem. |"],
  ["muse", "| Muse Code | `muse`, `muse-code` | `$XDG_DATA_HOME/muse/sessions` (default `~/.local/share/muse/sessions`). Each session is a directory holding `session.jsonl`; the ID is the directory name. |"],
  ["opencode", "| OpenCode | `opencode` | `$XDG_DATA_HOME/opencode` (default `~/.local/share/opencode`) holds the SQLite database `opencode.db`. The session is a `session_v2` row, its ID is that row's `id`, and its messages are `session_message` rows ordered by `seq`. |"],
  ["pi", "| Pi | `pi` | `$PI_CODING_AGENT_SESSION_DIR` (default under `$PI_CODING_AGENT_DIR/sessions`, then `~/.pi/agent/sessions`). Files are `<timestamp>_<id>.jsonl`; the ID is the first session record's `id`, or the filename suffix. |"],
  ["command-code", "| Command Code | `cmd`, `command`, `command-code` | `$COMMANDCODE_HOME/projects` (default `~/.commandcode/projects`). Session files are `.jsonl`, excluding `.checkpoints.jsonl`; the ID is the first record's `session.id`, falling back to the file stem. |"],
  ["antigravity", "| Antigravity CLI | `agy`, `antigravity` | `$ANTIGRAVITY_HOME/brain` (default `~/.gemini/antigravity-cli/brain`). A conversation's transcript is `transcript.jsonl` or `transcript_full.jsonl`; the ID is the conversation directory three levels above the file. |"],
  ["devin", "| Devin | `devin`, `devin-cli` | `$XDG_DATA_HOME/devin/cli/transcripts/<ID>.json` (default `~/.local/share/devin/cli/transcripts`), or under `DEVIN_SESSIONS_DIR` when set. The ID is the root `session_id` and the file stem. |"],
]

const DETAILS: readonly Entry[] = [
  ["deepseek", "- **DeepSeek TUI:** look for the exact ID under `~/.dsh/sessions/` (or `DSH_HOME` when set; commonly compressed JSONL). Decode with an already installed reader, if available, and inspect the event structure before deriving any conclusion. Do not treat binary or compressed bytes as text."],
  ["fx", "- **fx:** read the exact `~/.fx/sessions/<ID>/session.json` manifest and its `events.jsonl` append-only log, read-only. Validate the manifest's session ID, workspace and committed log extent; treat `history_turn_committed` records as conversation evidence and ignore uncommitted trailing events. fx's log envelope differs from the other harnesses. Do not attribute a subagent's turns to the parent without explicit lineage. If the session or its committed history is missing, report the gap."],
  ["devin", "- **Devin:** read the exact `.../transcripts/<ID>.json` read-only and match its root `session_id` to the requested ID. It is an ATIF JSON document: `steps` is the ordered conversation as `{step_id, timestamp, source, message, ...}`, where `source` is `user`, `agent` or `system`; assistant steps carry `reasoning_content`, `tool_calls` (`function_name`, `arguments`, `tool_call_id`) and `observation.results` (`source_call_id`, `content`), and the root `final_metrics` aggregates usage. `~/.local/share/devin/cli/sessions.db` (or `DEVIN_SESSIONS_DIR/sessions.db`) supplies workspace/title/model/timestamp metadata when the transcript alone is ambiguous; `summaries/history_*.md` are prior-thread compaction summaries, useful as navigation but not primary evidence. Verify claims against the actual steps and current workspace, and do not attribute a delegated subagent's turns to the parent without explicit lineage."],
]

function selected(entries: readonly Entry[], switches: HarnessSwitches): string[] {
  return entries.filter(([id]) => harnessEnabled(id, switches)).map(([, text]) => text)
}

export function resumeCommands(switches: HarnessSwitches): string {
  const rows = selected(COMMANDS, switches)
  return rows.length ? ["| Agent | Host-shell command |", "| --- | --- |", ...rows].join("\n") :
    "No harness is enabled for native reopening."
}

export function resumeLocations(switches: HarnessSwitches): string {
  const rows = selected(LOCATIONS, switches)
  return rows.length ? ["| Agent | Names accepted | Transcript files and ID |", "| --- | --- | --- |", ...rows].join("\n") :
    "No harness transcript locations are enabled."
}

export function resumeDetails(switches: HarnessSwitches): string {
  const details = selected(DETAILS, switches)
  return details.length ? "Read only the exact local session's files:\n\n" + details.join("\n") : ""
}
