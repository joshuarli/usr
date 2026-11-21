Prefix: USR
Next: 129

### USR-83 · P2 · running sessions on two hosts cannot reach each other over intercom

- **Area:** Delegation
- **Where:** launcher intercom-tailnet (docs/intercom-tailnet.md), pi-build broker/tailnet-admin.js, the Claude/Codex intercom MCP adapters (claude-intercom-mcp), intercom_list scope handling
- **Problem:** On 2026-11-17 a Claude Code session on the Mac had to coordinate with a Claude Code session on threadripper (the one in ~/repos/laputa-systems/xsh) before using that host for a Chromium build. `intercom_list` showed only same-machine sessions. Neither host runs a hub. Neither session was enrolled or launched under `intercom-tailnet run`, so neither can be reached without restarting it. On threadripper over SSH, `intercom-tailnet doctor` fails with `Node.js is missing`, because Node lives under ~/.local/share/nodejs and is not on a non-login PATH. Cross-host use needs four manual steps before any message flows: start a hub, enroll each session, transfer each credential, and relaunch the session through the launcher. In practice agents cannot coordinate across hosts and fall back to asking the owner to relay.
- **Recommendation:** Keep the trust model: enrolled, tailnet-only, credential per host. Remove the per-session ceremony. (1) Run the hub on one always-on host under its existing supervisor, from one documented command. (2) Enroll once per host, not per session, storing the credential at a fixed private path. (3) Have the normal claude/codex/pi launchers join the hub automatically whenever that host credential exists, so every ordinary session is reachable without relaunching through intercom-tailnet run. (4) Give intercom_list a fleet scope that shows remote sessions by host. The pinned Node lookup for doctor over non-login SSH is fixed. Acceptance: two ordinary sessions started normally on the Mac and on threadripper can intercom_list each other and exchange intercom_ask.
- **Fix with:** none
- **Effort:** M

### USR-100 · P2 · sync uninstall refuses to remove anything once managed trees have been used

- **Area:** Sync · ownership and uninstall
- **Where:** tools/sync/uninstall.py:40; tools/sync/ownership.py:176; tools/sync/installer.py:3155, 3166, 1477, 3211, 3195; tools/sync/companions.py:197; tools/sync/main.py:375
- **Problem:** Uninstall verifies every recorded path before removing any and aborts on one unverified or changed proof. Whole-directory (D) proofs hash entire trees that normal use rewrites: the managed Python writes __pycache__ into its release tree, companions-mcp writes archives and SHA256SUMS into the shared Pi cache without re-recording its proof, and records older than the proof file never get one. A read-only replay of uninstall's check on this Mac's live dl-owned reported 9 drifted and 106 unverified paths (Pi cache, Node.js and pnpm-npm roots, two python-build releases, ish, srv, stuff, opencode); a unit reproduction with merge_claims, capture_new and _uninstall_locked raised unverified or modified managed path for the Pi cache. sync doctor reports none of it.
- **Recommendation:** Stop proving runtime-mutated trees by whole-tree hash: verify each release payload against its own manifest, or record caches as disposable. Give companions their own cache or re-record its proof. Add a doctor row counting paths uninstall would refuse, and a supported way to record proofs for existing records. Acceptance: an integration case that installs python3, runs it once, installs pi and companions, then uninstalls removes every managed path, and doctor reports drifted and unverified counts beforehand.
- **Fix with:** durable-state
- **Effort:** M

### USR-101 · P2 · Alpine wget-pipe bootstrap fails when USER_NAME is unset

- **Area:** Alpine provisioner
- **Where:** host/setup.sh:163; host/alpine/provision.py:1150, 992; host/alpine/README.md:48, 79, 104, 159
- **Problem:** setup.sh always exports USER_NAME=${USER_NAME:-}, so provision.py's os.environ.get("USER_NAME", "josh") returns an empty string and resolve_user('') fails with user does not exist. The documented one-liners therefore fail unless USER_NAME is set, contradicting README:104 (defaults to user josh); setup.sh:47 defaults to josh while provision.py sees empty. The VM journey always sets USER_NAME, so no check covers this path. Proven by code trace, not on an Alpine host.
- **Recommendation:** Own the default in one place, for example os.environ.get("USER_NAME") or "josh" in provision.py, and stop exporting an empty value. Acceptance: a test running provision main with USER_NAME='' resolves the user josh.
- **Fix with:** single-source-of-truth
- **Effort:** S

### USR-105 · P2 · A worker that leaves a background process stays running and cannot be cancelled

- **Area:** pi-subagent-bridge · process lifecycle
- **Where:** tools/pi-subagent-bridge/src/command.ts:73, 150; src/codex.ts:67; src/hybrid.ts:148
- **Problem:** workerAlive treats a Codex or Command Code run as alive while any member of the leader's process group lives, but cancel verifies only the leader's identity and refuses to signal once it has exited. The worker prompt tells workers to detach slow commands, so one leftover server or sleep & keeps the session running with a success receipt on disk, holds the worktree lease, and worker_cancel returns interrupted false. A scratch test spawning sh -c 'sleep 20 & exit 0' with a success result printed state after leader exit: running and cancel signaled: false.
- **Recommendation:** While the recorded process group still exists, let cancel signal the group (a pgid cannot be reused while the group lives), or report a distinct state for a leader that exited with a receipt while descendants remain, so the lease and the parent's next step are clear. Acceptance: that fixture can be cancelled through worker_cancel and status then leaves running.
- **Fix with:** lifecycle-concurrency
- **Effort:** M

### USR-114 · P2 · Core tools install the newest prerelease with no pin, signature or hold

- **Area:** Sync · installers and release trust
- **Where:** tools/sync/installer.py:428, 384, 1115, 1133, 2180, 2218, 2349, 2528, 1453
- **Problem:** build_release installs the newest of five release tags from releases.atom for python3, node, git, ssh, oxish and ffmpeg, and SHA256SUMS comes from the same release as the archive, so it proves only transport integrity: whoever can publish to the laputa-systems build repositories can ship a matching archive and sum, and sh sync hosts apply rolls it to every host, including ssh and python3. Only the Pi runtime has a tracked pin (tools/pi/runtime.pin.json), while fx (1028) and player (2841) check signatures. No tool can be held on its current build: rolling back a broken release means repointing current by hand, which the next sync undoes. Code facts proven; exploitation unproven.
- **Recommendation:** Pin git, ssh, python3 and node like Pi, with a tag and sha256 per target in a tracked pin file, so a bump is a reviewed commit and a revert is the rollback; at minimum add a per-tool hold. Acceptance: sh sync tools git installs exactly the pinned digest, and a test shows a newer release is ignored.
- **Fix with:** security
- **Effort:** M

### USR-115 · P2 · Changed-file check selection passes Python with lint only and omits five suites

- **Area:** Tests · change-selected gate
- **Where:** tools/sync/checks.py:228, 229, 309
- **Problem:** The per-file ruff and ty checks count as covering every .py file, so unmapped never fires for Python: tools/todo/src/todo.py, tools/usage/src/usage.py, tools/close-stale-prs/src/close_stale_prs.py and tools/sync/checks.py select only ruff and ty, tools/pi/test_runtime_profiles.py does not select itself, and tools/sync/test_checks.py, tools/todo/tests/test_todo.py, tools/usage/tests/test_usage.py, tools/close-stale-prs/tests/test_close_stale_prs.py and tools/sync/test_kache_archive.py are in no registry entry. On 2026-11-20 a checks.py edit broke test_checks.py while sh sync check --changed selected only lint for it.
- **Recommendation:** Stop per-file lint checks from counting toward coverage and register the five suites with covers patterns. Acceptance: in test_checks.py, an edit to todo.py selects test_todo, checks.py selects test_checks, a changed test selects itself, and a Python file with no behavior check is reported unmapped.
- **Fix with:** test-pyramid
- **Effort:** S

### USR-116 · P2 · Tracked sh shim overrides test fixtures' XDG directories with the host's

- **Area:** Tests · host contamination
- **Where:** dotfiles/base/.local/bin/sh:4; dotfiles/base/.config/sh/config.sh:19; dotfiles/dsh-launcher-test.sh
- **Problem:** Checks invoke sh from PATH, which on synced hosts and in CI is ~/.local/bin/sh; it sources config.sh, which re-exports XDG_CONFIG_HOME, XDG_CACHE_HOME and XDG_DATA_HOME, overwriting a test's inline values when XDG_CONFIG_HOME is already exported. dsh-launcher-test.sh fails through the shim at HEAD (exec: .../home/.local/share/dsh/bin/dsh-tui: not found although the test set XDG_DATA_HOME) and passes with /bin/sh and the shim off PATH. Twenty test files set XDG variables.
- **Recommendation:** Run registry sh checks with /bin/sh or with ~/.local/bin removed from PATH, and have config.sh keep XDG values that are already set. Acceptance: sh dotfiles/dsh-launcher-test.sh passes through the shim on this host, and a fixture proves a preset XDG_DATA_HOME survives a shim-invoked child.
- **Fix with:** isolate-effects
- **Effort:** S

### USR-127 · P2 · Live Codex bridge workers die silently on this Mac

- **Area:** pi-subagent-bridge · test isolation
- **Where:** tools/pi-subagent-bridge/test/ (npm test); test/codex.test.ts:126-132; test/command.test.ts:195-269
- **Problem:** On 2026-11-20 on this Mac, Codex bridge workers started after about 18:02 local exited mid-run with no turn.completed, turn.failed or error event and stderr only Reading additional input from stdin; the bridge reported interrupted with no fallback. Affected: usrw_de2f41eb, usrw_ae450e43, usrw_b0273670, usrw_593cd847 and usrw_47289e45 in another checkout, and usrw_ff4bc30e and usrw_32520f9d here. The first deaths overlapped a bridge test run (pid 25124), but usrw_47289e45 died at about 02:08:50Z after 21 completed items with no node --test process running, no jetsam or memorystatus log entries, 71% free memory and 686 of 8000 user processes. Workers started before 18:02 ran for an hour. The cause is unestablished: candidates include a test or tool signalling a process group it did not create, an external reaper, and Codex CLI itself exiting.
- **Recommendation:** Reproduce with a long Codex worker while recording the exit status and signal of the codex process (for example by having the bridge launcher record wait status) and process accounting around the exit, then fix the killer or, if Codex exits on its own, classify a silent exit before edits as a provider failure eligible for fallback. Acceptance: a recorded death names its signal or exit status, and a regression check keeps an unrelated detached worker process group alive across the full bridge test suite.
- **Fix with:** root-cause
- **Effort:** M

### USR-128 · P2 · sh sync on Ubuntu 24.04 leaves the agent control plane incomplete

- **Area:** Sync · Linux hosts
- **Where:** sync (entry shim); tools/sync/installer.py:1703 (Node npm check); tools/sync/main.py:393 (kache goal); dotfiles/base/.cargo/config.toml (rustc-wrapper)
- **Problem:** A pristine ubuntu:24.04 arm64 container (2026-11-21, usr deee8dc2, clone at ~/usr, run as root) cannot set up the agent control plane. (1) `sh sync plan` exits 1: 'no working Python 3.9+'; glibc Linux has no bootstrap, so python3 must preinstall. (2) With python3 and curl installed, `sh sync` fails tool:nodejs with 'Node.js archive does not contain a working bundled npm': the official linux-arm64 node needs libatomic.so.1, which the image lacks and sync never names. Nine tasks block on it, including tool:pi, pnpm, cmd, cf, pi-auth, claude-mcp and pi-mcp, so `pi-subagent-bridge` exits 'node: not found'. (3) tool:python3 and tool:ffmpeg fail with FileNotFoundError on their musl binaries (python-build#19; Ubuntu 24.04 musl is 1.2.4). (4) kache is a default goal only when ~/.cargo/bin/rustup exists at sync time, yet the linked ~/.cargo/config.toml always sets rustc-wrapper = "kache", so cargo fails in every Rust repository until rustup is installed and sync reruns. todo, worktree-retire, mdtool, fastermod, fd, rg and the skills install correctly. jaq is not in the Linux default tool list.
- **Recommendation:** State the Debian/Ubuntu prerequisites (python3, curl, libatomic1, and rustup before sync) in README and agent-setup, and have sync report a missing libatomic instead of 'no working bundled npm'. Fall back to a verified uv CPython where python-build cannot run (the buildlib shim's fallback). Keep the kache wrapper from breaking cargo when kache is absent, by linking the cargo config only once kache is installed. Acceptance: a fresh ubuntu:24.04 container that follows the documented commands gets todo, pi-subagent-bridge --help, node, pnpm and a working cargo build.
- **Fix with:** none
- **Effort:** M

### USR-75 · P3 · clang plus mold host links intermittently segfault and leave truncated artifacts

- **Area:** rust toolchain
- **Where:** dotfiles cargo config (linker clang, -B/usr/local/libexec/mold); Linux host, clang 23.1.3, mold 3.0.0
- **Problem:** On 2026-11-15 several XSH cargo test builds failed with linking with clang failed: signal 11 (SIGSEGV), with 48 GiB free and under heavy unrelated host load; a retry usually succeeds, but one crash left an 18 KiB build_script_build that cargo treated as fresh, so every later build failed until the target directory was deleted.
- **Recommendation:** Capture a crashing link (RUSTC_LOG or -Clink-arg=-v plus a core dump) to tell a mold crash from a clang driver crash, then report upstream or pin a mold release; meanwhile document deleting the target directory after a crashed link.
- **Fix with:** A reproduced crash with a core or backtrace and the mold/clang versions
- **Effort:** M

### USR-86 · P3 · Qualify optional copy-on-write worktree and cache seeding

- **Area:** Delegation
- **Where:** docs/worktree-cow.md; dotfiles/base/.local/bin/worktree-create; dotfiles/base/.local/bin/worktree-retire
- **Problem:** Native worktrees duplicate working files and per-lane build artifacts. Current CoW wrappers can save disk but add metadata, template or mount lifecycle risks; no usr-native APFS or Linux-musl measurements establish their value.
- **Recommendation:** Run the bounded comparison in docs/worktree-cow.md: native Git, allowlisted quiescent cache reflinks and one add-only adapter on APFS plus native Linux Btrfs/XFS, with ext4 fallback. Measure post-build physical disk delta and responsiveness; require correct Git isolation and no silent full cache copies. Keep usr as the sole lifecycle owner and adopt only demonstrated improvements.
- **Fix with:** none
- **Effort:** M

### USR-87 · P3 · FX ACP worker has no live-inference proof on the intended Go DeepSeek route

- **Area:** Delegation
- **Where:** tools/pi-subagent-bridge/experiment/fx/live-pilot.mjs; docs/CAMPAIGN-RUNTIME-INDEPENDENCE-FX.md (Phase 2 parked)
- **Problem:** Every FX qualification used a scripted loopback provider; the 2026-11-19 recheck hit the OpenCode Go monthly limit (429 GoUsageLimitError), so FX prompts and tools have never produced useful work on a real model, and whether compaction helper calls are counted in reported usage is unverified.
- **Recommendation:** After the Go reset run npm run spike:fx -- --live opencode-go (ACP transport, bounded six jobs plus one correction), independently check results, record usage including compaction, then the Contributor Spark scout/mechanic cells.
- **Fix with:** none
- **Effort:** M

### USR-88 · P3 · FX 0.0.17 built-in web_fetch cannot be prevented, giving read-only FX tiers public-URL egress

- **Area:** Delegation
- **Where:** tools/pi-subagent-bridge/src/fx.ts (FX_UNGATED_TOOLS); tools/pi-subagent-bridge/src/fx-acp-supervisor.ts (policy stop); docs/CAMPAIGN-RUNTIME-INDEPENDENCE-FX.md (egress defect)
- **Problem:** web_fetch runs for public URLs under a deny-all permission set in auto and ask modes, and still runs when hidden by tool_placement or called through a denied toolbox; the bridge only detects and stops the run after the call may have executed, unlike Pi scouts which have no network tool.
- **Recommendation:** Before routing any read-only tier to FX, requalify a newer FX release that honors a deny rule for web_fetch, or contain FX network egress at the OS level to the provider endpoint; keep the detection stop either way.
- **Fix with:** security
- **Effort:** M

### USR-89 · P3 · FX pin carries workarounds for three 0.0.17 upstream defects that need requalification on upgrade

- **Area:** Delegation
- **Where:** tools/pi-subagent-bridge/experiment/fx/pin.json; tools/pi-subagent-bridge/src/fx.ts (ACP args, shell option, tool_placement)
- **Problem:** FX 0.0.17 fails ACP session/new with -32603 whenever --provider is passed, its shell tool cannot snapshot busybox ash on Alpine, and web_fetch is ungated; the adapter works around each, and a release upgrade could change any of them silently.
- **Recommendation:** When adopting a newer FX release, update pin.json per target, rerun npm run spike:fx -- --local plus experiment/fx/linux.sh arm64 and amd64, and drop each workaround only with a reproduction showing it is fixed.
- **Fix with:** none
- **Effort:** M

### USR-102 · P3 · Reusable Tailscale auth key leaks into argv and installer children

- **Area:** Alpine provisioner · secrets
- **Where:** host/alpine/provision.py:691, 54, 1059; tools/sync/installer.py:3325, 1749, 1806
- **Problem:** tailscale up receives --auth-key=KEY on its argv, visible in ps while it runs, and README:155 recommends a reusable key. as_user uses su without -l and installer.py passes env=dict(os.environ) to children, so TS_AUTHKEY reaches vendor bash installers and npm installs run by sync tools. Unproven at runtime: depends on busybox su keeping the environment.
- **Recommendation:** Remove TS_AUTHKEY from the environment given to as_user and installer children, and pass it to tailscale through a 0600 file or stdin. Acceptance: a unit test shows neither the as_user environment nor the tailscale argv carries the key.
- **Fix with:** security
- **Effort:** S

### USR-103 · P3 · pinact template-injection check misses workflow_run fields and github-script

- **Area:** pinact · security lint
- **Where:** tools/pinact/src/pinact/security.py:73, 409; tools/pinact/README.md:62
- **Problem:** UNTRUSTED_PREFIXES omits github.event.workflow_run head and display fields although workflow_run is a high-risk trigger at security.py:69, and only run: bodies are scanned, not with.script on actions/github-script. pinact lint --profile=strict on a scratch workflow reported only github.event.issue.title in run:, and passed workflow_run.head_branch, workflow_run.head_commit.message and an interpolation in github-script with.script.
- **Recommendation:** Add the workflow_run head and display fields to the untrusted set and scan with.script on actions/github-script. Acceptance: each of those three cases yields one template-injection finding and existing negative cases still pass.
- **Fix with:** security
- **Effort:** S

### USR-104 · P3 · Root setup.sh run drops GH_TOKEN and reports success without key upload

- **Area:** Alpine provisioner · GitHub auth
- **Where:** host/setup.sh:39, 59; host/alpine/README.md:86
- **Problem:** setup.sh re-executes through su -l, which resets the environment, so the unattended GH_TOKEN install documented at README:86-93 loses the token when run as root; without a terminal it prints GitHub is not authenticated, skips the key upload and still exits successfully. Unproven: code trace only.
- **Recommendation:** Pass GH_TOKEN through explicitly to the target-user step, or fail when the upload was requested and skipped. Acceptance: a root run with GH_TOKEN set registers the key, and a skipped upload exits nonzero.
- **Fix with:** root-cause
- **Effort:** S

### USR-106 · P3 · An unacknowledged Pi steer freezes worker_status for the MCP server's life

- **Area:** pi-subagent-bridge · steering
- **Where:** tools/pi-subagent-bridge/src/hybrid.ts:668, 673, 678, 536, 307; README.md:113
- **Problem:** A steer that returns pending keeps pending_steer with caller_pid set to the server's own pid; status skips advance while that caller lives and reconciles only when it is dead, so in a long-lived MCP server status becomes read-only: no lease release, no pre-edit fallback, and every later steer is refused. A repro using the hybrid test helpers showed state succeeded, pending true and the lease still held after the Pi run finished, and a second steer failed with A steer is already pending. test/hybrid.test.ts:812 stops before this point.
- **Recommendation:** Record the steer request_id and reconcile it from the receipts file in advance, or resolve the steer as failed once the Pi run is terminal; advance when the pending caller is the current process. Acceptance: the repro shows the lease released and last_steer set.
- **Fix with:** audit-implicit-state-machine
- **Effort:** S

### USR-107 · P3 · Bridge session lock can be stolen from a live holder and never recovers a dead one

- **Area:** pi-subagent-bridge · locking
- **Where:** tools/pi-subagent-bridge/src/hybrid.ts:101
- **Problem:** The session lock directory records no holder. On EEXIST any caller that sees a pending_steer with a dead caller_pid deletes the lock and enters, while the live process reconciling that steer may still hold it, and runResume and runCancel never clear pending_steer; two processes can then run fallback or launch concurrently, and the first holder's finally deletes the second's lock. Conversely, a crash while holding the lock without a pending steer wedges status, resume and cancel with transition in progress, and no recovery is documented. Proven by code trace, not executed.
- **Recommendation:** Write the holder pid and process start time into the lock and take it over only when that holder is proven dead. Acceptance: a test with a live holder and a dead pending-steer caller refuses the second caller, and a dead-holder lock is recovered.
- **Fix with:** lifecycle-concurrency
- **Effort:** M

### USR-108 · P3 · Admissions through a running MCP server lose their owner after any source edit

- **Area:** pi-subagent-bridge · owner protocol
- **Where:** tools/pi-subagent-bridge/src/server.ts:110, 120, 132; src/cli.ts:124; src/hybrid.ts:480, 502; src/source-manifest.ts; README.md:197
- **Problem:** When bridge sources change by mtime, the server dispatches to a fresh cli.ts --bridge-dispatch process that connects without an OwnerManager, so ownerResolver is undefined and new worker_start sessions are unowned; agentctl cannot observe or control them. The server runs straight from the checkout, so any edit, checkout or rebase triggers this. ensureRepo errors are swallowed at server.ts:120 and 132, and a stale generation.lock has the same silent effect. test/server.test.ts:42 checks only schemas. Proven by code trace.
- **Recommendation:** Pass the server's owner identity to the fresh dispatch, or refuse start in fresh-dispatch mode with the restart message; report owner endpoint failure in the admission result. Acceptance: a server test edits hybrid.ts, calls worker_start, and the record's owner equals the server identity.
- **Fix with:** api-surface-and-module-boundaries
- **Effort:** M

### USR-109 · P3 · Pi runs record no process identity and only their starter can cancel them

- **Area:** pi-subagent-bridge · Pi lifecycle
- **Where:** tools/pi-subagent-bridge/src/pi-port.ts:61, 97, 210; README.md:119
- **Problem:** Pi liveness is a bare kill(pid, 0) without start time, interrupt uses only the in-process children map, and the host is not spawned detached. A Pi run started from the CLI or before an MCP restart cannot be cancelled (interrupted false), a reused PID shows a dead host as running ahead of its result file, and the host shares the server's process group, contradicting README:119. Proven by code trace.
- **Recommendation:** Record and verify the Pi host's process start time as Codex and Command Code runs do, spawn it in its own group, and allow a verified signal from any bridge process. Acceptance: a Pi run started in one bridge instance is cancelled from a fresh instance after the identity check.
- **Fix with:** lifecycle-concurrency
- **Effort:** M

### USR-110 · P3 · No test drives real Codex failure events through fallback classification

- **Area:** pi-subagent-bridge · tests
- **Where:** tools/pi-subagent-bridge/src/codex.ts:68; test/hybrid.test.ts (Codex fallback tests)
- **Problem:** Every Codex fallback test injects status() directly; rg turn.failed test src matches only src/codex.ts:68. The mapping from a Codex event stream to failed plus error is unchecked, and a refusal that arrives only as an error event without turn.failed is classified interrupted (codex.ts:69), which never falls back, so provider-refusal fallbacks such as the cybersecurity refusal may not fire on real output. Unproven: what real Codex emits for that refusal. On 2026-11-20 a docs-only worker run (session usrw_ff4bc30e) exited after eight command_execution events with no turn.completed, turn.failed or error event and an empty stderr apart from Reading additional input from stdin; the bridge reported interrupted with no fallback, so the parent had to relaunch by hand.
- **Recommendation:** Add a fake Codex in test/codex.test.ts that emits thread.started, error and turn.failed with refusal text, asserting failed and fallback to command-code, plus a captured real refusal stream when available.
- **Fix with:** test-audit
- **Effort:** S

### USR-111 · P3 · Pre-existing owner end-to-end bridge test fails on this host at HEAD

- **Area:** pi-subagent-bridge · owner protocol
- **Where:** tools/pi-subagent-bridge/test/owner.test.ts:925
- **Problem:** On 2026-11-20 the test CLI start never becomes an owner and MCP server + owner CLI work end-to-end with clean shutdown failed in the full suite and alone, both with the working tree and in a clean worktree at 78bea96c: the owner command receipt was rejected with reason not-running instead of accepted for cli-int-1. The host load average was above 60, so a timing dependency is possible but unestablished. npm test therefore reports failure for every bridge change.
- **Recommendation:** Reproduce on a quiet host, then find whether the owner endpoint is not yet running when the command is sent or has shut down early, and fix the cause rather than widening timeouts. Acceptance: the test passes repeatedly under load and on a quiet host.
- **Fix with:** root-cause
- **Effort:** S

### USR-117 · P3 · make test and CI omit 29 registered checks, one red at HEAD

- **Area:** Tests · tier shape
- **Where:** tools/sync/checks.py:236 (SUITE); Makefile:35; .github/workflows/ci.yml; AGENTS.md:58
- **Problem:** 29 registered behavior checks outside SUITE run only through sh sync check --changed, which CI never uses: alpine-provision, instructions, sync-auth, sync-launcher, sync-hosts, intercom-tailnet, macos-tool, macos-lean, power-policy, skills-tool, cpu-guard, dsh, owned-help, setup-linux and others; dsh fails at HEAD. AGENTS.md flags only todo as outside make test, so the Verification section reads as complete. Running the omitted checks took about 120 s on a busy host.
- **Recommendation:** Run the changed-file selection against the merge base for pull requests, and mark each tier in AGENTS.md Verification as suite or changed-only. Acceptance: a change touching dotfiles/base/.local/bin/dsh runs the dsh check before merge.
- **Fix with:** test-pyramid
- **Effort:** S

### USR-118 · P3 · Suite runner stops at the first failure and records no per-check time

- **Area:** Tests · cost and observability
- **Where:** tools/sync/checks.py:435 (run_suite); Makefile:36; AGENTS.md:53
- **Problem:** run_suite returns on the first failing check, hiding later regressions behind one red result after minutes of waiting, and records no durations, so the 230 to 283 s suite time cannot be attributed to any check; execute() already records start and finish times for --changed.
- **Recommendation:** Run every suite check, print each exit status and duration, and exit nonzero at the end. Acceptance: with one injected failing check the remaining checks still run and a summary lists every duration.
- **Fix with:** test-pyramid
- **Effort:** S

### USR-119 · P3 · The test suite is defined in three places that drift

- **Area:** Tests · duplicated facts
- **Where:** Makefile:37; tools/sync/checks.py:236; tools/sync/test_checks.py:100
- **Problem:** make test runs nine inline commands besides sh sync check, seven duplicating registry checks (pi-release-install, pi-sync-bridge-offline, opencode-worker, pk, pk-sh-syntax, policy-generator, pi-offline), and tools/pi/test_runtime_profiles.py has no registry entry. test_checks.py:100 hard-codes a second copy of SUITE's rendered commands, so every suite change edits two lists; on 2026-11-20 adding the wol check broke it.
- **Recommendation:** Move the Makefile commands into SUITE, registering runtime-profiles, reduce test to sh sync check, and replace the hard-coded list with invariants such as uniqueness and existence. Acceptance: make test runs the same commands and SUITE is the only list.
- **Fix with:** single-source-of-truth
- **Effort:** S

### USR-120 · P3 · Installed runtime generations accumulate with no retention

- **Area:** Sync · operability
- **Where:** tools/sync/pi_release.py; tools/sync/installer.py:2234, 2253, 2472, 1736; docs/pi.md:14
- **Problem:** Only gluon, bctl and ffmpeg prune old releases; Pi never prunes pi-runtime/releases and Node removes only the release it replaces. On this Mac on 2026-11-20: 7 Pi generations in 4 days (906 MiB), Pi release cache 145 MiB, legacy ~/.local/share/pi 153 MiB, 3 Node releases 1.6 GiB, 7 python-build trees 329 MiB, 5 git trees 29 MiB, about 3 GiB. The cleanup skill excludes host caches and uninstall is all-or-nothing, so nothing supported reclaims them.
- **Recommendation:** Apply one retention rule, such as current plus one previous plus anything pinned, in every versioned installer, and document it beside rollback in docs/pi.md. Acceptance: after two upgrades each tool's releases directory holds at most two trees, with a test per installer.
- **Fix with:** single-source-of-truth
- **Effort:** M

### USR-121 · P3 · claude-or and claude-ds read one vault secret for two providers

- **Area:** Dotfiles · provider launchers
- **Where:** dotfiles/base/.local/bin/claude-or:7; dotfiles/base/.local/bin/claude-ds:14; dotfiles/base/.local/bin/dsh
- **Problem:** Both launchers run vault ANTHROPIC_AUTH_TOKEN -- claude against different base URLs (OpenRouter and api.deepseek.com), so whichever provider's key is stored under that name is sent to the other provider too; dsh already names the DeepSeek key DEEPSEEK_API_KEY. Neither forwards its arguments or has a test, and a missing entry fails with a hex-encoded file name. The shared name is proven; no host here has the entry, so an actual leak is unproven.
- **Recommendation:** Use one vault name per provider (OPENROUTER_API_KEY, DEEPSEEK_API_KEY) mapped to ANTHROPIC_AUTH_TOKEN inside each launcher, and forward "$@". Acceptance: a stub-vault test shows each launcher requests only its own provider's entry and passes its arguments through.
- **Fix with:** security
- **Effort:** S

### USR-122 · P3 · ruff and ty run unpinned through uvx in lint and checks

- **Area:** Build · lint dependencies
- **Where:** lint:15; tools/sync/checks.py:109, 228, 229, 233; ty.toml
- **Problem:** uvx resolves whatever ruff and ty version is cached or newest; ty is pre-1.0 and ty.toml enables many rules by name at error severity, so lint results can change or break on rule renames without a repository change and differ between hosts and CI.
- **Recommendation:** Pin ruff and ty versions in one place that both ./lint and checks.py read. Acceptance: no unpinned uvx ruff or uvx ty invocation remains.
- **Fix with:** single-source-of-truth
- **Effort:** S

### USR-73 · P4 · The refactor-web-ui skill has only been applied to agentctl

- **Area:** Skills
- **Where:** dotfiles/base/.agents/skills/refactor-web-ui/SKILL.md; docs/CAMPAIGN-AGENTCTL-WEB-UI.md: Transfer after agentctl
- **Problem:** The skill was exercised and sharpened on one product only. Its rules have not been tested against a dashboard (stats), a developer tool with canvas rendering (stuff), or a reading/research product (discover), so overfit rules cannot yet be told apart from transferable ones.
- **Recommendation:** On separate requests, apply the skill to stats (with refactor-dashboard-ui owning metrics and trends), stuff (keep canvas rendering and its performance invariants), and discover (evidence and provenance hierarchy, mobile reading). Follow the campaign's Transfer section, and after the second product delete or move rules that turned out to be agentctl-specific.
- **Fix with:** none
- **Effort:** L

### USR-74 · P4 · Designed UIs lack the required make preview and shared golden dataset

- **Area:** Skills
- **Where:** refactor-web-ui skill: Preview and goldens; repos discover, niceforge, laputa-ui-dashboard, stats
- **Problem:** refactor-web-ui now requires every designed UI to ship `make preview` on one canonical mock dataset that its integration goldens also use. On 2026-11-15 discover, niceforge and laputa-ui-dashboard have no `make preview`; stats has one, but whether its preview data is the same dataset its tests use is unverified. agentctl conforms; stuff gains it in its redesign.
- **Recommendation:** Per repo, on its own request: extract the fixture its browser tests seed into one dataset module, serve it with `make preview`, and add a semantic golden over the same dataset. For stats, check that preview and tests share one dataset before changing anything.
- **Fix with:** none
- **Effort:** M

### USR-90 · P4 · Muse and Devin Pi routes have no FX-side replacement design

- **Area:** Delegation
- **Where:** tools/pi-subagent-bridge/src/tier-policy.ts (MUSE_TIER_MODELS, DEVIN_TIER_MODELS); docs/CAMPAIGN-RUNTIME-INDEPENDENCE-FX.md (Phase 5 routes parked)
- **Problem:** Muse speaks MSP and serves its own ACP, and Devin needs its own CLI auth, so neither is an FX provider configuration; retiring Pi or pi-build would drop these worker routes and the final fallback rung of every root plan.
- **Recommendation:** Decide in an RFC whether to add native ACP executors for muse acp and Devin reusing the FX ACP supervisor, or keep Pi for these routes permanently; Pi stays until then.
- **Fix with:** architect
- **Effort:** L

### USR-91 · P4 · FX worker budgets remain at experiment caps of 15 minutes and 20 steps

- **Area:** Delegation
- **Where:** tools/pi-subagent-bridge/src/fx.ts (FX_PILOT_MAX_STEPS, wallMs cap 900000)
- **Problem:** Pi workers get a four-hour deadline while FX is capped at 15 minutes and 20 model steps, so FX cannot run the same long tasks; raising the caps needs an approved production budget and long-run evidence.
- **Recommendation:** If FX is promoted, choose production wall and step budgets, make the cap an admitted policy value rather than a constant, and qualify a long real task under it.
- **Fix with:** none
- **Effort:** S

### USR-92 · P4 · Retiring pi-build would also orphan the agent-intercom companion artifacts

- **Area:** Sync
- **Where:** tools/pi/runtime.pin.json (companions); docs/CAMPAIGN-PI-BUILD.md
- **Problem:** pi-build publishes the agent-intercom-claude, -codex and -opencode companion archives as well as the Pi runtime, so dropping pi-build after an FX migration would break intercom installation.
- **Recommendation:** Before any pi-build retirement, move companion packaging and pinning to another pinned release source and verify sync installs them unchanged.
- **Fix with:** none
- **Effort:** M

### USR-93 · P4 · FX workers lack the planned pinned research tools (pi-web-access MCP)

- **Area:** Delegation
- **Where:** docs/CAMPAIGN-RUNTIME-INDEPENDENCE-FX.md (Phase 3 parked, grant shape); tools/pi-subagent-bridge/src/fx-acp-supervisor.ts (mcp_servers)
- **Problem:** Phase 3 needs pi-web-access 0.48.0 in a pinned closure plus separate search credentials; the npm tarball gitHead 896d75be differs from the campaign record 438e58be, and nothing packages it yet. It is an addition, not Pi parity.
- **Recommendation:** If wanted, package pi-web-access through a pinned release, re-verify its source revision, supply it as a per-tool-granted ACP MCP server for approved roles only, and prove search, fetch, citation and restart offline before any live check.
- **Fix with:** none
- **Effort:** L

### USR-112 · P4 · Bridge fallback notices name OpenCode Go for Devin fallbacks

- **Area:** pi-subagent-bridge · notices
- **Where:** tools/pi-subagent-bridge/src/inspect.ts:144, 285
- **Problem:** continuedOn and the inherited Pi notice choose between Muse and OpenCode Go only, but devin/swe-2-flash is a production worker fallback, so a Devin fallback tells the parent the wrong provider. Proven by code trace.
- **Recommendation:** Derive provider labels from the policy's provider table. Acceptance: a Devin fallback notice names Devin.
- **Fix with:** single-source-of-truth
- **Effort:** S

### USR-113 · P4 · Pi path still runs through an OpenCode-shaped port

- **Area:** pi-subagent-bridge · maintainability
- **Where:** tools/pi-subagent-bridge/src/bridge.ts (OpenCodePort, unbox, DEFAULT_MODEL, USR_PI_SUBAGENT_MODEL); src/pi-port.ts; src/pi-adapter.ts:6
- **Problem:** pi-port.ts emulates OpenCode's create, prompt, get, active, inbox and messages API, and ownership relies on a usr-worker title prefix; selectedModel, DEFAULT_MODEL and USR_PI_SUBAGENT_MODEL are used only as a default parameter that pi-adapter.ts:6 always overrides (rg finds them only in bridge.ts and its test). Every Pi change passes through this translation layer.
- **Recommendation:** Replace it with a direct Pi adapter interface and delete the OpenCode-shaped surface. Acceptance: no OpenCodePort references remain and the Pi fixtures pass.
- **Fix with:** dead-code-archaeology
- **Effort:** M

### USR-123 · P4 · make test silently skips the no-npm sync bridge case in a dev checkout

- **Area:** Tests · verification
- **Where:** Makefile:38; tools/pi/test_sync_bridge_offline.py:45; docs/development.md:175
- **Problem:** The test skips itself whenever tools/pi-subagent-bridge/node_modules exists, which it does in the owner's checkout (a symlink into the Pi runtime), so make test reports OK (skipped=1) locally without exercising the fresh-home and second-sync no-npm case; only .github/workflows/pi-offline-verify.yml:44 runs it.
- **Recommendation:** Run it in a temporary clone from make test, or print that it was skipped and why. Acceptance: local make test output names the skip or exercises the case.
- **Fix with:** none
- **Effort:** S

### USR-124 · P4 · Doctor mislabels the bridge and its Codex check only greps the config

- **Area:** Dotfiles · doctor and Codex config
- **Where:** dotfiles/doctor:81, 88, 109; dotfiles/base/.codex/config.toml:392
- **Problem:** doctor reports Claude/Codex/Pi DeepSeek bridge is configured for pi-subagent-bridge, which is not DeepSeek-specific; the Codex check greps for the section header in the repo's own linked file, so it passes when the bridge launcher is missing. The shared base layer enables node_repl with a hard-coded /Applications/ChatGPT.app path, unproven to fail on Linux.
- **Recommendation:** Correct the labels, have the Codex check verify that pi-subagent-bridge resolves, and move node_repl to the darwin layer. Acceptance: doctor fails when the bridge launcher is absent.
- **Fix with:** none
- **Effort:** S

### USR-125 · P4 · check-parallel is a second full runner with different coverage

- **Area:** Tests · tier shape
- **Where:** tools/sync/main.py:455; docs/development.md:5
- **Problem:** sh sync check-parallel runs pytest over tools, dotfiles and host/macos through uvx with a pinned plugin and Python 3.15; it covers Python only but picks up suites the registry omits, and no Makefile target or CI job uses it, so the repository has two disagreeing definitions of the full suite. Unproven: not run.
- **Recommendation:** Decide whether check-parallel becomes the documented full tier or is removed once the registry covers every suite. Acceptance: one documented full-suite entrypoint.
- **Fix with:** debloat
- **Effort:** S

### USR-126 · P4 · sync links --json mixes LINK lines into its JSON output

- **Area:** Sync · CLI output
- **Where:** tools/sync/main.py (links --json)
- **Problem:** sh sync links --json prints LINK: progress lines on stdout before the JSON object, so stdout is not one JSON document; tools/bench/bench.py reads only the last line to work around it.
- **Recommendation:** Send progress lines to stderr, or suppress them under --json. Acceptance: stdout of sh sync links --json into a scratch TARGET parses as one JSON value.
- **Fix with:** design-cli
- **Effort:** S

