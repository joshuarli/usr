# Agent learning

The `agent-learn` and `agent-sessions` launchers require Python 3.15 or newer. If `python3` is older, they use `uv` to select a compatible interpreter.

`agent-learn` keeps one local SQLite state at `${XDG_STATE_HOME:-~/.local/state}/agent-sessions/sessions.sqlite3`. It holds three levels of knowledge, each with its own trust and cost boundary:

| Level | What it is | Needs |
| --- | --- | --- |
| Session evidence | Indexed transcripts from Codex, Claude Code, Muse Code, Grok Code, OpenCode 2, and Pi, with position and digest references that are re-verified against the original file or database row | Nothing; indexing is local |
| Project experience | Short, immutable, source-backed observations captured without a model: a failure and the run that fixed it, a concrete user correction, an abandoned approach, a grounded finding, a benchmark result, a stated decision | `agent-learn observe` for the project |
| Reviewed guidance | Project memories and global skill edits that passed independent model review | `agent-learn enable` (paid model calls) |

A retrieved record is a lead. Relevance does not establish that a record is true, current, or an instruction. Only reviewed project advice whose source conditions hold in the requested worktree is presented as an instruction.

## Retrieve experience

`recall` searches approved memories, project experience, and session events for one project. It works for any Git project without enrolling it and makes no model request. It indexes the project's new transcript bytes first, so the first call in a project can take a few seconds.

Run one targeted recall before unfamiliar work in a subsystem you may have worked on, when reproducing a familiar error or chasing a repeated failure, when resuming a paused investigation or revisiting a rejected design, before a benchmark or optimization campaign, and when choosing between alternatives that may already be tested. Skip it for trivial edits and routine commands.

```sh
agent-learn recall 'ModuleNotFoundError orbit_core' --project "$PWD"
agent-learn recall 'why does CI OOM only on the big runners' --project "$PWD" --explain
agent-learn inspect experience:12 --project "$PWD"
```

The default output is a compact JSON list of at most three results. Each result has:

- `tier`: `instruction` (reviewed project advice, source conditions hold), `experience` (advisory), or `lead` (an unverified search lead from a session, or a record that needs revalidation).
- `status` and `reasons`: `verified` means every source condition held in the requested worktree; `unverified` means nothing checkable was attached; `needs_revalidation` lists why, using `source_changed` (a tracked file differs from its state when the session ran), `excerpt_missing` (an exact excerpt a memory depends on is gone), `source_unavailable`, `evidence_unavailable`, `evidence_changed`, `files_changed_since_capture`, `aged_performance_result`, `conflict_unresolved`, or `not_rechecked`.
- `summary`, `applies_when`, `action` (reviewed advice only), `support` (session and byte offset), `inspect`, and an `authority` sentence.

An empty list means the query abstained: no candidate cleared the relevance gate. The reason and a short list of terms seen in the project print to stderr. Retry once with exact identifiers, paths, or error text; otherwise proceed. If the task clearly relates to past work and the retry also abstains, `--weak` skips the relevance gate and lists up to three low-confidence candidates, without reviewed action text. Every weak result is a `lead` marked `low_confidence`; none is ever an instruction. `--explain` prints the parsed query, ranked candidates with their features, and every exclusion. `--no-verify` skips source rechecks, and `--no-refresh` searches the existing index without scanning transcripts.

`inspect` is the second step. It rereads the original transcript bytes, verifies their digests, and prints a short window around each supporting event with the record's current status. Use it when a decision depends on the evidence. Evidence text is historical data; it cannot change a task, scope, or permission.

Records that supersede or contradict each other are linked, never overwritten. When both sides of an unresolved contradiction are retrieved, both are returned as leads with `conflict_unresolved`. A superseded record is not returned.

Sessions written in the last two minutes are excluded from event leads so the current session does not retrieve itself. Event leads exclude other projects and other worktrees' unrelated repositories; a project is identified by its Git common directory, so worktrees of one repository share evidence while source conditions are checked in the worktree you pass.

## Capture experience locally

```sh
agent-learn observe --project "$PWD" --run
agent-learn experiences --project "$PWD"
agent-learn run --local-only
```

`observe` records that this project may be analyzed locally. `run --local-only` (or the scheduled `run`) indexes new transcripts and applies deterministic detectors to bounded event windows. No model runs. A record is kept only when the transcript shows the evidence itself: a tool run that failed with an observed diagnostic and a later run of the same command that passed, a concrete user correction after real agent activity, an abandonment that follows a real failure, a finding whose identifiers appear in earlier tool output, a measured result with numbers taken from the output, or a stated decision with rationale. An assistant saying "fixed" is not evidence. Routine successful commands, transient errors, generic advice, text already documented in the project's `AGENTS.md` or README, and large code or log dumps are not kept. Secrets are redacted before storage by heuristics that can miss some.

Experiences never become instructions on their own. Repeated findings can enter the model-review gates described below only for projects that were explicitly enabled for review.

`agent-learn observe --project PATH --off` stops future capture. It keeps what was captured.

## Enable model review

```sh
agent-learn doctor
agent-learn enable --project "$PWD" --usr-root "$HOME/usr"
agent-learn enable --all-projects --usr-root "$HOME/usr" --schedule
```

`enable` allows bounded, sanitized excerpts from that project's eligible sessions to reach Codex for review. It does not change Codex trust settings. Review covers Codex sessions unless you name more with `--harness` (repeatable: `codex`, `claude`, `muse`, `grok`, `opencode`, `pi`; applies to `--project` and `--all-projects`). Local indexing and observation never imply this grant. The wildcard enrolls Git projects found in session history.

On macOS, `--schedule` installs a user LaunchAgent that runs `agent-learn run --scheduled` every 15 minutes. Without it, run reconciliation yourself; Linux has no bundled scheduler. The dotfiles sync does not install or start the LaunchAgent.

Each run starts at most two finding reviews. A review starts only when the previous 24 hours leave room for its full reservation: four model calls within a 24-call budget, two for a regression monitor. The reservation is written before the first call and replaced by recorded usage when the review finishes, so a crash cannot hide spend and the budget is a hard cap. `agent-learn status` reports `model_calls_24h`, `model_tokens_24h`, deferred reviews, and rejected candidates.

Run `agent-learn status` for grants, findings, observation, retrieval counts, transcript coverage, and scheduler state. `agent-learn findings` lists findings and `agent-learn show ID` inspects one.

## Withdraw, delete, and disable

- `agent-learn withdraw experience:N` stops retrieval and keeps the evidence. `withdraw memory:N` withdraws an approved project memory.
- `agent-learn forget experience:N` deletes the record, its sources, links, receipts, feedback, and any still-pending review candidate built from it, and remembers its fingerprint so the same observation is not captured again. It withdraws memories derived from it (a withdrawn memory keeps only its finding row, stripped of the reviewed text, proposal, and evaluations) and reports a promoted skill edit it cannot safely reverse as `unresolved_derived_findings` with a non-zero exit. It never forces a revert.
- `agent-learn forget-session SESSION` deletes one session's index rows, every experience that cites it, and everything derived only from it, and records a tombstone so a later refresh does not index or archive the same transcript again. Experiences supported by other sessions are rebuilt from those sessions on the next run. It deletes the session's archived copy (see [Retention](#retention)) and never touches the harness's own transcript file.
- `agent-learn undo ID` withdraws a promoted skill edit or approved memory. A promotion can be reversed after later commits when its paragraph is unchanged; otherwise the reversal is refused and `status` lists the finding under `unresolved_regressions`.
- `agent-learn disable --project "$PWD"` stops review for one project; `--all-projects` revokes the wildcard; `--schedule` removes the LaunchAgent for every project. Disabling stops future work and deletes nothing.
- `agent-learn reindex` rebuilds the search projection from the canonical records.

## Feedback and measurement

Every recall writes a receipt of what was returned, and `inspect` writes one for what was inspected. `agent-learn feedback REF helped|irrelevant|stale|misleading` records a verdict; it is self-declared and nothing reads it for ranking, tier, or authority. Feedback and frequency never raise a record's tier or ranking. `agent-learn quality` reports abstentions, stale results returned, leads never inspected, queries that repeatedly abstained, consolidation candidates, feedback counts, and follow-through. Follow-through is derived from transcripts: a result was presented when its reference appears in the recall output, acted on when a later tool call used an identifier the query did not already contain, and verified when a later test or build run passed or failed. It is observational. It cannot show that a record caused an outcome, that an agent obeyed it, or that a missing memory existed.

## Hook and data boundaries

The user-level Codex `Stop` hook runs `agent-learn hook`. It reads the event name and working directory and records a project-scoped hint for enabled projects. It does not read transcripts or run a model. `SubagentStop` events and sessions marked with `AGENT_LEARN_WORKER` create no hints. No harness injects memory on every turn; agents call `recall` through the [`do`](../../dotfiles/base/.agents/skills/do/SKILL.md) skill's rule, and the result arrives late in the context as an ordinary tool result, which leaves the system prompt and its cache untouched. See [`config.toml`](../../dotfiles/base/.codex/config.toml) for the hook, which Codex may ask you to trust.

The store keeps local transcript indexes and learning records; it never copies original transcripts into Git. State directories use mode `0700`; database files use `0600`. Redaction is heuristic and can miss credentials or confidential text. Enabling a project or the wildcard allows bounded excerpts from eligible sessions to reach Codex. Review workers use isolated scratch directories, disabled tools and hooks, ignored user configuration, read-only sandboxing, and ephemeral sessions. These settings do not establish VM isolation or prevent every host read. `agent-learn doctor --probe-cli` runs an unpaid loopback diagnostic with synthetic input.

## Search sessions

`agent-sessions` indexes Codex, Claude Code, Muse Code, Grok Code, OpenCode 2, and Pi transcripts. Search defaults to the current Git repository and its worktrees; cross-project search requires `--all-projects`.

```sh
agent-sessions recent
agent-sessions search 'cargo test' --harness claude
agent-sessions search 'permission denied' --kind tool-output
agent-sessions show claude:SESSION --position BYTE_OFFSET
agent-sessions doctor
```

To find your own prompts, filter to `--kind user` and widen the scope with `--all-projects`. Hyphenated identifiers and slashes are autoquoted, so `codegen-units` and `thin lto / codegen-units` work unquoted; quoting still forces an exact phrase and `AND`/`OR` still combine terms. Limit to today with `--since 1d` (or an ISO date), and use `--regex` only for pattern matching.

```sh
agent-sessions search 'codegen-units' --all-projects --kind user
agent-sessions search 'thin lto / codegen-units' --all-projects --kind user --since 1d
agent-sessions search '"codegen-units"' --all-projects --kind user --limit 5
```

`agent-learn recall` is for reviewed memories and fuzzy session leads (technical tokens handled, ranked, gated); `agent-sessions search` is the direct full-text index for exact message lookup.

A Codex session keeps its bare ID. Other harnesses use `harness:ID`, so identical IDs from different tools never collide. Use the full session ID and byte offset printed with a hit. `show` verifies source bytes before displaying context. `doctor` prints per-harness coverage: complete, degraded, and unsupported sessions, unrecognized event kinds, and sessions whose ancestry is unknown. A session whose lines parse but contain no understood content is `unsupported`, not an empty success. Muse and Grok do not always state their ancestry; unknown ancestry is never counted as an independent root. `doctor --rebuild-index` rebuilds transcript tables while preserving learning records.

Default roots are `$CODEX_HOME/sessions` and `archived_sessions`, `$CLAUDE_CONFIG_DIR/projects`, `$XDG_DATA_HOME/muse/sessions`, `$GROK_HOME/sessions`, `$XDG_DATA_HOME/opencode`, and Pi's session directory (`$PI_CODING_AGENT_SESSION_DIR`, else `$PI_CODING_AGENT_DIR/sessions`, else `~/.pi/agent/sessions`), each falling back to its usual home directory. Pass `--root [HARNESS=]PATH` to override. Indexing never follows symlinks. Pi sessions are the `<timestamp>_<id>.jsonl` files, so pi-subagents artifacts such as `events.jsonl` are not mistaken for sessions. Pi stores one tool call or result per entry; several calls from one assistant entry become one event whose call ID lists them all. A session whose header names a `parentSession` links to that session and is labeled `child`: Pi writes the same field for a user fork and for a delegated subagent. Every entry of a branched session is indexed and searchable, but experience detectors and review read only the active branch: the chain from the newest entry back through `parentId`, so a failure on an abandoned branch is never paired with a success on another. OpenCode 2 keeps sessions in a SQLite database (`opencode.db`), not transcript files: the indexer opens it read-only, reads only the `session_v2` and `session_message` tables (never the account or credential tables), reindexes a session whenever its message count or update time changes, and takes shell exit codes from the recorded tool metadata. A hit's byte offset is `message sequence × 1000 + block`, and `show` verifies the row's digest. Search matches whole tokens, so a Chinese or Japanese query matches only a whole unsegmented run.

## Retention

Every refresh also hard-links each transcript file into `${XDG_STATE_HOME:-~/.local/state}/agent-sessions/archive/HARNESS/ORIGINAL_PATH`, a `0700` tree. A link costs no extra disk space and keeps the data alive after a harness deletes or expires the file (Claude Code removes old transcripts after `cleanupPeriodDays`). When the original is gone, the session is indexed from the link: search, `show`, `agent-learn recall`, and evidence verification keep working with the same positions and digests. Evidence also resolves from the link before the next refresh runs.

- Capture happens during a refresh, which any `agent-sessions` command or scheduled `agent-learn run` performs for every transcript root regardless of the project filter. A file a harness deletes before any refresh saw it is not recoverable.
- The link is the same file, so a harness that rewrites a transcript in place changes the archived copy too. A harness that replaces the file leaves the old data in the link until the next refresh relinks it. Grok's `summary.json` and `events.jsonl` are linked with `chat_history.jsonl`.
- The state directory must share a filesystem with the transcripts. Otherwise the refresh summary shows `archive_errors` and nothing is retained.
- OpenCode's database cannot be hard-linked. The archive keeps its own `opencode.db` with only the session and message rows, added or updated on refresh and never removed when OpenCode drops them. Credential tables are never copied.
- Learning-worker sessions and forgotten sessions are never archived. `reset-agents` does not touch the archive.
- The archive holds complete, unredacted transcripts. Keep it out of Git and include it in backup and disk-encryption decisions. `agent-learn forget-session` is the only way to remove an archived session.

## Promotion policy

Recurring findings can propose a contextual sentence in an existing allowlisted skill or a trigger before its `Skip` clause. Two independent originating sessions in two enabled repositories must support a global skill edit. Findings in other repositories with similar wording and the same direction nominate evidence for review; the reviewer decides whether it supports the same action, and distinct projects and root sessions establish independence. Commands and conventions belong in project memory. The applier uses an ignored `.work/wt/` worktree and the existing skill checker, and integrates only into a clean, unchanged branch. It does not push. See [`learning_promote.py`](src/agent_memory/learning_promote.py) for validation, staging, and recovery rules.

A malformed edit, or an independent approval that lists risks, goes back to the proposer with the reason and is retried up to three times against unchanged evidence. An independent reviewer that declines holds the finding. A proposal that contradicts approved advice for the same owner and applicability goes back to the reviewer with that advice attached; otherwise the new finding is held with reason `conflict` and the approved advice stays.

Project memories are stored exactly as reviewed, at most 600 characters of action and 400 of applicability, with optional source-file conditions. Global instructions, routers, security and permission policy, dependencies, unrelated projects, and broad new skills cannot be auto-promoted. `recurring_mistakes` counts later sessions whose correction clusters with the original finding; `regressions_reported` counts complaints that quote the promoted advice. Neither counts an unrelated correction, and neither establishes that an edit caused improvement.

## Evaluation

All evaluation is offline unless a command says otherwise.

```sh
uv run --no-project --python '>=3.15' python -I tools/agent-memory/eval/bench_recall.py validate
TMPDIR="$PWD/.work/tmp" uv run --no-project --python '>=3.15' python -I tools/agent-memory/eval/bench_recall.py run --split dev
TMPDIR="$PWD/.work/tmp" uv run --no-project --python '>=3.15' python -I tools/agent-memory/eval/bench_recall.py run --split heldout --haystack 150 --detail
```

The benchmark renders synthetic multi-project episodes into real Git repositories, worktrees, and transcripts in all four harness formats, indexes them, captures experience, installs approved memories, applies source edits, and scores recall against labeled episodes. `--system` selects the legacy word-overlap recall, plain FTS5 search, or the new pipeline. `--haystack N` adds N synthetic routine sessions per project. The `dev` split is for tuning. The `heldout` split was written independently and was not used to choose any parameter. `explain CASE` shows why one case passed or failed.

`tools/agent-memory/eval/live_recall.py --live` compares a no-memory baseline, a retrieved-experience treatment, and an unrelated-task control with native Codex runs and scores the commands the agent ran, not its prose. It makes paid model calls and refuses to run without `--live`. Its offline tests are `tools/agent-memory/eval/test_live_recall.py`.

### Measured results

Both splits are synthetic: 12 projects each, about 90 episodes across four harnesses, 14 approved memories, source edits, worktrees, and hard negatives. `dev` has 175 cases (148 answerable, 27 that should abstain) and was used to choose parameters. `heldout` has 141 (117 and 24), was written independently, and was run with the pipeline frozen. Precision@3 counts the results actually returned. Context is the compact JSON of the default three results.

| System | Split | Recall@1 | Recall@5 | Precision@3 | MRR | Multi-record coverage | Correct abstention | Context chars |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Previous `recall` (word overlap over memories) | dev | .25 | .25 | .23 | .25 | .45 | .70 | 88 |
| Plain FTS5, query as typed | dev | .08 | .10 | .08 | .09 | .00 | 1.00 | 11 |
| Plain FTS5, terms joined with OR | dev | .70 | .93 | .52 | .80 | .69 | .00 | 200 |
| New `recall`, default | dev | .57 | .65 | .57 | .61 | .38 | .89 | 472 |
| New `recall`, after one agent-written retry | dev | .74 | .82 | .74 | .77 | .50 | .85 | n/a |
| New `recall --weak` | dev | .78 | .86 | .74 | .81 | .74 | .30 | 724 |
| Previous `recall` | heldout | .24 | .24 | .24 | .24 | .17 | .96 | 53 |
| Plain FTS5, query as typed | heldout | .12 | .12 | .12 | .12 | .00 | 1.00 | 17 |
| Plain FTS5, terms joined with OR | heldout | .78 | .95 | .48 | .86 | 1.00 | .00 | 230 |
| New `recall`, default | heldout | .64 | .68 | .63 | .66 | .83 | 1.00 | 452 |
| New `recall`, after one agent-written retry | heldout | .77 | .80 | .75 | .79 | .83 | 1.00 | n/a |
| New `recall --weak` | heldout | .85 | .92 | .79 | .88 | .75 | .46 | 700 |

Cross-project leakage and stale-memory-as-verified violations are zero for the new pipeline on both splits, with and without a 150-session-per-project synthetic haystack (about 60,000 extra events; default recall Recall@5 .66, abstention .89 on dev and Recall@5 .66, abstention 1.00 on heldout). The previous `recall` also showed zero stale violations because it already filtered failed source conditions. Context is about 450 to 500 characters, roughly 120 tokens, per answered recall; an abstention prints `[]` and a short hint.

What the table shows:

- The new pipeline beats the previous `recall` by about 2.5 times on Recall@5 and searches session evidence the old one could not reach. It does not beat plain OR-joined FTS5 on Recall@5. That query returns five loosely related sessions for every question, abstains on none, and has lower precision. The new default trades recall for abstention: the same ranking reaches Recall@5 .91 on dev when the relevance gate is disabled, but the signals that separate a real match from a near miss (term coverage, rarity, score) have AUC about .88, so no threshold gives both high recall and high abstention.
- The targets of Recall@5 at least .90, Precision@3 at least .80, and abstention at least .95 are not met together. Default recall meets abstention on heldout (1.00) but not on dev (.89); `--weak` reaches Recall@5 .92 on heldout and Precision@3 .79 by giving up abstention.
- Paraphrases with almost no shared words are the main loss (dev Recall@5 .16 for that category). One agent-written retry recovers most of them (+17 points dev, +13 heldout) at a small abstention cost on dev (.89 to .85) and none on heldout. The retries were written by a separate agent shown only the query, the abstention hint, the project's seen terms, and the file list, never the fixtures. That models the retry the `do` rule asks for; it is not a measurement of any particular model.

Rejected as not paying for themselves on `dev`: a static software-synonym lexicon (+2 points Recall@5 at equal abstention), session-level evidence pooling (+1 point), and tuning the rarity threshold (no effect on small corpora). Embeddings and model reranking were not tried; the retry result is the cheaper mechanism and no model call is needed for retrieval.

Latency on the synthetic corpora is about 20 ms per answered query in process (26 ms with the haystack). On a private index of 841,000 events (471 real sessions, 1.0 GB, built in about 60 seconds, never committed), warm queries ran at about 40 to 50 ms with a maximum near 120 ms. These timings were taken under ordinary desktop load and are not perf-gate certified. Unchanged incremental indexing does the same I/O as the previous release for Codex transcripts (the benchmark's gated CPU median for 1,000 unchanged sessions is 30 ms). `tools/agent-memory/eval/bench_sessions.py --baseline-ref REV` reproduces the comparison.

### Not established

- The live memory-use evaluation has not been run; it needs paid model calls and an explicit decision to spend them. Whether agents actually call `recall` in each harness, and whether retrieval changes outcomes, is unmeasured. The offline tests cover the fixture, the real capture pipeline, and the scoring only.
- The corpora are synthetic. Quality on real sessions is unknown beyond latency and a spot check that exact identifiers return hits and generic requests abstain.
- Muse Code transcripts index only the events verified from fixtures (user messages, skill reads), so Muse has no tool-based experience capture. Chinese and Japanese queries match only whole unsegmented runs.
- Follow-through and receipts are observational; nothing here shows that a record caused an outcome.
