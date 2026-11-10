# pi-subagent-bridge

One shared delegation bridge for every coding harness. Parents remain responsible for decomposition, verification, integration and cleanup. The MCP server and CLI expose the **same** durable session state and worktree contracts. **Command Code runs first** (Muse Ember for scout/mechanic, DeepSeek V4.1 Flash for worker/expert); **OpenCode Go via embedded Pi SDK + pi-subagents RPC is the only fallback**. No OpenCode server or separate custom agent loop is started.

| Tier | Command Code first | Effort | OpenCode Go fallback | Thinking |
| --- | --- | --- | --- | --- |
| scout | `meta/muse-ember` | medium | `opencode-go/muse-spark-1.3-contributor` | medium |
| mechanic | `meta/muse-ember` | xhigh | `opencode-go/muse-spark-1.3-contributor` | high |
| worker | `deepseek/deepseek-v4.1-flash` | high | `opencode-go/deepseek-v4.1-flash` | high |
| expert | `deepseek/deepseek-v4.1-flash` | max | `opencode-go/deepseek-v4.1-flash` | max |

No `god` tier. Claude Code and Codex alone use their pinned native `god` agents. Command Code runs remain leaves. Native Pi fallback children may spawn exactly one additional generation, equal-or-weaker only (typed tier guard, immutable child extension, and max depth 2). **Only OpenCode Go models are eligible for OpenCode/Pi delegation.** Do not use `opencode/*` Zen, metered OpenCode models, or custom endpoints. Ember runs on Command Code only; the OpenCode Go scout/mechanic fallback remains Muse Spark 1.3 Contributor. The bridge requires `cmd login` for its preferred provider and a separate configured OpenCode Go credential for fallback. No unapproved models are permitted.

## Setup

`sh sync` installs Node.js, Pi, Command Code, and the bridge's pinned Pi SDK and pi-subagents dependencies, and registers the MCP server in Claude, Pi and OpenCode. Codex reads its tracked config. `sh sync bridge` reconciles MCP registrations; the old recognized `usr-opencode-worker` entry migrates to `pi-subagent-bridge` while foreign servers are preserved.

`sh sync plan`
`sh sync doctor`

The explicit CLI shim is installed at `~/.local/bin/pi-subagent-bridge`. No OpenCode service or `pi -p` is needed. A scoped SDK host loads only pi-subagents and calls its `spawn`/`resume` RPC. The package owns detached child execution, session continuation, and completion artifacts. `sh sync` now also reconciles the pinned interactive Pi extension automatically; no separate command is necessary.

## Bounded native Pi nesting

The Pi fallback is a real subagent runtime, not a prompt-only coordination promise. Its required child extension registers an inherited `allowedAgents` capability ceiling for each tier and blocks unapproved `subagent` launches (model/cwd/worktree overrides, workflow scripting, higher tiers). Upstream Pi separately enforces the depth cap at launch; an inner child cannot spawn a third layer. The bridge validates the typed tier contract against parsed agent YAML and strict Go-only model scope **before a new child starts**. Nested calls must use `options: { agentScope: "user" }` to prevent project-scoped agent shadows; per-call model, worktree, and tool overrides fail before delegation. The central rules are `src/tier-policy.ts`, the required guard is `src/nested-guard.ts`, and the profile validator is `src/tier-profile.ts`.

| Pi parent | Allowed nested child |
| --- | --- |
| scout | scout |
| mechanic | scout, mechanic |
| worker | scout, mechanic, worker |
| expert | scout, mechanic, worker, expert |

**Command Code is first but still does not support child delegation.** Nested Pi children share their first-level worktree and scope; native restrictions do not replace OS sandboxing, worktree diff review or acceptance proof. The CLI/MCP entrypoint is not an authorized child launcher.

## MCP tools

`worker_model_check(cwd, tier)` reports Command Code first (executable installed) and the exact OpenCode Go-only Pi fallback model/auth.

`worker_start(cwd, title, tier, scope, brief)` admits exactly one scoped assignment in a **clean linked worktree** at `<repo>/.work/wt/<name>`. It returns `usrw_*`; this means **admitted**, not complete. Its scope:

- `base_revision`: exact 40-character HEAD.
- `writable_paths`: no more than 20 exact relative files/prefixes; empty only for a read-only scout.
- `acceptance_proof`: one named check and expected result, or read-only file:line evidence.
- `attempt_limit`: 1 or 2, with the second only for a justified same-scope correction.
- `stop_on`: ambiguity, new dependencies, scope or contract changes, unavailable proof.

`worker_status(cwd,session_id)` observes the real backend, tier/effort, result, changed and out-of-scope paths, HEAD stability and fallback reason. The parent verifies the output and independently checks the diff; an assistant claim cannot count as test proof.

`worker_resume(cwd,session_id,feedback)` preserves the approved scope and either resumes the owned native pi-subagents child in its original SDK host session, or the Command Code session. It refuses uncertain active runs, scope expansion, and depleted attempts.

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

The Command Code runner is preferred and pins an exact model and effort. If Command Code is not installed or its provider/model/usage fails conclusively before edits, the embedded Pi SDK host loads only the pinned pi-subagents extension and submits the allowed OpenCode Go model via `subagents:rpc:v1:request`. An absent receipt, interrupted process, or uncertain admission remains blocked. Cross-process worktree leases and locks remain at the MCP/CLI boundary. No fallback after edits or a second fallback from Go is allowed. The switch is reported transparently, not as a failure: `worker_start`/`worker_status` return `fallback_reason` (what happened), `fallback_notice` (that the switch was automatic and needs no parent action, with the same scope and pinned tier model and no duplicate start), and `fallback_detail` (the original provider message, for diagnosis). The `error` field is cleared once the fallback has safely taken over. Partial work is never replayed under a second provider.

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
