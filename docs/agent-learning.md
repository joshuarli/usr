# Agent learning

`agent-learn` keeps one local SQLite state at `${XDG_STATE_HOME:-~/.local/state}/agent-sessions/sessions.sqlite3`. It holds three levels of knowledge, each with its own trust and cost boundary:

| Level | What it is | Needs |
| --- | --- | --- |
| Session evidence | Indexed transcripts from Codex, Claude Code, Muse Code, and Grok Code, with byte-offset and digest references to the original files | Nothing; indexing is local |
| Project experience | Short, immutable, source-backed observations captured without a model: a failure and the run that fixed it, a concrete user correction, an abandoned approach, a grounded finding, a benchmark result, a stated decision | `agent-learn observe` for the project |
| Reviewed guidance | Project memories and global skill edits that passed independent model review | `agent-learn enable` (paid model calls) |

A retrieved record is a lead. Relevance does not establish that a record is true, current, or an instruction. Only reviewed project advice whose source conditions hold in the requested worktree is presented as an instruction.

## Retrieve experience

`recall` searches approved memories, project experience, and session events for one project. It works for any Git project without enrolling it and makes no model request. It indexes the project's new transcript bytes first, so the first call in a project can take a few seconds.

```sh
agent-learn recall 'ModuleNotFoundError orbit_core' --project "$PWD"
agent-learn recall 'why does CI OOM only on the big runners' --project "$PWD" --explain
agent-learn inspect experience:12 --project "$PWD"
```

The default output is a compact JSON list of at most three results. Each result has:

- `tier`: `instruction` (reviewed project advice, source conditions hold), `experience` (advisory), or `lead` (an unverified search lead from a session, or a record that needs revalidation).
- `status` and `reasons`: `verified` means every source condition held in the requested worktree; `unverified` means nothing checkable was attached; `needs_revalidation` lists why, using `source_changed`, `excerpt_missing`, `source_unavailable`, `evidence_unavailable`, `evidence_changed`, `files_changed_since_capture`, `aged_performance_result`, `conflict_unresolved`, or `not_rechecked`.
- `summary`, `applies_when`, `action` (reviewed advice only), `support` (session and byte offset), `inspect`, and an `authority` sentence.

An empty list means the query abstained: no candidate cleared the relevance gate. The reason and a short list of terms seen in the project print to stderr. Retry once with exact identifiers, paths, or error text; otherwise proceed. `--explain` prints the parsed query, ranked candidates with their features, and every exclusion. `--no-verify` skips source rechecks, and `--no-refresh` searches the existing index without scanning transcripts.

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

`enable` allows bounded, sanitized excerpts from that project's eligible sessions to reach Codex for review. It does not change Codex trust settings. Review covers Codex sessions unless you name more with `--harness claude` (repeatable). Local indexing and observation never imply this grant. The wildcard enrolls Git projects found in Codex session history.

On macOS, `--schedule` installs a user LaunchAgent that runs `agent-learn run --scheduled` every 15 minutes. Without it, run reconciliation yourself; Linux has no bundled scheduler. The dotfiles sync does not install or start the LaunchAgent.

Each run starts at most two finding reviews and stops starting reviews once the previous 24 hours hold 24 model calls. A review reserves four calls when it starts and replaces the reservation with recorded usage when it finishes, so a crash cannot hide spend. `agent-learn status` reports `model_calls_24h`, `model_tokens_24h`, deferred reviews, and rejected candidates.

Run `agent-learn status` for grants, findings, observation, retrieval counts, transcript coverage, and scheduler state. `agent-learn findings` lists findings and `agent-learn show ID` inspects one.

## Withdraw, delete, and disable

- `agent-learn withdraw experience:N` stops retrieval and keeps the evidence. `withdraw memory:N` withdraws an approved project memory.
- `agent-learn forget experience:N` deletes the record, its sources, and its links, withdraws memories derived from it, and reports any promoted skill edit it cannot safely reverse as `unresolved_derived_findings` with a non-zero exit. It never forces a revert.
- `agent-learn forget-session SESSION` deletes one session's index rows and everything derived only from it. It never touches the transcript file.
- `agent-learn undo ID` withdraws a promoted skill edit or approved memory. A promotion can be reversed after later commits when its paragraph is unchanged; otherwise the reversal is refused and `status` lists the finding under `unresolved_regressions`.
- `agent-learn disable --project "$PWD"` stops review for one project; `--all-projects` revokes the wildcard; `--schedule` removes the LaunchAgent for every project. Disabling stops future work and deletes nothing.
- `agent-learn reindex` rebuilds the search projection from the canonical records.

## Feedback and measurement

Every recall writes a receipt of what was returned, and `inspect` writes one for what was inspected. `agent-learn feedback REF helped|irrelevant|stale|misleading` records the agent's own verdict; `--user` records yours. Feedback and frequency never raise a record's tier or ranking. `agent-learn quality` reports abstentions, stale results returned, leads never inspected, queries that repeatedly abstained, consolidation candidates, feedback counts, and follow-through. Follow-through is derived from transcripts: a result was presented when its reference appears in the recall output, acted on when a later tool call used an identifier the query did not already contain, and verified when a later test or build run passed or failed. It is observational. It cannot show that a record caused an outcome, that an agent obeyed it, or that a missing memory existed.

## Hook and data boundaries

The user-level Codex `Stop` hook runs `agent-learn hook`. It reads the event name and working directory and records a project-scoped hint for enabled projects. It does not read transcripts or run a model. `SubagentStop` events and sessions marked with `AGENT_LEARN_WORKER` create no hints. No harness injects memory on every turn; agents call `recall` through the [`do`](../dotfiles/base/.agents/skills/do/SKILL.md) skill's rule, and the result arrives late in the context as an ordinary tool result, which leaves the system prompt and its cache untouched. See [`config.toml`](../dotfiles/base/.codex/config.toml) for the hook, which Codex may ask you to trust.

The store keeps local transcript indexes and learning records; it never copies original transcripts into Git. State directories use mode `0700`; database files use `0600`. Redaction is heuristic and can miss credentials or confidential text. Enabling a project or the wildcard allows bounded excerpts from eligible sessions to reach Codex. Review workers use isolated scratch directories, disabled tools and hooks, ignored user configuration, read-only sandboxing, and ephemeral sessions. These settings do not establish VM isolation or prevent every host read. `agent-learn doctor --probe-cli` runs an unpaid loopback diagnostic with synthetic input.

## Search sessions

`agent-sessions` indexes Codex, Claude Code, Muse Code, and Grok Code transcripts. Search defaults to the current Git repository and its worktrees; cross-project search requires `--all-projects`.

```sh
agent-sessions recent
agent-sessions search 'cargo test' --harness claude
agent-sessions search 'permission denied' --kind tool-output
agent-sessions show claude:SESSION --position BYTE_OFFSET
agent-sessions doctor
```

A Codex session keeps its bare ID. Other harnesses use `harness:ID`, so identical IDs from different tools never collide. Use the full session ID and byte offset printed with a hit. `show` verifies source bytes before displaying context. `doctor` prints per-harness coverage: complete, degraded, and unsupported sessions, unrecognized event kinds, and sessions whose ancestry is unknown. A session whose lines parse but contain no understood content is `unsupported`, not an empty success. Muse and Grok do not always state their ancestry; unknown ancestry is never counted as an independent root. `doctor --rebuild-index` rebuilds transcript tables while preserving learning records.

Default roots are `$CODEX_HOME/sessions` and `archived_sessions`, `$CLAUDE_CONFIG_DIR/projects`, `$XDG_DATA_HOME/muse/sessions`, and `$GROK_HOME/sessions`, each falling back to its usual home directory. Pass `--root [HARNESS=]PATH` to override. Indexing never follows symlinks. Search matches whole tokens, so a Chinese or Japanese query matches only a whole unsegmented run.

## Promotion policy

Recurring findings can propose a contextual sentence in an existing allowlisted skill or a trigger before its `Skip` clause. Two independent originating sessions in two enabled repositories must support a global skill edit. Findings in other repositories with similar wording and the same direction nominate evidence for review; the reviewer decides whether it supports the same action, and distinct projects and root sessions establish independence. Commands and conventions belong in project memory. The applier uses an ignored `.work/wt/` worktree and the existing skill checker, and integrates only into a clean, unchanged branch. It does not push. See [`agent_learning_promote.py`](../dotfiles/base/.local/bin/agent_learning_promote.py) for validation, staging, and recovery rules.

A malformed edit, or an independent approval that lists risks, goes back to the proposer with the reason and is retried up to three times against unchanged evidence. An independent reviewer that declines holds the finding. A proposal that contradicts approved advice for the same owner and applicability goes back to the reviewer with that advice attached; otherwise the new finding is held with reason `conflict` and the approved advice stays.

Project memories are stored exactly as reviewed, at most 600 characters of action and 400 of applicability, with optional source-file conditions. Global instructions, routers, security and permission policy, dependencies, unrelated projects, and broad new skills cannot be auto-promoted. `recurring_mistakes` counts later sessions whose correction clusters with the original finding; `regressions_reported` counts complaints that quote the promoted advice. Neither counts an unrelated correction, and neither establishes that an edit caused improvement.

## Evaluation

All evaluation is offline unless a command says otherwise.

```sh
python3 -I dotfiles/agent-recall-bench.py validate
TMPDIR="$PWD/.work/tmp" python3 -I dotfiles/agent-recall-bench.py run --split dev
TMPDIR="$PWD/.work/tmp" python3 -I dotfiles/agent-recall-bench.py run --split heldout --haystack 150 --detail
```

The benchmark renders synthetic multi-project episodes into real Git repositories, worktrees, and transcripts in all four harness formats, indexes them, captures experience, installs approved memories, applies source edits, and scores recall against labeled episodes. `--system` selects the legacy word-overlap recall, plain FTS5 search, or the new pipeline. `--haystack N` adds N synthetic routine sessions per project. The `dev` split is for tuning. The `heldout` split was written independently and was not used to choose any parameter. `explain CASE` shows why one case passed or failed.

`dotfiles/agent-recall-live.py --live` compares a no-memory baseline, a retrieved-experience treatment, and an unrelated-task control with native Codex runs and scores the commands the agent ran, not its prose. It makes paid model calls and refuses to run without `--live`. Its offline tests are `dotfiles/agent-recall-live-test.py`.

RESULTS_PLACEHOLDER
