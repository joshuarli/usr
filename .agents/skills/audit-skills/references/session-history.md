# Session-history audit

Read this when `/audit-skills` is given a timeframe argument such as `past 2h` (default: today). The goal is evidence about delegation and qualification tooling — `pi-subagent-bridge`, `agentctl`, harness MCP registrations — from what sessions actually did.

## Data (all read-only)

- OpenCode: `sqlite3 ~/.local/share/opencode/opencode.db`. Sessions from `session_v2` (`time_updated` is epoch ms); assistant turns from `session_message` (JSON `data.content` holds the tool calls); parts from `session_part` if the JSON layout differs.
- Claude: `~/.claude/projects/*/<session>.jsonl`. Codex: `~/.codex/sessions/YYYY/MM/DD/rollout-*.jsonl` (the `session_meta` line carries `cwd` and `originator`). Pi: `~/.pi/agent/sessions/*/*.jsonl` (scan the first lines for `cwd`).
- List candidates with `fd -I -H --changed-within <window>`. Bridge state and qualification logs live under `.work/`, which is gitignored, so `-I` is required for those trees.
- Bridge state: `<repo>/.work/worker-bridge/usrw_*.json` (`tier`, `attempts`, `execution.selection`, `cancel_requested`) with sibling `*.codex.ndjson` / `*.codex.stderr`. Live qualification writes `.work/tmp/bridge-live-run*.log`.
- Filed friction: `rg -n 'USR-[0-9]+ ' TODO.md` and `git log --grep` in the owning repo.

## Steps

1. **Inventory.** Every session touched in the window, by harness and repo; classify parent or child (child cwds sit under `.work/wt/` or `.work/tmp/qualify-*`).
2. **Read the tool surface.** Per harness, pull calls and results mentioning `pi-subagent-bridge`, `worker_*`, the MCP bridge, or qualification. Count admissions, successes, `attempts > 1`, `fallback_reason`, `acceptance_blocked`, refused cancels or resumes, quota (429) answers, and stale MCP module errors; note repeats of one error across runs. Check `TODO.md` and `git log --grep` for tickets the friction already produced.
3. **Verify before reporting.** Each candidate friction must be backed by the log or job file that shows it. Drop what does not survive. Confirm jobs share the host before reading retry storms as flakiness.

Keep transcripts private: counts, dates, and one-line paraphrases, never pasted prompts or code. Rank friction by severity and tag each item defect / guard firing correctly / operator papercut; separate tool defects from host noise (a noisy machine, a wedged `agent-browser` daemon).

## Report

The window and session counts; a per-harness table of admissions, successes, retries, fallbacks and blocks; friction ranked by severity with the evidence line or job id and its defect / guard / papercut tag; what could not be verified; and what was filed or deferred.
