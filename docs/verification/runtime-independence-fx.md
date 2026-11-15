# FX 0.0.17 spike

## Verdict

**Limited-go for deterministic local qualification on native macOS ARM64.** The real CLI works through the shared bridge, including scope checks, leases, continuation and owner control. Live account behavior, intended-model quality and native Linux remain unqualified. Production promotion is prohibited.

Accepted source checkpoints are `91642ad`, `6dd9583`, `c6f94ad`, `09815d1` and `d986a7f`, against runtime-independence baseline `2025e04`. The owner's existing Codex configuration change is excluded. No remote update, home sync, production route change, Pi removal or Intercom change was performed.

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
| `npm run test:fx` | Nine offline process/state contract cases passed. Fake binaries are used here; they are separate from real-binary qualification. |
| `npm run test:runtime-contract -- --adapter fx` | 32 FX, saved-state, no-Pi and owner cases passed; zero skips. |
| `npm run test:no-pi` | Passed with zero skips and zero trapped Pi accesses. |
| `npm test` | 237 passed; only the existing opt-in live Muse test skipped. |
| `npm run spike:fx -- --live` | Exit 75; zero jobs. Existing FX settings are not an account credential. The FX ChatGPT credential file was absent; no credentials were read/copied and no keychain was consulted. |
| `npm run bench:runtime` | Initial attempt deferred with gate exit 75. A later before/after gate window passed and produced interleaved local harness measurements. |

Root checks also passed: policy generation, ten policy-generator tests, eight orchestration tests, changed Python Ruff/ty checks, TypeScript checks, Markdown links and `git diff --check`.

An independent read-only review of `91642ad` found no demonstrated introduced P1/P2 defects. The parent checked the diff and clean review worktree. The subsequent cancellation-identity and unavailable-control guards have focused regression cases and real owner-control verification.

Private replayable evidence is in `.work/tmp/fx-qualification.json`, `.work/tmp/fx-benchmark.json` and the fixture roots those files name. The review checkout is retained at `.work/wt/fx-review` as source evidence.

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

- **Live account/model qualification:** `npm run spike:fx -- --live` reports the bounded scope and refuses an unqualified account route. Establish an FX-owned ChatGPT account and verify the exact approved model/provider/effort before implementing or enabling live execution. Do not import unrelated client credentials or substitute metered Gateway access.
- **Native Linux:** qualify each musl architecture separately, including its exact artifact and libc linkage. This macOS pin provides no Linux, emulation or WASM proof.
- **External consumers:** real agentctl and Intercom peer integrations were not exercised. Owner v1 fixtures and coordinator credential exclusion passed locally.
- **Production decision:** no production lane is approved by this result. A rollout requires live intended-tier acceptance, resource qualification and a separate owner decision.

The spike stops here. Pi remains available, the production routes remain unchanged, and no SDK rewrite or rollout follows from this verdict.
