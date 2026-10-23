# Agent learning

`agent-learn` stores opt-in review state and findings in `${XDG_STATE_HOME:-~/.local/state}/agent-sessions/sessions.sqlite3`. Review stays off until you enable a project or the global wildcard.

## Enable project review

Run `agent-learn doctor` to check local setup. Then enable one project:

```sh
agent-learn enable --project "$PWD" --usr-root "$HOME/usr"
```

`enable` allows bounded, sanitized excerpts from that project's eligible sessions to reach Codex for review. It does not change Codex trust settings. To enroll Git projects in Codex session history, enable the global wildcard:

```sh
agent-learn enable --all-projects --usr-root "$HOME/usr" --schedule
```

On macOS, `--schedule` installs a user LaunchAgent that runs `agent-learn run --scheduled` every 15 minutes. Without it, run scheduled reconciliation yourself. Linux has no bundled scheduler. The dotfiles sync does not install or start the LaunchAgent.

Run `agent-learn status` to inspect grants, findings, and scheduler state. Use `agent-learn findings` to list findings, `agent-learn show ID` to inspect one, and `agent-learn recall 'question' --project "$PWD"` to retrieve relevant retained findings. Check each result against current code and instructions before using it.

Run `agent-learn undo ID` to withdraw one promoted skill edit or approved project memory without quoting it. A promotion can be reversed after later commits when its paragraph is unchanged; otherwise the reversal is refused and `agent-learn status` lists the finding under `unresolved_regressions`. The scheduled monitor records the same state when it finds an attributed regression it cannot reverse.

Run `agent-learn disable --project "$PWD"` to stop review for one project. Under the wildcard, this also excludes that project. Run `agent-learn disable --all-projects` to revoke the wildcard. Projects enabled individually remain enabled. Pass `--schedule` to either disable command to remove the macOS LaunchAgent; this stops scheduled reviews for every project.

## Codex hook and data boundaries

The user-level Codex `Stop` hook runs `agent-learn hook`. It reads the event name and working directory, then records a project-scoped hint. The scheduled runner discovers wildcard projects and checks hints. It does not read transcripts or run a model from the hook. `SubagentStop` events and sessions marked with `AGENT_LEARN_WORKER` do not create hints.

The hook is configured in [`config.toml`](../dotfiles/base/.codex/config.toml). Codex may ask you to review and trust this unmanaged hook. The config does not add a trust record.

The store keeps local transcript indexes and learning records; it does not modify or copy original transcripts into Git. State directories use mode `0700`; database files use `0600`. Redaction is heuristic and can miss credentials or confidential text. Enabling a project or the wildcard allows bounded excerpts from eligible sessions to reach Codex. Local indexing alone makes no model request. See [`agent_session_store.py`](../dotfiles/base/.local/bin/agent_session_store.py) for transcript handling and [`agent_learning.py`](../dotfiles/base/.local/bin/agent_learning.py) for enrollment and review rules.

Review workers use isolated scratch directories, disabled tools and hooks, ignored user configuration, read-only sandboxing, and ephemeral sessions. These settings do not establish VM isolation or prevent every host read. Use `agent-learn doctor --probe-cli` for an unpaid loopback diagnostic with synthetic input; it does not contact a model provider. Check `/hooks` inside Codex for the actual hook trust decision.

## Search sessions

`agent-sessions` indexes Codex transcripts. Search defaults to the current Git repository and its worktrees; cross-project search requires `--all-projects`.

```sh
agent-sessions recent
agent-sessions search 'cargo test'
agent-sessions search 'permission denied' --kind tool-output
agent-sessions search 'actually|I meant|wrong' --kind user --regex
agent-sessions show SESSION --position BYTE_OFFSET
agent-sessions doctor
```

Use the full session ID and byte offset printed with a search hit. `show` verifies source bytes before displaying context. `doctor --rebuild-index` rebuilds transcript tables while preserving learning records. Codex search reads `$CODEX_HOME/sessions` and `$CODEX_HOME/archived_sessions`, falling back to `~/.codex`. The shared normalizer also serves `skill-usage` for Claude, Muse, and Grok, but their sessions are not indexed for search.

## Promotion policy

Recurring findings can propose a contextual sentence in an existing allowlisted skill or a trigger before its `Skip` clause. Two independent originating sessions in two enabled repositories must support a global skill edit. Findings in other repositories with similar wording and the same direction nominate evidence for review; the reviewer decides whether it supports the same action, and distinct projects and root sessions establish independence. Commands and conventions belong in project memory. The applier uses an ignored `.work/wt/` worktree and the existing skill checker, and integrates only into a clean, unchanged branch. It does not push. See [`agent_learning_promote.py`](../dotfiles/base/.local/bin/agent_learning_promote.py) for validation, staging, and recovery rules.

Each run starts at most two finding reviews and stops starting reviews once the previous 24 hours hold 24 recorded model calls. One review may exceed that by its own calls, and a review that crashes before recording usage is not counted. `agent-learn status` reports `model_calls_24h` and the budget. Deferred findings resume when calls free up.

A malformed edit, or an independent approval that lists risks, goes back to the proposer with the reason and is retried up to three times against unchanged evidence. An independent reviewer that declines holds the finding.

A proposal that contradicts approved advice for the same owner and applicability goes back to the reviewer with that advice attached. The reviewer may withdraw an approved project memory. Otherwise the new finding is held with reason `conflict`, the approved advice stays, and new independent evidence reopens the review. Project memories are stored exactly as reviewed, at most 600 characters of action and 400 of applicability.

Global instructions, routers, security and permission policy, dependencies, unrelated projects, and broad new skills cannot be auto-promoted. Project memories are advisory and checked against current files. Current code, tests, and instructions take precedence. `recurring_mistakes` counts later sessions whose correction clusters with the original finding; `regressions_reported` counts complaints that quote the promoted advice. Neither counts an unrelated correction. Invocation counts and recurrences are observational measurements; they do not establish that an edit caused improvement.
