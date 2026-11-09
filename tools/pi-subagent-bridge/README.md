# pi-subagent-bridge

One Pi SDK subagent runtime for every coding harness. Parents remain responsible for decomposition, verification, integration and cleanup. The MCP server and CLI expose the **same** durable session state and worktree contracts. Pi runs the primary worker directly through `@earendil-works/pi-coding-agent`; Command Code is the separate, pinned DeepSeek V4.1 Flash fallback.

| Tier | Pi SDK / OpenCode Go primary | Thinking | Command Code |
| --- | --- | --- | --- |
| scout | `muse-spark-1.3-contributor` | medium | `deepseek/deepseek-v4.1-flash`, low |
| mechanic | `muse-spark-1.3-contributor` | high | `deepseek/deepseek-v4.1-flash`, high |
| worker | `deepseek-v4.1-flash` | high | `deepseek/deepseek-v4.1-flash`, high |
| expert | `deepseek-v4.1-flash` | max | `deepseek/deepseek-v4.1-flash`, max |

No `god` tier. Claude Code and Codex alone use their pinned native `god` agents. Neither runner may spawn another agent. Primary models require the OpenCode Go session configured in Pi; fallback requires `cmd login`. No other model is permitted.

## Setup

`sh sync` installs Node.js, Pi, Command Code, and the bridge's pinned SDK dependency, and registers the MCP server in Claude, Pi and OpenCode. Codex reads its tracked config. `sh sync bridge` reconciles MCP registrations; the old recognized `usr-opencode-worker` entry migrates to `pi-subagent-bridge` while foreign servers are preserved.

`sh sync plan`
`sh sync doctor`

The explicit CLI shim is installed at ``/.local/bin/pi-subagent-bridge`. No extra long-running OpenCode service or native Pi subagent extension is required. The worker SDK subprocess starts only when a task is admitted.

## MCP tools

`worker_model_check(cwd, tier)` checks the specific pinned Pi model and Command Code installation.

`worker_start(cwd, title, tier, scope, brief)` admits exactly one scoped assignment in a **clean linked worktree** at `<repo>/.work/wt/<name>`. It returns `usrw_*`; this means **admitted**, not complete. Its scope:

- `base_revision`: exact 40-character HEAD.
- `writable_paths`: no more than 20 exact relative files/prefixes; empty only for a read-only scout.
- `acceptance_proof`: one named check and expected result, or read-only file:line evidence.
- `attempt_limit`: 1 or 2, with the second only for a justified same-scope correction.
- `stop_on`: ambiguity, new dependencies, scope or contract changes, unavailable proof.

`worker_status(cwd,session_id)` observes the real backend, tier/effort, result, changed and out-of-scope paths, HEAD stability and fallback reason. The parent verifies the output and independently checks the diff; an assistant claim cannot count as test proof.

`worker_resume(cwd,session_id,feedback)` preserves the approved scope and either resumes the owned Pi SDK conversation or the Command Code session. It refuses uncertain active runs, scope expansion, and depleted attempts.

`worker_cancel(cwd,session_id)` interrupts only a child owned by the current process. Never signal a stale PID after restart. Cancellation is not proof of termination.

## CLI

Identical actions are available to harnesses without MCP:

```
pi-subagent-bridge mcp
pi-subagent-bridge model-check CWD TIER
pi-subagent-bridge start CWD TITLE TIER SCOPE_JSON_FILE BRIEF_FILE
pi-subagent-bridge status CWD SESSION_ID
pi-subagent-bridge resume CWD SESSION_ID FEEDBACK_FILE
pi-subagent-bridge cancel CWD SESSION_ID
```

The CLI prints one JSON result to stdout on success and a diagnostic on stderr on error. Pass a scope file rather than interpolating JSON into a shell command. Do not put credentials or private source into task briefs.

## Safety and durability

The primary SDK subprocess has an exact model/effort, explicit tool allowlist, private session storage, and an isolated resource loader with no ambient extensions or subagent launches. The SDK prompt settles before its terminal result is written atomically. Ambiguous process exits and interrupted admissions **block** new attempts. The parent maintains cross-process worktree leases and per-session locks. Only a verified quota/model availability error may switch to Command Code, **before any edits**. A partial worktree is never replayed under another provider.

State, prompt job files, SDK JSONL transcripts and Command Code NDJSON results live under ignored `.work/worker-bridge/`. These files may contain code and model output; keep that directory private. This is *not* an OS sandbox: ignored files, absolute-path reads, and external processes are beyond Git write-scope detection.

## Tests

```
cd tools/pi-subagent-bridge
npm test
cd ../..
python3 -I dotfiles/pi-test.py
python3 -I dotfiles/orchestrate-test.py
python3 -I tools/sync/claude-worker-test.py
python3 -I tools/sync/pi-worker-test.py
python3 -I tools/sync/opencode-worker-test.py
sh dotfiles/worker-watch-test.sh
```

Mock tests cover scope, fallback, locking, resumes, and protocol shape but do not prove live account access or SDK catalog compatibility. Before unattended use, complete a disposable one-file worktree test of each tier, pre-edit model/quota fallback, post-edit quota refusal, same-session resume and restart recovery. Never claim these checks passed without executing them.
