Prefix: USR
Next: 56



### USR-50 · P1 · Muse fallback workers fail because their workspace is untrusted

- **Area:** Delegation
- **Where:** `pi-build` `sources/pi-muse-subscription/src/home.ts` (`writeHostConfig`), `src/host.ts:160-174`, the pinned release archives
- **Problem:** Every Muse-backed bridge worker fails at startup with `invalid run configuration: unknown tool mcp__pi__*`. The selector is not the fault: Muse Code 1.4.15 loads MCP servers only in a trusted workspace. pi-muse-subscription gives each host a private `XDG_CONFIG_HOME` and links in only the user's `auth.json`. With no `trust.json` there, the worker's cwd (a bridge worktree) is untrusted, the `pi` MCP server never loads, and Muse treats its tool selector as unknown. Reproduced 2026-11-12 with a stub `pi` stdio server: in an untrusted cwd, `mcp__pi__*` and `mcp__pi__read` are both rejected. With a private `trust.json` that trusts the cwd, the same settings run, though Muse still reports `child tool 'mcp__pi__*' is unavailable` for agent delegation. A worker cut off by a usage limit after making edits also stays leased as `blocked_partial_work`, and `worker_cancel` cannot release it.
- **Recommendation:** Upstream in jkeskikangas/pi-muse-subscription, have `writeHostConfig` also write a private `muse/trust.json` that marks the host's `spec.cwd` as trusted. Do not link the user's own trust file, so no other projects are trusted. Then advance the source SHA in `pi-build`, publish a new release, and bump the `usr` pin with `/pi-update`. The source snapshot is hash-pinned to upstream, so an unrecorded local edit fails `tools/vendor.py check`; a deliberate local change belongs in `pi-build` `patches/`. Add a bridge smoke test that runs one real Muse turn through the `pi` MCP server, and have `worker_model_check` report the Muse version it was qualified against. Let the parent release a `blocked_partial_work` lease once it has preserved the work.
- **Fix with:** `root-cause`
- **Effort:** S

### USR-38 · P2 · Complete companion intercom adapters and supervisor consultation

- **Area:** Architecture
- **Where:** `tools/pi-subagent-bridge/src/sdk-worker.ts:156`, `tools/sync/pi_offline.py` (`configure_intercom`), `pi-build` `sources/upstreams.json`
- **Problem:** Interactive Pi has a local intercom adapter, but Claude/Codex/OpenCode companion adapters remain absent. Scoped SDK children deliberately load only subagents and the optional Muse provider, so they expose no `contact_supervisor` integration. The offline CLI/SDK packaging is delivered; the remaining gap is communication across harnesses and bounded child-supervisor consultation. Rechecked the SDK loader, source inventory, and local broker defaults without live provider calls.
- **Recommendation:** Package compatible companion adapters and core protocol revisions with upstream commit SHAs. `pi-build` owns those inputs and artifacts; `usr` retains harness registration and the first-party bridge. Register the required hooks/wrappers and verify cross-harness send/ask/reply plus bounded consultation as separate feature work. Preserve typed tier restrictions, worktree ownership, acceptance proof, explicit send authorization, and disabled unsolicited wakeups. Moving the existing runtime does not complete this ticket or authorize intercom in scoped SDK children.
- **Fix with:** `pi-update`
- **Effort:** L
