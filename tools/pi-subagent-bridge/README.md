# pi-subagent-bridge

One shared delegation bridge for every coding harness except OpenCode. Parents own scoping, worktrees, verification, integration and cleanup. The MCP and CLI expose the same durable session state.

<!-- policy:begin routing-summary -->
<!-- Generated from tools/pi-subagent-bridge/src/policy.ts; run make generate. -->
New `expert` assignments use Antigravity CLI `gemini-4-hydrogen-xhigh` (`xhigh`) exclusively, with no fallback. The available tiers are `scout`, `mechanic`, `worker`, `expert`; there is no `god` tier. The model families `gemini-4-argon` and `gemini-4-carbon` are prohibited, including every effort variant. Already-admitted sessions retain their recorded models and routes.

| Tier | Primary | Fallback (in order) |
| --- | --- | --- |
| scout | Codex `gpt-6-luna` (`medium`) | Command Code `meta/muse-ember` (`medium`); Pi `opencode-go/muse-spark-1.3-contributor` (`medium`) |
| mechanic | Codex `gpt-6-luna` (`high`) | Command Code `meta/muse-ember` (`xhigh`); Pi `opencode-go/muse-spark-1.3-contributor` (`high`) |
| worker | Codex `gpt-6.1-terra` (`medium`) | Command Code `deepseek/deepseek-v4.1-flash` (`high`); Pi `muse-sdk/muse-spark-1.3` (`xhigh`); Pi `opencode-go/deepseek-v4.1-flash` (`high`) |
| expert | Antigravity CLI `gemini-4-hydrogen-xhigh` (`xhigh`) | **None. Fail closed.** |
<!-- policy:end routing-summary -->

The bridge verifies the exact Antigravity model with `agy models` before admission, pins it on launch and resume, and checks the streaming `init` model before accepting success. Missing entitlement, authentication failures and quota exhaustion stop the terminal lane. This repository does not purchase API credits. Direct Antigravity selection follows the approved pins in [orchestrate](../../dotfiles/base/.agents/skills/orchestrate/SKILL.md).

The Antigravity executor is a leaf and may not launch native subagents. It runs headlessly with tool permissions allowed; independent diff/scope verification remains mandatory. This does not provide an OS sandbox.

## Setup

`sh sync` installs Node.js and Command Code as usual, but installs the Pi 1.5.0 CLI/SDK plus pinned subagents/Muse/intercom dependencies **exclusively from the pinned, SHA-256-verified `pi-build` release archive** named in `tools/pi/runtime.pin.json`. It links the bridge to the same selected dependency closure (no npm install). The bridge MCP is registered for Claude and Pi; OpenCode never registers it (`sh sync` removes an owned OpenCode registration instead). Codex uses tracked config. `sh sync bridge` reconciles MCP registrations; foreign servers are preserved.

`sh sync plan`
`sh sync doctor`

The explicit CLI shim is installed at `~/.local/bin/pi-subagent-bridge`. No OpenCode service or `pi -p` is needed. A scoped SDK host loads only pi-subagents and calls its `spawn`/`resume` RPC. The package owns detached child execution, session continuation, and completion artifacts. Interactive Pi loads locally bundled subagents and intercom extensions through its managed launcher; no `pi install`, `pi update`, npm or npx runs on the Pi setup path. The scoped SDK bridge continues to load only subagents and (when needed) Muse, never unrestricted intercom tools.

## Bounded native Pi nesting

The Pi fallback is a real subagent runtime, not a prompt-only coordination promise. Its required child extension registers an inherited `allowedAgents` capability ceiling for each tier and blocks unapproved `subagent` launches (model/cwd/worktree overrides, workflow scripting, higher tiers). Upstream Pi separately enforces the depth cap at launch; an inner child cannot spawn a third layer. The bridge validates the typed tier contract against parsed agent YAML and the exact model scope **before a new child starts**. Nested calls must use `options: { agentScope: "user" }` to prevent project-scoped agent shadows; per-call model, worktree, and tool overrides fail before delegation. The central rules are `src/tier-policy.ts`, the required guard is `src/nested-guard.ts`, and the profile validator is `src/tier-profile.ts`.

<!-- policy:begin pi-nesting -->
<!-- Generated from tools/pi-subagent-bridge/src/policy.ts; run make generate. -->
| Pi parent | Allowed nested child |
| --- | --- |
| scout | scout |
| mechanic | scout, mechanic |
| worker | scout, mechanic, worker |
| expert (native Pi) | scout, mechanic, worker, expert |
<!-- policy:end pi-nesting -->

**Codex and Command Code workers are leaves.** Nested Pi children share their first-level worktree, scope and write budget, and the outer parent still owns acceptance and review; native restrictions do not replace OS sandboxing, worktree diff review or acceptance proof. The CLI/MCP entrypoint is not an authorized child launcher.

## MCP tools

`worker_model_check(cwd, tier)` reports the approved routes and current availability for the requested tier. When the Muse route is probed it also reports the `Muse Code` version of the installed `muse` binary it was qualified against. `make policy` exports the approved policy offline without probing account availability.

`worker_start(cwd, title, tier, scope, brief)` admits exactly one scoped assignment in a **clean linked worktree** at `<repo>/.work/wt/<name>`. It returns `usrw_*`; this means **admitted**, not complete. Its scope:

- `base_revision`: exact 40-character HEAD.
- `writable_paths`: no more than 20 exact relative files/prefixes; empty only for a read-only scout.
- `acceptance_proof`: one named check and expected result, or read-only file:line evidence.
- `attempt_limit`: 1 or 2, with the second only for a justified same-scope correction.
- `stop_on`: ambiguity, new dependencies, scope or contract changes, unavailable proof.

No backend runs in an OS sandbox, so workers have the network and host access of the user running the bridge. Records admitted with the retired `network` scope flag still decode; new requests that set it are rejected.

The admission result includes `watch`, a `pi-subagent-bridge watch` command that blocks until the executor ends. The bridge has no completion callback, so run `watch` as a background task; a harness that only polls never learns that a worker finished.

`worker_status(cwd,session_id)` first advances the session under its lock (pre-edit fallbacks, a blocked fallback, and releasing the lease of a terminal run), then reports what read-only inspection observes of the real backend, tier/effort, result, changed and out-of-scope paths, HEAD stability and fallback reason. The prompt requires the proof record to end with `ACCEPTANCE: met` or `ACCEPTANCE: not met`. A run that exits cleanly without a final `ACCEPTANCE: met` reports state `incomplete`, `acceptance_claim` `not_met` or `missing`, and `acceptance_blocked: true`; `incomplete` is resumable like any finished attempt. It also reports `continuations` used against `continuation_limit`, so a `turn_limit` session can be continued for free with `worker_resume` until that cap, and `steers` used against `steer_limit`. A Codex or Command Code run whose recorded process is gone, or whose PID now has a different start time (a reused PID), is reported as the terminal `interrupted` state and its worktree lease is released; an alive PID with the recorded start time stays `running` and keeps the lease. The parent verifies the output and independently checks the diff; an assistant claim cannot count as test proof.

`worker_resume(cwd,session_id,feedback)` preserves the approved scope and either resumes the owned native pi-subagents child in its original SDK host session, the Codex thread, or the Command Code session. It refuses uncertain active runs, scope expansion, and depleted attempts. A `turn_limit` result is continued with `TURN_LIMIT_CONTINUATIONS` free continuations that do not consume attempts; the used count and cap are in `worker_status`.

`worker_steer(cwd,session_id,note)` redirects a **running** worker without changing its scope or write boundaries. On the Pi backend it forwards the note to the native pi-subagents `steer` RPC for the owned run. On Codex and Command Code it verifies HEAD and the write boundary exactly as `worker_resume` does, interrupts the run, waits until the recorded process is proven gone, then resumes the same session and the original prompt plus `PARENT STEERING (same scope and write boundaries): <note>`. It never changes `attempts`; it is bounded by its own `steer_limit`, and it refuses to signal a PID that this bridge process does not own. A finished or non-running session is refused with a pointer to `worker_resume`.

`worker_cancel(cwd,session_id)` interrupts only a child owned by the current process. Never signal a stale PID after restart. Cancellation is not proof of termination. For Codex and Command Code, a later `worker_status` can report `cancelled` and release the lease after proving the recorded process gone. Pi requires a terminal result: a dead host without one remains `unknown_or_interrupted` and keeps its lease. A worker that already ended at a provider usage limit with partial edits (`blocked_partial_work`) is not signaled; once the parent has preserved the work, the call releases the worktree lease instead.

## Coordinating many workers

Use `pi-subagent-bridge campaign` to discover persisted sessions, wait for notifications and print a JSON campaign snapshot, `pi-subagent-bridge watch` to follow one session, and `pi-subagent-bridge inspect` to print one session's snapshot. See [campaign coordination](../../docs/pi.md#coordinating-a-campaign) for commands and state-file locations.

All of them, and `worker_status`, share one read-only interpretation (`src/inspect.ts`): provider receipts, Pi child records and the recorded process identity (start time, so a reused PID is `interrupted`). A live process is `running` even when a receipt already exists. Inspection never saves a session, creates a directory, changes a lease, signals a process or launches a provider; only `worker_status` advances a session. Watch and campaign output does not release a lease, and a dead Pi host without a result is `unknown_or_interrupted`, which is not an accepted terminal result: check `worker_status` before reusing the worktree.

## CLI

Identical actions are available to harnesses without MCP:

```
pi-subagent-bridge mcp
pi-subagent-bridge policy
pi-subagent-bridge model-check CWD TIER
pi-subagent-bridge start CWD TITLE TIER SCOPE_JSON_FILE BRIEF_FILE
pi-subagent-bridge status CWD SESSION_ID
pi-subagent-bridge resume CWD SESSION_ID FEEDBACK_FILE
pi-subagent-bridge steer CWD SESSION_ID NOTE_FILE
pi-subagent-bridge cancel CWD SESSION_ID
pi-subagent-bridge inspect PATH SESSION_ID
pi-subagent-bridge watch [--state] ROOT SESSION_ID [IDLE_MINUTES]
pi-subagent-bridge campaign wait [--timeout DURATION] [ROOT...]
pi-subagent-bridge campaign ack ID...
pi-subagent-bridge campaign list [--json] [ROOT...]
```

Inspection snapshots include `attention`: `active`, `finished`, `gone`, `needs_attention`, or `unknown`, alongside the detailed `execution_state`. Campaign wait reports every non-active session, including blocked and unknown sessions; timeout ticks count only active sessions. Watch exits 4 for sessions needing attention or with unknown state.

`inspect`, `watch` and `campaign` only read bridge state (`campaign ack` writes its own acknowledgement file). `inspect` prints one JSON snapshot; `watch` and `campaign wait|ack|list` print text with documented exit codes (`watch`: 0 finished, 2 stalled, 3 exited without a terminal result, 4 uninspectable). The other commands print one JSON result to stdout on success and a diagnostic on stderr on error. Pass a scope file rather than interpolating JSON into a shell command. Do not put credentials or private source into task briefs.

`pi-subagent-bridge policy` exports approved routes, native Pi restrictions and
harness exceptions without loading the SDK, probing a provider, or reading home
configuration. `make policy` provides the same inspection directly from a checkout.
Edit the typed policy and run `make generate`; [policy projections](../policy/README.md)
explains generated ownership and read-only drift checks.

## Safety and durability

Codex and Command Code record process start time (Linux `/proc/<pid>/stat` field 22; macOS `ps -o lstart=`) to distinguish the owned child from a reused PID. An alive process with that identity keeps its lease; proven interruption releases it. `--verbose` records the Command Code session identity before the result so steering can resume the same session. Cross-process worktree leases and locks sit at the MCP/CLI boundary.

Codex runs use the signed-in ChatGPT account and do not use API keys. Codex runs with `--sandbox danger-full-access`, like every other backend. Codex scouts disable shell, unified exec, computer-use, and browser tools (the code-mode host stays enabled because Codex routes every tool call, including the scout's MCP tools, through it) and expose read-only tools through a dedicated local MCP server; Codex's built-in patch tool cannot be disabled, so a scout write is caught by the Git scope check (scouts own no paths) rather than prevented. The routing policy permits switching only for a missing executable, unavailable exact model/provider, or recognized usage limit before edits and with unambiguous admission. Scout/mechanic/worker go from Codex to Command Code and their approved Pi fallbacks; a run never switches after an OpenCode Go attempt and never returns to Command Code. The terminal expert lane cannot switch to another model after a provider failure. An admitted Pi session retains its provider. Task failures, uncertain admissions, missing completion receipts, and partial work do not authorize another start. `fallback_reason` summarizes a switch, `fallback_notice` describes its automatic handling, and `fallback_detail` retains the original provider diagnostic; a successful switch clears `error`.

Exception recovery accepts only the admitted run's matching metadata and paired output. Uncertain create or prompt dispatch retains the transition and lease without provider replay. New lower-tier sessions snapshot their root plan at admission, including every pending Pi destination, and record the exact selection of each active state. New expert sessions retain their admitted Antigravity pin; removed tiers cannot be admitted.

### Typed state

The routing policy is one `RootPlan` per tier (`ROOT_PLANS` in `src/policy.ts`): either `{ kind: "exclusive", target }` (expert, Antigravity only) or `{ kind: "fallback", codex, command, pi }` with a non-empty ordered Pi list whose entries all carry an effort. `routesOf(plan)` is the one ordered view used by the policy export, the generated tables and the MCP routing summary. An unsupported arrangement does not type-check, so admission performs no route-order validation. The banned-model rule is a test over every plan and a generation-time check.

A session persists that plan snapshot next to an `Execution`. Every active state holds its selection: `process` (Codex, Command Code or Antigravity with a `CliPin` and its run), `pi` (a `PiSelection`, effort required, and the Pi session) or `transition` (the destination executor and selection, plus the previous run or Pi session it must keep as evidence). Adapters receive one `LaunchRequest` per start (`src/launch.ts`): directory, log directory, prompt, the selection, a closed access union (`read-only`, or `write` with a network flag) and an optional resume token. Antigravity accepts only write access. Status, resume, steering and fallback read the selection from the execution and the destinations from the snapshot, never from current policy.

`schema_version: 2` is the current record. The top-level `backend`, `command_run` and `pi_id` fields remain as derived projections for outside readers; decoding ignores them. Decoding converts `schema_version: 1` and unversioned records whenever the execution has its own selection. The session's plan is the arrangement the record admitted: the root plans, plus the legacy `fallback-unresolved-pi` (Codex and Command Code pins but no exact Pi snapshot, such as symbolic Muse/Go destinations), `command-first` and `command-first-unresolved-pi` (no Codex lane) and `pi-first` (no execution order: Pi falls back to Command Code and Command Code is terminal). Only a plan with resolved Pi destinations can start the Pi fallback; from an unresolved plan that attempt alone fails with the "Legacy Pi fallback has no exact model snapshot; manual reconciliation required" diagnostic, and observation, resume, steering and cancellation work as before. Symbolic destinations are never resolved against current policy. An unversioned `hydrogen` record maps to its historical exact pin, never the current default. Records that cannot be converted without guessing fail with a manual reconciliation diagnostic and are never replayed: a missing pin for the executor the record is on, a missing Command Code pin on a Codex or Pi record, a Pi pin without an effort, a version 1 expert record outside Antigravity, or a prohibited model. CLI continuations preserve complete snapshots. Native Pi still validates its installed capability policy: a retired native model may be refused on continuation or pending fallback, never replaced with the current pin. Unknown scope fields are rejected, matching the published schema.

MCP and CLI requests share one command spec (`src/commands.ts`). Raw arguments decode once into a typed `Command`, the MCP input schemas derive from the same field list, and both entry points dispatch on the decoded command.

## Reloading the server

Each MCP client runs its own bridge server, so a code change reaches a client only after its server restarts. `pi-subagent-bridge-reload` stops the server that belongs to the calling client (`--all` stops every client's, `--dry-run` lists them). It signals only the server process: workers are separate processes with on-disk state, so running workers keep running. In Claude Code, `/mcp`, then Reconnect on `pi-subagent-bridge`, restarts that session's server without the script. The script finds its target by walking up from the shell it runs in, so run it from a shell the client started, or pass `--all`.

State, prompt job files, SDK JSONL transcripts, Codex and Command Code NDJSON results live under ignored `.work/worker-bridge/`. These files may contain code and model output; keep that directory private. This is *not* an OS sandbox: ignored files, absolute-path reads, and external processes are beyond Git write-scope detection.

## Tests

```
cd tools/pi-subagent-bridge
./dev-install.sh   # once; installs the dev toolchain into .dev/ (never touches node_modules)
npm test
cd ../..
python3 -I dotfiles/pi-test.py
python3 -I dotfiles/orchestrate-test.py
python3 -I tools/sync/claude-worker-test.py
python3 -I tools/sync/pi-worker-test.py
python3 -I tools/sync/opencode-worker-test.py
```

`npm test` covers inspection, `watch` and `campaign` (fixture logs and fake `sleep` executors; no real provider). It is an explicit developer check requiring a supported Node; the production archive does not supply that test toolchain, so `./dev-install.sh` installs the exact-pinned dev dependencies (and the pinned runtime closure, for type declarations) into the ignored `.dev/` directory, leaving the runtime `node_modules` symlink untouched. Mock tests cover scope, fallback, locking, resumes, and protocol shape but do not prove live account access or SDK catalog compatibility. Before unattended use, complete a disposable one-file worktree test of each tier, pre-edit model/quota fallback, post-edit quota refusal, same-session resume and restart recovery. Never claim these checks passed without executing them.

## Muse Code subscription

The bridge uses the exact-pinned
[`pi-muse-subscription`](https://github.com/jkeskikangas/pi-muse-subscription) extension
as the Pi fallback listed in the generated routing table, after earlier approved routes
are unavailable or fail conclusively before edits. Expert has no Muse route. The provider is
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
