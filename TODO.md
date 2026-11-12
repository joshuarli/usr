Prefix: USR
Next: 51

### USR-39 · P1 · Failed Pi workers can inherit another worker's successful proof

- **Area:** Data
- **Where:** `tools/pi-subagent-bridge/src/sdk-worker.ts:28`, `tools/pi-subagent-bridge/src/sdk-worker.ts:266`, `tools/pi-subagent-bridge/src/pi-port.ts:77`, `tools/pi-subagent-bridge/src/pi-port.ts:93`
- **Problem:** SDK hosts share `pi-sessions/subagent-artifacts`. After dispatch or admission, the exception handler calls `artifactResult` with an empty run ID, which matches every artifact filename. A failed worker can persist an earlier worker's success and proof as its own. An offline probe executed the unmodified recovery and main function bodies with the real persistence function: an old successful metadata/output pair plus a current-run timeout produced `state: "succeeded"`, the old proof text, and `runId: ""`. The host exited 1, but `pi-port` accepts the result JSON independently of that exit code, so status can report false success and release the lease. Vendored `pi-subagents` enables session artifacts by default.
- **Recommendation:** Retain the admitted run ID, async directory, and session file across the exception boundary. Recover only an exact owned run, reject empty identities, and validate artifact identity before accepting success. Add a regression with one worker's success followed by another worker's timeout; the second must never inherit the first's proof or release its lease on that evidence.
- **Fix with:** `durable-state`
- **Effort:** S

### USR-40 · P1 · Failed Node upgrades remove the working runtime and block retry

- **Area:** Build
- **Where:** `tools/sync/installer.py:1388`, `tools/sync/installer.py:1400`, `tools/sync/installer.py:1439`, `tools/sync/installer.py:1485`
- **Problem:** The managed-release recognizer embeds the newly pinned `NODEJS_VERSION`. A valid previous-version installation is treated as stale, and `nodejs/current` is unlinked before downloading and validating the replacement. A scratch fixture installed working `26.12.0-npm11.9.0-linux-x64` launchers, then failed only the download edge of the real `install_nodejs()` upgrade to 26.13.0. All three `node`, `npm`, and `npx` launchers became dangling despite the old tree surviving. A second invocation refused the nonempty prefix as outside management and never attempted another download. A routine failed upgrade therefore disables Node-based agent tools and cannot recover by rerunning sync.
- **Recommendation:** Recognize historical managed releases independently of the desired version. Keep the previous selection until the new release passes validation, switch atomically, and prune only after success. Cover a failed previous-version upgrade and successful retry in the installer fixtures.
- **Fix with:** `durable-state`
- **Effort:** S

### USR-41 · P2 · Uncertain Muse admission starts a second worker in the same worktree

- **Area:** Concurrency
- **Where:** `tools/pi-subagent-bridge/src/hybrid.ts:333`, `tools/pi-subagent-bridge/src/hybrid.ts:227`, `tools/pi-subagent-bridge/src/hybrid.ts:418`, `tools/pi-subagent-bridge/src/bridge.ts:179`, `tools/pi-subagent-bridge/src/pi-port.ts:184`
- **Problem:** The Muse startup catch treats every error as permission to fall through, including `created but prompt admission failed`. The fallback helper checks Command Code termination but not an uncertain Pi admission. A fake provider port exercised the real bridges with Command Code absent: the first prompt left a child active and raised a receipt error; the bridge created and prompted a second child, retained only its session ID, and claimed no work was replayed. The real Pi adapter can fail after spawning and before saving its final admission record. The status-driven fallback has the same catch pattern. Two workers can then write the same worktree under one tracked assignment.
- **Recommendation:** Distinguish confirmed pre-admission provider failures from failures after session creation or dispatch. Persist the child identity before dispatch and retain the lease in a blocked state when admission is uncertain. Require proof of no admitted child or confirmed termination before another start. Assert exactly one creation and prompt in both ambiguous-admission paths.
- **Fix with:** `lifecycle-concurrency`
- **Effort:** M

### USR-42 · P2 · Automatic Claude worktree removal deletes ignored artifacts

- **Area:** Data
- **Where:** `dotfiles/base/.local/bin/worktree-remove:26`, `dotfiles/base/.claude/settings.json:35`, `dotfiles/base/.local/bin/worktree-retire:64`
- **Problem:** The automatic WorktreeRemove hook checks porcelain status without ignored files, then removes the worktree. A real hook fixture with a clean worktree and an ignored `.env` file exited 0 and deleted both. This can discard local configuration or research/build artifacts worth retaining. The separate `worktree-retire` command already detects ignored files and requires explicit `--discard-ignored`, but the automatic hook bypasses that protection.
- **Recommendation:** Apply the retirement command's ignored-file preflight to the hook. Retain the worktree and report ignored paths for parent review; leave reviewed disposal to explicit retirement. Cover an otherwise clean worktree containing a valuable ignored file.
- **Fix with:** `os-boundaries`
- **Effort:** S

### USR-43 · P2 · Stale-branch cleanup can delete a newly advanced branch

- **Area:** Data
- **Where:** `tools/close-stale-prs/src/close_stale_prs.py:214`, `tools/close-stale-prs/src/close_stale_prs.py:325`, `tools/close-stale-prs/src/close_stale_prs.py:374`, `tools/close-stale-prs/src/close_stale_prs.py:415`
- **Problem:** Cleanup snapshots commit ages and PR state, then deletes by branch name without retaining or comparing the observed tip OID. Another writer can advance an eligible old branch before deletion, and the command deletes the new tip despite its commit being newer than the cutoff. A transport fixture ran the real CLI eligibility and deletion path, advanced the simulated ref after the GraphQL response, and observed an unconditional DELETE of the new unmerged tip with exit 0. No live remote deletion was performed.
- **Recommendation:** Capture candidate tip OIDs and use deletion with an expected-tip condition. Refuse changed refs and report them for a later run. A separate read followed by unconditional deletion still races. Preserve dry-run behavior and the protected/default/open-PR exclusions.
- **Fix with:** `durable-state`
- **Effort:** S

### USR-44 · P2 · Interrupted link finalization permanently blocks recovery

- **Area:** Data
- **Where:** `tools/sync/link_recovery.py:117`, `tools/sync/link_apply.py:131`, `tools/sync/link_plan.py:164`
- **Problem:** Finalization deletes the stage symlink before its journal. An interruption between those operations leaves a correct destination and committed ownership proof, but recovery rejects the remaining journal because the stage inode is missing. A scratch probe invoked real discovery, planning, and apply, failed the journal unlink after stage deletion, and verified both destination and ownership record survived. Two retries then failed with `pending link stage changed`. Sync cannot converge without manual state repair.
- **Recommendation:** Make finalization idempotent across this crash window. Either retire the journal durably before discarding the stage once destination and ownership are durable, or recognize completed ownership using the recorded destination inode when only the stage is missing. Preserve rejection of foreign replacements. Add a numbered link case interrupting the two cleanup operations.
- **Fix with:** `durable-state`
- **Effort:** S

### USR-45 · P2 · Muse unavailability blocks the available OpenCode Go fallback

- **Area:** Errors
- **Where:** `tools/pi-subagent-bridge/src/hybrid.ts:140`, `tools/pi-subagent-bridge/src/hybrid.ts:227`, `tools/pi-subagent-bridge/src/hybrid.ts:308`, `tools/pi-subagent-bridge/src/hybrid.ts:418`
- **Problem:** Scout, mechanic, and worker sessions initialize `primary_model` to Muse. The helper advertised as the Go fallback calls `primaryFor(s)` without selecting the Go pin, so it checks Muse again. A real bridge fixture advertised the approved Go worker model and no Muse model: `modelCheck` reported Go available, but `start` failed with `Pinned OpenCode Go fallback model is unavailable` and created no child. Both missing-Command-Code startup and Command Code provider recovery use this helper. When the retry does launch, its notice can claim Go while the actual model remains Muse.
- **Recommendation:** Represent remaining fallback destinations explicitly and select/persist the destination's exact pinned model before an allowed transition. Cover Muse absent plus Go available, both at initial startup and after a confirmed Command Code provider failure, for every eligible tier. Preserve admitted sessions' original provider and resolve the uncertain-admission defect independently.
- **Fix with:** `make-invalid-states-unrepresentable`
- **Effort:** S

### USR-46 · P2 · Claude children start from the main checkout instead of the caller's worktree

- **Area:** Concurrency
- **Where:** `dotfiles/base/.local/bin/worktree-create:20`, `dotfiles/base/.local/bin/worktree-create:28`, `dotfiles/base/.local/bin/worktree-create:39`, `dotfiles/base/.claude/settings.json:24`
- **Problem:** The hook uses the supplied `cwd` to locate the common Git directory, then resolves `HEAD` through `git -C "$root" worktree add`. A child launched from a campaign worktree therefore starts at the main checkout's revision. A real hook fixture committed a file only in the caller's campaign branch: the child equaled main's HEAD, differed from the caller, and lacked that file. Children silently review or build against the wrong base and omit accepted campaign work.
- **Recommendation:** Resolve the exact base commit from the supplied `cwd` before creation. Use the common root only for placement. Cover distinct main/caller commits and assert the child inherits the caller's commit.
- **Fix with:** `os-boundaries`
- **Effort:** S

### USR-47 · P2 · Usage RPC reads time out on responses already buffered in Python

- **Area:** Errors
- **Where:** `tools/usage/src/usage:60`, `tools/usage/src/usage:88`, `tools/usage/src/usage:264`
- **Problem:** `read_rpc_response` calls `select` on a pipe wrapped in buffered text I/O. When a child writes a notification and response together, the first `readline` can buffer both. After skipping the notification, the loop waits on the empty descriptor instead of consuming the buffered response, eventually reporting the normal 35-second timeout. A local child fixture using the real reader and a 300 ms deadline returned a response sent alone, but timed out on notification-plus-response in one write; a subsequent `readline` recovered the already received response. Codex/Muse RPC and Grok ACP use this reader.
- **Recommendation:** Frame unbuffered bytes with deadline-aware polling, or read complete messages on a dedicated reader into a queue. Cover several JSON lines in one write, fragmented lines, and a child that remains alive after its response.
- **Fix with:** `os-boundaries`
- **Effort:** S

### USR-48 · P2 · Catalog upgrades reject valid same-major unpinned actions

- **Area:** Build
- **Where:** `tools/pinact/src/pinact/fixes.py:216`, `tools/pinact/src/pinact/fixes.py:524`, `tools/pinact/src/pinact/catalog.py:163`
- **Problem:** `fix --catalog C --upgrade W` labels every catalog edit as resolving `unapproved-pin`. An action at `actions/checkout@v4.1.0` is already approved by a catalog targeting `v4.2.2`, so its actual violation is `unpinned-uses`. Validation sees no decrease in the nonexistent `unapproved-pin` finding and rejects the edit. A real CLI fixture with that catalog exited 1, reported `fix for unapproved-pin did not resolve`, and left the workflow unchanged. The identical command without `--upgrade` exited 0 and pinned it correctly.
- **Recommendation:** Classify the edit by its actual preexisting violation, or validate the explicit catalog postcondition without demanding a nonexistent diagnostic decrease. Preserve correctness validation and idempotence. Cover same-major mutable refs, pinned upgrades, and cross-major catalog upgrades.
- **Fix with:** `error-model`
- **Effort:** S

### USR-38 · P2 · Complete companion intercom adapters and supervisor consultation

- **Area:** Architecture
- **Where:** `tools/pi-subagent-bridge/src/sdk-worker.ts:156`, `tools/sync/pi_offline.py:252`, `vendor/pi/upstreams.json:15`
- **Problem:** Interactive Pi has a local intercom adapter, but Claude/Codex/OpenCode companion adapters remain absent. Scoped SDK children deliberately load only subagents and the optional Muse provider, so they expose no `contact_supervisor` integration. The offline CLI/SDK packaging is delivered; the remaining gap is communication across harnesses and bounded child-supervisor consultation. Rechecked the SDK loader, vendor inventory, and local broker defaults without live provider calls.
- **Recommendation:** Package compatible companion adapters and core protocol revisions with upstream commit SHAs. Under the [Pi build migration](docs/CAMPAIGN-PI-BUILD.md), `pi-build` owns those inputs and artifacts; `usr` retains harness registration and the first-party bridge. Register the required hooks/wrappers and verify cross-harness send/ask/reply plus bounded consultation as separate feature work. Preserve typed tier restrictions, worktree ownership, acceptance proof, explicit send authorization, and disabled unsolicited wakeups. Moving the existing runtime does not complete this ticket or authorize intercom in scoped SDK children.
- **Fix with:** `pi-update`
- **Effort:** L

### USR-32 · P3 · Concurrent campaign allowances can overwrite each other

- **Area:** Concurrency
- **Where:** `dotfiles/base/.local/bin/codex-campaign-closeout.py:132`, `dotfiles/base/.local/bin/codex-campaign-closeout.py:171`, `dotfiles/base/.local/bin/codex-campaign-closeout.py:252`
- **Problem:** Concurrent allow commands load the same allowed dictionary, add different worktrees, then replace the state file without a lock or generation check. A two-process fixture using the real `allow` implementation and real Git worktrees synchronized both calls after `load_state`: both reported success, but only one allowance survived. The Stop hook can later block a worktree reported as allowed. Atomic file replacement protects syntax, not the read-modify-write transaction.
- **Recommendation:** Serialize the complete load-modify-save transaction or use a compare-and-retry revision. Preserve state validation and add the two-process disjoint-allowance regression.
- **Fix with:** `durable-state`
- **Effort:** S

### USR-50 · P1 · Muse Code 1.4.15 rejects the bridge's MCP toolset selector

- **Area:** Delegation
- **Where:** `tools/pi-subagent-bridge/node_modules/pi-muse-subscription/src/convert.ts:7-8` (`MCP_TOOLSET`), `src/host.ts:162`, `~/.local/bin/muse` (auto-update)
- **Problem:** pi-muse-subscription 0.1.0 writes `"toolset": ["mcp__pi__*"]` into each Muse host's settings. Muse Code auto-updated to 1.4.15 (R8339.1) on 2026-11-11 and now refuses that run with `invalid run configuration: unknown tool mcp__pi__*`. Every Muse-backed bridge worker fails at startup, so the Muse fallback for scout, mechanic and worker is dead. A worker whose Command Code run hit a usage limit after making edits also stays leased as `blocked_partial_work`, and `worker_cancel` cannot release it, so a parent must recreate the worktree to continue.
- **Recommendation:** Determine the selector form Muse 1.4.15 accepts, for example the namespaced `mcp__pi.*` that `convert.ts:75` already decodes, or an explicit tool list. Fix `MCP_TOOLSET`, and add a bridge smoke test that starts one real Muse run. Pin the Muse version the bridge supports, or check it in `worker_model_check`, so an auto-update fails visibly instead of at the first launch. Let the parent release a `blocked_partial_work` lease once it has preserved the work.
- **Fix with:** `root-cause`
- **Effort:** S

