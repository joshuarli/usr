Prefix: USR
Next: 64



### USR-56 · P1 · Stale branch cleanup deletes unmerged work added before discovery

- **Area:** Git maintenance
- **Where:** `tools/close-stale-prs/src/close_stale_prs.py:206`, `tools/close-stale-prs/src/close_stale_prs.py:219`, `tools/close-stale-prs/src/close_stale_prs.py:523`, `tools/close-stale-prs/src/close_stale_prs.py:550`
- **Problem:** Deletion eligibility uses the age and state of PRs associated with a branch name, but never establishes that the current tip was merged or otherwise retained. An old merged PR followed by unmerged commits older than the cutoff passes every check. The expected-OID lease succeeds because the new work predates discovery. Proven with real Git commits dated 2000-01-01 and a local bare remote: merge a feature head into main, advance that feature with an unmerged file, and run the real main/delete path with fixture API metadata for the actual current tip. The command exits 0 and prints DELETED while main lacks that file and the remote branch is absent. This is independent of the fixed post-snapshot movement race.
- **Recommendation:** Require positive integration evidence for the exact candidate tip before deleting it: compare it with the final head of a merged PR or prove integration into a retained ref, preserving branches when evidence is absent. Keep the expected-OID lease for later movement. Add a local-remote regression for a branch advanced after PR merge but before discovery; its ref and unmerged commit must survive.
- **Fix with:** `durable-state`
- **Effort:** M

### USR-57 · P1 · pnpm installation deletes or replaces unowned paths

- **Area:** Sync
- **Where:** `tools/sync/installer.py:1187`, `tools/sync/installer.py:1208`, `tools/sync/installer.py:1235`, `tools/sync/installer.py:543`
- **Problem:** install_pnpm mutates existing launcher and prefix paths without establishing ownership. It unlinks a non-directory or symlink at pnpm-npm, recursively removes a directory at .local/bin/pnpm, and replaces an existing regular executable. Two offline probes call the real installer: an unrecorded launcher directory containing valuable.txt disappears when npm_install subsequently fails, and an unrecorded executable becomes the managed symlink after a successful fixture install. Both are reachable through sh sync tools pnpm and the default tool set, so ordinary installation can destroy user content or an independently installed launcher.
- **Recommendation:** Preflight the launcher and prefix before mutation. Reject unowned files, directories and symlinks while preserving their bytes and targets; replace only a recognized managed installation. Add regressions for a foreign executable, a launcher directory with a sentinel, and foreign prefix objects on both successful and failed npm installs. Preserve the existing polluted-PNPM_HOME behavior without treating arbitrary content as owned.
- **Fix with:** `os-boundaries`
- **Effort:** M


### USR-38 · P2 · Complete companion intercom adapters and supervisor consultation

- **Area:** Architecture
- **Where:** `tools/pi-subagent-bridge/src/sdk-worker.ts:141`, `tools/sync/pi_offline.py:116` (`configure_intercom`), `pi-build` `sources/upstreams.json`
- **Problem:** Interactive Pi has a local intercom adapter, but Claude/Codex/OpenCode companion adapters remain absent. Scoped SDK children deliberately load only subagents and the optional Muse provider, so they expose no `contact_supervisor` integration. The offline CLI/SDK packaging is delivered; the remaining gap is communication across harnesses and bounded child-supervisor consultation. Rechecked the SDK loader, source inventory, and local broker defaults without live provider calls.
- **Recommendation:** Package compatible companion adapters and core protocol revisions with upstream commit SHAs. `pi-build` owns those inputs and artifacts; `usr` retains harness registration and the first-party bridge. Register the required hooks/wrappers and verify cross-harness send/ask/reply plus bounded consultation as separate feature work. Preserve typed tier restrictions, worktree ownership, acceptance proof, explicit send authorization, and disabled unsolicited wakeups. Moving the existing runtime does not complete this ticket or authorize intercom in scoped SDK children.
- **Fix with:** `pi-update`
- **Effort:** L


### USR-58 · P2 · Published tool bundles cannot recover after interrupted activation

- **Area:** Sync
- **Where:** `tools/sync/installer.py:1973`, `tools/sync/installer.py:2014`, `tools/sync/installer.py:2023`, `tools/sync/main.py:129`
- **Problem:** _archive_bundle publishes the validated release directory before selecting current, installing launchers, recording the asset identity or returning ownership claims. If activation fails or stops, retry rejects its own generation as already existing unless both current and the final state record match. Proven using the existing Git archive fixture: make switch_symlink return false once, then retry with a new Installer. The first run leaves a valid release and no current link; retry fails with '<release directory> already exists'. The shared path serves Git, SSH, oxish, bctl and gluon.
- **Recommendation:** Make activation resumable without adopting arbitrary existing directories. Persist verifiable generation identity before publication, or reconstruct and compare against the verified archive, then finish current selection, launchers, state and ownership on retry. Preserve the previous working selection until validation completes. Extend the Git fixture with interruption after publication, selection and launcher creation; retry must converge while foreign or modified generations remain rejected.
- **Fix with:** `durable-state`
- **Effort:** M


### USR-59 · P2 · Pi rejects intact generations after unrelated pin metadata changes

- **Area:** Sync
- **Where:** `tools/sync/pi_release.py:217`, `tools/sync/pi_release.py:240`, `tools/sync/pi_release.py:266`, `tools/sync/pi_release.py:293`
- **Problem:** Generation directories use the selected target archive SHA-256, but generation() requires the receipt to equal the entire multi-target pin. Changing another platform, release location or provenance therefore invalidates an unchanged installed generation. install() extracts the same cached archive, then rejects the occupied digest directory as modified. Proven without network: install a valid cached darwin-arm64 archive, add a linux-x64 pin entry without changing the Darwin artifact or installed bytes, and reinstall. It raises 'existing Pi release is modified; preserve and inspect before retry'; the same generation still validates under its original pin.
- **Recommendation:** Separate immutable target content identity from release-selection metadata. Verify target archive/profile/runtime identity and inventory before reuse, and atomically store or update selection metadata without conflating unrelated targets with modified content. Test another-target-only changes, provenance or URL changes with identical target bytes, and genuine on-disk modification. Metadata changes must converge; modified trees must remain rejected.
- **Fix with:** `durable-state`
- **Effort:** M


### USR-60 · P2 · Rejected Pi resumes strand live workers in an unrecoverable transition

- **Area:** Delegation
- **Where:** `tools/pi-subagent-bridge/src/hybrid.ts:393`, `tools/pi-subagent-bridge/src/bridge.ts:212`, `tools/pi-subagent-bridge/src/inspect.ts:192`, `tools/pi-subagent-bridge/src/hybrid.ts:436`
- **Problem:** worker_resume increments attempts and persists a Pi transition before the lower bridge checks whether the child is running or has queued input. A known pre-dispatch rejection leaves a healthy child classified as blocked_admission, consumes its correction attempt, prevents worker_cancel from reaching it and retains its lease after completion. An offline makeHybridBridge fixture with attempt_limit=2 reproduced running -> rejected resume -> blocked_admission, one prompt call, zero child interrupts, attempts=2 and the same blocked state after the child finished.
- **Recommendation:** Separate Pi resume preflight from dispatch under the existing session lock. Reject known active, queued or otherwise invalid resumes before changing execution or attempts; retain the conservative transition once dispatch can actually be ambiguous. Add regressions for rejected active/queued resumes, unchanged state and counters, usable cancellation and terminal lease release. Preserve the existing uncertain-dispatch regression.
- **Fix with:** `lifecycle-concurrency`
- **Effort:** M


### USR-61 · P2 · CLI result readers discard completion records across the 64 KiB split

- **Area:** Delegation
- **Where:** `tools/pi-subagent-bridge/src/codex.ts:50`, `tools/pi-subagent-bridge/src/codex.ts:59`, `tools/pi-subagent-bridge/src/antigravity.ts:56`, `tools/pi-subagent-bridge/src/antigravity.ts:64`
- **Problem:** Codex and Antigravity log readers join the first 65,536 bytes and their tail with an added newline even when those reads are contiguous. A valid JSONL completion crossing that offset becomes two invalid records and is silently discarded. A local fixture with a roughly 2 KB completion starting at byte 65,000 makes Codex report succeeded without finalText or acceptance and Antigravity report interrupted. The identical completion beginning at byte 60,000 succeeds in both readers. Transcript length changes the observed result independently of worker behavior.
- **Recommendation:** Preserve contiguous bytes exactly and handle actual gaps at JSONL record boundaries without joining unrelated fragments. Give the bounded reader one owner shared by both executors. Add boundary cases for a completion crossing byte 65,536, multibyte UTF-8 across the split, and a genuinely omitted middle section; assert retained identity, terminal state and acceptance text.
- **Fix with:** `error-model`
- **Effort:** S


### USR-62 · P2 · Alpine provisioning mistakes tool IDs for installed launcher names

- **Area:** Provisioning
- **Where:** `host/alpine/install.sh:326`, `host/alpine/install.sh:330`, `host/alpine/verify.sh:80`, `host/alpine/verify.sh:83`, `tools/sync/main.py:27`, `host/alpine/tools-server.txt:17`
- **Problem:** The Alpine install and verify loops assume a tool ID names its executable, except for nodejs and ffmpeg. The canonical sync mapping installs shuck as shellcheck, lz as less and gluon as meson/ninja/gluon-build. shuck is in the server profile, so a complete installation is marked missing on every provisioner run and fails the operator verifier. Proven with executables created from the real profile and TOOL_EXECUTABLES: every main.installed() probe reports current, but the extracted production loops report missing_tools=shuck and 'FAIL: shuck installed for'. The shared desktop checks have the same mapping drift.
- **Recommendation:** Make provisioning and verification consume the canonical tool-to-launcher mapping. Select installation by tool ID and check all required launcher names. Add a disposable-filesystem regression for the real server profile with shellcheck present and no shuck executable, plus the lz/gluon mappings. Complete profiles must report no missing tools, and removing any required launcher must still fail.
- **Fix with:** `single-source-of-truth`
- **Effort:** M


### USR-63 · P2 · sync accepts Python interpreters that cannot import its executor

- **Area:** Bootstrap
- **Where:** `sync:24`, `sync:26`, `sync:63`, `tools/sync/main.py:17`, `tools/sync/installer.py:37`, `tools/sync/pi_release.py:14`
- **Problem:** choose_python checks only sqlite3, ssl and subprocess, then execs main.py; its diagnostic advertises Python 3.9+. main imports installer, which eagerly imports pi_release and typing.TypeGuard, an API introduced in Python 3.10. A 3.9 interpreter can pass selection and fail before even plan/list execute, without trying another interpreter. Source evidence is confirmed by the Python 3.10 TypeGuard release notes. A bounded capability probe ran the actual launcher check successfully, removed TypeGuard from the process-local typing module, and reproduced the executor ImportError. Native Python 3.9 execution is unproven because that interpreter is unavailable here.
- **Recommendation:** Preserve the advertised standard-library-only compatibility by keeping annotation-only TypeGuard imports behind TYPE_CHECKING, and have interpreter selection validate executor import requirements before committing to a candidate. If the supported floor is deliberately raised instead, align the selector and diagnostic in the same change. Cover an incompatible first interpreter with a compatible fallback and a no-compatible-interpreter failure; confirm the chosen minimum on a native interpreter.
- **Fix with:** `os-boundaries`
- **Effort:** S
