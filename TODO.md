Prefix: USR
Next: 51



### USR-43 · P2 · Stale-branch cleanup can delete a newly advanced branch

- **Area:** Data
- **Where:** `tools/close-stale-prs/src/close_stale_prs.py:214`, `tools/close-stale-prs/src/close_stale_prs.py:325`, `tools/close-stale-prs/src/close_stale_prs.py:374`, `tools/close-stale-prs/src/close_stale_prs.py:415`
- **Problem:** Cleanup snapshots commit ages and PR state, then deletes by branch name without retaining or comparing the observed tip OID. Another writer can advance an eligible old branch before deletion, and the command deletes the new tip despite its commit being newer than the cutoff. A transport fixture ran the real CLI eligibility and deletion path, advanced the simulated ref after the GraphQL response, and observed an unconditional DELETE of the new unmerged tip with exit 0. No live remote deletion was performed.
- **Recommendation:** Capture candidate tip OIDs and use deletion with an expected-tip condition. Refuse changed refs and report them for a later run. A separate read followed by unconditional deletion still races. Preserve dry-run behavior and the protected/default/open-PR exclusions.
- **Fix with:** `durable-state`
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
- **Where:** `tools/pi-subagent-bridge/src/sdk-worker.ts:156`, `tools/sync/pi_offline.py` (`configure_intercom`), `pi-build` `sources/upstreams.json`
- **Problem:** Interactive Pi has a local intercom adapter, but Claude/Codex/OpenCode companion adapters remain absent. Scoped SDK children deliberately load only subagents and the optional Muse provider, so they expose no `contact_supervisor` integration. The offline CLI/SDK packaging is delivered; the remaining gap is communication across harnesses and bounded child-supervisor consultation. Rechecked the SDK loader, source inventory, and local broker defaults without live provider calls.
- **Recommendation:** Package compatible companion adapters and core protocol revisions with upstream commit SHAs. `pi-build` owns those inputs and artifacts; `usr` retains harness registration and the first-party bridge. Register the required hooks/wrappers and verify cross-harness send/ask/reply plus bounded consultation as separate feature work. Preserve typed tier restrictions, worktree ownership, acceptance proof, explicit send authorization, and disabled unsolicited wakeups. Moving the existing runtime does not complete this ticket or authorize intercom in scoped SDK children.
- **Fix with:** `pi-update`
- **Effort:** L

### USR-32 · P3 · Concurrent campaign allowances can overwrite each other

- **Area:** Concurrency
- **Where:** `dotfiles/base/.local/bin/codex-campaign-closeout.py:132`, `dotfiles/base/.local/bin/codex-campaign-closeout.py:171`, `dotfiles/base/.local/bin/codex-campaign-closeout.py:252`
- **Problem:** Concurrent allow commands load the same allowed dictionary, add different worktrees, then replace the state file without a lock or generation check. A two-process fixture using the real `allow` implementation and real Git worktrees synchronized both calls after `load_state`: both reported success, but only one allowance survived. The Stop hook can later block a worktree reported as allowed. Atomic file replacement protects syntax, not the read-modify-write transaction.
- **Recommendation:** Serialize the complete load-modify-save transaction or use a compare-and-retry revision. Preserve state validation and add the two-process disjoint-allowance regression.
- **Fix with:** `durable-state`
- **Effort:** S

### USR-50 · P1 · Muse fallback workers fail because their workspace is untrusted

- **Area:** Delegation
- **Where:** `pi-build` `sources/pi-muse-subscription/src/home.ts` (`writeHostConfig`), `src/host.ts:160-174`, the pinned release archives
- **Problem:** Every Muse-backed bridge worker fails at startup with `invalid run configuration: unknown tool mcp__pi__*`. The selector is not the fault: Muse Code 1.4.15 loads MCP servers only in a trusted workspace. pi-muse-subscription gives each host a private `XDG_CONFIG_HOME` and links in only the user's `auth.json`. With no `trust.json` there, the worker's cwd (a bridge worktree) is untrusted, the `pi` MCP server never loads, and Muse treats its tool selector as unknown. Reproduced 2026-11-12 with a stub `pi` stdio server: in an untrusted cwd, `mcp__pi__*` and `mcp__pi__read` are both rejected. With a private `trust.json` that trusts the cwd, the same settings run, though Muse still reports `child tool 'mcp__pi__*' is unavailable` for agent delegation. A worker cut off by a usage limit after making edits also stays leased as `blocked_partial_work`, and `worker_cancel` cannot release it.
- **Recommendation:** Upstream in jkeskikangas/pi-muse-subscription, have `writeHostConfig` also write a private `muse/trust.json` that marks the host's `spec.cwd` as trusted. Do not link the user's own trust file, so no other projects are trusted. Then advance the source SHA in `pi-build`, publish a new release, and bump the `usr` pin with `/pi-update`. The source snapshot is hash-pinned to upstream, so an unrecorded local edit fails `tools/vendor.py check`; a deliberate local change belongs in `pi-build` `patches/`. Add a bridge smoke test that runs one real Muse turn through the `pi` MCP server, and have `worker_model_check` report the Muse version it was qualified against. Let the parent release a `blocked_partial_work` lease once it has preserved the work.
- **Fix with:** `root-cause`
- **Effort:** S
