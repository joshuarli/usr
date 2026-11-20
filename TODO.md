Prefix: USR
Next: 95

### USR-83 · P2 · running sessions on two hosts cannot reach each other over intercom

- **Area:** Delegation
- **Where:** launcher `intercom-tailnet` (docs/intercom-tailnet.md), pi-build `broker/tailnet-admin.js`, the Claude/Codex intercom MCP adapters (`claude-intercom-mcp`), `intercom_list` scope handling
- **Problem:** On 2026-11-17 a Claude Code session on the Mac had to coordinate with a Claude Code session on threadripper (the one in ~/repos/laputa-systems/xsh) before using that host for a Chromium build. `intercom_list` showed only same-machine sessions. Neither host runs a hub. Neither session was enrolled or launched under `intercom-tailnet run`, so neither can be reached without restarting it. On threadripper over SSH, `intercom-tailnet doctor` fails with `Node.js is missing`, because Node lives under ~/.local/share/nodejs and is not on a non-login PATH. Cross-host use needs four manual steps before any message flows: start a hub, enroll each session, transfer each credential, and relaunch the session through the launcher. In practice agents cannot coordinate across hosts and fall back to asking the owner to relay.
- **Recommendation:** Keep the trust model: enrolled, tailnet-only, credential per host. Remove the per-session ceremony. (1) Run the hub on one always-on host under its existing supervisor, from one documented command. (2) Enroll once per host, not per session, storing the credential at a fixed private path. (3) Have the normal claude/codex/pi launchers join the hub automatically whenever that host credential exists, so every ordinary session is reachable without relaunching through `intercom-tailnet run`. (4) Give `intercom_list` a fleet scope that shows remote sessions by host. (5) Make `intercom-tailnet` find the pinned Node the same way the other usr tools do, so `doctor` works over non-login SSH. Acceptance: two ordinary sessions started normally on the Mac and on threadripper can `intercom_list` each other and exchange `intercom_ask`.
- **Fix with:** none
- **Effort:** M

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

### USR-82 · P3 · todo cannot read backlogs whose tickets carry extra fields

- **Area:** Tooling
- **Where:** `tools/todo/src/todo.py` (`FIELD`, `NAMES`, `parse`)
- **Problem:** `todo list`, `todo add` and `todo check` fail on laputa-systems/xsh `TODO.md` with `todo: XSH-1: malformed ticket fields`. Its tickets add `- **Acceptance:**`, `- **Progress:**` and `- **Coordination:**` fields, and some put several fields on one line; `FIELD` matches only the seven schema names, so the reconstructed field block differs from the file. Agents working in that repository must then edit the backlog by hand, which the todo skill forbids, and cannot allocate IDs safely.
- **Recommendation:** Accept additional `- **Name:** value` fields (preserving their order and text on round-trip) while still requiring the seven schema fields, or report the first unknown field name and line instead of `malformed ticket fields` so the backlog can be normalized. Acceptance: `todo check` from a laputa-systems/xsh checkout at master either passes or names the exact offending field and line.
- **Fix with:** none
- **Effort:** S

### USR-84 · P3 · bridge MCP worker_start rejects a scope that the client sends as a JSON string

- **Area:** Delegation
- **Where:** tools/pi-subagent-bridge/src/cli.ts --bridge-dispatch (worker_start argument validation)
- **Problem:** From Claude Code, worker_start with a well-formed scope object failed with `pi-subagent-bridge: Error: scope must be an object`; the dispatch log shows the scope arrived as a JSON-encoded string. The same scope sent as an object through `cli.ts --bridge-dispatch` was admitted. Every Claude Code delegation through MCP hits this, forcing a hand-built CLI dispatch.
- **Recommendation:** In worker_start (and other tools with object parameters), accept a string argument that parses to an object of the declared schema, then validate as today; add a test that dispatches the stringified form.
- **Fix with:** none
- **Effort:** S

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

### USR-94 · P3 · Make perf-gate-ready catch bursty load from short-lived processes

- **Area:** perf-gate-ready
- **Where:** `dotfiles/base/.local/bin/perf-gate-ready`
- **Problem:** On 2026-11-20 on the Laputa build host (32 cores), another session's kernel build ran bursts of `cc1` processes that each live under a second. `perf-gate-ready` checks load per core (default 0.7) and hot process trees (>= 100% CPU) at a few instants, so it reported ready before and after Laputa's `root-compose` benchmark while that workload's five rounds took 4.07, 3.15, 3.20, 1.70 and 1.68 s. The bench reported `inconclusive: spread` rather than a false verdict, but the gate's readiness did not reflect the contention. A 15-minute load average of 6.95 was visible at the same time.
- **Recommendation:** Sample /proc/stat over the check window (for example busy fraction across all CPUs over 1 to 2 s), and fail when non-idle CPU time from processes outside the caller's tree exceeds a threshold, in addition to the instantaneous hot-tree check. Acceptance: a background loop starting ten 0.3 s compiles per second on other cores makes `perf-gate-ready` exit nonzero, and an idle host still passes.
- **Fix with:** benchmark-checklist
- **Effort:** S

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

