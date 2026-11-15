Prefix: USR
Next: 76
















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


### USR-76 · P2 · pi-subagent-bridge treats directory scopes without a trailing slash as single files

- **Area:** pi-subagent-bridge
- **Where:** `tools/pi-subagent-bridge/src/git.ts` (`outside`), `src/scope.ts` (writable_paths validation)
- **Problem:** On 2026-11-15, four Asterinas kernel workers got `writable_paths` such as `kernel` and `test/initramfs/src/regression`. `outside()` treats an entry as a directory only when it ends in `/`, so every file the workers changed under those directories was reported out of scope. `resume` then refused with `Cannot resume changed HEAD or out-of-scope work`. Admission accepted the scope without warning.
- **Recommendation:** At admission, reject or normalize an entry that names an existing directory without the trailing slash, or match an entry as a path prefix at a `/` boundary.
- **Fix with:** A scope test where `kernel` admits `kernel/core/x.rs`, or where admission rejects the ambiguous entry with a message naming it
- **Effort:** S

### USR-77 · P2 · A finished incomplete or blocked session keeps its worktree locked after cancel

- **Area:** pi-subagent-bridge
- **Where:** `tools/pi-subagent-bridge/src/` (active-worker check in `start`, `cancel`)
- **Problem:** On 2026-11-15, three sessions ended with `ACCEPTANCE: not met` on legitimate stop conditions, and one stopped on a provider usage limit. Each left its worktree clean. `start` with a corrected scope in the same worktree failed with `Worktree already has active worker <id>; inspect it before starting another`, and `cancel` did not release the worktree (`interrupted: false`). The only workaround was a new worktree per retry.
- **Recommendation:** Treat a session whose process has exited and whose state is incomplete or finished as inactive for `start`, or make `cancel` mark such a session released once the worktree is verified clean.
- **Fix with:** A test that starts, lets the worker finish incomplete with a clean worktree, and then admits a new session in the same worktree
- **Effort:** S

### USR-75 · P3 · clang plus mold host links intermittently segfault and leave truncated artifacts

- **Area:** rust toolchain
- **Where:** dotfiles cargo config (linker clang, -B/usr/local/libexec/mold); Linux host, clang 23.1.3, mold 3.0.0
- **Problem:** On 2026-11-15 several XSH cargo test builds failed with linking with clang failed: signal 11 (SIGSEGV), with 48 GiB free and under heavy unrelated host load; a retry usually succeeds, but one crash left an 18 KiB build_script_build that cargo treated as fresh, so every later build failed until the target directory was deleted.
- **Recommendation:** Capture a crashing link (RUSTC_LOG or -Clink-arg=-v plus a core dump) to tell a mold crash from a clang driver crash, then report upstream or pin a mold release; meanwhile document deleting the target directory after a crashed link.
- **Fix with:** A reproduced crash with a core or backtrace and the mold/clang versions
- **Effort:** M

