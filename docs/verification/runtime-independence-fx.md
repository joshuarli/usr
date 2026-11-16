# FX 0.0.17 spike

## Verdict

**Limited-go for deterministic local qualification on native macOS ARM64.** The real CLI works through the shared bridge, including scope checks, leases, continuation and owner control. The opt-in live pilot is implemented and was executed against a real provider account; it is parked on reproduced account blockers (no FX Codex login; exhausted OpenCode Go monthly quota that blocks the incumbent identically). Live model usefulness, intended-model quality and native Linux remain unqualified. Production promotion is prohibited.

Accepted source checkpoints are `91642ad`, `6dd9583`, `c6f94ad`, `09815d1`, `d986a7f`, `c19b2f3`, `cdda03b` and `12df815`, against runtime-independence baseline `2025e04`. The owner's existing Codex configuration change is excluded. No remote update, home sync, production route change, Pi removal or Intercom change was performed.

## Release and installation

The experiment pins [FX v0.0.17](https://github.com/vercel-labs/fx/releases/tag/v0.0.17), source revision `d1d4a883382daf8f2e7447dc361978312cf403d2`, and `fx-macos-aarch64.tar.gz`. The archive SHA-256 is `5cacb5b3624a79db8fd4e31dcbc59d6a933d7e5ed4c397776d95df6b618296a9`. The extracted binary SHA-256 is `e840e7884b5c6a5c40d584770fd1b9dcee78fd5683994d85e32cf7f151959b4e`.

The binary reports `0.0.17`, is Mach-O ARM64, and passes `codesign --verify --strict`. Installation reuses usr's reviewed installer with an exact release and checksum override. It never follows the release feed or installs into the real home. The runner verifies the extracted binary hash before execution.

The native CLI was chosen because it supplies the tools and saved sessions needed by this leaf experiment. No libfx adapter, npm runtime dependency or replacement model loop was needed. FX is Apache-2.0; the release also includes third-party notices. Its experimental release policy and [documented update controls](https://fx.sh/docs/stability) require explicit pinning. Upgrades are disabled only inside private experiment processes and settings.

## Qualified behavior

| Contract | Observed result |
| --- | --- |
| Provider/model/effort | Loopback-only OpenAI Chat Completions connection; request body contains the exact fixture model and high effort. No provider fallback or helper requests. |
| Actual tools | Native read, write and shell check ran. Parent checks observed the original failing test, the repaired file and passing acceptance tests. |
| Continuation | Exact saved session ID, unchanged worktree and admitted pins. Previous tool history remains present. Changed connection/control settings or mismatched pins refuse resume. |
| Steering | Interrupt-and-resume through owner v1. The prior FX process terminates before the same native session resumes. Attempts remain unchanged; the steer budget advances. This is not live steering. |
| Missing optional adapter | Default composition can inspect the record, but unavailable FX control refuses before changing attempts or saved history. |
| Ownership and replay | Repeating owner correction/steering command IDs causes one effect. Cancellation checks the owned run tuple and current process identity before signaling. |
| Terminal evidence | Early JSON is insufficient while the process remains alive. Supervisor receipt, actual exit, model, native session and workspace must agree. Mismatch remains unknown and retains the lease. |
| Read-only controls | Native write, edit, shell, alternate toolbox write and subagent calls were denied. Hostile project permission settings did not widen the private controls. Parent verified unchanged files. |
| Leaf and ambient capabilities | Native fanout is denied by permission policy. Project MCP startup was disabled; its sentinel command did not run. Coordinator credentials and ambient environment variables are absent from the child environment. |
| Interruption | Before the first provider response, during a blocked writing tool, and after a write before final result persistence. No interrupted JSON was accepted. The blocked tool terminated; partial edits survived. |
| Shared bridge interruption | Owner interruption after an edit returns cancelled, preserves the edit and refuses a new start over the dirty worktree. |
| Compatibility | Production policy JSON matches the baseline byte for byte. Ordinary routes still write schema 2. Only experimental leaf records write schema 3; readers retain versions 1 and 2. A schema-2 FX record and an unknown FX version are rejected explicitly. |

The checked-in selection is `fixture/fixture-model` at high effort. It is a deterministic transport fixture, not a subscription or Gateway route. The read-only scout and one-file arithmetic repair are executable workloads; their scripted provider responses do not establish model quality.

FX walks ancestor skill roots until HOME. A sibling scratch home initially allowed usr skill metadata into the pilot. Keeping the fixture repository beneath its private HOME removed that ambient discovery. Native session discovery also accounts for the pinned runtime's index files and `.tmp` directory. It requires exactly one owned root session and never selects the newest ambient session.

Each qualifier job has a 20-model-step limit and a wall deadline no greater than 15 minutes. The independent process supervisor bounds stdout and stderr to 1 MiB each and records actual child termination. TERM, INT, HUP and QUIT request termination; a two-second escalation leaves missing receipts uncertain. Supervisor loss, unknown identity and corrupt evidence require manual reconciliation; they do not authorize replay or backend substitution.

Permission controls and Git scope checks do not provide an OS sandbox. Ignored-file and host-access limitations remain. The memory measurements below do not bound the whole process tree.

## Verification

Commands run from `tools/pi-subagent-bridge`, using managed Node 26.13.1:

| Command | Evidence |
| --- | --- |
| `npm run spike:fx -- --setup` | Exact pinned installation in `.work/tmp/fx-spike/installed-home`; repeat setup preserves the verified pin. |
| `npm run spike:fx -- --local` | Real CLI protocol and shared bridge scout, repair, same-session correction, steering, replay and interruption passed. |
| `npm run test:fx` | Nine offline process/state contract cases passed, plus secret-env-file, toolchain-PATH and auth-file-seeding cases. Fake binaries are used here; they are separate from real-binary qualification. |
| `npm run test:runtime-contract -- --adapter fx` | 36 FX, saved-state, no-Pi and owner cases passed; zero skips. |
| `npm run test:no-pi` | Passed with zero skips and zero trapped Pi accesses. |
| `npm test` | 245 passed; only the existing opt-in live Muse test skipped. |
| `npm run spike:fx -- --live codex` | Exit 75; zero jobs. No FX-owned ChatGPT credential exists; the runner prints the exact `FX_HOME=<profile> fx login codex` handoff and starts nothing. |
| `npm run spike:fx -- --live opencode-go` | Six bounded jobs admitted and run (report `.work/tmp/fx-live.json`). All three FX jobs reached the real OpenCode Go endpoint, retried `429 GoUsageLimitError` until their 15-minute deadlines and produced clean `deadline` receipts with zero worktree changes; all three incumbent Pi CLI jobs failed in ~1 s with the identical provider quota error. No model inference completed on either backend. |
| `npm run bench:runtime` | Initial attempt deferred with gate exit 75. A later before/after gate window passed and produced interleaved local harness measurements. |

Root checks also passed: policy generation, ten policy-generator tests, eight orchestration tests, changed Python Ruff/ty checks, TypeScript checks, Markdown links and `git diff --check`.

An independent read-only review of `91642ad` found no demonstrated introduced P1/P2 defects. The parent checked the diff and clean review worktree. The subsequent cancellation-identity and unavailable-control guards have focused regression cases and real owner-control verification.

Private replayable evidence is in `.work/tmp/fx-qualification.json`, `.work/tmp/fx-benchmark.json`, `.work/tmp/fx-live.json` and the fixture roots those files name. The review checkout is retained at `.work/wt/fx-review` as source evidence.

## Live pilot

`spike.mjs --live [profile]` replaces the former unconditional refusal with an opt-in runner (`experiment/fx/live-pilot.mjs`). It provisions a disposable Git repository containing Python, TypeScript and Rust work, selects one exact profile, and drives three bounded tasks (read-only scout, focused bug fix, multi-file rename with same-session correction) through the shared bridge owner controls, plus the matching incumbent backend where installed. Bounds: six new jobs, two corrections, 15-minute wall per job, 20 model steps.

Two profiles exist. `codex` uses the built-in FX provider with the production Codex tier pins and requires `chatgpt-auth.json` inside a private `FX_HOME`; absence prints an exact `fx login codex` handoff and exits 75 without starting jobs. `opencode-go` configures a custom OpenAI Completions connection against `https://opencode.ai/inference/go/openai/v1` with the approved `deepseek-v4.1-flash`/high pin, bearer auth from `LIVE_PROVIDER_TOKEN` and the required `x-opencode-session` routing header from `LIVE_PROVIDER_SESSION`.

Credential isolation is structural: the supervisor job record serializes only environment variable names and secret-file paths; values live in mode-0600 scratch files injected into the child environment at spawn. Verified on the live run: no token value appears anywhere under the run root, and FX settings reference only the environment variable name. `opencode auth export` supplies the bearer value without printing it; a random session ID is generated per run.

Observed live results (report `.work/tmp/fx-live.json`, run root `.work/tmp/fx-live/run-a1hpy6`):

- Wire path proven to the provider: FX authenticated, satisfied the session-header requirement and received real `429 GoUsageLimitError` responses; earlier direct probes confirmed `MissingSessionID` without the header and quota rejection with it.
- FX retried the rate limit until each job's 900 s deadline, then produced `reason: "deadline"` receipts, `state: "failed"`, zero worktree changes and correct parent-check outcomes. Sampled whole-tree peak RSS was ~100 MiB per job.
- The incumbent Pi CLI on the same account/model failed each task in ~1 s with the identical `GoUsageLimitError` ("monthly, resets in 14d 3h"), so the blocker is account quota, not an FX deficiency. No paired quality comparison is possible until quota or a Codex login exists.
- Behavioral difference recorded: FX's recovery loop treats provider 429 as retryable for the full wall budget, while the Pi CLI surfaces the quota error immediately. Both remain inside their bounded contracts.

## Resource results and limits

The installed native binary is **6,641,968 bytes**. The scratch installation occupies 6,492 KiB in filesystem blocks and contains only the binary and its installer receipt. Native-only samples in the small local protocol fixture observed approximately **5.4 MiB** while awaiting a provider response and a sampled maximum of approximately **7.0 MiB**. Sampling can miss peaks. Node bridge/supervisor and Python tool memory are excluded. These are not production-task RSS bounds.

The benchmark compares adapter supervision against full bridge admission and observation using the same FX binary, provider, pins, prompt and read/write/check workload. It alternates five runs per side with fresh processes/sessions and warm filesystem caches. Both load gates must pass. A separate diagnostic run attributes most harness cost to synchronous Git checks; Python subprocess launch and observation/polling also contribute. No model inference is timed.

At `d986a7f` with clean tracked runtime sources, both load gates returned zero. Five interleaved runs per side produced these accepted-fixture durations, including parent checks:

| Local path | Median | Range |
| --- | --- | --- |
| Adapter supervision | 268.05 ms | 266.77–270.69 ms |
| Shared bridge | 1,213.22 ms | 1,178.61–1,230.68 ms |

**Performance verdict: inconclusive for live runtime performance.** The loopback provider shares the driver's Node event loop. Synchronous bridge Git checks also delay fixture responses, so this comparison does not isolate production harness overhead. It measures this qualifier arrangement. No optimization or runtime choice follows from it.

Timing values and sample ranges are recorded in the benchmark artifact with `source_revision` and `tracked_source_dirty`. The dirtiness check covers tracked runtime sources, experiment sources and the bridge package manifest. They do not establish that FX is faster than Pi, Codex or another model. Fixture usage is synthetic, not a billing estimate. Real model usage, task quality, cold filesystem startup, warm-session performance and total peak RSS remain unknown.

## Parked proof and next boundary

- **Live account/model qualification:** implemented and executed; parked on reproduced blockers. Codex route: run `FX_HOME=/Users/josh/usr/.work/tmp/fx-live/fx-profile /Users/josh/usr/.work/tmp/fx-spike/installed-home/.local/bin/fx login codex` (browser login into the private profile), then `npm run spike:fx -- --live codex`. OpenCode Go route: provider reports the monthly quota resets in ~14 days; rerun `npm run spike:fx -- --live opencode-go` afterward. Do not import unrelated client credentials, prompt for secrets or substitute metered Gateway access. Until one route completes inference, live model usefulness and the Pi-route qualification below remain unproven.
- **Pi-dependent route qualification:** no existing Pi route has been qualified through FX. The OpenCode Go worker route is the intended first candidate once its account quota resets; Codex-tier routes additionally require the ChatGPT login above. This is the remaining step toward the Pi-removal question and is explicitly not satisfied by the ChatGPT path alone.
- **Native Linux:** qualify each musl architecture separately, including its exact artifact and libc linkage. This macOS pin provides no Linux, emulation or WASM proof.
- **External consumers:** real agentctl and Intercom peer integrations were not exercised. Owner v1 fixtures and coordinator credential exclusion passed locally.
- **Production decision:** no production lane is approved by this result. A rollout requires live intended-tier acceptance, resource qualification and a separate owner decision.

The spike stops here. Pi remains available, the production routes remain unchanged, and no SDK rewrite or rollout follows from this verdict.
