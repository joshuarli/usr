Prefix: USR
Next: 56



### USR-38 · P2 · Complete companion intercom adapters and supervisor consultation

- **Area:** Architecture
- **Where:** `tools/pi-subagent-bridge/src/sdk-worker.ts:156`, `tools/sync/pi_offline.py` (`configure_intercom`), `pi-build` `sources/upstreams.json`
- **Problem:** Interactive Pi has a local intercom adapter, but Claude/Codex/OpenCode companion adapters remain absent. Scoped SDK children deliberately load only subagents and the optional Muse provider, so they expose no `contact_supervisor` integration. The offline CLI/SDK packaging is delivered; the remaining gap is communication across harnesses and bounded child-supervisor consultation. Rechecked the SDK loader, source inventory, and local broker defaults without live provider calls.
- **Recommendation:** Package compatible companion adapters and core protocol revisions with upstream commit SHAs. `pi-build` owns those inputs and artifacts; `usr` retains harness registration and the first-party bridge. Register the required hooks/wrappers and verify cross-harness send/ask/reply plus bounded consultation as separate feature work. Preserve typed tier restrictions, worktree ownership, acceptance proof, explicit send authorization, and disabled unsolicited wakeups. Moving the existing runtime does not complete this ticket or authorize intercom in scoped SDK children.
- **Fix with:** `pi-update`
- **Effort:** L
