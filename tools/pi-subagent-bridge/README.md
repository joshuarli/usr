# pi-subagent-bridge

One shared delegation bridge for every coding harness except OpenCode and Devin. Parents own scoping, worktrees, verification, integration and cleanup. The MCP and CLI expose the same durable session state.

<!-- policy:begin routing-summary -->
<!-- Generated from tools/pi-subagent-bridge/src/policy.ts; run make generate. -->
Bridge tiers: `scout`, `mechanic`, `worker`. Native-only tier: `expert`, which always runs as a harness-native subagent and never through the bridge. There is no `god` tier. The model families `gemini-4-argon` and `gemini-4-carbon` are prohibited, including every effort variant.

| Tier | Primary | Fallback (in order) |
| --- | --- | --- |
| scout | Codex `gpt-6-luna` (`medium`) | Command Code `meta/muse-ember` (`medium`); Pi `opencode-go/muse-spark-1.3-contributor` (`medium`) |
| mechanic | Codex `gpt-6-luna` (`high`) | Command Code `meta/muse-ember` (`xhigh`); Pi `opencode-go/muse-spark-1.3-contributor` (`high`) |
| worker | Codex `gpt-6.1-terra` (`high`) | Command Code `deepseek/deepseek-v4.1-flash` (`high`); Pi `muse-sdk/muse-spark-1.3` (`xhigh`); Pi `opencode-go/deepseek-v4.1-flash` (`high`); Pi `devin/swe-2-flash` (`medium`) |
<!-- policy:end routing-summary -->

Expert assignments never enter the bridge. OpenCode and Devin top-level sessions delegate only through native subagents; Codex uses its configured native subagents (no per-tier pin); Claude Code pins `opus` at `xhigh` effort for expert work; Pi launches its native `expert` profile. `scope-check CWD SCOPE_JSON_FILE [BRANCH] --register TITLE` records a native lane, and `scope-check --lane ID` from its repository records its latest Git scope check. `campaign list` includes these lanes. `scope-check` applies the bridge's Git scope check to such a native lane (see `pi-subagent-bridge scope-check -h`). See [orchestrate](../../dotfiles/base/.agents/skills/orchestrate/SKILL.md).

## Setup

`sh sync` installs Node.js and Command Code as usual, but installs the Pi 1.5.0 CLI/SDK plus pinned subagents/Muse/intercom dependencies **exclusively from the pinned, SHA-256-verified `pi-build` release archive** named in `tools/pi/runtime.pin.json`. It links the bridge to the same selected dependency closure (no npm install). The bridge MCP is registered for Claude and Pi; OpenCode never registers it (`sh sync` removes an owned OpenCode registration instead). Codex uses tracked config. `sh sync bridge` reconciles MCP registrations; foreign servers are preserved.

`sh sync plan`
`sh sync doctor`

The explicit CLI shim is installed at `~/.local/bin/pi-subagent-bridge`. No OpenCode service or `pi -p` is needed. A scoped SDK host loads only pi-subagents and calls its `spawn`/`resume` RPC. The package owns detached child execution, session continuation, and completion artifacts. Interactive Pi loads locally bundled subagents and intercom extensions through its managed launcher; no `pi install`, `pi update`, npm or npx runs on the Pi setup path. The scoped SDK bridge continues to load only subagents and (when needed) Muse, never unrestricted intercom tools.

## Core-only installation and checks

The core runs on Node without npm production dependencies. Pi packages and YAML belong to the optional Pi adapter. Production routes and saved session formats remain unchanged. Missing Pi reports an unavailable optional route. Reading historical Pi process evidence does not require the SDK.

To register the bridge without installing Pi, run `python3 -I tools/sync/claude-worker.py install --core` from the repository root. `check --core` checks that registration. The Pi registration helper also accepts `--core`. These commands preserve existing dependency links and companion files. Supply executable locations through `PATH`; caller locations take priority over conventional tool directories appended by the server.

For core development, run `./dev-install.sh --core` from this directory. Use a fresh checkout to verify package absence. The default developer installation includes the pinned optional adapter dependencies.

From this directory:

- `npm run test:core` checks core types and runs offline core fixtures without the optional adapter suites.
- `npm run test:no-pi` copies the source into a private fixture without runtime packages. It checks core registration, CLI admission, completion, continuation, MCP model checking, owner RPC, steering and command replay against a deterministic Codex executable. It traps Pi module loading, credential reads and Pi/npm/npx subprocesses.
- `npm run test:runtime-contract -- --adapter codex` runs the Codex, owner, session and no-Pi fixtures. Supported adapter selections are `codex`, `command-code` and `pi`. Without a selection it runs shared lifecycle fixtures for the subprocess adapters.
- `npm test` retains the full typecheck and fixture suite, including optional Pi adapter tests. The live Muse smoke test requires its existing explicit opt-in.

Fake executors prove bridge lifecycle behavior, not live provider entitlement. The core-only fixture does not qualify Linux binaries or agentctl integration.

## FX qualification experiment

FX is available only through `experiment/fx/spike.mjs`. Installing it does not change production routes or add a runtime selector to `worker_start`. The current pin supports native macOS ARM64 only. Read the [spike result](../../docs/verification/runtime-independence-fx.md) before using it.

From this directory:

- `npm run spike:fx -- --setup` installs the exact checked-in release into a scratch home under usr's `.work/`, using the existing verified installer.
- `npm run spike:fx -- --local-protocol` runs the real CLI against a loopback provider, including tools, continuation, hostile read-only calls and interruption.
- `npm run spike:fx -- --local` also runs the real binary through shared bridge admission, owner control and parent-verified acceptance tests. No account credentials are required.
- `npm run test:fx` checks experiment types and offline supervisor/state fixtures. It does not download a binary or contact a provider.
- `npm run test:runtime-contract -- --adapter fx` adds saved-state, owner and no-Pi contracts.
- `npm run spike:fx -- --live` prints its bounded scope and returns unavailable for the unqualified account route. It never substitutes Gateway billing or copies another client's credentials.
- `npm run bench:runtime` interleaves five adapter/bridge samples for the same local workload. Failed load gates discard timing samples and return exit 75. Native RSS samples and binary size are separate from live task performance.

Ordinary sessions retain schema-2 writes. Experimental leaf sessions use schema 3; versions 1 and 2 remain readable. FX resume tokens are runtime-tagged and bound to the original worktree, native session, model/provider/effort and private connection/control settings.

## Devin SWE-2 Flash

`devin/swe-2-flash` at **medium** effort is an explicitly pinned **last**
Pi fallback for the `worker` tier and a dedicated interactive
`devin-worker` profile; the default Codex/Command/Muse/OpenCode routes
and the worker-tier Muse route are unchanged — no other tier
routes to Devin. The provider is supplied by a hash-verified `pi-build` release, never a
local `pi install`. See [pi-build PR #5](https://github.com/joshuarli/pi-build/pull/5).
Only the admitted `medium` variant is allowed by the typed tier policy.
Unavailability cannot authorize another effort level or tier.

On the target machine, `sh sync` installs the Devin CLI (`sh sync tools
devin`) and the pinned `pi-build` runtime that bundles `pi-devin-local`.
Sign in once with `devin auth login`, then seed Pi's credential store and
model catalog without the interactive `/login` flow: run the bundled
`pi-devin-local` extension through the Pi SDK with `PI_OFFLINE` unset
(a single `-p` prompt is enough — extension startup refreshes
`~/.cache/pi-devin/models.json`), and store the CLI `windsurf_api_key`
as the provider's `oauth` entry in `~/.pi/agent/auth.json`. Verify that
`swe-2-flash-medium` appears in the catalog and that the account is
entitled to `swe-2-flash` — catalog presence alone does not prove
entitlement. For an explicit experiment, launch native `devin-worker`
through the Pi subagent tool. Scoped bridge workers start
`PI_OFFLINE=1`, so no live catalog bootstrap is attempted; missing
credentials/cache fail before admission.
No tokens or account data are copied into the repo.

Offline fixture checks do not prove paid/free entitlement, streaming or
tool loops; the owner must run an actual SWE-2 Flash tool-and-resume test.

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

The admission result includes `watch`, a `pi-subagent-bridge watch` command that blocks until the executor ends. Its idle threshold defaults to 45 minutes. While active it skips worktree scans and backs off polling from 15 to 60 seconds until output changes; inspection Git probes run at low priority when supported. The bridge has no completion callback, so run `watch` as a background task; a harness that only polls never learns that a worker finished.

`worker_status(cwd,session_id)` first advances the session under its lock (pre-edit fallbacks, a blocked fallback, and releasing the lease of a terminal run), then reports what read-only inspection observes of the real backend, tier/effort, result, changed and out-of-scope paths, HEAD stability and fallback reason. The prompt requires the proof record to end with `ACCEPTANCE: met` or `ACCEPTANCE: not met`. A run that exits cleanly without a final `ACCEPTANCE: met` reports state `incomplete`, `acceptance_claim` `not_met` or `missing`, and `acceptance_blocked: true`; `incomplete` is resumable like any finished attempt. It also reports `continuations` used against `continuation_limit`, so a `turn_limit` session can be continued for free with `worker_resume` until that cap, and `steers` used against `steer_limit`. A Codex or Command Code run whose recorded process is gone, or whose PID now has a different start time (a reused PID), is reported as the terminal `interrupted` state and its worktree lease is released; an alive PID with the recorded start time stays `running` and keeps the lease. The parent verifies the output and independently checks the diff; an assistant claim cannot count as test proof.

`worker_resume(cwd,session_id,feedback)` preserves the approved scope and either resumes the owned native pi-subagents child in its original SDK host session, the Codex thread, or the Command Code session. It refuses uncertain active runs, scope expansion, and depleted attempts. A `turn_limit` result is continued with `TURN_LIMIT_CONTINUATIONS` free continuations that do not consume attempts; the used count and cap are in `worker_status`.

`worker_steer(cwd,session_id,note)` redirects a **running** worker without changing its scope or write boundaries. On the Pi backend it forwards the note to the native pi-subagents `steer` RPC for the owned run. On Codex and Command Code it verifies HEAD and the write boundary exactly as `worker_resume` does, interrupts the run, waits until the recorded process is proven gone, then resumes the same session and the original prompt plus `PARENT STEERING (same scope and write boundaries): <note>`. It never changes `attempts`; it is bounded by its own `steer_limit`, and it refuses to signal a PID that this bridge process does not own. A finished or non-running session is refused with a pointer to `worker_resume`.

`worker_cancel(cwd,session_id)` interrupts a run only while its recorded PID identity (start time, command line, cwd) still matches the record, however that run was started — a CLI-started or restarted MCP worker is included, a reused PID is never signaled. Cancellation is not proof of termination. For Codex and Command Code, a later `worker_status` can report `cancelled` and release the lease after proving the recorded process gone. Pi requires a terminal result: a dead host without one remains `unknown_or_interrupted` and keeps its lease. A worker that already ended at a provider usage limit with partial edits (`blocked_partial_work`) is not signaled; once the parent has preserved the work, the call releases the worktree lease instead.

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
pi-subagent-bridge resume CWD SESSION_ID FEEDBACK_FILE [--extend-attempts N --reason TEXT]
pi-subagent-bridge steer CWD SESSION_ID NOTE_FILE
pi-subagent-bridge cancel CWD SESSION_ID
pi-subagent-bridge inspect PATH SESSION_ID
pi-subagent-bridge watch [--state] ROOT SESSION_ID [IDLE_MINUTES]
pi-subagent-bridge campaign wait [--timeout DURATION] [ROOT...]
pi-subagent-bridge campaign ack ID...
pi-subagent-bridge campaign list [--json] [ROOT...]
```

For unmet acceptance, the worker ends with `STOPPED_ON: <condition>` followed by `ACCEPTANCE: not met`. Status and inspection report `stopped_on` and `stop_condition_valid`; an unlisted or missing condition makes the run incomplete.

Inspection snapshots include `attention`: `active`, `finished`, `gone`, `needs_attention`, or `unknown`, alongside the detailed `execution_state`. Campaign wait reports every non-active session, including blocked and unknown sessions; timeout ticks count only active sessions. Watch exits 4 for sessions needing attention or with unknown state.

`inspect`, `watch` and `campaign` only read bridge state (`campaign ack` writes its own acknowledgement file). `inspect` prints one JSON snapshot; `watch` and `campaign wait|ack|list` print text with documented exit codes (`watch`: 0 finished, 2 stalled, 3 exited without a terminal result, 4 uninspectable). The other commands print one JSON result to stdout on success and a diagnostic on stderr on error. Run `mcp` explicitly to serve; no arguments prints usage and exits 2. Relative paths resolve against the process working directory. Pass a scope file rather than interpolating JSON into a shell command. Do not put credentials or private source into task briefs.

`pi-subagent-bridge policy` exports approved routes, native Pi restrictions and
harness exceptions without loading the SDK, probing a provider, or reading home
configuration. `make policy` provides the same inspection directly from a checkout.
Edit the typed policy and run `make generate`; [policy projections](../policy/README.md)
explains generated ownership and read-only drift checks.

## Safety and durability

Codex and Command Code record process start time (Linux `/proc/<pid>/stat` field 22; macOS `ps -o lstart=`) to distinguish the owned child from a reused PID. An alive process with that identity keeps its lease; proven interruption releases it. `--verbose` records the Command Code session identity before the result so steering can resume the same session. Cross-process worktree leases and locks sit at the MCP/CLI boundary.

Codex runs use the signed-in ChatGPT account and do not use API keys. Codex runs with `--sandbox danger-full-access`, like every other backend. Codex scouts disable shell, unified exec, computer-use, and browser tools (the code-mode host stays enabled because Codex routes every tool call, including the scout's MCP tools, through it) and expose read-only tools through a dedicated local MCP server; Codex's built-in patch tool cannot be disabled, so a scout write is caught by the Git scope check (scouts own no paths) rather than prevented. The routing policy permits switching only for a missing executable, unavailable exact model/provider, or recognized usage limit before edits and with unambiguous admission. Scout/mechanic/worker go from Codex to Command Code and their approved Pi fallbacks; a run never switches after an OpenCode Go attempt and never returns to Command Code. An admitted Pi session retains its provider. Task failures, uncertain admissions, missing completion receipts, and partial work do not authorize another start. `fallback_reason` summarizes a switch, `fallback_notice` describes its automatic handling, and `fallback_detail` retains the original provider diagnostic; a successful switch clears `error`.

Exception recovery accepts only the admitted run's matching metadata and paired output. Uncertain create or prompt dispatch retains the transition and lease without provider replay. New lower-tier sessions snapshot their root plan at admission, including every pending Pi destination, and record the exact selection of each active state. The bridge admits no expert tier; removed tiers cannot be admitted.

### Pi run deadline

pi-subagents silently defaults an unset run deadline to 30 minutes; the bridge never lets that apply. One typed constant in `src/tier-policy.ts` (`PI_RUN_DEADLINE_MS`, 4 hours) is the single source for the deadline in Pi dispatches (`spawn`/`resume` carry `timeoutMs`) and in the generated native Pi profiles (`timeoutMs` frontmatter, verified at admission by `assertTierProfiles`). `worker_start` and `worker_status` surface the effective deadline as `run_deadline_ms` (`null` for backends with no wall-clock cap). A Pi run that reaches the deadline reports state `timed_out` with its partial output — distinct from a provider failure, and it releases the worktree lease without any automatic fallback or retry.

### Typed state

The routing policy is one `RootPlan` per tier (`ROOT_PLANS` in `src/policy.ts`): `{ kind: "fallback", codex, command, pi }` with a non-empty ordered Pi list whose entries all carry an effort. `routesOf(plan)` is the one ordered view used by the policy export, the generated tables and the MCP routing summary. An unsupported arrangement does not type-check, so admission performs no route-order validation. The banned-model rule is a test over every plan and a generation-time check.

A session persists that plan snapshot next to an `Execution`. Every active state holds its selection: `process` (Codex or Command Code with a `CliPin` and its run), `pi` (a `PiSelection`, effort required, and the Pi session) or `transition` (the destination executor and selection, plus the previous run or Pi session it must keep as evidence). Adapters receive one `LaunchRequest` per start (`src/launch.ts`): directory, log directory, prompt, the selection, a closed access union (`read-only` or `write`) and an optional resume token. Status, resume, steering and fallback read the selection from the execution and the destinations from the snapshot, never from current policy.

`schema_version: 2` is the current record. The top-level `backend`, `command_run` and `pi_id` fields remain as derived projections for outside readers; decoding ignores them. Decoding converts `schema_version: 1` and unversioned records whenever the execution has its own selection. The session's plan is the arrangement the record admitted: the root plans, plus the legacy `fallback-unresolved-pi` (Codex and Command Code pins but no exact Pi snapshot, such as symbolic Muse/Go destinations), `command-first` and `command-first-unresolved-pi` (no Codex lane) and `pi-first` (no execution order: Pi falls back to Command Code and Command Code is terminal). Only a plan with resolved Pi destinations can start the Pi fallback; from an unresolved plan that attempt alone fails with the "Legacy Pi fallback has no exact model snapshot; manual reconciliation required" diagnostic, and observation, resume, steering and cancellation work as before. Symbolic destinations are never resolved against current policy. Records that cannot be converted without guessing fail with a manual reconciliation diagnostic and are never replayed: a missing pin for the executor the record is on, a missing Command Code pin on a Codex or Pi record, a Pi pin without an effort, an `expert` or otherwise unknown tier, or a prohibited model. CLI continuations preserve complete snapshots. Native Pi still validates its installed capability policy: a retired native model may be refused on continuation or pending fallback, never replaced with the current pin. Unknown scope fields are rejected, matching the published schema.

MCP and CLI requests share one command spec (`src/commands.ts`). Raw arguments decode once into a typed `Command`, the MCP input schemas derive from the same field list, and both entry points dispatch on the decoded command.

## Owner endpoint (v1)

Long-lived `pi-subagent-bridge mcp` processes expose a local, versioned newline-delimited JSON-RPC 2.0 endpoint per repository so external tools (`agentctl`) can observe and control jobs admitted by that bridge process without bypassing ownership, leases, attempts, or scope. CLI subcommands (`start`, `status`, `resume`, `cancel`, `steer`) never become owners. An MCP server checks changed source against its advertised tool names and input schemas. If they still match, calls run in a fresh process; changed schemas require a server restart and identify the affected tools.

- **Identity and files**: Each MCP server process picks a random UUID `owner_id` and allocates a monotonic per-repo `owner_generation` (`>= 1`) persisted in `<repo>/.work/worker-bridge/owner/generation.json`. Once active for a repository (`--repo <dir>` on `mcp`, or any `worker_*` call targeting a repo), it creates `<repo>/.work/worker-bridge/owner/` (`0700`), binds `<owner_id>.sock` (`0600`), and writes `<owner_id>.json` (`0600`) containing `{ owner_protocol: 1, owner_id, owner_generation, pid, socket, capabilities }`. Admitted sessions store `owner: { owner_id, owner_generation }` (`schema_version: 2`, backward-compatible; unowned records remain readable and uncontrollable). A restarted MCP server gets a new `owner_id` and incremented `owner_generation`, never adopts older jobs, and removes its `.json` and `.sock` on clean shutdown.
- **Methods** (`owner_protocol: 1`; unknown methods return JSON-RPC `-32601`, malformed envelopes `-32600`, unknown parameter or `target` fields `-32602`):
  - `hello` -> `{ owner_protocol: 1, owner_id, owner_generation, capabilities }` where `capabilities` is `["status", "steer", "interrupt", "resume"]`.
  - `jobs` -> read-only list `[{ job_id, run_id, owner_generation, state }]` of jobs admitted by this owner.
  - `status { target }` -> read-only job snapshot (`state`, `execution_state`, `job_id`, `run_id`, `owner_id`, `owner_generation`, worktree and usage fields). `hello`, `jobs`, and `status` never mutate leases, counts, session records, campaign acks, or providers.
  - `steer { target, command_id, note }`, `interrupt { target, command_id }`, `resume { target, command_id, feedback }` -> run the process's existing steer, cancel, and resume checks with all invariants preserved. `interrupt` requires a running latest run and never releases a lease (including `blocked_partial_work`, which remains exclusive to MCP `worker_cancel`).
  - `command { command_id }` -> read-only lookup across any owner instance's journal (`<repo>/.work/worker-bridge/owner/<owner_id>/commands.jsonl`).
- **`target` and `run_id` definition**: `target` is `{ job_id, run_id, owner_generation }`. `run_id` (`run_<32-hex>`) deterministically hashes (`sha256`) the session's current executor run: `(executor, selection, run: { pid, output, errors, started_at, proc_start }, attempts, continuations, steers)` for process executors (`codex`, `command-code`); `(selection, session_id, pi_run: { pid, startedAt, runId, log }, attempts, continuations)` for Pi (stable across in-process Pi steering); and `(to, previous_run, pi_id, attempts, continuations, steers)` for `transition`. `run_id` changes whenever `resume`, `fallback`, or CLI `steer` starts a new run. Target mismatch (wrong generation, unowned job, or non-latest `run_id`) returns `{ receipt: "rejected", reason: "stale-target" }`; terminal state alone is not stale.
- **Receipts and journal**: Controlled commands append an `admitted` record to `<repo>/.work/worker-bridge/owner/<owner_id>/commands.jsonl` after pre-checks pass and before executing effects, then append a `result` record afterward. Receipts are strictly `{ receipt: "accepted", command_id }`, `{ receipt: "rejected", reason }`, `{ receipt: "pending", command_id }`, or `{ receipt: "uncertain", command_id }`. Retrying the same `command_id` returns the recorded receipt without a second effect; `admitted` without a `result` resolves to `{ receipt: "uncertain", command_id }` without replay (including across restarts via `command`).
- **CLI client**: `pi-subagent-bridge owner <hello|jobs|status|steer|interrupt|resume|command> --repo <dir> --owner <owner_id> [--job <id> --run <id> --generation <n>] [--command <id>] [--note <text> | --note-file <path>] [--feedback <text> | --feedback-file <path>] [--timeout <ms>]` prints JSON.

## Reloading the server

Each MCP client runs its own bridge server. Source changes with unchanged tool schemas apply to subsequent tool calls; schema changes require a restart. `pi-subagent-bridge-reload` stops the server that belongs to the calling client (`--all` stops every client's, `--dry-run` lists them). It signals only the server process: workers are separate processes with on-disk state, so running workers keep running. In Claude Code, `/mcp`, then Reconnect on `pi-subagent-bridge`, restarts that session's server without the script. The script finds its target by walking up from the shell it runs in, so run it from a shell the client started, or pass `--all`.

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

A parent may extend a session by one or two attempts using `worker_resume` fields `extend_attempts` and `extension_reason`, or the corresponding CLI flags. The lifetime extension cap is two; status reports the total.

Steering persists `pending_steer` before signaling and records `last_steer` on completion or failure. Process relaunches record their planned output paths before spawning; status reconciles an abandoned caller using the replacement process identity or its output, retaining the original run if no replacement started. A pending steer blocks another. A 12-second shared deadline bounds the external probes and asynchronous phases; a timed-out relaunch can return `steering` for status to reconcile. A Pi delivery awaiting acknowledgement remains pending.
