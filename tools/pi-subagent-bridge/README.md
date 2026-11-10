# pi-subagent-bridge

One shared delegation bridge for every coding harness. Parents remain responsible for decomposition, verification, integration and cleanup. The MCP server and CLI expose the **same** durable session state and worktree contracts. **Command Code runs first** (Muse Ember for scout/mechanic, DeepSeek V4.1 Flash for worker/expert); the exact-pinned **Muse SDK subscription is the default middle option** for scout/mechanic/worker; **OpenCode Go via embedded Pi SDK + pi-subagents RPC is the last-resort fallback**. No OpenCode server or separate custom agent loop is started.

| Tier | Command Code first | Effort | Muse SDK middle | OpenCode Go fallback |
| --- | --- | --- | --- | --- |
| scout | `meta/muse-ember` | medium | `muse-sdk/muse-ember-1.0` (medium) | `opencode-go/muse-spark-1.3-contributor` (medium) |
| mechanic | `meta/muse-ember` | xhigh | `muse-sdk/muse-ember-1.0` (xhigh) | `opencode-go/muse-spark-1.3-contributor` (high) |
| worker | `deepseek/deepseek-v4.1-flash` | high | `muse-sdk/muse-spark-1.3` (xhigh) | `opencode-go/deepseek-v4.1-flash` (high) |
| expert | `deepseek/deepseek-v4.1-flash` | max | — | `opencode-go/deepseek-v4.1-flash` (max) |

No `god` tier. Claude Code and Codex alone use their pinned native `god` agents. Command Code runs remain leaves. Native Pi children may spawn exactly one additional generation, equal-or-weaker only (typed tier guard, immutable child extension, and max depth 2), on both the Muse SDK and OpenCode Go routes. **Only OpenCode Go models are eligible for the last-resort Go fallback.** Do not use `opencode/*` Zen, metered OpenCode models, or custom endpoints. The bridge requires `cmd login` for its preferred provider, a Muse Code login for the middle option, and a configured OpenCode Go credential for the last-resort fallback. No unapproved models are permitted.

## Setup

`sh sync` installs Node.js, Pi, Command Code, and the bridge's pinned Pi SDK and pi-subagents dependencies, and registers the MCP server in Claude, Pi and OpenCode. Codex reads its tracked config. `sh sync bridge` reconciles MCP registrations; the old recognized `usr-opencode-worker` entry migrates to `pi-subagent-bridge` while foreign servers are preserved.

`sh sync plan`
`sh sync doctor`

The explicit CLI shim is installed at `~/.local/bin/pi-subagent-bridge`. No OpenCode service or `pi -p` is needed. A scoped SDK host loads only pi-subagents and calls its `spawn`/`resume` RPC. The package owns detached child execution, session continuation, and completion artifacts. `sh sync` now also reconciles the pinned interactive Pi extension automatically; no separate command is necessary.

## Bounded native Pi nesting

The Pi fallback is a real subagent runtime, not a prompt-only coordination promise. Its required child extension registers an inherited `allowedAgents` capability ceiling for each tier and blocks unapproved `subagent` launches (model/cwd/worktree overrides, workflow scripting, higher tiers). Upstream Pi separately enforces the depth cap at launch; an inner child cannot spawn a third layer. The bridge validates the typed tier contract against parsed agent YAML and the exact model scope **before a new child starts**. Nested calls must use `options: { agentScope: "user" }` to prevent project-scoped agent shadows; per-call model, worktree, and tool overrides fail before delegation. The central rules are `src/tier-policy.ts`, the required guard is `src/nested-guard.ts`, and the profile validator is `src/tier-profile.ts`.

| Pi parent | Allowed nested child |
| --- | --- |
| scout | scout |
| mechanic | scout, mechanic |
| worker | scout, mechanic, worker |
| expert | scout, mechanic, worker, expert |

**Command Code is first but still does not support child delegation.** Nested Pi children share their first-level worktree and scope; native restrictions do not replace OS sandboxing, worktree diff review or acceptance proof. The CLI/MCP entrypoint is not an authorized child launcher.

## MCP tools

`worker_model_check(cwd, tier)` reports Command Code first (executable installed), the Muse SDK middle option where the tier has one, and the exact OpenCode Go last-resort model/auth.

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

The Command Code runner is preferred and pins an exact model and effort. If Command Code is not installed or its provider/model/usage fails conclusively before edits, the bridge tries the pinned Muse SDK model for scout/mechanic/worker, then the allowed OpenCode Go model for every tier; each Pi route loads only the pinned pi-subagents extension (plus the pinned Muse provider on the Muse route) and submits via `subagents:rpc:v1:request`. An absent receipt, interrupted process, or uncertain admission remains blocked. Cross-process worktree leases and locks remain at the MCP/CLI boundary. No fallback after edits or a second fallback from Muse/Go is allowed. The switch is reported transparently, not as a failure: `worker_start`/`worker_status` return `fallback_reason` (what happened), `fallback_notice` (that the switch was automatic and needs no parent action, with the same scope and pinned tier model and no duplicate start), and `fallback_detail` (the original provider message, for diagnosis). The `error` field is cleared once the fallback has safely taken over. Partial work is never replayed under a second provider.

## Reloading the server

Each MCP client runs its own bridge server, so a code change reaches a client only after its server restarts. `pi-subagent-bridge-reload` stops the server that belongs to the calling client (`--all` stops every client's, `--dry-run` lists them). It signals only the server process: workers are separate processes with on-disk state, so running workers keep running. In Claude Code, `/mcp`, then Reconnect on `pi-subagent-bridge`, restarts that session's server without the script. The script finds its target by walking up from the shell it runs in, so run it from a shell the client started, or pass `--all`.

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

## Muse Code subscription

The bridge uses the exact-pinned
[`pi-muse-subscription`](https://github.com/jkeskikangas/pi-muse-subscription) extension
as the default **middle option** for **scout (medium)**, **mechanic (xhigh)** and
**worker (xhigh)** when Command Code is unavailable or fails conclusively before edits.
Expert has no Muse route and stays on Command Code then OpenCode Go. The provider is
loaded only inside Muse SDK workers, never globally into ordinary Pi sessions.
This is subscription usage via the official Muse Code SDK, **not** the metered Meta API.

- Install Muse Code >=1.4.14, launch `muse`, and sign in with `/login`.
- Run `sh sync`; it installs the exact local bridge npm pin. No environment flag
  selects the Muse route, and `USR_PI_MUSE_SUBSCRIPTION` is ignored. `sh sync bridge`
  reconciles the bridge.
- On a clean *linked* worktree, run `pi-subagent-bridge model-check CWD scout`
  and a disposable scout task using `worker_start` / `worker_status`. The model
  check proves the local extension and Muse CLI exist, **not** subscription login
  or available quota. The real run verifies entitlement and tool handling.
- Monitor `muse usage`. The bridge sets `PI_MUSE_SDK_CONTRIBUTOR=on` for its Muse
  workers, so Meta may use prompts, code and outputs for training in exchange for
  more usage; do not route material you cannot share under those terms through the
  Muse middle option. Keep `META_API_KEY` unset: it would otherwise select metered
  API billing (the extension also strips it from its Muse Code subprocess).

Dedicated `muse-scout`, `muse-mechanic` and `muse-worker` profiles restrict nested
tasks to the same subscription provider, with immutable equal-or-weaker tier ceilings
and max depth 2. The SDK host explicitly loads the pinned provider and requires it in
each detached child, even when ambient extensions are disabled. If admission is
uncertain, the bridge never replays it; an admitted Muse session keeps its pinned
provider and does not fall back again.

This is a community adapter using a developer-preview Muse Code SDK.
Live account compatibility and network behavior must be tested locally before
unattended use.
