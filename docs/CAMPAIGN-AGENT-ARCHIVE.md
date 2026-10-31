# Campaign: Agent archive

Durable, cross-machine preservation and search for coding-agent sessions, and first-class Command Code (`cmd`) and Antigravity CLI (`agy`) adapters.

## Status

- **Goal:** every locally available conversation becomes durable before a harness deletes it, one central archive collects from several machines over SSH, and `agent-sessions` searches and verifies that history from any machine — with existing learning records and their authority boundaries intact.
- **Accepted:** every slice except `W3.7`. Green: `test_sessions` 65, `test_archive` 15, `test_transfer` 13, `test_identity` 4, `test_recovery` 4, `test_learning` 56, `test_learning_review` 18, `test_learning_promote` 32, `test_learning_ops` 11, `test_recall` 83.
- **Parked:** `W3.7` SSH integration is implemented and reviewed (fixed receiver command, drained stderr, watchdog timeout, required allowed origins) but was not exercised against a live `sshd`, because starting a listener is outside the execution boundary. It is on **Needs environment** and is not called tested.
- **Review:** one focused adversarial review ran before close. It reproduced six P1 defects — a stale-prefix splice on growing rewrites, invisible capture failure, a central forget that tombstoned the wrong origin, a restore that reinstated forgotten sessions and grants, a durable ack over a corrupt object, and an SSH path that could hang. All six are fixed with regression tests; the SSHD hang test remains environment-bound.
- **Baseline recorded:** see [Baseline](#baseline). Two suites are red for an environment reason, not a code reason.
- **Next slice:** none. The campaign is closed; the only open item is the environment-bound `W3.7`.
- **Reopen prompt:** `Re-execute docs/CAMPAIGN-AGENT-ARCHIVE.md for W3.7 against a disposable sshd, then re-run the recovery test.`
- **First command:** `TMPDIR="$PWD/.work/tmp" uv run --no-project --python '>=3.15' python -I tools/agent-memory/tests/test_recovery.py`

## Charter

- Decide and keep going. Record a decision only when a later slice depends on it. The doc pre-answers the contract, privacy, and authority questions; the remaining calls are delegated with a bound.
- Parity before optimization. Stage P1 and P2 must be complete and green before any P4 item starts.
- One writer by default. Parallel lanes only for the disjoint pairs named in [Sequence](#sequence), in worktrees at `.work/wt/<lane>`, never `/tmp`.
- Each commit is a Conventional Commit whose scope is the workstream (`adapters`, `archive`, `transfer`, `query`, `lifecycle`, `ops`). Put the item ID in the body. Code comments never cite this doc.
- Never weaken or delete an existing test to make a slice land. If a test is wrong, say so in the commit body and land the correction as its own commit.
- A red slice never lands on the integration branch. Fix the cause; do not add a retry around it.
- **Time-box a failing slice** at three attempts or two hours, whichever comes first. Then park it on its branch with the cause, the failing command, and the condition that would let a retry start.
- **Two loop speeds.** A slice ends on its acceptance command plus the narrowest affected suite on the integrated tree. Run every existing suite plus the new ones at the P2 gate, the P3 gate, and the close; not on every slice.
- No formatters. No pushes. No sync, install, reset, or host-config commands against the real home.
- Every effect stays inside the [execution boundary](#execution-boundary-and-non-goals). A slice that needs an effect outside it is parked with its cause, never improvised.
- **Fix egregious problems met on the way** in their own commit, to these numbers: any capture path that can silently accept bytes it did not verify, any deletion that removes canonical learning data, any command that interpolates transcript content or session IDs into a shell string, and any test that passes while its boundary is mocked away. Record anything else and leave it.

## Decisions

**Prescribed** — settled from the code, the brief, or the verified formats. Reversal conditions are stated so the owner can overrule.

| ID | Decision | Reason | Reversal |
| --- | --- | --- | --- |
| D1 | `cmd` is the canonical Command Code identifier; `command`, `command-code`, `commandcode` are aliases. `agy` is canonical for Antigravity; `antigravity` is an alias. Normalize once, at the CLI and skill boundary, before any lookup. | The brief fixes both id/alias sets. `cmd` and `agy` are the installed binary names (`cmd 1.88.2`, `agy 1.4.10`). | An alias set that collides with an existing harness or with `dsh`/`fx`. |
| D2 | The `Harness` literal gains exactly `cmd` and `agy`. `dsh` and `fx` stay out of the index in this campaign. | The brief forbids letting unrelated harnesses delay this work. | An owner request to index `dsh` or `fx`. |
| D3 | The authoritative Antigravity indexing source is `transcript_full.jsonl` when present, else `transcript.jsonl`. `logs/chunks/**` is never indexed as a separate session. | Measured: chunks are a byte-exact 100 KiB split of the same log, and `truncated_fields` appears only in `transcript.jsonl` (433 records across 8 conversations) and never in `transcript_full.jsonl`. Indexing both would double-count and silently index known-truncated text. | A future format where `_full` diverges in record count, not just content. |
| D4 | Command Code's active branch is the ancestor chain of `meta.json`'s `branchPoint` when that field exists, else the chain ending at the newest entry. All entries stay indexed and searchable. | The published format says `/fork` copies the whole tree and records `parentSessionId` + `branchPoint`, so the newest physical line can belong to a branch the session is not on. | A captured real fork where `branchPoint` is absent or disagrees with the observed tree. Capture one before trusting the fallback. |
| D5 | A `tool_result` with no recorded status field yields `outcome=None` (`unknown`). Never infer `ok` from an assistant's claim. | Command Code `tool_result` blocks carry only `content`, `tool_use_id`, `type`; no `is_error`. Antigravity records `status` (`DONE`/`RUNNING`/`ERROR`) on the result record, not the call. | A verified field that records the outcome. |
| D6 | Archive layout is content-addressed (`archive/objects/<2>/<sha256>`), with one versioned generation manifest per capture, stored in canonical SQLite tables. The path-mirrored `archive/<harness>/<abspath>` copy is retired after migration. | Measured: the current in-place copy re-copies the entire file on every append (28,348× amplification for a 1-line append to a 4 MB log) and keeps no earlier generation. | A layout that cannot satisfy the byte-verification requirement. |
| D7 | Canonical data is `learning_*`, `forgotten_sessions`, `archive_*`, `transfer_*`, `origin_*`, `project_map`, and `collector_identity`. Derived data is exactly `sessions`, `events`, `events_fts`, `index_issues`, `unindexed_sources`. Every new derived table is added to `rebuild_index`'s drop list and to `_schema_ready`; no canonical table is. | Proved by running the real code: `rebuild_index` preserves `learning_projects` and `learning_global_grant` and recreates the five derived tables. See [Foundation proof](#foundation-proof). | None. This is the safety property the whole campaign rests on. |
| D8 | Origin identity is a persisted random 128-bit id in canonical SQLite, plus a human display label. A hostname never identifies a host; MAC and hardware ids are never read. `agent-sessions identity regenerate` mints a new collector id and leaves historical origins untouched. | The brief requires it; a hostname is not identity and cloned machine state must not merge two collectors. | None. |
| D9 | A session's durable identity is `(origin_host, harness, native_id)`. A bare native id resolves only when unique; `show`/`search` print the qualified form and never silently pick among collisions. | Two hosts can legitimately use the same native id; the brief forbids overwriting one with the other. | None. |
| D10 | A logical project is an `origin_host` + an explicit mapping name. A normalized Git remote may *suggest* a mapping in `doctor` output; it never creates or merges one. The central host never runs Git in, or `chdir`s to, a foreign `cwd`. | The brief forbids silent merging and foreign path interpretation. Matching basenames and remotes are not evidence of one project. | None. |
| D11 | Transfer is at-least-once with idempotent ingestion. The sender marks a generation remotely durable only after the receiver has durably published every referenced object and the manifest row. Re-delivery of an accepted generation is a no-op that re-emits the ack. | The brief requires precise acks and forbids claiming exactly-once. | None. |
| D12 | Transport is a fixed receiver command reading length-prefixed frames on stdin and writing frames on stdout. No transcript content, query, path, or session id is ever interpolated into a remote command string. The local transport calls the same receiver function in-process. | Quoting bugs are the obvious failure; one code path is the only way to prove local and remote agree. | A protocol version bump. |
| D13 | Default capture boundary is the chosen transcript source plus the verified sidecar set (`<id>.meta.json`, `<id>.checkpoints.jsonl`, `<id>.prompts.jsonl`, `<id>.share.json` for `cmd`; `conversation_summaries.db` row for `agy`). `agy` `tasks/`, `steps/`, `messages/`, `scratch/`, and Command Code `file-history/` and the scratchpad are outside the boundary; `doctor` reports their counts and bytes as `artifacts_excluded`. `--artifacts` captures them under a per-file 8 MiB cap and 200 artifacts per session. Ephemeral sessions and learning-worker sessions stay excluded from capture and archive, and an absent native transcript never licenses recovering an intentionally non-persistent conversation from another source. | Measured sizes for 8 Antigravity conversations: logs 24.3 MB, steps 9.1 MB (1,327 files), tasks 1.5 MB, messages 0.7 MB. A conservative default keeps raw private data lean; the tool-output artifacts are real evidence, so the opt-in must exist. Ephemeral and worker exclusions are existing behavior the brief requires preserving. | An owner decision that artifact capture is the default. |
| D14 | `forget-session` remains the only deletion entry point. It writes a canonical tombstone keyed by `(origin_host, harness, native_id)` with a scope of `local` or `global`, propagates through the transfer protocol, and is applied before any received or restored data becomes searchable. A native cleanup event is never recorded as an intentional global deletion. | The brief requires extending existing semantics, not a competing system, and forbids letting native cleanup masquerade as a global delete. | None. |
| D15 | Imported memory records carry their origin and evidence. Applicability is revalidated against the requesting checkout; imported records never import a grant, a review authorization, a tool permission, or a project trust. | The brief forbids synchronizing authority. | None. |
| D16 | `restic` is an optional external integration behind configuration. Core collect/search/sync/restore work with no `restic` installed; its absence is an actionable `doctor` line, not an error. Backups additionally produce a self-contained SQLite-API snapshot plus a manifest pinning object digests, so restore works without `restic`. | The brief requires both. Two independent mechanisms also means a broken `restic` cannot remove the ability to recover. | None. |
| D17 | Restore always targets a new destination path by default. `--in-place` must be explicit and refuses unless the target is a `Store` directory whose backup manifest matches. | The brief requires new-destination default. | None. |
| D18 | Schema migrations use `BEGIN IMMEDIATE` in one transaction, bump `PRAGMA user_version` last, and refuse to open a newer version without writing. A consistent backup is taken before any migration that rewrites a canonical table. | `store.py:24` shows the existing versioned scheme; the brief requires transactional, recoverable migration. | None. |
| D19 | An unchanged refresh must read zero content bytes. A changed source may be read once end to end, because no prefix is reused without hashing it; a one-line append to a 4 MB log must write at most `append_bytes + 64 KiB` to the archive. | Measured today: unchanged refresh is already 0 content bytes; the old archive wrote 4.19 MB per append. A review found that verifying only the tail before reusing a prefix let a rewrite splice stale bytes into a new generation, so the read bound was dropped in favour of correctness and the write bound kept. | A chunking scheme that proves the prefix unchanged without reading it. |

**Delegated** — the executor decides inside the stated bound and records it in the commit body.

| ID | Bound |
| --- | --- |
| G1 | Chunking granularity for incremental capture: any fixed or rolling scheme whose measured append cost satisfies D19 and whose unchanged cost is zero content bytes. Prefer the simplest that passes; do not build a general dedup engine. |
| G2 | The `cmd` compaction entry's field names are unverified. Recognize it by its entry type, preserve the raw record, and emit `unknown:<type>` until a real compaction record is captured. Never guess a field name. Add the parser branch and a fixture only after capturing one. |
| G3 | The `agy` tool-call identity is synthesized from `(step_index, ordinal)` because the format records no id. Mark it synthesized in the event row so `show` does not imply a native id exists. |
| G4 | Backoff constants, frame size limits, and timeouts: bounded, documented in one place, and tested at the boundary. Defaults: 30 s connect, 120 s per frame, 5 attempts, exponential 1–60 s. |
| G5 | Whether `agy` `steps/*/output.txt` duplicates `transcript_full` content is unmeasured. Answer it while implementing `--artifacts`; if it duplicates, do not capture it by default even under the flag, and say so in the support matrix. |

## Baseline

### Known red, and why it is not ours

`test_learning` (56 errors) and `test_learning_promote` (31 errors) fail before any change, on `FileNotFoundError: <scratch>/usr/.git/info/exclude`. `git init` on this host resolves its template directory to `~/.local/share/git-core/templates`, which does not exist, so it does not create `.git/info/`. Same tests pass with `GIT_TEMPLATE_DIR=/opt/homebrew/share/git-core/templates`.

Do not "fix" this in the repo and do not let it mask a real regression. Run those two suites with `GIT_TEMPLATE_DIR=/opt/homebrew/share/git-core/templates` and note the environment cause. `test_sessions`, `test_recall`, `test_learning_review`, and `test_learning_ops` are green without it.

### Loop timings (this host, under unrelated load)

| Suite | Result | Wall |
| --- | --- | --- |
| `tests/test_sessions.py` | 56 OK | 7.3 s |
| `tests/test_learning_review.py` | 18 OK | 8.6 s |
| `tests/test_learning_ops.py` | 11 OK | 0.2 s |
| `tests/test_recall.py` | 83 OK | 97 s |
| `tests/test_learning.py` (with `GIT_TEMPLATE_DIR`) | 56 OK | 148 s |

`perf-gate-ready` exits 75: the host is busy with an unrelated `cargo test` and OrbStack. **Time-based gates are deferred for this plan.** Do not treat the absence of timings as a pass; re-run the gate when the host is idle and record `perf gate deferred: host busy` if it is not.

### Work performed, measured

`eval/bench_sessions.py --sessions 200 --messages 10 --projects 10` (2,600 events, 472,590 source bytes):

| Operation | bytes read | content opens | stat ops | SQLite changes |
| --- | --- | --- | --- | --- |
| fresh index | 506,390 | 400 | 800 | 23,579 |
| one-line append (504 B) | 504 | 3 | 403 | 8 |
| unchanged refresh | 0 | 0 | 400 | 0 |

The index already has the property D19 requires. The archive does not:

| Archive measurement (4.19 MB log) | Value |
| --- | --- |
| initial capture | 4,194,765 B, 1 copy |
| unchanged refresh | 0 B |
| 10 single-line appends (1,480 B total) | 41,955,790 B copied |
| amplification | 28,348× |
| generations retained on disk | 1 |
| **after:** one 160 B append | 160 B written; 17,848 B read (one pass + tail) |
| **after:** generations retained | 2, oldest still resolvable |

### Existing test coverage the campaign must not regress

`test_sessions.py` already covers same-size rewrite with restored mtime (index), archive fallback after deletion, archive move, `forget-session` purge, symlinked companions, and learning-worker exclusion. Read those before changing `_archive_copy`: the new capture path must keep every one of them meaningful, re-pointed at the new layout rather than deleted.

### Foundation proof

From `.work/tmp`, running the real `Store` and `rebuild_index`:

- `rebuild_index` preserved `learning_projects` and `learning_global_grant` and recreated the five derived tables empty. D7 is proved at blast-radius rung 4.
- An equal-size rewrite with a restored mtime left the archived copy holding the **old** bytes while the index reset to the new ones. After source deletion the archive cannot satisfy the digest, so evidence becomes unavailable even though a copy exists. This is the concrete defect D6 and `W2.2` remove; it is also the reason `W2.1` must not trust size and mtime.

## Sequence

Phases: **P1 adapters** → **P2 archive** → **P3 transfer** → **P4 query/lifecycle** → **P5 ops and close**. P1 and P2 are disjoint by file and may run as two lanes. Within P1, `W1.1`→`W1.2` and `W1.3`→`W1.4` are serial; the two chains are disjoint and may run in parallel only after `W1.1` lands the shared `types.py` and fixture helpers.

### P1 — Adapters

| ID | Slice | Owns | Prereq | Acceptance |
| --- | --- | --- | --- | --- |
| `W1.1` | Add `cmd`/`agy` to the closed harness set, alias normalization, default roots, and source-name discovery that excludes sidecars and chunks. | `types.py`, `transcripts.py` (`Harness`, `default_roots`, `is_source_name`, `coerce_roots`), `sessions_cli.py` (`--harness` choices), `tests/test_sessions.py` | — | `test_sessions.py` green; a new test asserts `*.checkpoints.jsonl`, `*.meta.json`, `logs/chunks/**`, and `transcript_full.jsonl` are not admitted as separate sessions. |
| `W1.2` | Command Code normalization: content blocks, tool ids, `parentId` ancestry, active branch from `branchPoint`, unknown-entry preservation. | `transcripts.py` (`_cmd_record`, `_cmd_header`, `normalize`), `store.py` (`active_branch` caller), `tests/test_sessions.py` | `W1.1` | Golden fixture test: user/assistant/thinking/tool-call/tool-result events, one fork whose newest line is off the active branch, unknown entry type preserved as `unknown:`. |
| `W1.3` | Antigravity discovery: choose `_full` over `transcript`, never index chunks, read workspace and lineage from `conversation_summaries.db` read-only, report absent/truncated/`step_count` mismatch. | `transcripts.py` (Antigravity header/discovery), `store.py` (database-harness handling if reused), `tests/test_sessions.py` | `W1.1` | Golden fixture test: multi-workspace session reports all workspaces and refuses to pick one; missing DB reports `workspace_unknown`; `step_count` mismatch reports `truncated`. |
| `W1.4` | Antigravity normalization: `USER_INPUT`, `PLANNER_RESPONSE`, `GENERIC`, `SYSTEM_MESSAGE`, `CHECKPOINT`, `tool_calls` with synthesized ids, `status=ERROR` → `outcome=error`, `truncated_fields` surfaced. | `transcripts.py`, `tests/test_sessions.py` | `W1.3` | Golden fixture test: error result yields `outcome=error`; a `DONE` call with no result yields `unknown`; `CHECKPOINT` is `compacted`; unknown type preserved. |
| `W1.5` | Branch-safe experience detection: detectors read only the active branch; both new harnesses feed `agent-learn observe` and review eligibility only when named. | `learning.py` (review harness gate), `experience.py` (branch window), `store.py` (`active_branch`) | `W1.2`, `W1.4` | A test proves a failure on an abandoned `cmd` branch is never paired with a success on the active branch; `enable` without `--harness cmd` never reviews a `cmd` session. |
| `W1.6` | Move `cmd`/`agy` from "not yet indexed" to the indexed path in the skills and docs; add alias rows; update the support matrix. | `dotfiles/base/.agents/skills/resume-session/SKILL.md`, `session-handoff/SKILL.md`, `README.md`, `docs/development.md` | `W1.4` | `sh dotfiles/skills-check.sh dotfiles/base/.agents/skills`; `mdtool check --untracked` on changed docs; `agent-sessions show cmd:<id>` and `agy:<id>` from a scratch fixture state dir. |

### P2 — Local archive

| ID | Slice | Owns | Prereq | Acceptance |
| --- | --- | --- | --- | --- |
| `W2.1` | Canonical archive schema (v7): `archive_object`, `archive_generation`, `archive_artifact`, `collector_identity`, `origin_host`, `project_map`, `transfer_*`, `tombstone`. Derived/allowed split per D7; `rebuild_index` and `_schema_ready` updated together. | `store.py`, `tests/test_sessions.py`, new `tests/test_archive.py` | `W1.1` | Migration test: v6 → v7 preserves every session, event, learning record, and tombstone; `rebuild_index` preserves the new canonical tables (extend the existing proof). |
| `W2.2` | Content-addressed capture: chunked append, per-generation manifest, generation retention on rewrite/truncation, full-digest change detection that ignores size and mtime. | `store.py` (new `archive.py`), `tests/test_archive.py` | `W2.1` | Append 1 line to a 4 MB log: bytes written ≤ append + 64 KiB, generations = 2, both retrievable. Equal-size rewrite with restored mtime: new generation, old generation retained, digest differs. |
| `W2.3` | Crash-safe publication: `O_EXCL` unique staging names, `fsync` file and parent directory, atomic rename, startup recovery of orphan staging, cross-filesystem capture, and explicit disk-full and permission-denied handling that reports failure instead of dropping a generation. | `archive.py`, `tests/test_archive.py` | `W2.2` | A test interrupts at each publication boundary (staging written, file synced, renamed, manifest committed) by injecting `OSError`, then asserts recovery leaves either the old generation intact or the new one complete, never a half state. A permission and a `ENOSPC` case each fail loudly and leave the previous generation resolvable. |
| `W2.4` | Migrate the path-mirrored archive into CAS: consistent backup first, verify digests, keep the old tree readable until migration reports complete, then remove it in its own commit. | `store.py`, `tests/test_archive.py`, `README.md` | `W2.3` | Migration on a fixture state dir with 3 harnesses and a Grok companion set: every session's evidence still resolves at the same position and digest; `doctor` reports `archive_migrated=1`. |
| `W2.5` | Active-file guarantee: respect Command Code's per-turn commit boundary, never advance past a partial tail, record `partial_bytes` and diagnostic offsets, retry instead of inventing an atomic snapshot, and retain or explicitly report oversized input rather than truncating it while labelling the session complete. | `store.py` (`_refresh_file`), `tests/test_archive.py` | `W2.2` | A test appending a half line then completing it indexes the record once, with `partial_bytes>0` in between and no cursor advance past the tail. A record above the input limit leaves the session `degraded` with a reported issue, never `complete`. |
| `W2.6` | Keep OpenCode's extraction path: read-only DB, session/message tables only, never copy credentials or the live WAL as files; archived DB still satisfies digests. | `store.py`, `tests/test_sessions.py` | `W2.1` | Existing OpenCode tests stay green; a test asserts the archive contains no `account`/`credential` table and that evidence verifies from the archived DB. |

### P3 — Identity and transfer

| ID | Slice | Owns | Prereq | Acceptance |
| --- | --- | --- | --- | --- |
| `W3.1` | Origin and collector identity: random id, display label, `identity show`/`regenerate`, `origin_host` table, provenance columns on sessions and generations. | `archive.py`, `sessions_cli.py`, `tests/test_identity.py` | `W2.1` | Regenerating a collector id leaves historical `origin_host` rows unchanged; two scratch homes produce two distinct origins; no hostname is used as identity. |
| `W3.2` | Qualified session identity and divergent continuations: `(origin_host, harness, native_id)`; bare-id resolution only when unique; explicit filters for collisions. | `store.py`, `sessions_cli.py`, `tests/test_identity.py` | `W3.1` | Two origins with the same native id both survive and are both searchable; bare `show <id>` errors with the candidates listed instead of picking one. |
| `W3.3` | Project mapping: logical project vs checkout path, explicit `project map`, `project list`, ambiguity reporting; no Git execution on foreign paths. | `archive.py`, `sessions_cli.py`, `tests/test_identity.py` | `W3.1` | A test proves the central side never invokes `git` with a foreign `cwd` (subprocess is intercepted and asserted unused); two repos sharing a basename stay separate until explicitly mapped. |
| `W3.4` | Transfer protocol v1: length-prefixed frames under a stated byte cap, fixed receiver entry point, manifest with object digests and sizes, digest/size verification before acceptance, idempotent re-delivery, conflict rejection, protocol-version refusal, one serialized catalog writer with concurrent read-only readers, and a manifest field that separates `stored` from `indexed`. | new `transfer.py`, `tests/test_transfer.py` | `W2.3`, `W3.2` | Duplicate delivery acks twice and stores once; corrupted frame is rejected with a typed error; unsupported protocol version is refused without writing; two concurrent senders both commit while a third process reads without a lock error; a stored-but-unindexed generation is reported as stored, not searchable. |
| `W3.5` | Local transport using the same receiver function, for offline tests and as the default until a remote is configured. | `transfer.py`, `tests/test_transfer.py` | `W3.4` | The same test matrix runs over the in-process transport and the SSH transport from identical fixtures. |
| `W3.6` | Durable ack semantics and backlog: remote-durable only after all objects and the manifest commit; persistent local backlog while offline; bounded retry/backoff; resumable progress; disk-pressure and outage status. | `transfer.py`, `store.py`, `tests/test_transfer.py` | `W3.4` | Drop the ack after commit: sender retries, receiver no-ops, sender then marks durable. Kill the sender mid-batch: the next run resumes without re-uploading accepted objects. |
| `W3.7` | SSH transport hardening and integration test against a disposable local `sshd`, when available. | `transfer.py`, `tests/test_transfer.py` | `W3.4` | With a throwaway sshd on a high port and a scratch key, a session with spaces, quotes, and shell metacharacters in its cwd syncs and verifies. If no sshd can be started, record it under [Needs environment](#needs-environment); do not call SSH tested. |

### P4 — Query, handoff, lifecycle

| ID | Slice | Owns | Prereq | Acceptance |
| --- | --- | --- | --- | --- |
| `W4.1` | Central queries: `search`/`recent`/`show --central`, configured remote, explicit failure or labeled partial result, no silent local-only completion. Every result names origin host, harness, native id, project or workspace, coverage, captured generation, and the evidence reference. | `sessions_cli.py`, `store.py`, `transfer.py`, `tests/test_transfer.py` | `W3.6` | With the central unreachable, a `--central` query exits non-zero and says so; it never prints "matches=0" as if the search were complete. Every printed result line carries the seven identity fields. |
| `W4.2` | Remote `show` verifies archived evidence from the central store alone: source host absent, no original filesystem, digest checked against the captured generation. | `store.py`, `sessions_cli.py`, `tests/test_recovery.py` | `W4.1` | Delete the source scratch home, then `show --central <session> --position <byte>` returns the same text and digest as before deletion, or a typed `EvidenceChanged`. |
| `W4.3` | Tombstones: scope `local`/`global`, propagation, pre-exposure application, withdrawal of derived records, and a status line per state (`applied_local`, `acked_central`, `pending_remote`, `in_backup`). | `store.py`, `learning.py`, `transfer.py`, `tests/test_learning_ops.py` | `W4.2` | Forget locally, sync, then replay an older generation from a restored backup: the session is not searchable and its derived experiences are withdrawn. |
| `W4.4` | Cross-host memory exposure with origin and evidence, applicability revalidated against the requesting checkout, no imported authority, and the existing small conflict model: independent records are preserved, supersession and withdrawal are respected, unresolved contradictions stay `conflict_unresolved`, and imported text is data, never an instruction. | `recall.py`, `learning.py`, `tests/test_recall.py` | `W4.3` | A memory whose source conditions fail in the requesting checkout is returned as `lead`/`needs_revalidation`, never `instruction`; a copied history on a second host is not counted as independent evidence; both sides of an unresolved contradiction come back as leads. |
| `W4.5` | Handoff integration: `resume-session` and `session-handoff` use the indexed adapters for both harnesses; native-resume info names owning host, workspace, command, and surviving native state; handoff never executes a recovered command. | the two `SKILL.md` files, `README.md` | `W4.2` | Skills checker green; a test asserts the recorded native command is printed and never executed. |

### P5 — Ops, proof, close

| ID | Slice | Owns | Prereq | Acceptance |
| --- | --- | --- | --- | --- |
| `W5.1` | Model-free `sync` command with explicit opt-in scheduling: LaunchAgent template, portable cron line, overlap lock, sleep/wake and offline behavior; nothing installed on the real machine. The existing `agent-learn hook` may submit a local hint only, never block a session on network access, and periodic reconciliation recovers missed hints. | `sessions_cli.py`, `transfer.py`, `dotfiles/launchd/*.in`, `README.md` | `W4.1` | Two concurrent `sync` runs: the second exits 0 with `overlapped` and does nothing. Scheduler templates are checked with `sh -n` and `plutil -lint`. With the remote unreachable, the hook still returns promptly and a later `sync` delivers the generation. |
| `W5.2` | `doctor --json`: native discovery and unsupported formats, capture failures, missing artifacts, local progress, pending remote content and last durable ack, central indexing progress, ambiguous mappings, integrity, pending deletions, backup health. | `sessions_cli.py`, `transfer.py` | `W5.1` | A fixture with one offline remote, one unacked generation, one ambiguous mapping, and one pending tombstone produces every field, and `--json` parses with `jaq`. |
| `W5.3` | Consistent backup: SQLite backup API snapshot plus a manifest pinning object digests; GC refuses to remove a pinned object and never removes unacknowledged local evidence; retention documented. | `archive.py`, `sessions_cli.py`, `tests/test_recovery.py` | `W3.6` | Run backup concurrently with capture and GC under a loop; every object named in the manifest exists and verifies after the run, and no unacknowledged generation is collected. |
| `W5.4` | Optional `restic` integration through configuration, with R2-compatible S3 support delegated to `restic`; absent `restic` gives an actionable line. | `archive.py`, `README.md` | `W5.3` | With `restic` absent, `backup create` still succeeds using the built-in snapshot and `doctor` names the missing optional dependency. |
| `W5.5` | Restore into a new destination: schema/protocol compatibility check, digest and integrity verification, canonical and learning records restored, current tombstones reapplied before exposure, derived indexes rebuilt, provenance preserved, no services or grants activated. | `archive.py`, `sessions_cli.py`, `tests/test_recovery.py` | `W5.3`, `W4.3` | Restore an old backup that predates a tombstone: the restored store is searchable except the forgotten session, and no review grant is active. |
| `W5.6` | Mandatory recovery scenario: two scratch source homes, one central store. Ingest both harnesses, interrupt and retry a transfer, verify acks, delete source data, rebuild the central derived index, search and inspect from the central archive, restore onto a third scratch host, verify hashes, identities, lineage, learning records, and tombstones. | `tests/test_recovery.py` | `W5.5`, `W3.7` | The test asserts the essential criterion: after a durable ack, deleting the source home does not prevent verified retrieval; after restore, no forgotten session reappears and no grant is active. |
| `W5.7` | Measure and record: initial ingestion, unchanged refresh, small append to a large log, small incremental sync, large tool output, search and show, restart after interrupted capture and transfer. Track bytes read/uploaded and work done, not only elapsed time. | `eval/bench_sessions.py`, `eval/bench_archive.py` (new) | `W5.6` | Numbers recorded in `README.md` against D19's bounds. Time-based numbers only when `perf-gate-ready` exits 0; otherwise state the deferral. |
| `W5.8` | Documentation close-out: setup guide, security and data boundaries (raw archives unredacted and private, redacted presentation separate, nothing raw in logs, Git, diagnostics, or tests), the crash-versus-power-loss guarantee statement, format support matrix, exact recovery commands, the freeze-and-test rule for the documented CLI syntax, and `docs/development.md` rows for every new suite. Run Ruff, `ty`, shell checks, and doc-reference checks. | `README.md`, `docs/development.md`, `docs/agent-learning.md` | `W5.7` | `mdtool check --untracked` on changed docs; every new test file appears in the development-check table; `uvx ruff check` and `uvx ty check` clean on changed Python; every documented command runs verbatim against a scratch state dir. |
| `W5.9` | Independent review of durability, identity, migration, and deletion paths, then fix P1/P2 findings. | the touched files | `W5.8` | Review reports concrete counterexamples, not praise. Each P1/P2 finding is fixed or parked with cause. |

## Acceptance

Each deliverable with its proof and threshold. A slice is accepted only when its row passes on the integrated tree.

| # | Deliverable | Proof | Threshold |
| --- | --- | --- | --- |
| 1 | `cmd` is first class | fixture + `test_sessions.py` | Every verified entry kind normalizes; fork active branch correct; unknown types preserved; sidecars never become sessions |
| 2 | `agy` is first class | fixture + `test_sessions.py` | `_full` preferred; chunks never indexed; workspace, lineage, truncation reported; no empty-success session |
| 3 | Raw evidence is durable | `tests/test_archive.py` | Every capture is a verified, immutable generation; append cost ≤ D19; earlier generations survive rewrite and truncation |
| 4 | Capture is crash safe | `tests/test_archive.py` | No interruption point leaves a half-published generation or an advanced cursor |
| 5 | Identity and project mapping | `tests/test_identity.py` | Same native id on two hosts both survive; no silent merge; no foreign Git |
| 6 | Central transfer | `tests/test_transfer.py` | Duplicate, corrupted, missing, out-of-order, conflicting, and wrong-version deliveries all resolve without loss or silent acceptance |
| 7 | Remote query and inspection | `tests/test_transfer.py`, `tests/test_recovery.py` | Outage is explicit, never silently complete; `show` verifies from the archive with the source gone |
| 8 | Forgetting is durable | `tests/test_learning_ops.py`, `tests/test_recovery.py` | Tombstone beats a replayed generation and a restored backup; dependent records withdrawn |
| 9 | Learning boundaries hold | `tests/test_recall.py` | No imported record becomes an instruction or a grant; no copied history counts as independent |
| 10 | Backup and restore | `tests/test_recovery.py` | Restored store verifies every object, keeps provenance, reapplies tombstones, rebuilds indexes, activates nothing |
| 11 | Roles stay distinct | docs + `tests/test_identity.py` | Transcript preservation, search, handoff, native resume, and live attachment are described and labelled separately; no claim that archiving recovers a process |
| 12 | Full recovery scenario | `tests/test_recovery.py` | The essential criterion holds end to end |

### Parity register

The reference for both new adapters is the **existing six-adapter contract**, not a document: the normalized record shape and the behaviors `tests/test_sessions.py` already asserts for Codex, Claude, Muse, Grok, OpenCode, and Pi. The oracle is those tests plus the real local transcripts read in the support matrix above. The reference for the archive is the current `_archive_copy` path and the seven existing archive and evidence tests.

Every behavior below needs a test that fails if the adapter gets it wrong. Run a behavior's single case by name while building it; run the whole file at each P1 and P2 gate.

| Behavior | `cmd` | `agy` |
| --- | --- | --- |
| One native session per transcript; sidecars and duplicate representations excluded | `W1.1` test | `W1.1` + `W1.3` tests |
| Native id, qualified id, alias normalization | `W1.1` | `W1.1` |
| Workspace and project identity | header `cwd` | `workspace_uris`; multi-workspace reported, never first-picked |
| Ancestry and subagent lineage | `parentId`; fork via `branchPoint` | `parent_conversation_id` + `nesting_depth` |
| User, assistant, tool-call, tool-result, compaction events | `W1.2` | `W1.4` |
| Tool-call identity and parentage | native `tool_use.id` | synthesized `(step_index, ordinal)`, labelled |
| Outcome `ok`/`error`/`unknown` | `unknown` unless verified (D5) | `status` field, `ERROR` → `error` |
| Active-branch selection | `W1.2` fork fixture | unverified; report `ancestry=unknown` |
| Coverage `complete`/`degraded`/`unsupported` | unsupported when nonempty and ununderstood | same, plus `truncated` on `truncated_fields` or `step_count` mismatch |
| Archive capture and digest-verified evidence | existing archive tests, re-pointed | same |
| Review eligibility only when named | `W1.5` | `W1.5` |

**Oracle test:** for each new adapter, break one normalization branch on purpose and confirm its golden fixture fails before restoring it. A fixture that still passes proves nothing.

**Intentional differences, recorded once:** `agy` tool calls have no native id (G3); the `cmd` compaction entry's field names are unverified (G2); `agy` ancestry is unverified, so it is reported unknown rather than invented.

**What the corpus does not cover:** a real `cmd` fork, rewind, or compaction transcript; a real `agy` `/fork` persistence sample; and a multi-workspace `agy` conversation (the format allows an array, the sample only had singletons). Capture one of each, sanitize it, and add it to the corpus before claiming those behaviors.


## Needs environment

| Item | Why it cannot run here | Command the owner would run |
| --- | --- | --- |
| Real SSH destination | No destination is configured, and none may be invented. | `agent-sessions sync --to <alias> --dry-run` after configuring `~/.config/agent-sessions/config.json` |
| Disposable `sshd` integration (`W3.7`) | `/usr/sbin/sshd` exists but starting a listener is outside the execution boundary. | start `sshd` on a high port with a scratch key, then run `agent-sessions sync --to <alias>` against `agent-sessions-serve ingest --protocol 1 --origin <id>` |
| `restic` and R2/S3 destination | `restic` is not installed and no bucket may be created. | `agent-sessions backup create --restic --repo <url>` |
| LaunchAgent and cron activation | Installing a service on the real machine is forbidden. | `plutil -lint` on the template, then the owner's install step |
| Perf-gated timings | Host busy; `perf-gate-ready` exits 75. | `sh dotfiles/perf-gate-ready-test.sh` then the bench, on an idle host |

## Execution boundary and non-goals

**Authorized:** edits under `tools/agent-memory/`, `dotfiles/base/.agents/skills/`, `dotfiles/base/.local/bin/` launchers, `dotfiles/launchd/`, `docs/`, and `tools/agent-memory/README.md`; scratch state under `.work/`; commits on a working branch; read-only inspection of local harness directories.

**Forbidden:** running `sh sync`, `host/macos/*`, `host/setup-*`, reset scripts, or an installer; writing to `~`; pushing; creating cloud resources or buckets; enabling background services; uploading real transcripts anywhere; configuring a real remote without an owner-supplied destination; changing model selections, permission modes, sandbox settings, or existing paid-review grants; interpolating transcript content, paths, or session ids into a shell command; synchronizing a writable SQLite database between hosts; `rsync --delete` or bidirectional file sync as the lifecycle model; hard-linking a native transcript.

**Contract changes for the owner:**

1. `Harness` gains `cmd` and `agy`; `agent-sessions --harness` and `agent-learn enable --harness` accept them (closed-set widening).
2. Schema v7 adds canonical tables; `rebuild_index`'s drop list grows to cover new derived tables only.
3. The archive layout moves from path-mirrored files to content-addressed objects; the old tree is retired after a verified migration.
4. Session identity becomes `(origin_host, harness, native_id)`; a bare id that is not unique becomes an error instead of a match.
5. `agent-sessions` gains `sync`, `identity`, `project`, `archive`, and `backup`/`restore` subcommands, and `--central` on `search`/`recent`/`show`.
6. `forget-session` gains a scope and a tombstone; it remains the only deletion entry point.

**Non-goals:** `dsh`, `fx`, or other harnesses; mobile UI; ACP gateway; Rex integration; live process migration; a public web server, message broker, distributed database, CRDT, or new agent runtime; systemd or D-Bus as a requirement; a wholesale rewrite or language migration; exactly-once transport; immediate erasure from offline machines or immutable backups.

## Reference

### Verified format support matrix

Provenance: read-only inspection of the local installs on 2026-10-30, plus the publishers' current documentation. Nothing here is inferred from another harness's format.

| | Command Code | Antigravity CLI |
| --- | --- | --- |
| Version verified | `cmd 1.88.2`; transcript `version: 3` | `agy 1.4.10`; language server 1.4.10 |
| Root | `~/.commandcode/projects/<cwd-slug>/` | `~/.gemini/antigravity-cli/brain/<conversation-id>/` |
| Source | `<session-id>.jsonl` | `.system_generated/logs/transcript_full.jsonl`, else `transcript.jsonl` |
| Header | `{type:"session", version, id, cwd, timestamp}` | none; identity from directory name |
| Entry | `{type, id, parentId, timestamp, message?, model?, effort?, usage?}` | `{type, created_at, source, status, step_index, content?, tool_calls?, tokens?, truncated_fields?}` |
| Ancestry | `parentId` tree | none; `parent_conversation_id` + `nesting_depth` in `conversation_summaries.db` |
| Entry types seen | `session`, `message`, `model_change` | `USER_INPUT`, `PLANNER_RESPONSE`, `GENERIC`, `SYSTEM_MESSAGE`, `CHECKPOINT` |
| Tool call | `tool_use{id,name,input}` | `tool_calls[]{name,args}` — **no id** |
| Tool result | `tool_result{tool_use_id,content}` — **no status** | separate `GENERIC` record, `status` `DONE`/`RUNNING`/`ERROR` |
| Branch selection | `meta.json` `parentSessionId` + `branchPoint` (fork) or newest entry | `/fork`, `/rewind`, `/undo` documented; persistence mechanism unverified |
| Compaction | entry type documented, **field names unverified** | `CHECKPOINT` record |
| Truncation | none observed | `truncated_fields` on 433 records in `transcript.jsonl`, none in `transcript_full.jsonl` |
| Workspace | header `cwd` | `conversation_summaries.db` `workspace_uris` (JSON array of `file://` URIs) |
| Sidecars | `.meta.json`, `.checkpoints.jsonl`, `.prompts.jsonl`, `.share.json`; `file-history/<id>/` | `conversation_summaries.db`; `annotations/<id>.pbtxt`; `tasks/`, `steps/`, `messages/`, `scratch/` |
| Duplicate representations | none observed | `transcript`, `transcript_full`, and `chunks/` — chunks concatenate byte-exactly to their parent log |
| Local sample | 13 sessions, 4,876 messages | 8 conversations, ~3,500 records, 8 DB rows |

Command Code's published durability claims, which the capture path may rely on: per-turn commit, an appends-only transcript that is never rewritten in place, and torn lines being skipped on load. Antigravity publishes no transcript durability claim, and its `/resume` verifies a conversation against the backend, so a resumable cloud conversation is not evidence of a complete local log. Do not conflate Antigravity CLI with Gemini CLI, the Antigravity app, or the IDE; imported App conversations can appear as CLI conversations.

**Honest coverage limits:** no real Command Code fork, rewind, or compaction sample was available; the fork rule comes from the publisher's documentation and a synthetic fixture. No Antigravity `/fork` persistence sample was available. `tool_calls` carry no native id, so identity is synthesized. `.prompts.jsonl` and `.share.json` were absent locally and are handled as optional. Artifact duplication between `steps/*/output.txt` and `transcript_full` is unmeasured (G5).

### Code map

| Concern | Location |
| --- | --- |
| Closed harness set | `src/agent_memory/types.py:11`, `:14` |
| Default roots | `src/agent_memory/transcripts.py:80` |
| Source-name filter | `src/agent_memory/transcripts.py:120` |
| Normalizers | `src/agent_memory/transcripts.py:488` |
| Header and ancestry | `src/agent_memory/transcripts.py:566` |
| Schema version and companions | `src/agent_memory/store.py:24`, `:26` |
| In-place archive copy | `src/agent_memory/store.py:283` |
| Size/mtime skip guard | `src/agent_memory/store.py:296` |
| Branch selection | `src/agent_memory/store.py:310` |
| Refresh and admission | `src/agent_memory/store.py:565` |
| File indexing cursor | `src/agent_memory/store.py:973` |
| Evidence resolution | `src/agent_memory/store.py:1117` |
| Forget and purge | `src/agent_memory/store.py:1152`, `src/agent_memory/learning.py:1436` |
| Search | `src/agent_memory/store.py:1226` |
| Index rebuild (derived only) | `src/agent_memory/store.py:1335` |
| CLI surface | `src/agent_memory/sessions_cli.py:243` |
| Review grants | `src/agent_memory/learning.py:335` |
| Scheduler | `dotfiles/launchd/com.josh.agent-learning.plist.in` |
| Existing work-counter bench | `eval/bench_sessions.py:459` |
| Durability patterns to reuse | `src/agent_memory/learning_ops.py:186`, `:300`, `:317`; `src/agent_memory/learning_promote.py:669`, `:678` |

`store.py` has no `fsync` on any archive path; `learning_ops.py` and `learning_promote.py` already have the file-and-directory sync pattern. Reuse it rather than writing a second one.
