Prefix: USR
Next: 80
















### USR-78 · P2 · long-lived bridge MCP model checks fail after policy updates

- **Area:** Delegation
- **Where:** tools/pi-subagent-bridge/src/cli.ts (MCP mode), src/policy.ts, src/tier-policy.ts
- **Problem:** On macOS 27.2, repeated worker_model_check requests for a clean mechanic worktree fail with SyntaxError: tier-policy.ts does not provide an export named DEVIN_TIER_MODELS. The same source-linked installation at ff3059803c7e2615e29e5ee1a3b292764496ddc2 succeeds through a fresh pi-subagent-bridge model-check CWD mechanic process and reports available providers. Ownership is verified as joshuarli/usr by repomod which.py with source-link evidence. Current policy.ts imports and tier-policy.ts exports agree, so stale long-lived MCP module state is suspected but unproven. MCP admission was unavailable during the bctl Helium release cleanup; the fresh CLI is a supported workaround.
- **Recommendation:** Reproduce a policy update with a running MCP server and compare the same read-only model check through MCP and a fresh CLI. Establish whether server module caching or deployed module mismatch causes the import failure, then make policy rollout consistent or return an actionable reload instruction. Regression acceptance: both interfaces return the same admitted pins after an update without starting a worker or throwing a missing-export SyntaxError.
- **Fix with:** root-cause
- **Effort:** M

### USR-79 · P2 · pi-subagent-bridge cancel never signals a CLI-started codex worker

- **Area:** pi-subagent-bridge
- **Where:** tools/pi-subagent-bridge (cancel)
- **Problem:** On 2026-11-15, `pi-subagent-bridge cancel <worktree> <session>` on a codex worker started with the CLI `start` returned interrupted:false twice, with the note "Never signal a Command Code PID left by an earlier MCP process", while inspect showed execution_state running and pid 49676, a live `codex exec` whose cwd was that worktree. The parent had to SIGINT/SIGTERM it by hand.
- **Recommendation:** Make cancel signal a worker whose recorded PID identity (start time, command, cwd) still matches, whatever started it, and add a test that cancels a CLI-started worker.
- **Fix with:** root-cause
- **Effort:** S

### USR-73 · P3 · The refactor-web-ui skill has only been applied to agentctl

- **Area:** Skills
- **Where:** dotfiles/base/.agents/skills/refactor-web-ui/SKILL.md; docs/CAMPAIGN-AGENTCTL-WEB-UI.md: Transfer after agentctl
- **Problem:** The skill was exercised and sharpened on one product only. Its rules have not been tested against a dashboard (stats), a developer tool with canvas rendering (stuff), or a reading/research product (discover), so overfit rules cannot yet be told apart from transferable ones.
- **Recommendation:** On separate requests, apply the skill to stats (with refactor-dashboard-ui owning metrics and trends), stuff (keep canvas rendering and its performance invariants), and discover (evidence and provenance hierarchy, mobile reading). Follow the campaign's Transfer section, and after the second product delete or move rules that turned out to be agentctl-specific.
- **Fix with:** none
- **Effort:** L


### USR-74 · P3 · Designed UIs lack the required make preview and shared golden dataset

- **Area:** Skills
- **Where:** refactor-web-ui skill: Preview and goldens; repos discover, niceforge, laputa-ui-dashboard, stats
- **Problem:** refactor-web-ui now requires every designed UI to ship `make preview` on one canonical mock dataset that its integration goldens also use. On 2026-11-15 discover, niceforge and laputa-ui-dashboard have no `make preview`; stats has one, but whether its preview data is the same dataset its tests use is unverified. agentctl conforms; stuff gains it in its redesign.
- **Recommendation:** Per repo, on its own request: extract the fixture its browser tests seed into one dataset module, serve it with `make preview`, and add a semantic golden over the same dataset. For stats, check that preview and tests share one dataset before changing anything.
- **Fix with:** none
- **Effort:** M


### USR-75 · P3 · clang plus mold host links intermittently segfault and leave truncated artifacts

- **Area:** rust toolchain
- **Where:** dotfiles cargo config (linker clang, -B/usr/local/libexec/mold); Linux host, clang 23.1.3, mold 3.0.0
- **Problem:** On 2026-11-15 several XSH cargo test builds failed with linking with clang failed: signal 11 (SIGSEGV), with 48 GiB free and under heavy unrelated host load; a retry usually succeeds, but one crash left an 18 KiB build_script_build that cargo treated as fresh, so every later build failed until the target directory was deleted.
- **Recommendation:** Capture a crashing link (RUSTC_LOG or -Clink-arg=-v plus a core dump) to tell a mold crash from a clang driver crash, then report upstream or pin a mold release; meanwhile document deleting the target directory after a crashed link.
- **Fix with:** A reproduced crash with a core or backtrace and the mold/clang versions
- **Effort:** M

