# pi-subagent-bridge

One shared delegation bridge for every coding harness. Parents own scoping, worktrees, verification, integration and cleanup. The MCP and CLI expose the same durable session state. New `expert` and `god` tasks run **only** Antigravity CLI `gemini-4-carbon-high`; no Argon, native Opus/Sol, or fallback. Scout, mechanic and worker retain the existing Codex → Command Code → Pi backend chain. Already-admitted legacy sessions retain their original models.

| Tier | Primary | Fallback (in order) |
| --- | --- | --- |
| scout | Codex `gpt-6-luna` (medium) | Command Code `meta/muse-ember` (medium), Pi `opencode-go/muse-spark-1.3-contributor` (medium) |
| mechanic | Codex `gpt-6-luna` (high) | Command Code `meta/muse-ember` (xhigh), Pi `opencode-go/muse-spark-1.3-contributor` (high) |
| worker | Codex `gpt-6.1-terra` (medium) | Command Code `deepseek/deepseek-v4.1-flash` (high), Pi `muse-sdk/muse-spark-1.3` (xhigh), Pi `opencode-go/deepseek-v4.1-flash` (high) |
| expert | Antigravity `gemini-4-carbon-high` (high) | **None** |
| god | Antigravity `gemini-4-carbon-high` (high) | **None** |

The bridge validates `agy models` for the exact Carbon slug before admission and pins it on every launch and resume. Its streaming JSON `init` record must confirm the same model before success is accepted. Carbon entitlement is required (Google AI Ultra or eligible enterprise); absence, quota or authentication errors stop the lane. This repository does not purchase API credits. For tasks formerly using Gemini 3.8 Flash in Antigravity, the documented successor slugs are `gemini-4-hydrogen-{low,medium,high,xhigh}`; no tracked Gemini 3.8 bridge pin exists to migrate. Direct Antigravity use should pin available Hydrogen and must never select Argon or fall back to 3.8. See [Google's headless CLI reference](https://antigravity.google/docs/cli/headless/).

The lower-tier Pi route retains bounded native Pi nesting. There is **no Pi `god` tier**. The Carbon backend is a root executor, not a Pi agent; it may not use bridge nesting and must not start separate native subagents. Carbon invokes `agy` headlessly with tool permissions allowed, so independent diff/scope verification remains mandatory; this does **not** provide an OS sandbox.

## Setup

`sh sync` installs Node.js and Command Code as usual, but installs the Pi 1.5.0 CLI/SDK plus pinned subagents/Muse/intercom dependencies **exclusively from the pinned, SHA-256-verified `pi-build` release archive** named in `tools/pi/runtime.pin.json`. It links the bridge to the same selected dependency closure (no npm install). The bridge MCP is registered for Claude, Pi and OpenCode; Codex uses tracked config. `sh sync bridge` reconciles MCP registrations; the old recognized `usr-opencode-worker` entry migrates to `pi-subagent-bridge` while foreign servers are preserved.

`sh sync plan`
`sh sync doctor`

The explicit CLI shim is installed at `~/.local/bin/pi-subagent-bridge`. No OpenCode service or `pi -p` is needed. A scoped SDK host loads only pi-subagents and calls its `spawn`/`resume` RPC. The package owns detached child execution, session continuation, and completion artifacts. Interactive Pi loads locally bundled subagents and intercom extensions through its managed launcher; no `pi install`, `pi update`, npm or npx runs on the Pi setup path. The scoped SDK bridge continues to load only subagents and (when needed) Muse, never unrestricted intercom tools.

## Bounded native Pi nesting

The Pi fallback is a real subagent runtime, not a prompt-only coordination promise. Its required child extension registers an inherited `allowedAgents` capability ceiling for each tier and blocks unapproved `subagent` launches (model/cwd/worktree overrides, workflow scripting, higher tiers). Upstream Pi separately enforces the depth cap at launch; an inner child cannot spawn a third layer. The bridge validates the typed tier contract against parsed agent YAML and the exact model scope **before a new child starts**. Nested calls must use `options: { agentScope: "user" }` to prevent project-scoped agent shadows; per-call model, worktree, and tool overrides fail before delegation. The central rules are `src/tier-policy.ts`, the required guard is `src/nested-guard.ts`, and the profile validator is `src/tier-profile.ts`.

| Pi parent | Allowed nested child |
| --- | --- |
| scout | scout |
| mechanic | scout, mechanic |
| worker | scout, mechanic, worker |
| expert | scout, mechanic, worker, expert |

**Codex and Command Code workers are leaves.** Nested Pi children share their first-level worktree and scope; native restrictions do not replace OS sandboxing, worktree diff review or acceptance proof. The CLI/MCP entrypoint is not an authorized child launcher.

## MCP tools

`worker_model_check(cwd, tier)` reports pinned Carbon and no fallback for expert/god; for scout/mechanic/worker it reports Codex first, then Command Code and the pinned Pi fallback.

`worker_start(cwd, title, tier, scope, brief)` admits exactly one scoped assignment in a **clean linked worktree** at `<repo>/.work/wt/<name>`. It returns `usrw_*`; this means **admitted**, not complete. Its scope:

- `base_revision`: exact 40-character HEAD.
- `writable_paths`: no more than 20 exact relative files/prefixes; empty only for a read-only scout.
- `acceptance_proof`: one named check and expected result, or read-only file:line evidence.
- `attempt_limit`: 1 or 2, with the second only for a justified same-scope correction.
- `stop_on`: ambiguity, new dependencies, scope or contract changes, unavailable proof.

`worker_status(cwd,session_id)` observes the real backend, tier/effort, result, changed and out-of-scope paths, HEAD stability and fallback reason. It also reports `continuations` used against `continuation_limit`, so a `turn_limit` session can be continued for free with `worker_resume` until that cap, and `steers` used against `steer_limit`. A Codex or Command Code run whose recorded process is gone, or whose PID now has a different start time (a reused PID), is reported as the terminal `interrupted` state and its worktree lease is released; an alive PID with the recorded start time stays `running` and keeps the lease. The parent verifies the output and independently checks the diff; an assistant claim cannot count as test proof.

`worker_resume(cwd,session_id,feedback)` preserves the approved scope and either resumes the owned native pi-subagents child in its original SDK host session, the Codex thread, or the Command Code session. It refuses uncertain active runs, scope expansion, and depleted attempts. A `turn_limit` result is continued with `TURN_LIMIT_CONTINUATIONS` free continuations that do not consume attempts; the used count and cap are in `worker_status`.

`worker_steer(cwd,session_id,note)` redirects a **running** worker without changing its scope or write boundaries. On the Pi backend it forwards the note to the native pi-subagents `steer` RPC for the owned run. On Codex and Command Code it verifies HEAD and the write boundary exactly as `worker_resume` does, interrupts the run, waits until the recorded process is proven gone, then resumes the same session and the original prompt plus `PARENT STEERING (same scope and write boundaries): <note>`. It never changes `attempts`; it is bounded by its own `steer_limit`, and it refuses to signal a PID that this bridge process does not own. A finished or non-running session is refused with a pointer to `worker_resume`.

`worker_cancel(cwd,session_id)` interrupts only a child owned by the current process. Never signal a stale PID after restart. Cancellation is not proof of termination. For Codex and Command Code, a later `worker_status` can report `cancelled` and release the lease after proving the recorded process gone. Pi requires a terminal result: a dead host without one remains `unknown_or_interrupted` and keeps its lease.

## Coordinating many workers

Use `worker-campaign` to discover persisted sessions and wait for notifications, or `worker-watch` to follow one session. See [campaign coordination](../../docs/pi.md#coordinating-a-campaign) for commands and state-file locations. These shell watchers do not perform the bridge's process-start identity checks or release leases. Their `interrupted` observation for a dead Pi host is not equivalent to an accepted terminal result; check `worker_status` before reusing the worktree.

## CLI

Identical actions are available to harnesses without MCP:

```
pi-subagent-bridge mcp
pi-subagent-bridge model-check CWD TIER
pi-subagent-bridge start CWD TITLE TIER SCOPE_JSON_FILE BRIEF_FILE
pi-subagent-bridge status CWD SESSION_ID
pi-subagent-bridge resume CWD SESSION_ID FEEDBACK_FILE
pi-subagent-bridge steer CWD SESSION_ID NOTE_FILE
pi-subagent-bridge cancel CWD SESSION_ID
```

The CLI prints one JSON result to stdout on success and a diagnostic on stderr on error. Pass a scope file rather than interpolating JSON into a shell command. Do not put credentials or private source into task briefs.

## Safety and durability

Codex and Command Code record process start time (Linux `/proc/<pid>/stat` field 22; macOS `ps -o lstart=`) to distinguish the owned child from a reused PID. An alive process with that identity keeps its lease; proven interruption releases it. `--verbose` records the Command Code session identity before the result so steering can resume the same session. Cross-process worktree leases and locks sit at the MCP/CLI boundary.

Codex runs use the signed-in ChatGPT account and do not use API keys. Codex scouts disable shell execution and expose read-only tools through a dedicated local MCP server. Codex writers use the workspace-write sandbox. The routing policy permits switching only for a missing executable, unavailable exact model/provider, or recognized usage limit before edits and with unambiguous admission. Scout/mechanic/worker go from Codex to Command Code and their approved Pi fallbacks. Expert/god run Carbon only; provider failure cannot switch them to another model. An admitted Pi session retains its provider. Task failures, uncertain admissions, missing completion receipts, and partial work do not authorize another start. `fallback_reason` summarizes a switch, `fallback_notice` describes its automatic handling, and `fallback_detail` retains the original provider diagnostic; a successful switch clears `error`.

Exception recovery accepts only the admitted run's matching metadata and paired output. Uncertain create or prompt dispatch retains the transition and lease without provider replay. New lower-tier sessions persist remaining Muse/Go destinations and the exact selected model; legacy admitted sessions retain their pins. New expert/god sessions pin Carbon as their only provider.

## Reloading the server

Each MCP client runs its own bridge server, so a code change reaches a client only after its server restarts. `pi-subagent-bridge-reload` stops the server that belongs to the calling client (`--all` stops every client's, `--dry-run` lists them). It signals only the server process: workers are separate processes with on-disk state, so running workers keep running. In Claude Code, `/mcp`, then Reconnect on `pi-subagent-bridge`, restarts that session's server without the script. The script finds its target by walking up from the shell it runs in, so run it from a shell the client started, or pass `--all`.

State, prompt job files, SDK JSONL transcripts, Codex and Command Code NDJSON results live under ignored `.work/worker-bridge/`. These files may contain code and model output; keep that directory private. This is *not* an OS sandbox: ignored files, absolute-path reads, and external processes are beyond Git write-scope detection.

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
sh dotfiles/worker-campaign-test.sh
```

`npm test` is an explicit developer check requiring the package's development dependencies and a supported Node; the production archive does not supply that test toolchain. Mock tests cover scope, fallback, locking, resumes, and protocol shape but do not prove live account access or SDK catalog compatibility. Before unattended use, complete a disposable one-file worktree test of each tier, pre-edit model/quota fallback, post-edit quota refusal, same-session resume and restart recovery. Never claim these checks passed without executing them.

## Muse Code subscription

The bridge uses the exact-pinned
[`pi-muse-subscription`](https://github.com/jkeskikangas/pi-muse-subscription) extension
as the Pi fallback for **worker (xhigh)** when Command Code is unavailable or fails
conclusively before edits. Scout and mechanic use the pinned Contributor Spark models instead;
expert has no Muse route and stays on Command Code then OpenCode Go. The provider is
loaded only inside Muse SDK workers, never globally into ordinary Pi sessions.
This is subscription usage via the official Muse Code SDK, **not** the metered Meta API.

- Install Muse Code >=1.4.14, launch `muse`, and sign in with `/login`.
- Run `sh sync`; it links the bridge to the local pinned SDK/Muse archive, without npm. No environment flag
  selects the Muse route, and `USR_PI_MUSE_SUBSCRIPTION` is ignored. `sh sync bridge`
  reconciles the bridge.
- On a clean *linked* worktree, run `pi-subagent-bridge model-check CWD scout`
  and a disposable scout task using `worker_start` / `worker_status`. The model
  check proves the local extension and the OpenCode Go credential exist, **not** entitlement
  or available quota. The real run verifies both.
- Monitor `muse usage`. The bridge sets `PI_MUSE_SDK_CONTRIBUTOR=on` for its Muse
  workers, so Meta may use prompts, code and outputs for training in exchange for
  more usage; do not route material you cannot share under those terms through the
  Muse worker lane. Keep `META_API_KEY` unset: it would otherwise select metered
  API billing (the extension also strips it from its Muse Code subprocess).

Dedicated `muse-worker` profile restricts nested tasks to the Muse subscription
provider, with immutable equal-or-weaker tier ceilings and max depth 2; scout and
mechanic children run the pinned Contributor Spark agents instead. The SDK host explicitly loads
the pinned provider and requires it in each detached child, even when ambient
extensions are disabled. Admitted sessions retain their pinned provider; uncertain
admissions retain their lease under [Safety and durability](#safety-and-durability).

This is a community adapter using a developer-preview Muse Code SDK.
Live account compatibility and network behavior must be tested locally before
unattended use.
