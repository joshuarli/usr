Prefix: USR
Next: 81
















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


### USR-80 · P3 · Bridge snapshots omit the admitting parent's explicit identity

- **Area:** Delegation
- **Where:** tools/pi-subagent-bridge/src/session.ts, inspect.ts, owner.ts; agentctl ACTL-28
- **Problem:** At installed usr 6a203c459fe32dd82b75c4d7efd6d45f8da11fef, read-only campaign snapshots and owner_protocol 1 carry job and owner identities but no admitting parent session identity. Agentctl cannot link delegated jobs to their coordinator without guessing from worktrees or process trees.
- **Recommendation:** Accept an optional explicit admitting-parent identity at admission, persist it in the versioned session record, and expose it unchanged in read-only snapshots and owner status. Keep absent legacy values unknown. Prove round-trip identity, legacy absence and no guessed lineage with fixture tests. Preserve routing, leases, retries and acceptance in usr.
- **Fix with:** durable-state
- **Effort:** M

