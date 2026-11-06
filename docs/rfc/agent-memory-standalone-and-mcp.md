# Plan: extract agent-memory into an independently deployable Cloudflare project

Status: **Gates A, B, and C implemented; Gate D (remote MCP) not started.** The standalone repository is `~/d/agent-memory`, pushed to the public `github.com/joshuarli/agent-memory`. Its `chore: import agent-memory from usr@b16294d unchanged` commit has the same tree as `b16294d:agent-memory`. The host launchers and both LaunchAgents run the package installed in `~/d/agent-memory/.venv`, and `usr` no longer carries the source. The Worker is deployed only by `make deploy` in the new repository (no Workers Builds trigger exists); the first such deploy replaced version `1f2964c0-c11e-4a1a-9241-6f7858775782`, the rollback target, with `290b2cb2-6f23-48bf-a0a2-14b41d2655ba`. The remote MCP adapter needs separate authorization.

## Summary

Make `agent-memory` a standalone repository, conventionally checked out at `~/d/agent-memory`, owning its Python package, Cloudflare Worker, migrations, tests, deployment commands, and operational documentation. Keep `usr` as a consumer: command shims, native-harness integration, host scheduling, and the promotion target. Preserve local-first operation and the existing production service.

**An independent project does not require new production resources.** The source already configures a dedicated Worker, D1 database, and R2 bucket. Transfer responsibility for building and deploying that service to the new repository; do not create a second database, copy production objects, or rename the Worker during extraction.

There are three separately verifiable deliverables:

1. **Standalone source and installable package:** behavior-preserving extraction, self-contained checks, and a prepared `usr` integration change.
2. **Operational cutover:** explicitly authorized installation/host activation and deployment ownership transfer, using the same state and Cloudflare resource identities.
3. **Remote MCP:** a later read-only HTTP adapter inside the existing TypeScript Worker. Local Python stdio MCP is optional, not a prerequisite or a substitute for the Cloudflare endpoint.

Do not combine these with a storage redesign, Python-to-TypeScript rewrite, framework migration, or new agent runtime.

## Motivation and verified baseline

The original plan was a useful file-move inventory, but left the deployment boundary implicit, relied too heavily on source-checkout imports, suggested discarding staging work, and treated local stdio MCP as the next Cloudflare interface. This revision addresses those gaps.

Repository facts checked at `8fb804cd19f5f99f372410a5888f581e84b78f44`:

| Area | Existing behavior to preserve |
| --- | --- |
| Python | `agent-memory/pyproject.toml` declares Python `>=3.15` and no runtime dependencies, but has no build backend or console entrypoints. |
| Worker | `agent-memory/cloudflare/cloudflare.config.ts` names `usr-memories`, serves `memories.17166969.xyz`, binds `DB` and `BUCKET`, disables `workersDev` and preview URLs, disables response caching, and sends tail events to `stats-observe`. |
| Toolchain | The Worker uses `cf`, `cloudflare.config.ts`, a custom Build Output script, `tsrs`, and Miniflare-backed tests. Do not replace this with Wrangler/Vite/another emulator merely to move it. |
| Deployment | The root `Makefile` owns deploy, migration, provisioning, smoke, and performance targets. `cloudflare/scripts/deploy-gate.sh` also derives paths from the old layout. These are extraction work, not optional polish. |
| Authorization | `cloudflare/src/auth.ts` distinguishes readers from origin-bound collectors. `routes/memories.ts` enforces collector scope before calling database helpers. Reusing a database helper alone does not reuse that authorization. |
| Cost fixes | `agent-memory/docs/cost.md` records R2 snapshot membership pages, delta-only generation-object references, removal of `last_referenced_at`, snapshot retry backoff, and an hourly mirror schedule. Preserve these changes, including migration history through the source revision. |
| Promotion | `Learner._learning_repository()` validates the intended `usr` target using Git and the tracked skill layout. That check is already independent of the package's location; fix defaults without weakening the target check. |

The earlier report that `~/d/agent-memory` was partially populated, had no `.git`, and that a stray `~/usr/tools/agent-memory/src` existed is **historical host information, not a fresh observation**. Reinspect before acting. Likewise, a tracked plist or cost report does not prove which jobs are currently loaded or which revision is deployed.

Relevant documents: `~/d/agent-memory/README.md`, `~/d/agent-memory/docs/install.md`, `~/d/agent-memory/docs/operations.md`, `~/d/agent-memory/docs/cost.md`, [development checks](../development.md), and [repository rules](../../AGENTS.md).

## Design

### 1. Boundaries and non-negotiable invariants

```text
usr                                      agent-memory
  command shims -----------------------> installed Python package
  harness hooks / host schedules           local SQLite + FTS5
  skill-usage consumer                     transcript / archive / learning core
  reviewed promotion target <------------- explicit, existing promotion workflow
                                                |
                                          existing sync protocol
                                                |
                                      TypeScript Cloudflare Worker
                                        existing REST / HTML adapters
                                        later: /mcp read-only adapter
                                                |
                                          existing D1 + R2
```

- Local transcript capture, indexing, verification, review, crypto, and recovery remain local. Preserve `~/.agent-sessions`, its identity, grants, locks, configuration, keys, cursors, and pending work. Do not reinitialize state, recapture the archive, or resync everything to prove a directory move.
- Preserve command names, argument semantics, caller working directory, exit status, stdin/stdout behavior, native-harness behavior, and opt-in learning authority. Do not enable a disabled learner or paused mirror.
- Preserve protocol versions, session/origin identities, object keys and digests, encryption format, tombstones, retention, and existing D1 migrations. The extraction itself introduces **no data/schema migration**.
- Keep Python runtime dependencies empty and shell POSIX-compatible. Build/test dependencies are explicit and separate. No new daemon, vector database, agent framework, Durable Object, queue, or public unauthenticated data endpoint.
- `stats-observe` remains an explicit production telemetry integration, not a dependency on a sibling source checkout or a requirement for offline tests. Do not add another telemetry framework.
- File edits are not automatically harmless to the host: installed commands may be symlinks into `~/usr`. Inspect that relationship before changing launchers or removing their implementation.
- This plan authorizes no host activation, `sync` apply, `launchctl` action, credential change, resource creation, package publication, remote repository publication, or production deployment. Prepare changes and tests without those effects; cross each live gate only when separately authorized.
- Follow `usr` conventions: scratch under `.work/`, no formatters, focused Conventional Commits, and no interference with unrelated work or processes.

### 2. Destination layout and ownership

```text
agent-memory/
  AGENTS.md
  README.md
  pyproject.toml
  .gitignore
  Makefile                         # project-owned checks and operational targets
  src/agent_memory/
  tests/                           # includes shared protocol fixtures
  eval/
  docs/                            # architecture, install, operations, cost
  cloudflare/
    package.json
    package-lock.json
    cloudflare.config.ts
    tsconfig.json
    migrations/
    src/
    test/
    scripts/
    bench/
    perf.sh
    dev-age.sh
```

Copy the relevant lint/type-check/test settings into the standalone project rather than depending on parent-directory discovery. Account for `.github/workflows`, `pytest.ini`, `ruff.toml`, and `ty.toml` where applicable. Do not copy unrelated dotfiles policy or tooling wholesale.

The new repository owns all memory-specific `Makefile` targets, including deployment gates, migration checks, provisioning safeguards, smoke probes, and benchmarks. Preserve unrelated `usr` targets such as `deploy-setup.sh`. `usr` checks retain integration coverage, not the entire memory test suite.

Use `~/d/agent-memory` as a documented checkout convention, never as an import-path requirement. A checkout under a different directory name, including one containing spaces, must build and test. Production configuration remains in `cloudflare/cloudflare.config.ts`; do not add a second competing configuration file.

### 3. Safe extraction and provenance

Before changes, record the source commit, tracked subtree, executable modes/symlinks, dirty files, existing destination contents, installed launcher targets, and relevant host-job state. Do not read secrets or transcript content into the migration report.

Export the tracked subtree from an exact source revision, for example with `git archive "$SOURCE_REV:agent-memory"`, into a new scratch directory. Do not use `git ls-files` followed by copying arbitrary working-tree bytes while claiming the result represents the commit. Preserve any intentional uncommitted source changes separately and reconcile them explicitly.

Create an unchanged import commit with the source repository, commit, and prefix recorded. Verify its paths, bytes, and modes against the source tree before packaging/path edits. This gives a reviewable baseline without rewriting `usr` history. History-preserving subtree extraction is optional; do not silently claim a snapshot import preserves all earlier ancestry.

Never discard/reset the reported destination scratch tree blindly. Compare it with the pinned source; preserve unique edits and local files in a named backup under `.work/` before replacing anything. If the destination has become a real repository, reconcile it instead of reinitializing it. Leave the unrelated stray `tools/agent-memory` directory untouched, while proving no new code relies on it.

Exclude generated environments, caches, runtime state, credentials, and production data. Ignore at least `.venv/`, `__pycache__/`, `*.pyc`, `.work/`, `node_modules/`, `.cloudflare/`, `.wrangler/`, `dist/`, and `*.egg-info/`. Audit tracked inputs for local configuration/secrets rather than assuming an ignore file removes them.

Keep the new repository private/unpublished until its intended remote and visibility are explicitly established. A local commit is not proof of remote recoverability; record where the extracted history is durably retained before removing the old tree.

### 4. Packaging and deterministic CLI execution

Add a minimal build backend with explicit `src` discovery and these console entrypoints, verifying the callable names against source:

| Command | Callable |
| --- | --- |
| `agent-learn` | `agent_memory.learning:main` |
| `agent-sessions` | `agent_memory.sessions_cli:main` |
| `agent-sessions-serve` | `agent_memory.serve:main` |

A small pinned build-only backend is sufficient; keep `dependencies = []` and Python `>=3.15`. Build both a wheel and source distribution, and verify their contents. Resolve interpreter/build tooling during explicit setup, not from a scheduled invocation.

**Runtime decision:** shims execute console scripts from an explicitly provisioned environment, without dependency resolution on every call. Use `AGENT_MEMORY_VENV` as an optional override, with the documented development default `~/d/agent-memory/.venv`. `uv` may provision/install that environment during setup; it is not mandatory in the runtime hot path. An editable install is convenient for development, but acceptance requires a non-editable wheel install too.

The three `usr` shims are small POSIX shell wrappers that validate the selected environment and `exec` its absolute entrypoint with `"$@"`. Do not change directory, resolve the same command back through `PATH`, insert `src` into `sys.path`, set `PYTHONPATH`, auto-install/download anything, or silently fall back to the old tree. Missing setup produces a specific stderr diagnostic and a nonzero exit. Document that virtual environments must be created at their final location, not copied between hosts or paths.

Fix package-location assumptions systematically:

- `learning.py` must not derive the promotion target or reviewer working directory from `__file__.parents[3]`. An explicit `--usr-root` wins when configuring a grant; ongoing operations honor the stored authorized target. Use `Path.home() / "usr"` only for the existing default when no target has been configured.
- Preserve `_learning_repository()`'s checks that the target is the intended tracked `usr` repository. Do not turn "package is location-independent" into "promotion may target any Git repository."
- CLI help currently constructs a checkout-relative README path with `parents[2]`. That is not a valid installed-wheel documentation contract. Use a stable documentation reference or packaged resource; do not print a nonexistent site-packages README path.
- Separate developer checkout assets, such as Worker build scripts, from installed runtime resources. Any runtime-required resource must be packaged and accessed explicitly. Audit subprocess commands and scheduler templates as well as Python imports.

### 5. The skill-usage boundary

`tools/skill-usage/src/skill_usage.py` imports `default_roots`, `is_source_name`, and `normalize` from `agent_memory.transcripts`, plus `Harness` from `agent_memory.types`. Keep that as a small, explicitly tested Python consumer contract for this extraction; do not duplicate the normalizer or invent a plugin API.

Remove its `parents[2]/agent-memory/src` insertion. Its `usr` launcher invokes the script using the same provisioned environment's Python with `-I`, so the installed `agent_memory` package is available without user-site or `PYTHONPATH` accidents. Preserve its CLI and selftest. Type checking must resolve the installed dependency too, not a hardcoded sibling source path.

Update every documented or scripted invocation that assumes the launcher is a Python file. In particular, `python3 -I dotfiles/base/.local/bin/skill-usage selftest` is not valid once that launcher is a shell shim. Test the actual launcher and the isolated underlying Python invocation separately.

### 6. Cloudflare ownership transfer, not resource migration

Preserve these production identities/configuration values from the reviewed source, and verify them against the actual account before a live deployment:

| Item | Extraction invariant |
| --- | --- |
| Worker | `usr-memories` |
| Custom domain | `memories.17166969.xyz` |
| D1 | Binding `DB`, name `usr-memories`, ID `9870c4da-3758-4f0c-ab6d-2372eb34009b` |
| R2 | Binding `BUCKET`, bucket `usr-memories`; preserve namespace/key format |
| Access | Existing application, team domain, audience, authorized readers, collector bindings, and disabled-collector state |
| Exposure | `workersDev: false`, `previewUrls: false`, no unauthenticated alternate origin |
| Compatibility | Existing date `2026-10-30` and `nodejs_compat`; no unrelated compatibility upgrade |
| Telemetry | `stats-observe` tail consumer, existing sampling and private-response cache policy |

Record the account identity, deployed Worker version, applied migration set, secret **names** and provisioning source, and deployment mechanism. Source inspection does not establish live values. Preserve deployed secrets and reader configuration without exporting them into Git or reports.

Move and fix **all** operational paths: `scripts/deploy-gate.sh`, `scripts/smoke-deployed.sh`, `scripts/provision.sh`, `scripts/config.mjs`, `scripts/build.mjs`, `perf.sh`, `dev-age.sh`, test helpers, Python mirror/eval subprocesses, and Makefile targets. Derive paths from the relevant script/project root, not a parent directory coincidentally named `agent-memory`. Test command execution from a different working directory.

Keep the existing `cf` Build Output flow. `scripts/build.mjs` currently records production mode; deployment and dry-run must request the matching mode. Pin the existing toolchain/lockfile during extraction. Build once, test that artifact, record its digest, and deploy the same prebuilt artifact; a later rebuild is not evidence for what was tested.

Separate safe local commands from live ones:

- Local checks, local migrations, and `cf deploy --prebuilt --dry-run --mode production` need no production credentials or writes.
- Production preflight/migration listing is explicitly remote and read-only. Applying production migrations, provisioning, and deployment are separate explicit commands/gates; no implicit provisioning or migration as a side effect of `test`, `sync`, or install.
- The extraction must have no pending new migration. Preserve numbered SQL files and migration bookkeeping; do not rerun historical destructive migrations or squash them during the move.
- The default migration workflow must not silently act on production. Distinguish local and production targets in help and tests; require explicit target/account/resource validation for production writes.

Inventory existing CI/Workers Builds/manual deploy paths before changing them. The new repository becomes the single deployment source; retire the old source's deploy trigger before enabling its replacement. Do not leave two independently advancing production deployers. CI runs without production secrets by default, uses pinned actions where applicable, and has no automatic production provisioning.

### 7. Data safety and cost invariants

This is a relocation, not a replay of the cost-remediation campaign. Carry the current fixes forward and add/retain executable regression gates:

- Snapshot membership stays in immutable R2 pages/manifests. A snapshot commit must not recreate a D1 row per retained object or touch every historical object merely to update a reference timestamp.
- Generation commits preserve delta-only membership and idempotent retries. Test a long session across several generations, not only one-shot ingestion.
- Learning changes do not force extra recovery snapshots. Preserve snapshot cadence, persisted retry backoff, and the configured hourly mirror interval; do not infer or reset whether the actual host job is enabled.
- A repeated no-change sync must not repeat generation/snapshot domain writes or object uploads. Necessary bounded bookkeeping, if any, is separately identified and measured rather than hidden in "zero-cost" claims.
- Test failure after object upload but before commit, retries after restart, interruption, duplicate delivery, overlapping invocations, tombstones/forget, recovery, and GC reachability/grace periods. No source relocation may change lock identity or permit concurrent writers that were previously excluded.
- Never use real archive reupload, a production synthetic load test, GC sweep, tombstone, or snapshot restore as an extraction smoke test.

Benchmark fixed synthetic fixtures before and after: no-op sync, one appended chunk to a long session, snapshot creation at increasing retained-object counts, duplicate commit, failed-commit retry, bounded search, and record inspection. Report D1 operations/rows, R2 operations/bytes, elapsed time, Worker CPU where measurable, response bytes, and total emitted bundle/module bytes. Entry-module size alone is not total deployment size.

Compare identical workloads and publish the observed delta; set numerical regression tolerances from repeated baseline runs, not invented universal millisecond or KB targets. Local measurements establish regressions, not exact billed usage. After an authorized cutover, use existing `stats` telemetry to compare equivalent workload windows. Keep content, query text, credentials, and encryption keys out of telemetry.

### 8. Remote MCP: the later, deliberately narrow phase

The Cloudflare MCP endpoint belongs in the existing **TypeScript Worker**, at `/mcp`, not in a Python process deployed to Workers. Keep REST and the CLI first-class. Do not introduce an MCP proxy Worker or new storage just to expose the same operations.

Use the official `@modelcontextprotocol/server` SDK's web-standard `createMcpHandler` and `McpServer` directly. Current official documentation supports this fetch-native shape without the Cloudflare Agents SDK, Hono, Express, or a Durable Object. Pin and verify the exact SDK release during implementation and test the protocol versions actually supported by the chosen clients. Do not copy an unverified version number or advertise compatibility merely because a handler builds.

Plain JSON Schema through `fromJsonSchema` can avoid an additional application schema-library dependency. This does **not** make the SDK dependency-free. Handwritten JSON-RPC is not the default: protocol/security maintenance would defeat the desired small adapter.

#### Shared operations and honest capability names

Extract the smallest authorized application operations from the existing REST paths. Both REST and MCP call the same TypeScript operation, with an authenticated principal and validated arguments. Do not loop back through HTTP to the Worker's own public endpoint, duplicate SQL/ranking, or create a generic service framework.

Collector-origin restrictions currently live in `routes/memories.ts`; move/reuse those checks at the shared operation boundary before adding another caller. An adapter that invokes `searchMemories()` or `readRecord()` directly with arbitrary origin parameters can bypass route-level scope. Tool listing and invocation both respect the caller's allowed capabilities; listing is not authorization.

Start only with operations the cloud service can truthfully provide:

| Proposed MCP tool | Existing capability / restriction |
| --- | --- |
| `memory_search` | Bounded, paginated search over cloud-synced learning records, preserving caller scope and filters. |
| `memory_inspect` | Read one authorized cloud record with its available sources/links; identity includes origin, record kind, and ID. |
| `server_status` | Sanitized service/protocol/sync information for that principal; not a remote shell, local doctor, or model probe. |

Do not call this full local `recall` parity. The Worker cannot inspect the caller's current Git worktree, run local source verification, or decrypt an archive whose keys remain local. Return explicit origin/provenance, sync/verification freshness when known, truncation/pagination information, and advisory/unverified status where current applicability is unproven. An origin's previously verified tier is not proof that a remote caller's checkout still satisfies it.

Do not promise session `search`/`recent`/`show` over encrypted raw transcripts without a separately designed server-readable projection and privacy decision. Do not upload decryption keys to make that promise work. Preserve the distinction between retained learning records and raw archive evidence.

Read-only means no implicit sync, indexing refresh, receipt write, review/model call, promotion, enablement, deployment, migration, or GC. Preserve abstention and "retrieved text is data, not instructions" semantics. Keep mutation/maintenance capabilities CLI-only in this phase.

Python and TypeScript remain separate runtime implementations with explicit protocol/fixture contracts; "shared core" does not mean pretending they share executable code. A future local stdio adapter may wrap the Python core for local verification/offline retrieval, but is deferred unless a real client needs it.

#### Authentication and isolation

Preserve existing Access validation and reader/collector distinctions. Validate identity before accessing data, never trust an identity/scope supplied in tool arguments, and never share request-specific principals or mutable MCP servers across requests.

The SDK handler does not authenticate callers or validate Host/Origin for the application. Mount it behind the existing authorization boundary plus explicit allowed-host/origin handling, bounded request/response sizes, cursor/query limits, sanitized errors, and private/no-store responses. Native clients may omit Origin; test that supported case rather than disabling checks for present origins.

Choose and test a real client's authentication flow. Existing Access service-token headers are not automatically interoperable with an OAuth-only MCP client; neither an Access login redirect nor a new SDK dependency supplies that integration. Do not repurpose an origin-bound collector credential as an all-origin reader or weaken Access to get a demonstration working. If the selected client requires OAuth, design/test its discovery, token validation, and principal mapping separately; public authentication metadata must not make tools/data public.

#### Build and compatibility gate

The current Worker build emits a module graph with `tsrs`; it is not proof that arbitrary npm runtime imports will be bundled. Adding the MCP SDK requires resolving/bundling its transitive graph for workerd and validating any emitted dynamic imports/validator modules. Use the smallest build-only adjustment necessary; do not replace the entire toolchain or add Node-only adapters by default.

Prove the actual deployment artifact starts in workerd, serves existing REST unchanged, and completes tool discovery/calls with an official SDK client and one selected real harness. Cover malformed messages, unsupported versions/methods, schema errors, unauthorized/disallowed-origin requests, bounded pagination, private response handling, and cross-principal concurrent requests. Pin any legacy compatibility that is actually tested; do not enable stateful sessions or persistent streaming machinery without a demonstrated requirement.

Record baseline versus MCP bundle size, startup behavior, request CPU, and query/operation counts, including REST paths that do not use MCP. A successful `tools/list` call in a Node mock is not completion.

## Execution and acceptance gates

### Gate A — baseline, extraction, and standalone source

1. Recheck the exact source revision and host/destination facts. Preserve unrelated edits, scratch work, and runtime state. Record live-linked launcher risks and current deploy ownership.
2. Produce the unchanged import/provenance commit, then separate packaging/path changes. Bring over operational commands and relevant check configuration, not just `src/`.
3. Make tests/eval/worker scripts project-root-relative without depending on a checkout named `agent-memory`. Preserve shared fixtures and their semantics; do not blindly trust the earlier staging auto-rewrite.
4. Run the complete existing Python suite and inference-free eval selftests. Include `test_mirror_crypto.py` explicitly: the old root Makefile's eleven-suite list does not cover it. Discover newly added suites instead of freezing that historical count.
5. Run Worker check/lint/build/tests, protocol/adversarial/runtime suites, local migrations, and the prebuilt dry-run. Keep the existing Miniflare/workerd setup; no emulator replacement is required by this extraction.
6. Exercise SQLite/FTS5, D1, and R2 together with synthetic fixtures. Test a fresh database and a migrated fixture representing the supported existing schema. Mock only genuine external boundaries such as Access key retrieval/model calls; never use production bindings for offline tests. Block unexpected external network access.

**Pass:** the standalone checkout builds/tests with `usr` and other sibling repositories unavailable, no production credentials, and no source/runtime data mutation outside scratch. Report missing tooling or failed tests as blockers, not passes. Local simulation does not prove Cloudflare's live Access/domain configuration; that belongs to Gate C.

### Gate B — installed package and prepared usr integration

Build a non-editable wheel and install it into a fresh environment. Execute outside either checkout, with a scratch HOME/state directory, no `PYTHONPATH`, and isolated Python imports. Verify console entrypoints, imports, help/doc references, representative index/search/archive/recovery operations, and declared runtime resources. Run equivalent core fixtures against source and installed-package lanes; existing test `sys.path` helpers must not mask a broken wheel.

Prepare the `usr` change in a separate worktree when its normal checkout feeds live symlinks. Test the three launchers, `skill-usage selftest`, missing-environment diagnostics, arguments containing spaces, preserved cwd/stdin/exit behavior, and a minimal LaunchAgent-like environment. No network, package resolution, or installation may occur during these invocations.

Audit and update these consumer categories, using symbols/current contents rather than old line numbers:

| Consumer | Required treatment |
| --- | --- |
| `dotfiles/base/.local/bin/agent-{learn,sessions,sessions-serve}` | Thin installed-environment shims; no source-path imports. |
| `dotfiles/base/.local/bin/skill-usage`, `tools/skill-usage/` | Explicit installed dependency and corrected isolated/selftest commands. |
| `dotfiles/launchd/` and generated scheduler templates | Preserve labels, arguments, state/log paths, cadence, environment resolution, and enabled/disabled state. Fix cwd assumptions only. |
| Native harness hooks/configuration | Keep invoking the stable CLI contract; do not relocate user-specific orchestration into the library. |
| `sync`, `Makefile`, `.github/workflows`, Python/lint/type configs | Remove memory-owned suite/deploy coupling; retain focused integration checks and unrelated jobs/targets. |
| `AGENTS.md`, `SKILLS.md`, `TODO.md`, `audit.md`, `docs/development.md`, `docs/agent-setup.md`, `docs/sync.md`, `docs/pi.md` | Replace current instructions with install/consumer contracts and destination documentation. |
| `.agents/skills/audit-skills/SKILL.md`, campaign docs | Repair actionable stale paths, including the old `tools/agent-memory/eval` reference; label historical paths rather than rewriting history. |

Check shell syntax, plist syntax where available, scoped lint/type checks, and the relevant `mdtool` links/refs/router checks. Audit tracked text for old source paths, parent traversals, source imports, test commands, and deployment references. Classify intentional historical mentions explicitly; a broad grep match is not automatically a defect.

**Pass:** both projects' source changes and install artifacts are ready, and scratch integration works. This does not mean the live host has switched. Do not delete the live source tree or land live-linked launcher changes before a working replacement environment exists and activation is authorized.

### Gate C — authorized host and deployment cutover

Installation and Cloudflare deployment are independent actions; request/record the required authorization for each, not a blanket permission inferred from this plan.

1. Preserve the previous package/build artifacts, `usr` revision, deployment version, and migration/resource fingerprint. Establish how to restore command execution before changing it.
2. Provision/test the replacement local environment at its final path. Switch host shims/integration without changing state or grants. Existing running jobs must finish safely or be paused through an authorized procedure; do not start duplicate collectors. Preserve the prior loaded/paused state when handling jobs.
3. Verify actual CLI/skill-usage operation from the host's normal and scheduled environments. Only then remove the obsolete implementation from `usr`. Retain durable extraction provenance and rollback commits. Never remove or reset `~/.agent-sessions`.
4. Transfer deployment ownership. Verify account, existing resource IDs, Access settings, no pending new migration, and the exact prebuilt artifact. A Worker update is permitted here only after explicit deploy authorization; no resource rename/recreation or production dataset copy.
5. Perform authenticated, bounded read-only smoke checks and unauthorized/cross-origin-scope rejection checks. Compare schema/protocol identities and available counts/digests without logging private content. Confirm `stats-observe` still receives expected telemetry and existing clients continue working.
6. Report actual post-cutover evidence from ordinary traffic/sync when available. Do not manufacture a successful recurring-job observation or claim unattended monitoring that was not set up. Leave any unobserved operational acceptance item open.

**Pass:** the same production service is deployed from the new project, the intended host integrations use the new package, no duplicate deployment/scheduler owner remains, and rollback has been documented/tested at the applicable layer. If live actions are not authorized, stop with Gates A/B complete and Gate C pending; do not call the extraction operationally complete.

### Gate D — optional remote MCP implementation

Begin only after the extraction boundary is stable. Implement the thin Worker adapter and the security/build/client tests in section 8. Keep its changes and rollout independently revertible. Remote MCP completion requires a tested real client's authenticated calls against the intended endpoint; local stdio or a curl-only demonstration is not a substitute.

## Rollback

Treat code, installed runtime, and persistent data as different layers.

- **Before activation:** discard/revert only the prepared extraction/integration changes, retaining any unique user edits and the imported history. Neither host state nor production should have changed.
- **Host/package:** restore the previous `usr` shims/implementation and compatible runtime artifact. Reuse the existing state directory and locks; do not restore an old mutable SQLite copy over newer state. Restore the previous scheduler enabled/paused state only through an authorized action.
- **Worker:** redeploy/roll back to the recorded compatible Worker version/build while retaining the same bindings, domain, Access boundary, and storage. Verify existing clients and read-only smoke again. A repository revert is not a deployment rollback.
- **Data:** Worker rollback does not undo D1/R2 writes or migrations. This is why extraction introduces none. Any future schema/MCP change needs a separate compatibility/recovery plan; do not promise "revert the commit" after destructive schema changes.

Do not delete old recovery artifacts, credentials, or fallback source until the replacement and its rollback path have been accepted. Do not run provisioning, GC, or archive restore as a rollback shortcut.

## Alternatives considered

- **New Worker/D1/R2 names during extraction:** rejected. Separate repository/build ownership achieves the goal without a production data migration or auth/domain cutover.
- **`uv run --project` for every invocation:** unnecessary runtime resolution/startup behavior for hooks and scheduled jobs. Explicit setup plus direct installed entrypoints is simpler to reason about offline.
- **Hardcoded sibling `src` imports or fallback to the old tree:** rejected. They hide incomplete packaging and make isolation tests meaningless.
- **Move only the Worker:** rejected for this extraction. Its Python client, protocol fixtures, crypto/recovery tests, and cost invariants are one versioned system; `cloudflare/` is still independently buildable within it.
- **Local stdio MCP first:** not required for a Cloudflare-facing service. Retain it as an optional adapter for genuinely local capabilities, not a second mandatory server to maintain.
- **Agents SDK/Durable Objects or hand-rolled MCP:** neither is required for these stateless read operations. Start with the official fetch-native server package and measured overhead.

## Open inputs and decision

Architecture is fixed by this revision. Before execution, discover rather than guess: actual destination contents; new repository remote/visibility; installed symlinks and scheduler state; usable Python/build tooling; live deployment owner/version/account/configuration; and the first real MCP client's authentication requirements.

These inputs do not justify silently broadening scope. Preserve existing behavior, report unavailable evidence, and stop only the affected live gate. The implementation report must distinguish source changes, checks executed, blocked checks, installed/activated components, deployed artifacts, and still-deferred MCP work.

**Decision:** extract the local-first Python system and its existing Cloudflare subproject together; leave `usr` as an explicit consumer and promotion target; keep production identities/data unchanged; then add the smallest authorized, measured remote MCP adapter that the existing cloud data can honestly support.

External implementation references, checked 2026-11-05:

- [Cloudflare CLI project/build/deploy behavior](https://developers.cloudflare.com/cf/projects/) and [programmatic configuration](https://developers.cloudflare.com/cf/projects/cloudflare-config/): preserve the existing `cf` path and match prebuilt modes; missing resource identifiers can trigger provisioning.
- [Official MCP SDK web-standard serving](https://ts.sdk.modelcontextprotocol.io/v2/serving/web-standard) and [handler API](https://ts.sdk.modelcontextprotocol.io/v2/api/%40modelcontextprotocol/server/server/createMcpHandler.html): fetch-native handler, per-request construction, and application-owned authentication/Host/Origin checks.
- [Cloudflare Worker rollback semantics](https://developers.cloudflare.com/workers/versions-and-deployments/rollbacks/): rolling back Worker code does not roll back connected resource state.
