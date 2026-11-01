# Campaign: Cloudflare agent memories

Durable, encrypted, cross-machine mirror of the agent-memory archive, a D1 learning
projection with FTS5 search, and a private HTML browser at
`https://memories.17166969.xyz` — with measured performance as a release gate.

Implementation paths in this document are relative to `tools/agent-memory/` unless they
start with `docs/`, `dotfiles/`, or name a repository root file.

## Status

- **Goal:** every locally captured session and every local learning record reaches an
  encrypted Cloudflare mirror incrementally; the owner can browse and search the
  projection privately; a lost collector restores from R2; a forgotten session never
  returns; meaningfully wasteful work on the no-op path is a failing gate.
- **Accepted:** `P0.1` (benchmark harness, root `Makefile`, and the deterministic capture
  baseline), `P0.2` (age adapter, dev `rage` build, and the crypto suite), `P1.1`
  (Worker scaffold, Access gate, status, and the runtime harness), `P1.2` (initial
  D1 schema and store metadata), and `P1.3` (observability, span allowlist, and
  `Server-Timing`).
- **In flight:** none.
- **Next slice:** `P1.4` (Worker bench harness); the first command re-checks the baseline:
  `cd tools/agent-memory/cloudflare && npm test`.
- **Known red:** none. All ten agent-memory suites are green on the baseline commit.
- **perf gate deferred: host busy.** An unrelated `cargo test` in another checkout held load
  near 13 on 18 cores during the P0.1 run, so no wall or CPU time is accepted as a baseline.
- **Launch prompt:** `Execute docs/CAMPAIGN-AGENT-MEMORIES-CLOUDFLARE.md from P0.1.`

## Charter

- **The code is the truth.** Read the named file before changing it; verify every claim
  this document makes about existing behavior. Correct the document when the code
  disagrees.
- **Decide and keep going.** Record a decision only when a later slice depends on it.
  This document pre-answers the contract, privacy, authority, deployment, and performance
  questions; remaining calls are delegated with a bound.
- **Performance is a release gate, not a phase.** Deterministic operation-count
  invariants gate every slice. Time-based gates run only when
  `dotfiles/base/.local/bin/perf-gate-ready` exits 0 and again with `-1` immediately
  after the measurement; a run that overlapped load is discarded, and a busy host
  reports `perf gate deferred: host busy` in **Status**, never a pass.
- **Correctness before speed.** A faster path that weakens a digest check, an
  acknowledgement, an authority boundary, or a tombstone is a defect, not an
  optimization.
- **A failing item gets its cause established before any retry.** A retry that hides a
  race, a lost ack, or a corrupt object is a defect. Reproduce with the smallest failing
  test; keep the test.
- **The tree is shared.** Re-check `git status` before every commit, stage only this
  campaign's files, and leave unrelated work alone.
- **Parity first, then optimization.** New remote behavior matches the existing local
  and SSH semantics before any tuning slice starts. Optimizations require a measured
  trigger stated in **Decisions**.
- **One writer by default.** Parallel lanes only for the disjoint pairs named in
  **Sequence**, in worktrees at `.work/wt/<lane>`. Never `/tmp`.
- **Every commit is a Conventional Commit** with scope `mirror`, `worker`, `learning-sync`,
  `perf`, `ops`, or `docs`. Put the item ID in the body. Code comments never cite this
  document.
- **Never weaken or delete an existing test** to make a slice land. If a test is wrong,
  say so in the commit body and land the correction as its own commit.
- **A red slice never lands on `main`.** Fix the cause; do not add a retry around it.
- **Time-box a failing slice** at three attempts or two hours, whichever comes first.
  Park it on its branch with the cause, the failing command, and the retry condition.
- **Fix egregious problems met on the way** in their own commit, to these numbers: a
  path that can accept bytes it did not verify, a deletion that removes canonical local
  data, a remote write that can make a forgotten session searchable again, an unbounded
  remote scan or request loop, or a test that passes while its boundary is mocked away.
  Record anything else and leave it.
- **No formatters. No pushes. No CI edits.** Verify locally. The owner runs the first
  real sync; this campaign never writes `~`.
- **Guards against the likely repeat mistakes:** a test that still passes when the Worker
  is absent is a stub and is deleted; a validation rule copied into a second language gets
  one shared fixture corpus; no code path trusts a caller-supplied origin; no secret or
  record text reaches a log, span attribute, or error message; no timing is recorded from a
  busy host.
- **Status stays a short block.** Git history is the log; never append dated checkpoints.

## Decisions

**Owner-decided:** none. The brief already grants deployment, provisioning, and production
verification; every remaining choice is settled below or delegated. The owner's manual
steps are in **Needs you**, not blocking questions.

**Prescribed** — settled from the code, the brief, or a proof run on 2026-10-31. Each row
names what would reverse it.

| ID | Decision | Reason | Reversal |
| --- | --- | --- | --- |
| CF1 | The Worker is TypeScript under `tools/agent-memory/cloudflare/` with `compatibility_date = "2026-10-30"` (the date `stuff` deploys with and `ctx.access` is documented for), built and deployed with `cf`; `wrangler.toml` is the source of truth and `cf migrate` regenerates `cloudflare.config.ts`. No Rust/Wasm, no frontend framework, no bundler beyond what `cf deploy` runs. | D1, R2, `ctx.access`, and HTML are native Worker APIs; a Wasm boundary would add a build and serialization cost with no measured benefit. `stuff` proves the `wrangler.toml` → `cf migrate` → `cf deploy` path. | A measured CPU or correctness need that TS cannot meet. |
| CF2 | `ctx.access` is the authentication source. The Worker requires it on every route and fails closed when it is absent. No hand-rolled JWT parsing. | Cloudflare documents that Access runs before the Worker when the Worker is protected by a Worker-level Access application, and `ctx.access.getIdentity()` exposes the authenticated identity including `service_token_id`. Parsing the JWT again adds a network dependency for no security gain. | `ctx.access` regression on the deployed compatibility date, a route outside Access coverage, or a deployed identity that omits `service_token_id` for service tokens; in that last case verify the `Cf-Access-Jwt-Assertion` `common_name` against the team JWKS before P2.1 ships. |
| CF3 | Access protection is deployed as a **Worker-level** application (`destination: worker`) plus `workers_dev = false` and `preview_urls = false` in `wrangler.toml`. Hostname-only protection is not sufficient. | Worker-level Access covers custom domains, `workers.dev`, and previews; the manifest flags remove the alternate hostnames entirely. | Cloudflare removes Worker-level Access destinations. |
| CF4 | Two principals: browser readers (owner email, read-only) and collector service tokens (`client_id` bound to exactly one `origin_host` in D1). A collector token may read and write only its bound origin; a browser identity may read all origins and write nothing. The Access policy names the owner email and each specific service-token id; `any_valid_service_token` is not used. Collector tokens are created with a one-year duration and rotated by enrolling a new token before the old one expires. | The brief forbids trusting a caller-supplied origin. The binding is data, not a header. | A second human reader, added to `READERS`. |
| CF5 | All responses are `Cache-Control: no-store`; Workers Cache is never made eligible (no `max-age`, no `s-maxage`, no public directive). No cache API calls. | Workers Cache can bypass Worker execution and its default key is not hostname-isolated; a private, mutable, authenticated service must not enter it. `no-store` is the documented opt-out. | A future immutable public asset on a separate Worker and route. |
| CF6 | Protocol v1 is resource-oriented under `/api/v1/`, JSON for control and metadata, raw ciphertext for object bodies. The SSH frame protocol is untouched. | A stream protocol over chunked POSTs hides stalls and duplicates error semantics; a small resource API matches Workers and gives idempotent retries. | A protocol version bump. |
| CF7 | Per-origin fencing is a monotonic D1 `origin_sync.revision`; every publication (generation, tombstone, learning delta) carries `base_revision` and is applied in one `db.batch()` (a SQL transaction) whose first insert is guarded by a trigger that raises `stale_revision` on mismatch. Wall-clock time is never the fence. | D1 serializes a database; `batch()` rolls back the whole sequence on failure. A stale writer therefore cannot publish anything. | A D1 change that removes transactional batches. |
| CF8 | R2 keys are ciphertext digests, never plaintext digests or paths: `v1/o/<ciphertext_sha256>` for archive objects and snapshot chunks, `v1/m/<origin>/<ciphertext_sha256>` for encrypted manifests. D1 maps plaintext digest → ciphertext digest. | Randomised age encryption produces different ciphertext for the same plaintext; keying by ciphertext keeps R2 keys opaque and avoids confirmation of known plaintext, while D1 still provides dedupe. It also keeps raw keys out of custom telemetry. | A deterministic container format that proves no information disclosure. |
| CF9 | The generation commit carries only compact metadata: origin, harness, native id, manifest digest, source digest/size, capture time, the chunk digest/size list, and the encrypted-manifest object. `source_path`, `cwd`, workspace URIs, and session metadata live only inside the encrypted manifest in R2. | The Worker must validate chunk tiling and record references, but has no need for local paths. Keeping them out of D1 removes a class of private-path leakage. | A server-side feature that provably requires a path. |
| CF10 | Encryption is `age`/`rage` invoked as an external executable, resolved from `AGE_BIN`, then `rage`, then `age`. One collector identity plus one recovery identity; every object is encrypted to both. A recipients file may hold several recipients. Rotation is per origin: `mirror rotate` decrypts with the old identity, re-encrypts to the new recipient set, uploads new ciphertext, and swaps the D1 mapping before GC. | The brief forbids home-grown cryptography and keeps Python stdlib-only. Proved on 2026-10-31: `rage 0.12.1` encrypts to two recipients, either identity decrypts, a wrong identity exits non-zero and writes nothing, and ciphertext is randomised. | An audited in-process age implementation with the same properties. |
| CF11 | One remote object per local archive object (64 KiB chunks; artifacts up to 8 MiB). Packing is an optimization gated by measurement, not built up front. | The existing chunking is already incremental and dedupes across generations. Packing changes the restore and GC format; it needs evidence. | See **Delegated** G1. |
| CF12 | The searchable learning projection is **off by default**. `mirror enable --searchable-learning` prints the disclosure and writes the opt-in to local config; without it, no learning record is written to D1 or any searchable index. Learning records still travel inside the encrypted recovery snapshot, which is required for recovery. | The brief requires explicit opt-in for a projection that can contain sensitive text, while recovery of canonical records must not depend on that opt-in. | The owner makes the projection the default. |
| CF13 | Learning sync is a durable local change journal (SQLite triggers on the canonical learning tables), not a full export per run. Deltas are per-record digests applied in revision-fenced D1 batches. A full projection remains the explicit `--reconcile` fallback, reconciled by comparing a paginated remote key/digest index. | A full `export_snapshot()` on every 15-minute run serializes the whole corpus. The journal makes the no-op path one `max(seq)` query and the incremental path proportional to changed records. | A measured case where the journal coverage is incomplete. |
| CF14 | Projection reconciliation (the explicit `--reconcile` path) uses an epoch: staged rows carry a new epoch and `pending=1`; search filters on `learning_state.epoch`; commit flips the epoch and revision atomically; old rows and FTS entries are deleted afterwards. An interrupted reconciliation is invisible. | A 100k-record replace cannot be one D1 statement; the epoch makes publication atomic without a giant transaction. | D1 gains atomic multi-request transactions. |
| CF15 | Search is recency-ordered with keyset pagination on `(observed_at DESC, origin_host, record, remote_id)`; FTS5 is a filter, not a rank source. No relevance sort is implemented in this campaign; bm25 is recorded for diagnostics only. | bm25 scores are not stable enough for a keyset cursor; recency is stable, index-friendly, and right for a personal knowledge base. | A stable rank scheme. |
| CF16 | Project identity sent to D1 is `sha256("agent-memory-project:" + local_project_identity)[:16]`, optionally paired with a label the owner explicitly assigns with `mirror label <project-key> <name>`. No absolute checkout path or repository basename leaves the machine. | `project_identity` returns `git:/Users/...` or `path:/Users/...`; uploading it would leak private layout. The hash is stable and filterable, and a label is uploaded only when the owner chooses one. | The owner chooses to expose paths. |
| CF17 | Snapshots keep 7 daily and 4 weekly copies. GC is explicit (`mirror gc`, dry-run by default), deletes only objects unreferenced by any live generation or retained snapshot for at least 7 days, and never deletes the newest verified snapshot. | Bounded retention without an unbounded automatic background mutation. | A measured storage or cost need. |
| CF18 | Restic stays removed. The removal landed in `335fe09`; this campaign verifies no residue and changes nothing. | `rg -i restic` and `git log -S restic` show the CLI branch, option, doctor field, docs, and test references are gone; `backup create/restore` remain tested. | None. |
| CF19 | Development and every automated test use scratch state under `.work/` and synthetic corpora. The campaign never writes `~/.agent-sessions`, never runs a real-home sync, and never uploads the owner's real transcripts. Production smoke and performance use a synthetic origin that is then forgotten or GC'd. | `AGENTS.md` and the brief forbid host-altering and real-data actions. The owner's first real sync is theirs. | The owner explicitly authorizes a real upload. |
| CF20 | No CI changes. Gates are local commands; preview and production checks are manual and recorded. | `AGENTS.md`: do not add or extend workflows while doing other work. The brief asks for gates, not pipelines. | An explicit owner request for CI. |
| CF21 | A recovery snapshot is the consistent SQLite image stored as content-addressed 1 MiB plaintext chunks, compressed and encrypted like any object, with the chunk list in D1. A snapshot is taken when the sanitized database digest differs from the newest snapshot; an unchanged run writes no snapshot. Unchanged chunk digests are not re-uploaded. | A whole-file upload every sync would dominate the no-op path; chunking makes a snapshot proportional to changed pages while keeping the existing backup-API consistency. The DB contains canonical learning, so this is also what makes learning recoverable when the searchable projection is off. | Measurements show chunk-shift amplification above 50% of snapshot bytes for ordinary appends. |
| CF22 | Compress each object with zlib before encryption when it shrinks by at least 5%; record `encoding`, plaintext size, compressed size, ratio, and CPU per object in the manifest/commit metadata. Decompress to an exact bound, then verify the plaintext digest. | Transcript text compresses well (the SSH path measured 2.6 MB → 1.1 MB), and encryption follows compression so R2 stores less. The old path already has a bounded-inflate implementation to reuse. | Measured CPU cost outweighs bytes saved for a workload class. |
| CF23 | Routine collector sync uses stdlib `http.client` over HTTPS and never invokes `cf`. `cf` is only for provisioning, migrations, deploy, and administration. | The brief requires no `cf` dependency for scheduled sync, and `cf` is an interactive/admin tool. | A required administrative action that has no HTTP equivalent. |
| CF24 | Runtime dependencies stay: Python stdlib, one external `age`/`rage` executable, and no npm runtime packages. Dev dependencies are pinned to `stuff`'s `wrangler ^4.156.0` and `miniflare 4.20260730.0`; the Worker bundle must stay under 200 KiB uncompressed and `cf build` time is recorded. | `age` provides audited cryptography; Workers and Miniflare are platform tooling. The brief forbids a dependency that moves build time, bundle size, or startup without justification. | A measured capability that the platform cannot provide. |
| CF25 | `sync --to` gains the `cloudflare` transport, but `search --central`/`show --central` keep their existing local and SSH meaning. Remote search and inspection live in the authenticated web UI and `/api/v1/memories`. | A collector token is origin-scoped and should not become a general search credential; adding a second remote query stack duplicates the UI's query path. | The owner wants terminal search against the mirror. |
| CF26 | The local `transfer_generation.remote` and `transfer_learning.remote` keys for the mirror are the remote's stable `store_id`, not its URL. A replacement store at the same URL therefore has no local acks, and `mirror adopt` is the only way to clear them explicitly. | This is the same rule the SSH transport already applies by recording the receiving store's identity, and it makes URL reuse harmless. | A durable remote id that is not exposed by the API. |
| CF27 | Runtime placement is fixed: the collector stays Python stdlib plus the external `age`/`rage` binary; Cloudflare runs a TypeScript Worker. No Python is deployed to Cloudflare, so it cannot affect Worker CPU, bundle size, cold start, or platform cost. A Rust/Wasm Worker is rejected: it adds a Wasm/JSON boundary and cold-start cost for no measured CPU win. A Rust collector rewrite is out of scope unless P5.3 measures a named Python hotspot (not I/O, `rage`, or network) that materially affects the owner path; then a small helper is allowed, never a port. | Local paths are dominated by capture I/O, encryption subprocesses, and network. Cloudflare cost is dominated by R2/D1 operations and storage. A rewrite would risk the archive, tombstone, and authority semantics the campaign exists to preserve. | A measured hotspot with numbers, or a requirement to ship a static collector binary to many machines. |
| CF28 | Deployment mirrors `stuff`'s Makefile: one `cf build --mode production` bundle, the tests run on that bundle, `cf deploy --prebuilt` ships exactly the tested bundle, and `make deploy` gates on `cf auth whoami`, rejects pending D1 migrations, then runs test → deploy → read-only smoke. A root `Makefile` is the entry point; `make help` lists targets. | The owner asked for the same machinery, and testing a different bundle than the one deployed was a defect class `stuff` already removed. | A different deployment tool supersedes `cf`. |

**Delegated** — the executor decides inside the bound and records it in the commit body.

| ID | Bound |
| --- | --- |
| G1 | Chunk-to-request packing and upload concurrency. Default: one object per request, 4 concurrent archive-object uploads, 1 snapshot-chunk upload. Change only if a measured initial backfill shows request/encryption overhead above 50% of wall time; then pack consecutive chunks into versioned ≤1 MiB packs with an indexed manifest and re-run restore and GC tests. |
| G2 | Batch sizes for D1 writes. Bound by the platform limits (100 bound parameters and 100 KB per statement, 1000 queries per invocation): learning deltas use multi-row statements of at most 10 rows and at most 200 statements per `batch()`; a generation commit may use up to 800 multi-row statements (25 rows of 4 columns) to insert its chunk references. Tune only against measurements. |
| G3 | Cursor encoding and page size. Default page 20 in HTML, 100 for API; cursor is opaque base64 of the sort key. Never use `OFFSET`. |
| G4 | Backoff and timeouts: 30 s connect, 120 s per request, 5 attempts with exponential 1–60 s for idempotent requests. Object uploads may retry more within one sync run; a failed sync leaves the backlog. |
| G5 | Exact HTML copy and layout, provided it fits the payload budget and distinguishes reviewed guidance from advisory evidence. |
| G6 | Whether to run GC weekly from cron or only by hand; the default is by hand, documented in the README. |

## Design

### Roles and data separation

Local SQLite remains the operational source of truth: capture, indexing, recall, review,
promotion, and `forget-session` work with no network. The mirror is asynchronous. Python
runs only on the collector; the deployed Worker is TypeScript (CF27).

| Store | Holds | Never holds |
| --- | --- | --- |
| Local SQLite + archive | Canonical sessions, events, generations, learning records, grants, tombstones | — |
| R2 `usr-memories` | age-encrypted immutable archive objects, encrypted generation manifests, encrypted SQLite snapshot chunks | Plaintext, keys, identities |
| D1 `usr-memories` | origin/revision state, collector bindings, generation metadata, object ciphertext/plaintext digest map, tombstones, opt-in learning projection, FTS5 | Transcripts, paths, claims when the projection is off, grants, permissions |

The projection is a copy of `learning_sync.py`'s record types, not a second memory model.
Imported records stay advisory: the Worker stores no authority beyond a fixed label, and
the UI never presents a record as an instruction.

### Reused from `stuff`

| Pattern | Disposition |
| --- | --- |
| `wrangler.toml` as source, `cf migrate`, `cf deploy`, custom domain, Miniflare runtime tests, preview and deployed smoke discipline | Reused directly |
| Observability block (logs 0.25, traces 0.10) and `cf` preserving it | Reused directly |
| Immutable, digest-verified objects; verify before publish | Adapted: ciphertext digests, D1 revision fence instead of a `current` pointer |
| R2 generation promotion, `r2-sync.sh`, `r2-plan/put/pull/promote`, temporary S3 credentials, registry catalogs, Wasm | Not used; the Worker API is the only writer |
| Paced uploads and bounded parallelism | Reused as a requirement, implemented in the Python client and Worker limits |
| Root `Makefile`: bundle once, test that bundle, deploy that bundle, then read-only smoke (`worker-bundle`, `worker-test`, `worker-deploy`, `deploy`, `smoke-deployed`, `help`) | Reused directly; targets in **Deployment and observability machinery** |

### Deployment and observability machinery

The root `Makefile` is the operator entry point, mirroring `stuff`'s. `make` is developer
tooling: no runtime path calls it, and routine collector sync never needs it (CF23).
`WORKER_DIR ?= tools/agent-memory/cloudflare`; `make help` prints each target's `##` line.

| Target | Does |
| --- | --- |
| `help` | One sorted line per target from its `##` comment |
| `deploy` | `cloudflare/scripts/deploy-gate.sh`, then `worker-test worker-deploy`, then `smoke-deployed` |
| `worker-bundle` | `cf build --mode production` once, into `.cloudflare/output/v0/workers/default/bundle/index.js` |
| `worker-test` | Depends on `worker-bundle`; `npm run test:runtime` boots exactly that bundle in Miniflare with D1, R2, and real HTTP |
| `worker-check` | `cf deploy --dry-run`: validates configuration, bindings, and observability without uploading |
| `worker-deploy` | Depends on `worker-bundle`; `cf deploy --prebuilt --mode production` uploads the bundle `worker-test` exercised |
| `smoke-deployed` | Read-only live probe with the synthetic collector token: status, search, unauthenticated refusal, `no-store`, `Server-Timing`; never writes |
| `migrate` | Prints pending files, then `cf d1 migrations apply <database-id>` (remote is the default; `--local` selects the simulation) |
| `provision` | `cloudflare/scripts/provision.sh`: create R2 and D1, write their ids |
| `provision-access` | `provision.sh --access`: create the Worker-level Access app and policies, and enroll a collector token bound to one origin |
| `observe` | Asserts the generated config carries logs 0.25 and traces 0.10, prints the dashboard URLs, and lists the serving deployment with `cf workers deployments list --worker usr-memories` |
| `perf-local` | `eval/bench_mirror.py local` |
| `perf-worker` | `eval/bench_mirror.py worker` over the Miniflare bundle |
| `perf-deployed` | `eval/bench_mirror.py deployed` against the live origin with the synthetic token; exits with a message until `P1.6` deploys |
| `perf-report` | `eval/bench_mirror.py report --dir .work/perf` |
| `test` | The ten existing Python suites; `worker-test` joins it at `P1.5` |
| `test-all` | `test`, `worker-test`, the adversarial suite, Ruff, `ty`, and `mdtool` |
| `doctor` | `agent-sessions mirror doctor` against a scratch state dir, plus the auth and migration checks |

`perf-*` and `test` land with `P0.1`, `doctor` with `P5.1`, and the rest with `P1.5`.
`worker-test` and `worker-deploy` both depend on `worker-bundle`, so one build is tested and
deployed and no second build can drift between them. `cf deploy --prebuilt` is what makes
that hold: it skips building and uploads the existing Build Output Specification.

`make deploy` stops before the build when `cf auth whoami` fails or a migration file is
unapplied. A bundle that expects `0002_learning.sql` against a `0001` database would
otherwise fail mid-sync after a partial upload; the gate moves that failure to the start.
The gate also fails when `cloudflare.config.ts` is missing or lacks the worker name, any
configured domain, any binding, or the observability block, because `cf deploy` reads the
generated file and a stale one would ship stale settings. `deploy-gate.sh` is a separate script so the
gate can be tested with a stub `cf` on `PATH`.

From `P2.1` on, `worker-test` includes the shared protocol fixture parity check, so a Worker
that disagrees with the Python client on any fixture cannot be deployed.

Bootstrap is the one exception to "`make deploy` is the entry point", because a Worker-level
Access app cannot be created before the Worker exists. The order is `make provision`
(R2 and D1), `make migrate`, `make worker-deploy` (a one-time bootstrap with no data),
`make provision-access` (app, policies, synthetic token), then the first full `make deploy`.
The bootstrap deploy is safe by construction: `workers_dev` and preview URLs are off, the
custom domain is the only route, and every route fails closed with 403 when it has no Access
identity. `make deploy` is then the only path that ships after that, and it demands the smoke
pass.

`cloudflare/scripts/smoke-deployed.sh` is POSIX `sh`, needs no Cloudflare credentials, and
reads `MEMORIES_BASE` (default `https://memories.17166969.xyz`) and `MEMORIES_TOKEN_FILE`
(default `.work/secrets/collector.token`, written `0600` by `make provision-access`).
It fails on a non-200 token request, a missing `no-store`, a missing `Server-Timing` on the
API, an unauthenticated request that is neither a 403 from the Worker nor a redirect to
Access, or any attempted write; it prints one line per check so a partial failure names the
step.

`make observe` is deliberately thin: it checks what we ship and names what is serving.
Logs, traces, CPU and heap profiles, and R2 analytics are read in the dashboard, which has
no complete CLI surface; **Needs you** lists that step and `make observe` prints the URLs.

### `stuff` performance hypotheses

Each is a hypothesis, not a finding. No optimization lands unless the scenario that owns it
moves the counter.

| Hypothesis | Relevance here | Disposition |
| --- | --- | --- |
| Extra R2 reads for a mutable generation pointer | None: there is no `current` pointer; the fence is `origin_sync.revision` in D1, read once per `hello` | Not implemented |
| No application cache for immutable artifacts | Low: authenticated private responses must not be edge-cached; R2 itself is the durable copy | `no-store`; no cache |
| Independent R2 requests run sequentially | Real for restore and backfill | Bounded concurrency 4 for archive objects, 1 for snapshot chunks; measured |
| Redundant initial and ranged GETs | Real if a client re-reads or ranges objects | Each object is read once per verify/restore; no ranged GETs; counters recorded |
| JSON serialization across TS/Rust/Wasm | Removed: there is no Wasm boundary; control JSON stays small and bodies are raw | No Wasm; measured |
| Insufficient production profiling | Real: `stuff` had none until recently | Logs and traces enabled from P1.3; dashboard inspection in **Needs you** |

### HTTP protocol v1

All routes require `ctx.access`; writes require a collector token. Bodies are bounded and
validated before allocation. `GET` never mutates. Unknown routes return 404, wrong methods
405 with `Allow`, and oversized bodies 413 without reading them.

| Method and route | Purpose |
| --- | --- |
| `GET /api/v1/status` | Protocol, store id, caller principal, readiness, counts; no content |
| `POST /api/v1/sync/hello` | Bind origin, return `store_id`, `revision`, learning revision/digest, tombstone watermark |
| `GET /api/v1/sync/tombstones?after=` | Tombstones above the local watermark, bounded pages |
| `POST /api/v1/sync/tombstones` | Push unreconciled local tombstones before generations; idempotent by key and revision |
| `POST /api/v1/sync/objects/missing` | `{objects:[{plaintext_digest,size}]}` → missing digests plus known ciphertext metadata; one round trip per generation |
| `PUT /api/v1/sync/objects/{ciphertext_digest}` | Stream ciphertext to R2 with an R2 `sha256` checksum; headers carry plaintext digest/size; idempotent |
| `POST /api/v1/sync/objects/{plaintext_digest}/replace` | Swap the ciphertext mapping after a key-rotation re-encryption; the old object becomes unreferenced |
| `POST /api/v1/sync/generations` | Validate a manifest's tiling and digests, verify every object is recorded, commit in one D1 batch, return `{generation, manifest_digest, revision}` |
| `GET /api/v1/sync/generations?origin=&after=&limit=` | Recovery inventory, keyset paginated |
| `GET /api/v1/sync/manifests/{ciphertext_digest}` | Encrypted manifest body, scoped to the caller's origin |
| `POST /api/v1/sync/snapshots/{id}/verify` | Record a collector's successful full verification |
| `GET /api/v1/sync/objects/{ciphertext_digest}` | Encrypted object body, scoped to the caller's origin |
| `GET /api/v1/sync/learning/state?origin=` | Revision, digest, record count |
| `GET /api/v1/sync/learning/keys?origin=&after=&limit=` | Paginated `(record, id, digest)` index for reconciliation |
| `POST /api/v1/sync/learning/deltas` | Revision-fenced upserts/deletes, one atomic batch |
| `POST /api/v1/sync/learning/reconcile` | `begin` / `commit` staged reconciliation |
| `GET /api/v1/memories` | FTS5 search with `q`, `project`, `origin`, `type`, `kind`, `state`, `since`, `until`, `after`, `limit`; keyset paginated |
| `GET /api/v1/memories/{origin}/{record}/{id}` | Detail with provenance and relationships |
| `GET /`, `/search`, `/m/...`, `/status` | Server-rendered HTML |

The Worker validates what it can see: contiguous chunk tiling, the source digest derivation from
the chunk digests, closed-set harness, bounded sizes, and that every referenced object is
recorded with the same plaintext size the manifest declares. A digest absent from
`remote_object` is rejected as missing, which covers a manifest that was never uploaded or
whose objects GC removed. An object deleted or corrupted in R2 out of band is detected by
`mirror verify`, not by a per-object HEAD loop at commit. It cannot recompute
`manifest_digest` because the session metadata lives only in
the encrypted manifest; restore decrypts the manifest, recomputes the digest with
`archive.manifest_digest`, and refuses the generation if it differs. The ciphertext digest is
an opaque key on the server side and is not trusted as content proof.

### Sync order

1. Open the local lock and store; read the configured remote and `mirror_remote` state.
2. `hello`; verify the returned `store_id` matches the pinned one. A different store with
   existing acknowledgements stops the sync with `remote_identity_changed` until
   `mirror adopt` is run explicitly; it clears that remote's local acknowledgements and
   re-delivers, so an old ack never carries over.
3. Fetch and apply remote tombstones **before** capture, so a session forgotten elsewhere
   cannot be re-captured and uploaded in this run.
4. Refresh and capture locally (existing code).
5. Push local tombstones that the remote has not acknowledged, before any generation, and
   mark each durable only after its ack.
6. For each pending generation from **this collector's own origin** (imported generations
   are never re-mirrored): if the Worker already has the manifest digest, ack without
   objects; otherwise one missing-object request, upload only missing objects with bounded
   concurrency, then commit.
7. Send the learning delta when the journal head moved and the projection is enabled.
8. Mark each generation durable only after the matching ack; persist `mirror_remote` in
   one local transaction last. Report counters.
9. Upload a recovery snapshot only when this run changed generations, the journal head, or
   a tombstone, so an unchanged run writes nothing.

An unchanged run does: one `hello`, zero object requests, zero uploads, zero learning
requests when the journal head equals the durable head, and zero D1 writes.

### R2 objects and snapshots

- Archive object ciphertext: `v1/o/<ciphertext_sha256>`.
- Encrypted generation manifest (full `archive.generation_manifest` JSON): `v1/m/<origin>/<ciphertext_sha256>`.
- Snapshot chunks: `v1/o/<ciphertext_sha256>` as well. A snapshot is not a separate blob; it is a D1 record naming an ordered list of content-addressed chunks of the consistent SQLite image.
- A snapshot record in D1 pins the DB plaintext digest/size, chunk digest list, schema version,
  object count/bytes, and capture time, plus the archive objects its database references. Restore
  concatenates and verifies the chunks, verifies `PRAGMA integrity_check`, then verifies every
  archive object named by `snapshot_object` before rebuilding derived indexes. Pinning those
  objects is what lets a retained snapshot survive GC of generations it predates.
- A snapshot is taken when a sync changed generations, canonical learning, or tombstones; an unchanged
  database is not snapshotted again. Unchanged chunks keep their ciphertext and are never
  re-uploaded.
- The snapshot holds the archive's shared object lock from the database copy through the
  snapshot commit, the same discipline as `backup.create`, so a concurrent forget cannot
  unlink an object the snapshot pins. It copies the database, pins its archive objects, and
  only then releases the lock.
- The snapshot is a new `backup.snapshot` function that uses the existing SQLite backup API and
  consistency pattern but does not copy archive objects, because those are already in R2. Restore
  replays generation manifests committed after the snapshot revision, then applies current
  tombstones before indexing. The only loss window is a crash between a committed sync and its
  snapshot; the previous verified snapshot remains, and the collector still holds the backlog.
- The snapshot copy is sanitized before upload: `learning_global_grant` is emptied and
  `learning_projects.enabled = 0`, exactly as `backup.restore` deactivates them. No review grant,
  sandbox permission, or agent policy is uploaded, and a restore still activates nothing.
- The snapshot is not marked verified when it is uploaded. `snapshot.verified_at` is set only
  after an owning collector downloads, reassembles, and verifies every chunk, every pinned
  archive object, and the SQLite integrity check, then reports success. The UI's "last
  verified recovery point" reads that field.
- Upload uses R2's `sha256` put option so the platform verifies the ciphertext without
  buffering it in Worker memory. The Worker checks `Content-Length` against the declared
  size and rejects a mismatch before the put. Maximum request body is 8 MiB; archive chunks
  are 64 KiB, artifacts up to 8 MiB, and snapshot chunks 1 MiB.
- The searchable projection is separate from recovery: with the projection off, learning
  records still travel inside the encrypted snapshot, and D1 holds none of their text.

### D1 schema

```
store_meta(id, created_at)
collector(service_token_id PK, origin_host, label, created_at, disabled)
origin_sync(origin_host PK, revision, last_change_at)
remote_object(plaintext_digest PK, plaintext_size, encoding, ciphertext_digest UNIQUE,
              ciphertext_size, origin_host, created_at, last_referenced_at, gc_pending_at)
generation(id INTEGER PK, origin_host, harness, native_id, manifest_digest,
           source_digest, source_size, captured_at, committed_at, revision,
           manifest_object REFERENCES remote_object(ciphertext_digest),
           UNIQUE(origin_host, manifest_digest))
generation_object(generation, ordinal, plaintext_digest REFERENCES remote_object(plaintext_digest),
                  size, PK(generation, ordinal))
tombstone(origin_host, harness, native_id, scope, forgotten_at, revision,
          PK(origin_host, harness, native_id))
snapshot(id TEXT PK, origin_host, created_at, schema_version, db_digest, db_size,
         objects, object_bytes, verified_at, revision)
snapshot_chunk(snapshot, ordinal, plaintext_digest, size,
               ciphertext_digest REFERENCES remote_object(ciphertext_digest), PK(snapshot, ordinal))
snapshot_object(snapshot, plaintext_digest REFERENCES remote_object(plaintext_digest), size,
                PK(snapshot, plaintext_digest))
learning_state(origin_host PK, revision, epoch, digest, records, updated_at)
learning_experience(origin_host, epoch, remote_id, project_key, project_label, kind,
                    claim, applies_when, identifiers, fingerprint, basis, detector,
                    revision, worktree, observed_at, captured_at, validity, tags,
                    state, state_reason, state_at, sync_revision, pending,
                    PK(origin_host, epoch, remote_id))
learning_memory(origin_host, epoch, remote_id, project_key, project_label, action,
                applicability, revision, validity, state, created_at, sync_revision, pending,
                PK(origin_host, epoch, remote_id))
learning_source(origin_host, epoch, record, remote_id, session, position, digest, role,
                PK(origin_host, epoch, record, remote_id, session, position, role))
learning_link(origin_host, epoch, newer, older, relation,
              PK(origin_host, epoch, newer, older, relation))
learning_search(rowid INTEGER PK, origin_host, epoch, record, remote_id, text)
memory_fts USING fts5(text, content='learning_search', content_rowid='rowid',
           tokenize = "unicode61 remove_diacritics 2 tokenchars '-_./'")
```

Indexes: `generation(origin_host, committed_at DESC)`, `remote_object(ciphertext_digest)`,
`learning_experience(project_key, state, observed_at DESC)`,
`learning_experience(origin_host, state, observed_at DESC)`,
`learning_experience(kind, observed_at DESC)`, `learning_memory(project_key, state, created_at DESC)`,
`learning_source(origin_host, record, remote_id)`, `tombstone(origin_host, harness, native_id)`,
unique `learning_search(origin_host, epoch, record, remote_id)`. `memory_fts` uses external
content with insert/update/delete triggers, the same pattern as `store.py:728`'s `events_fts`.
Migrations live in `cloudflare/migrations/` and are applied with
`cf d1 migrations apply <database-id>`; `cf` targets the real database by default and
`--local` selects its simulation.

The FTS tokenizer above was proved in Miniflare on 2026-10-31, including prefix queries
and identifiers containing `_`, `-`, `.`, and `/`. A raw `:` is FTS5 column syntax, so the
query builder quotes every term; `no:cacheprovider` must be searched as a quoted phrase.

### Revision, replay, and deletion

- `hello` is read-only and returns the origin's current revision; it never updates a
  timestamp, so an unchanged sync performs zero D1 writes. `last_change_at` moves only
  when a generation, tombstone, learning delta, or snapshot commits.
- Every write sends `base_revision`.
- Generation commit: an existing `(origin, manifest_digest)` is an idempotent re-ack with
  its stored revision, whatever `base_revision` was sent. A new manifest inserts with
  `revision = base + 1`; a trigger compares it with `origin_sync.revision + 1` and raises
  `stale_revision`, and the final `UPDATE origin_sync SET revision = revision + 1` runs in
  the same batch.
- Learning delta: `revision = base + 1`, `digest = sha256(canonical records)`. An identical
  digest re-acks; only a different digest takes the revision fence, and a stale one returns
  409 with the state so the client reconciles.
- Tombstone commit is idempotent by key and `forgotten_at`; an older timestamp is ignored
  without a write, a newer one applies and increments the revision. A tombstoned
  `(origin, harness, native_id)` rejects every later generation commit with 410, regardless
  of revision. Applying it deletes every projection record that cites
  `harness:native_id@origin` in `learning_source`, together with its sources, links, and FTS
  rows, matching `learning_sync.forget_session_imports`. A record whose other evidence
  survives is kept with the remaining sources; a record left with none is deleted.
- A restored copy keeps the original origin id so acknowledgements and history line up. If it
  runs at the same time as the original, the revision fence lets only one publish; the other
  gets 409 and must stop or `mirror adopt`/reconcile. Regenerating the identity with
  `agent-sessions identity regenerate` is the explicit way to make a second independent
  collector. Two origins never merge silently.
- A snapshot restored from R2 has its current tombstones applied from D1 before indexing.
- R2 object deletion uses two phases so a racing commit cannot lose data: `mirror gc` first
  marks unreferenced objects `gc_pending_at` in one D1 batch, then sweeps only marks older
  than one hour that are still unreferenced, deleting the R2 object and the row. A commit
  that references an object clears its pending mark; a commit after a sweep finds the
  object absent, is refused, and the client re-uploads it.
- The deletion limits are documented in the README and the final report in these terms:
  **logical deletion** makes a session unsearchable and rejects new generations immediately;
  **physical removal** from live R2 happens only at GC after the grace period and never for
  a referenced object; **historical snapshots** retain encrypted bytes until retention
  expires, but restore applies current tombstones before indexing, so they never become
  searchable again; **provider-side** backups and replicas are outside this system and are
  not claimed to be erased.

### Authentication and request safety

- Worker-level Access app for `usr-memories`; `workers_dev = false`; `preview_urls = false`.
- `READERS` (comma-separated emails) authorizes browser reads. `collector` rows authorize
  service tokens. `ctx.access` absent → 403; unknown principal → 403; wrong origin → 403.
  A digest is not authorization: every object, manifest, generation, and snapshot read is
  scoped to the caller's bound origin.
- Request limits: JSON ≤ 8 MiB, manifest ≤ 20,000 chunks, object body ≤ 8 MiB, search
  `limit` ≤ 100, cursor and ids validated against closed patterns, all SQL parameterized.
- The Worker never decompresses and never parses a transcript; restore does the bounded
  inflation on the collector, reusing `transfer.decompress` (exact-size bound, reject
  trailing bytes). The collector runs `rage` with an argv list, never a shell string.
- No dynamic SQL table names from input, no shell execution, no evaluation, no outbound
  fetch from the Worker, no generic SQL or R2-object management route.
- Browser identities are read-only: HTML and `/api/v1/memories` accept only `GET`/`HEAD`;
  every mutation route requires a collector token.
- HTML escapes every record field; CSP allows no scripts, styles, images, or frames from
  anywhere except the inline stylesheet; the UI needs no JavaScript. Every response also
  carries `X-Content-Type-Options: nosniff`, `Referrer-Policy: no-referrer`, and
  `frame-ancestors 'none'`. No content in logs or
  custom span attributes. A test asserts that a token, identity
  path, claim, and absolute path never appear in a rendered error or logged line.

### Observability

`wrangler.toml` carries `[observability] enabled = true`,
`[observability.logs] enabled = true, invocation_logs = true, head_sampling_rate = 0.25`,
and `[observability.traces] enabled = true, head_sampling_rate = 0.10`. `cf migrate`
preserves this (verified in `stuff` commit `2558239` and its generated
`cloudflare.config.ts`); the deploy step asserts the generated file contains the block.
Preview runs may set both rates to 1.0 for the duration of a measurement and must restore
them before the production deploy. The rates are a starting point; if volume or cost makes
them noisy, lower them and record the change, never below what still shows a tail.

Every API response also carries `Server-Timing` with the time spent in D1 and R2 for that
request, for example `Server-Timing: d1;dur=2.7, r2;dur=18.4`. Values are milliseconds
rounded to one decimal, summed per binding, and never include keys, digests, origins,
counts, or SQL. This is what lets `make perf-deployed` separate storage latency from Worker
CPU over the wire, and it is the deployed half of F12. HTML pages carry it too, because a
slow page is usually a slow query.

Platform metrics provide Worker CPU and wall time and p50/p95/p99 request latency; R2
provides operation and storage analytics. The dashboard is read in **Needs you**. Custom
spans wrap auth, sync negotiation, missing-object planning, R2 checksum put, manifest
commit, learning validation, D1 batch, FTS search, and HTML render. Attributes are an
allowlist of counts, bytes, durations, status codes, and revisions. Never keys, digests,
origins, projects, claims, session ids, or paths. R2 automatic instrumentation shows
ciphertext keys, which are opaque; the privacy limitation is documented rather than hidden.
A test asserts the custom-attribute allowlist. One residual exposure is documented rather
than hidden: the HTML search form is a `GET`, so search terms travel in the request URL and
may appear in Cloudflare's own request metadata. The Worker does not log them and custom
spans carry only counts; the owner should not paste secrets into the search box.

## Baseline

Inspected at `usr` `335fe09` (`main`, clean) and `joshuarli/stuff` `2558239` (`main`,
clean). Measured 2026-10-31 on this host. `perf-gate-ready` exited 0, but an unrelated
`cargo test` started during the run; re-run the gate before any timing gate.

| Suite | Result | Wall |
| --- | --- | --- |
| `tests/test_sessions.py` | 65 OK | 4.3 s |
| `tests/test_archive.py` | 30 OK | 1.5 s |
| `tests/test_transfer.py` | 33 OK | 5.9 s |
| `tests/test_identity.py` | 5 OK | 0.1 s |
| `tests/test_recovery.py` | 8 OK | 0.8 s |
| `tests/test_learning_ops.py` | 11 OK | 0.1 s |
| `tests/test_learning_review.py` | 18 OK | 5.2 s |
| `tests/test_recall.py` | 83 OK | 20.1 s |
| `tests/test_learning.py` | 56 OK | 36.4 s |
| `tests/test_learning_promote.py` | 32 OK | 29.9 s |

`test_learning.py` and `test_learning_promote.py` need
`GIT_TEMPLATE_DIR=/opt/homebrew/share/git-core/templates` on this host (the same
environment defect the archive campaign recorded); the other suites do not.

`make perf-local REPEATS=5` on 2026-10-31 (200 sessions × 10 messages × 10 projects,
2,600 events, 472,790 source bytes). Each repeat builds a fresh corpus, so all five repeats
produced identical work counters. `perf-gate-ready` returned 75 for every sample, so no
wall or CPU time is accepted as a baseline; the run records `perf_gate: deferred`.

| Operation | bytes read | content opens | stat ops | git processes | SQLite changes |
| --- | --- | --- | --- | --- | --- |
| fresh index | 979,580 | 400 | 600 | 10 | 24,181 |
| one-line append | 3,015 | 3 | 203 | 1 | 11 |
| unchanged refresh | 0 | 0 | 200 | 0 | 0 |

`SCENARIO=learning-import` measures snapshot export and serialization; at 200 synthetic
records it exported 133,647 bytes with a stable digest. The 1k/10k/100k dataset baselines
land with `P3.2`, when the projection applies those records.

These are the local hot paths the mirror must not slow. `make perf-local` records them
under one JSON schema with repeat statistics; the first quiet run becomes the timing
baseline. Mirror upload scenarios record plaintext, compressed, and ciphertext bytes so
CF22 compression savings are measured rather than assumed.

## Performance contract

**Harness.** `Makefile` targets call `cloudflare/perf.sh`, which drives
`eval/bench_mirror.py`. Each accepts `REPEATS=5`, `SCENARIO=<name>`, and `OUT=<path>`, and
writes JSON under `.work/perf/`. The runner prefix
`TMPDIR="$PWD/.work/tmp" uv run --no-project --python '>=3.15' python -I` belongs to the
target, not to the caller.

```
make perf-local                  # collector paths, no network
make perf-worker                 # the Miniflare bundle over real HTTP
make perf-deployed               # the production origin, synthetic token, synthetic data
make perf-report                 # compare a baseline and a candidate, render the table
```

`perf-worker` boots the bundle built by `make worker-bundle` on a random loopback port with
real Miniflare D1/R2 and a real HTTP client; it never touches the deployed Worker.
`perf-deployed` is the only target that leaves the machine, it is opt-in, and it needs the
deployed Worker from `P1.6`; the full production matrix runs in `P6.2` with
`environment: "production"`.

**Scenarios and measurements.** Every scenario reports wall time and work counters.

| Scenario | Datasets | Measurements |
| --- | --- | --- |
| `recall` | 200 sessions, 1k/10k learning records | p50/p95/p99, SQLite time, process CPU, peak RSS |
| `capture` | 200 sessions, unchanged / 1-line append / fresh | bytes read, content opens, objects written, amplification |
| `search` | 1k/10k/100k records | p50/p95/p99, D1 rows examined, FTS time, response bytes |
| `inspect` | 20-result page and one detail | D1 queries, response bytes, TTFB |
| `mirror-initial` | 200 sessions, 1 GB archive, 1 and 3 origins | objects/bytes uploaded, requests, encryption time and CPU, R2 puts, D1 writes, wall |
| `mirror-noop` | same | requests, objects uploaded, D1 writes, local serialization count, wall |
| `mirror-append` | 1-line tail, 10k-record corpus with 3 changed records | bytes uploaded vs changed bytes, objects, requests, D1 writes |
| `learning-import` | 1k/10k/100k | records/sec, serialization time, D1 batches, statement count |
| `learning-delta` | 100 changed records at 100k corpus | records/sec, bytes, D1 writes; must not scale with corpus |
| `recovery` | 200 sessions, 100 MB archive | download throughput, decrypt/verify CPU, peak RSS, wall |
| `html` | empty, 20-result page, detail | render time, uncompressed and gzip bytes, browser requests |
| `mirror-concurrent` | 3 origins, 50 sessions each | throughput, conflicts, retry cost, p50/p95 tail |
| `worker-status` | cold and warm | wall, CPU if reported, D1/R2 calls |

**JSON shape.** Top level: `schema_version`, `commit`, `generated_at`, `environment`
(`local`, `miniflare`, `preview`, `production`), `runtime` (Python, Node, workerd
compatibility date, `rage` version), `dataset` (counts and bytes), `perf_gate`
(`passed|deferred`), `load`, `samples`, `summary`, `counters`. Each sample carries
`wall_ms`, `cpu_ms` where available, and counters. `summary` carries `runs`, `median`,
`p50`, `p95`, `p99`, `min`, `max`, `spread` (p95 − p50), and `mad`.

**Gate policy.**

- Deterministic counters (F1–F10, F12 below) are hard gates: any violation fails the slice.
- Time comparisons run baseline and candidate interleaved on the same host, with a warmup
  and at least five samples each, only when `perf-gate-ready` exits 0 before and `-1` after.
  Fail when the candidate median exceeds the baseline median by more than
  `max(5%, 2 × baseline MAD)`, and record both. A failed time gate needs a fix or a
  quantified justification in the commit body and the final report.
- Never change a fixture, drop a sample, or narrow an assertion to make a gate pass.
  Fixture changes require re-baselining both sides and saying so.
- Local Miniflare timings detect regressions only; they are not claims about R2 or
  network latency. Production numbers come from `P6.2` and platform traces.
- The first accepted run of each scenario becomes the baseline; the doc records it. No
  budget is invented before that run.

**Counters the collector reports.** Changed sessions and learning records; objects
uploaded/skipped; plaintext, compressed, and ciphertext bytes; HTTP requests; encryption
and compression time; network duration; end-to-end duration; D1 writes; last durable
revision. `mirror sync --dry-run` reports pending objects, bytes, and the estimated
request count without uploading.

## Sequence

Phases: **P0 baseline and harness** → **P1 Cloudflare foundation** → **P2 encrypted
mirror** → **P3 D1 projection** → **P4 API and UI** → **P5 integration and adversarial
proof** → **P6 deploy and production validation**.

Workstreams: **W** = `cloudflare/**`; **C** = `src/agent_memory/mirror*.py`,
`sessions_cli.py`; **B** = `eval/bench_mirror.py`, `cloudflare/bench/**`; **L** =
`learning.py`/`learning_sync.py`/`experience.py` and their tests. W and C share the protocol
contract; L and C share the journal contract and both touch `store.py`, so P2.3 and P3.1
are serial. No two lanes are disjoint before P2.1; after P2.1 freezes the protocol, B may
run beside W because it owns only the harness and benchmark files. Everything else is one
writer.

### P0 — Baseline and harness

| ID | Slice | Owns | Prereq | Acceptance |
| --- | --- | --- | --- | --- |
| `P0.1` | `bench_mirror.py` with `local`, `worker`, `deployed`, `compare`, `report`; JSON schema with commit, runtimes, dataset, environment, repeats, median/p95/min/max, work counters; synthetic corpus generators for 1k/10k/100k learning records and 200 sessions; root `Makefile` with `help`, `perf-local`, `perf-worker`, `perf-deployed`, `perf-report`, `test`. Record the local baseline in this doc and `README.md`. | `eval/bench_mirror.py`, `cloudflare/perf.sh`, `Makefile`, this doc | — | `make perf-local REPEATS=5` runs and `make help` lists it; output parses with `jaq`; the doc's baseline table matches the run; no network. |
| `P0.2` | `age` adapter proof and dev binary: resolve `AGE_BIN`/`rage`/`age`, fail loudly with the install hint; `cloudflare/dev-age.sh` builds `rage` into `.work/tools/rage` when absent. | `src/agent_memory/mirror_crypto.py`, `cloudflare/dev-age.sh`, `tests/test_mirror_crypto.py` | — | Round trip to two recipients; either identity decrypts; wrong identity fails, leaves no output, and the error is typed; `sha256(ciphertext)` and length are returned. |

### P1 — Cloudflare foundation

| ID | Slice | Owns | Prereq | Acceptance |
| --- | --- | --- | --- | --- |
| `P1.1` | Worker scaffold, `wrangler.toml`, `cf migrate` output, `workers_dev=false`, `preview_urls=false`, `READERS`, Access gate, `/api/v1/status`, JSON error envelope. A test harness boots the built bundle, injects a synthetic `ctx.access` (Miniflare does not provide one), and wraps the D1/R2 bindings to count calls; the deployed bundle is scanned to prove no test hook is compiled into it. The Worker `package.json` declares `"test": "node --test test/*.test.mjs"` and `"test:runtime": "node --test test/runtime.test.mjs"`, and pins the same `miniflare`/`wrangler` versions as `stuff`. | `cloudflare/{wrangler.toml,package.json,package-lock.json,cloudflare.config.ts,src/index.ts,src/auth.ts,src/errors.ts,test/*}` | `P0.2` | Case 15 and the fail-closed half of case 16 pass (the alternate-hostname half is P6.2); `npm test` green; unauthenticated request 403; wrong principal 403; status 200 for a reader; `cf deploy --dry-run` succeeds; `rg -q x-test-access .cloudflare/output` fails. |
| `P1.2` | D1 migration `0001_init.sql` for `store_meta`, `collector`, `origin_sync`, `generation`, `generation_object`, `remote_object`, `tombstone`, `snapshot`, `snapshot_chunk`, `snapshot_object`; local application and Miniflare schema test. | `cloudflare/migrations/**`, `cloudflare/src/db.ts`, `cloudflare/test/schema.test.mjs` | `P1.1` | The migration applies cleanly twice in Miniflare (idempotent); `cf d1 migrations apply <database-id>` is the production path (`--local` for the simulation); every table and index exists; constraint tests reject duplicate ciphertext digests and negative sizes. |
| `P1.3` | Observability config, custom span helper and allowlist, `Server-Timing` on API responses, privacy test; verify `cf migrate` preserves the block and the dry-run bundle reports it. | `cloudflare/wrangler.toml`, `cloudflare/cloudflare.config.ts`, `cloudflare/src/observe.ts`, `cloudflare/test/observe.test.mjs` | `P1.2` | The generated config contains logs 0.25, traces 0.10; `/api/v1/status` carries `Server-Timing` entries for its D1 work with values that are durations only; the allowlist test rejects a forbidden attribute (key, digest, origin, claim, path); `cf deploy --dry-run` shows the observability settings. |
| `P1.4` | Worker bench harness: seed D1/R2, run scenarios through the test harness, return counters and wall times; `make perf-worker` drives it over real HTTP. | `cloudflare/bench/**`, `cloudflare/test/serve.mjs`, `eval/bench_mirror.py` | `P1.2`, `P1.3` | `make perf-worker SCENARIO=status REPEATS=5` reports p50/p95; counters match the harness's own count; auth is required; a missing `node_modules` fails with the `npm ci` instruction instead of skipping. |
| `P1.5` | Deployment and observability machinery: extend the root `Makefile` with the worker, deploy, migrate, provision, provision-access, observe, and test-all targets; `cloudflare/scripts/deploy-gate.sh`; `cloudflare/scripts/smoke-deployed.sh`; `test:runtime` loading the built bundle; `make deploy` = gate → `worker-test worker-deploy` → `smoke-deployed`. | `Makefile`, `cloudflare/scripts/deploy-gate.sh`, `cloudflare/scripts/smoke-deployed.sh`, `cloudflare/package.json`, `cloudflare/test/{harness.mjs,runtime.test.mjs}`, this doc | `P1.4` | `make help` lists every target; `make worker-check` succeeds; with a stub `cf` and a pending-migration fixture, `make deploy` exits non-zero before `cf build` and names the file; with a stub `cf` and a stub origin, `make deploy` runs gate → bundle → test → `deploy --prebuilt` → smoke in order and never uploads; `worker-test` loads `.cloudflare/output/v0/workers/default/bundle/index.js`; `sh -n` passes. |
| `P1.6` | Provision and first deploy in the bootstrap order: `make provision` (R2 and D1, ids written to `wrangler.toml` and the generated config), `make migrate`, `make worker-deploy`, `make provision-access` (Worker-level Access app, owner policy, synthetic token bound to one origin), then `make deploy` and `make observe`; verify the unauthenticated redirect, the `workers.dev`/preview refusal, and a reader/service-token status. | `cloudflare/scripts/provision.sh`, `cloudflare/wrangler.toml`, `cloudflare/cloudflare.config.ts`, this doc | `P1.5` | `provision.sh --dry-run` lists every action; the real run records ids; `make migrate` applies `0001_init.sql` once and reports none pending on a second run; before `provision-access` every route returns 403; after it, unauthenticated is 302 and the token is 200; the collector token lands only in a `0600` file; `workers.dev` does not answer; status carries `no-store` and `Server-Timing`; `make observe` shows logs 0.25 and traces 0.10 and names the serving deployment; no memory data is uploaded. |

### P2 — Encrypted mirror

| ID | Slice | Owns | Prereq | Acceptance |
| --- | --- | --- | --- | --- |
| `P2.1` | Protocol module: constants, closed validators, error codes, cursor codec, request limits; client `mirror.py` with connection pooling (`http.client`, keep-alive), retry policy, and config parsing. Routes `status`, `hello`, `objects/missing`, `objects/{digest}`. | `cloudflare/src/protocol.ts`, `cloudflare/src/routes/sync.ts`, `src/agent_memory/mirror.py`, `tests/test_mirror.py` | `P1.2` | Case 22 passes; version mismatch is refused before writes; unsupported method 405; oversized JSON 413; a hello for an unbound origin 403; client and Worker agree on every fixture in the shared protocol JSON. |
| `P2.2` | Compression and encryption on upload: plaintext read from the local archive, zlib when it shrinks ≥5%, `rage` to the recipient set, ciphertext digest/size, `PUT` with R2 `sha256`, D1 mapping, bounded concurrency, no re-upload of known plaintext digests. | `mirror_crypto.py`, `mirror.py`, `cloudflare/src/routes/objects.ts`, `tests/test_mirror.py` | `P2.1`, `P0.2` | Cases 4, 20, and 23 pass; a retried upload of the same plaintext uploads zero bytes the second time; a corrupted ciphertext is rejected by R2 and recorded nowhere; a bounded-inflate refusal rejects an over-large payload; 4 concurrent uploads stay bounded; wrong identity restore fails safely; compression ratio and CPU are recorded per object class. |
| `P2.3` | Generation commit, manifest upload, durable ack, store identity pinning, duplicate ack, revision fencing, tombstone-first ordering, no-op path. | `cloudflare/src/routes/generations.ts`, `cloudflare/src/routes/tombstones.ts`, `mirror.py`, `sessions_cli.py`, `store.py` (schema v10 `mirror_remote(remote PK, store_id, revision, tombstone_watermark, learning_seq, learning_digest, last_sync_at, last_error)`), `tests/test_mirror.py` | `P2.2` | Cases 1–6, 8, 12, 13 pass; a changed remote `store_id` refuses to inherit local acks; unchanged sync does one hello, zero uploads, zero D1 writes; a stale revision commits nothing. |
| `P2.4` | Content-addressed recovery snapshots, `backup.snapshot` (consistent DB copy without object copying), restore into a new directory including replay of generations committed after the snapshot, tombstone merge, grant deactivation, index rebuild, `mirror verify` (manifests and snapshots always; object bodies on `--objects`, default a 100-object or 5% sample), `mirror snapshots`, `mirror gc`, `mirror rotate`. | `cloudflare/src/routes/snapshots.ts`, `store.py`, `mirror.py`, `backup.py`, `tests/test_mirror.py` | `P2.3` | Cases 1, 9, 10, 11, 21 pass; restore from a deleted local state verifies every chunk and every archive object, and replays a generation committed after the snapshot; an unchanged database creates no snapshot and uploads zero chunks; a snapshot that predates a tombstone cannot expose it; GC never removes the newest verified snapshot or a referenced object; rotation re-encrypts a small origin and restores with the new identity only; the restored store has no enabled project, no grant, and no scheduler; a corrupted object is named by digest. |

### P3 — D1 learning projection

| ID | Slice | Owns | Prereq | Acceptance |
| --- | --- | --- | --- | --- |
| `P3.1` | Local change journal: `learning_change` table, triggers on `learning_experiences`, `learning_experience_sources`, `learning_experience_links`, `learning_memories`, `learning_incidents`; prune after a durable ack, or after a recovery snapshot when the projection is off; `export_record` shared by snapshot and delta; project hashing and the explicit `mirror label` mapping. | `learning.py`, `learning_sync.py`, `experience.py`, `store.py`, `tests/test_learning.py`, `tests/test_learning_ops.py` | `P2.3` | Every real mutation path (observe, promote, retire, supersede, withdraw, forget, forget-session) leaves the journal head moved; applying all journal rows from empty equals `export_snapshot()` of the final database; `rebuild_index` preserves the journal and triggers. |
| `P3.2` | D1 projection schema and delta apply: epoch, pending, revision fence, tombstones, FTS rows, deletes; sources rewritten to the qualified `harness:native_id@origin` form; forgetting a session removes every record citing it; TS record validator ported from `validate_record` with a shared fixture parity test. | `cloudflare/migrations/0002_learning.sql`, `cloudflare/src/learning.ts`, `cloudflare/src/routes/learning.ts`, `tests/test_mirror.py`, `tests/fixtures/learning_records.json` | `P3.1`, `P2.1` | Cases 5, 6, 8, 17, 19 pass; a delta stream and a reconciled full projection of the same database are identical; an unrecognised field or a bad closed-set value is rejected by both validators; a stale delta changes nothing; a tombstone deletes the citing records and leaves no FTS hit. |
| `P3.3` | Search and inspection queries: FTS5, filters, keyset pagination, batched source fetch, detail; query-plan assertions. | `cloudflare/src/memories.ts`, `cloudflare/src/routes/memories.ts`, `cloudflare/test/search.test.mjs` | `P3.2` | `EXPLAIN QUERY PLAN` shows the FTS index and composite index, no full scans for filtered pages; a 20-result page issues ≤3 D1 queries; deep pages scan O(page); 1k/10k/100k benchmarks recorded. |
| `P3.4` | Reconciliation: paginated key/digest index, diff, reconcile begin/commit, interrupted staging invisibility, retry idempotency. | `cloudflare/src/routes/learning.ts`, `mirror.py`, `tests/test_mirror.py` | `P3.2` | Case 7, 8, 17 pass; an interrupted reconciliation shows the old epoch until commit; a repeated identical reconciliation performs zero D1 writes; a concurrent delta during staging gets 409 and retries. |

### P4 — API and UI

| ID | Slice | Owns | Prereq | Acceptance |
| --- | --- | --- | --- | --- |
| `P4.1` | Server-rendered HTML: landing with counts, last durable sync, last verified recovery point, an immediate search box, and recent retained experiences and approved memories; search with project/origin/type/kind/state filters, defaulting to retained experiences and approved memories with an explicit `state=all` for history; result summaries with timestamps and an explicit `Reviewed` / `Observed` / `Advisory` marker (never `instruction`); detail with provenance, supporting sessions, digests, applicability, and supersession/conflict links; status; empty state; responsive inline CSS; autofocus and keyboard-operable form with no script; escaping; CSP; `no-store`. Payload budget 64 KiB uncompressed per page, no external requests. | `cloudflare/src/render.ts`, `cloudflare/src/routes/html.ts`, `cloudflare/test/render.test.mjs` | `P3.3` | Case 18 and 19 pass; a record containing `<script>`, quotes, and control characters renders inert; every response carries `no-store` and CSP; an empty database renders the explainer; a 20-result page is ≤64 KiB and ≤3 requests; no page links to raw evidence or a key. |
| `P4.2` | Status page and API completeness: counts, last durable change per origin, last verified snapshot, tombstone count, storage bytes, caller identity; bounded queries. | `cloudflare/src/routes/status.ts`, `cloudflare/src/render.ts`, `cloudflare/test/status.test.mjs` | `P4.1`, `P2.4` | Status works with zero data and with data; a 20-origin fixture issues ≤10 queries; no private content in the response. |

### P5 — Integration and adversarial proof

| ID | Slice | Owns | Prereq | Acceptance |
| --- | --- | --- | --- | --- |
| `P5.1` | CLI and scheduling: `mirror configure/enable/disable/label/keygen/adopt/status/sync/verify/restore/snapshots/gc/rotate/doctor`; `sync` transport `cloudflare`; doctor fields; LaunchAgent and README setup; overlap and offline behavior; routine sync uses HTTPS only, never `cf`; `--central` query behavior is unchanged (CF25). | `sessions_cli.py`, `mirror.py`, `dotfiles/launchd/**.in`, `tools/agent-memory/README.md`, `docs/development.md`, `tests/test_mirror.py` | `P4.2` | Every documented command runs verbatim against a scratch state dir; `mirror status --json` reports pending objects and bytes, the last error, the last durable revision, and the last verified snapshot; `mirror sync --dry-run` reports estimated objects, bytes, and requests without network writes; two concurrent syncs: second exits 0 `overlapped=1`; offline sync exits non-zero with a backlog and local recall unaffected; the plist lints with `plutil -lint`; a test intercepts subprocess creation and asserts no `cf` process runs during sync; a world-readable token file is refused and a `0600` file is accepted. |
| `P5.2` | Adversarial suite: cases 1–24 in one file with real Miniflare/HTTP, including auth bypass, cross-origin isolation, corrupt/missing objects, stale revisions, concurrent collectors, malformed and oversized requests, bounded memory, and a 10-collector load run with retries under induced 429/500 responses. | `tests/test_mirror.py`, `cloudflare/test/adversarial.test.mjs` | `P5.1` | All 24 cases pass by name; the suite fails if the persistence boundary is stubbed; peak RSS increases by less than 64 MiB over the idle process while uploading an 8 MiB artifact and a 1 MiB snapshot chunk; the load run records p50/p95 latency and zero lost or duplicated records. |
| `P5.3` | Performance close-out and cleanup: run all benchmark scenarios at 1k/10k/100k, compare with baseline, record JSON and the report table, document budgets and variance; delete superseded helpers and shims and prove no caller remains; confirm restic residue is absent; run the full existing suite, Ruff, `ty`, `mdtool`, and the skill checks for touched docs. | `eval/bench_mirror.py`, `README.md`, this doc | `P5.2` | Every deterministic invariant in **Acceptance** passes; `backup create`, `backup restore`, `archive verify`, and `archive reindex` stay green; time comparisons use interleaved runs and reject regressions beyond the measured spread; `perf-gate-ready` status recorded; `rg -n -i restic` returns nothing outside the campaign records and `git log -S restic` shows only the removal; no new export lacks a caller. |

### P6 — Deploy and production validation

| ID | Slice | Owns | Prereq | Acceptance |
| --- | --- | --- | --- | --- |
| `P6.1` | Finish production deployment from `P1.6`: `make migrate` for any new migration, `make deploy`, enroll a synthetic origin with `provision.sh --access --origin <id> --label <name> --token-out <path>`, and run `make smoke-deployed` with synthetic data only. A missing permission stops before any data upload and records the exact scope. | `Makefile`, `cloudflare/scripts/provision.sh`, `cloudflare/wrangler.toml`, this doc | `P5.3` | `make deploy` ships the bundle `make worker-test` exercised; the token secret lands only in a `0600` file; a synthetic generation round-trips and restores; a refused permission reports the API and scope without claiming success. |
| `P6.2` | Validate the production deployment at `memories.17166969.xyz`; verify the custom domain, Access redirect, service-token API, and `workers.dev`/preview refusal; run `make smoke-deployed` and `make perf-deployed`, recording p50/p95/p99, CPU where reported, bytes, and R2/D1 operation counts; tombstone every synthetic session, GC its objects, and verify no synthetic row is searchable. | `cloudflare/wrangler.toml`, this doc | `P6.1` | Unauthenticated browser request redirects to Access; `workers.dev` does not answer; service-token search works; deployed benchmark JSON is recorded; no real transcript is uploaded; after cleanup no synthetic record is searchable or referenced by a live generation, and encrypted remnants in retained snapshots expire with retention. |
| `P6.3` | Independent review of durability, fencing, deletion, auth, and performance evidence; fix P1/P2 findings; final report. | touched files, this doc | `P6.2` | Review reports concrete counterexamples, not praise; every P1/P2 finding is fixed or parked with cause; the final report carries the brief's ten items with numbers: commits and changed files, deployed/blocked status, R2/D1 schema and data boundary, encryption and recovery verification, test counts, before/after local benchmarks, preview/production measurements, p50/p95/p99 and CPU/bytes/operations/throughput, the bottlenecks actually proven and the optimizations landed, the security guarantees and their limits, and remaining risks and exact setup steps. |

## Acceptance

**Reference for parity.** The existing system is the reference, not a document: the
receiver and durable-ack rules in `transfer.py:257`, the record rules in
`learning_sync.py:141`, and the restore rules in `backup.py:121`. The corpus is
`tests/test_transfer.py` (33), `tests/test_recovery.py` (8), and
`tests/test_learning_ops.py` (11); every behavior those tests prove for the local and SSH
transports gets an equivalent case against the Worker, including duplicate delivery,
corrupt objects, tombstone races, conflicting digests, and restore. The accepted
guarantees in `docs/CAMPAIGN-AGENT-ARCHIVE.md` stay in force; a mirror behavior that
contradicts one is a defect.

Correctness cases from the brief, each mapped to the slice that owns it. A slice is
accepted only when its named cases pass on the integrated tree with real Miniflare D1/R2
and real HTTP.

| # | Case | Proof |
| --- | --- | --- |
| 1 | Initial upload and full recovery | `P2.3`, `P2.4` |
| 2 | No-op sync and zero redundant writes | `P2.3`, `P5.3` |
| 3 | Changed tail with minimal upload amplification | `P2.3`, `P5.3` |
| 4 | Interrupted uploads and retries | `P2.2`, `P2.3` |
| 5 | Duplicate generation and learning delivery | `P2.3`, `P3.2` |
| 6 | Colliding native IDs across origins | `P2.3`, `P3.2` |
| 7 | Concurrent collector updates | `P2.3`, `P3.4` |
| 8 | Stale revision rejection | `P2.3`, `P3.2` |
| 9 | Tombstone-first processing | `P2.3`, `P2.4` |
| 10 | No resurrection after restore or replay | `P2.4` |
| 11 | Corrupt/missing R2 object detection | `P2.4` |
| 12 | Missing-object manifest rejection | `P2.3` |
| 13 | Invalid durable acknowledgement rejection | `P2.3` |
| 14 | Local operation during Cloudflare failure | `P5.1`, `P5.2` |
| 15 | Unauthorized read/write rejection | `P1.1`, `P5.2` |
| 16 | Authentication bypass attempts | `P1.1`, `P6.2` |
| 17 | Cross-origin data isolation | `P2.3`, `P3.2`, `P5.2` |
| 18 | Untrusted HTML escaping | `P4.1` |
| 19 | Imported advice never gains authority | `P3.2`, `P4.1` |
| 20 | Encryption/decryption failures and rotation | `P0.2`, `P2.2`, `P2.4` |
| 21 | Consistent restore of canonical records | `P2.4` |
| 22 | Large and malformed request rejection | `P2.1`, `P5.2` |
| 23 | Bounded memory consumption | `P2.2`, `P5.2` |
| 24 | Collector concurrency and backpressure | `P2.2`, `P5.2` |

Performance gates — deterministic invariants always fail the slice; time comparisons
fail only beyond the measured spread, and only on a quiet host.

| # | Invariant | Command / evidence |
| --- | --- | --- |
| F1 | No network dependency in local recall, capture, or search | `make perf-local` with no remote configured; a test patches socket creation to raise during recall, observe, refresh, and search, and an import test proves the recall/learning modules do not import the mirror client |
| F2 | Unchanged sync uploads zero objects and performs zero D1 writes | `make perf-worker SCENARIO=noop` counters; case 2 |
| F3 | Unchanged learning sends zero requests when the journal head is durable | `make perf-worker SCENARIO=learning-noop`; one `max(seq)` local query |
| F4 | Incremental sync cost tracks changed data, not corpus size | 10k-record corpus, change 3 records: uploaded bytes ≤ changed record bytes + one batch; D1 statements ≤ one batch |
| F5 | No per-object HEAD loop | one missing-object request per generation; HTTP request count recorded |
| F6 | No systematic duplicate R2 reads | commit reads no object body; restore reads each object once |
| F7 | No N+1 search query | ≤3 D1 queries for a 20-result page; `EXPLAIN QUERY PLAN` assertions |
| F8 | Bounded concurrency and batching | 4 archive uploads, 1 snapshot chunk, ≤200 statements per learning batch and ≤800 for a generation chunk insert |
| F9 | No unnecessary buffering | 1 MiB snapshot chunks and 8 MiB artifacts stream to R2 with the `sha256` option; peak RSS recorded |
| F10 | No JSON/Wasm round-trip amplification | no Wasm; controls are JSON, bodies are raw; request/byte counts recorded |
| F11 | Local recall latency not materially worse | interleaved baseline/candidate, p95 regression ≤5% or the measured spread, whichever is larger |
| F12 | Worker CPU and R2/D1 latency separately observable | custom spans, platform metrics, and the `Server-Timing` d1/r2 durations; production record |

## Needs you

| Step | Why the campaign cannot do it | Command the owner runs |
| --- | --- | --- |
| Install `age` or `rage` on each collector for real use | The campaign builds `rage` only under `.work/tools`; installing host packages is outside its grant | `brew install age` |
| Enroll the real collector, generate its keys, and store the recovery copy offline | The campaign provisions only a synthetic origin; the owner's origin id and token are theirs, and the agent must not write `~` | `agent-sessions identity show`; `cloudflare/scripts/provision.sh --access --origin <id> --label <host> --token-out <token path>` (run after the Worker exists); `agent-sessions mirror keygen --identity <identity path> --recovery <recovery path>`; copy the token and recovery identity to the password manager, keep both local files `0600`, then `agent-sessions mirror configure`. The synthetic token under `.work/secrets/` is discarded. |
| First real sync | The campaign is forbidden from touching `~/.agent-sessions` or uploading real transcripts | `agent-sessions sync --to central` with the Cloudflare config installed |
| Enable the searchable projection on the real store | It is opt-in and holds private text | `agent-sessions mirror enable --searchable-learning` |
| Install the LaunchAgent | Host-altering | `cp` the rendered plist to `~/Library/LaunchAgents` and `launchctl load` it, or use the cron line in the README |
| Inspect captured traces and CPU profiles in the dashboard | No complete CLI surface for trace contents | `make observe` prints the URLs, then Cloudflare dashboard → Workers → `usr-memories` → Traces / Logs / Profiles |

## Execution boundary and non-goals

**Authorized:** edits under `tools/agent-memory/` (including the new `cloudflare/` tree),
the root `Makefile`, `dotfiles/launchd/`, `dotfiles/base/.local/bin/`, `docs/`, and the
agent-memory README;
scratch state, worktrees, secrets, and built tools under `.work/`; `cf` read calls anywhere;
`cf` create/deploy/migration calls for the names `usr-memories`, the Worker, its Access app,
its service tokens, and its migrations; commits on `main`; read-only inspection of local
harness data.

**Forbidden:** writing `~`, running `sh sync`/host scripts/installers, touching the
`stuff`, `crates`, `npm`, or `pypi` domains or buckets, touching the `memories-poc` D1
database, uploading real transcripts, pushing, enabling CI, creating Durable Objects, KV,
Queues, Vectorize, or external databases, using restic or rclone, storing a private key or
service secret in Git or logs, enabling response caching, and unbounded remote queries.
Deleting the bucket, database, Worker, or Access application, deleting R2 objects outside
`mirror gc`, and removing a service token in use are outside the grant.

**Contract changes for the owner:**

1. `~/.agent-sessions/config.json` gains a `central.transport: "cloudflare"` variant with
   `url`, `service_token_file`, `age_recipients_file`, `age_identity_file`, and
   `learning_projection`.
2. Local schema v10 adds `mirror_remote`; the learning layer adds `learning_change` and
   triggers. Both are canonical and survive `rebuild_index`.
3. `agent-sessions` gains `mirror` subcommands; `sync` accepts the new transport. Existing
   local and SSH behavior is unchanged.
4. New Cloudflare resources named `usr-memories` (Worker, R2, D1) and one Access
   application at `memories.17166969.xyz`.
5. The searchable projection is opt-in and excludes paths, grants, and authority. The
   encrypted recovery snapshot strips grant rows and disables every project before upload.
6. The repo root gains a `Makefile` (`make help`, `make deploy`, `make test`, `make perf-*`)
   as the operator entry point. It changes no runtime, config, or wire format, and no
   collector path depends on `make`.

**Non-goals:** a second memory model; syncing local grants, sandbox policy, or agent
instructions; storing the raw event index in D1; a public UI; WebSockets; a daemon;
`dsh`/`fx` harnesses; exactly-once delivery; claiming secure erasure from provider
backups; Rust/Wasm; CI pipelines.

## Reference

| Concern | Location |
| --- | --- |
| Schema version and canonical/derived split | `tools/agent-memory/src/agent_memory/store.py:24`, `:491`, `:1940` |
| Generation manifest shape and validation | `src/agent_memory/archive.py:400`, `:329` |
| Object write, lock, and read | `archive.py:99`, `:84`, `:128` |
| Retention report and pinning | `archive.py:596`, `:605` |
| Existing sender and receiver | `transfer.py:115`, `:257`, `:332` |
| Learning snapshot export/validate/import | `learning_sync.py:73`, `:141`, `:206` |
| Learning schema and mutation paths | `learning.py:74`, `:1417`, `:1450` |
| Experience/source/link schema | `experience.py:39`, `:50`, `:56` |
| Generation commit, tombstone, durable ack | `store.py:1502`, `:1708`, `:1746` |
| Forget-session (writes a global tombstone) | `store.py:1440` |
| Backup create/restore | `backup.py:36`, `:121` |
| Local sync orchestration and config | `sessions_cli.py:259`, `:130` |
| SSH receiver entry point | `src/agent_memory/serve.py` |
| Existing scheduler templates | `dotfiles/launchd/com.josh.agent-sessions-sync.plist.in` |
| Existing benchmark pattern | `eval/bench_sessions.py:273`, `:453` |
| Perf gate contract | `dotfiles/base/.local/bin/perf-gate-ready` |
| `stuff` deployment and observability | `joshuarli/stuff:crates/stuff-worker/{wrangler.toml,cloudflare.config.ts}`, `:docs/PUBLISHING.md` |
| `stuff` bundle-once deploy and live smoke | `joshuarli/stuff:Makefile`, `:deploy/deployed-smoke.sh` |

Verified on 2026-10-31: `cf` is authenticated (OAuth, valid); the account has no
`usr-memories` resources; `memories-poc` D1 exists and is empty; the zone `17166969.xyz` is
active; `cf zero-trust access applications create --body` carries a Worker-level
`destination`, `cf workers scripts search --name` resolves the Worker id that destination
needs, and `cf zero-trust access service-tokens create` mints the collector token;
`cf migrate` carries the observability block from `wrangler.toml` into the generated
`cloudflare.config.ts`; `cf deploy --dry-run` succeeds for a TypeScript Worker with R2, D1,
a custom domain, `workers_dev=false`, and that generated config; `cf build --mode production`
emits `.cloudflare/output/v0/workers/default/bundle/index.js` and
`cf deploy --prebuilt --mode production --dry-run` accepts that exact output; D1 FTS5 with
the planned tokenizer works in Miniflare, including external-content FTS5 whose insert/update/delete
triggers add, replace, and remove matches; `rage 0.12.1` round-trips to two recipients and a valid but
unrelated identity fails with `No matching keys found`, exit 1, and no output file; a D1
`batch()` with a `BEFORE INSERT` trigger that raises `stale_revision` rolls back both the
insert and the revision advance in Miniflare; D1 `batch()` is transactional; Workers request
bodies allow 100 MB on Free/Pro, so the 8 MiB body cap is safe; R2 `put` supports a `sha256`
checksum.
