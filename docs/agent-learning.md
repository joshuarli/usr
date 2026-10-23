# Agent learning

`agent-learn` records project-scoped review state and retained findings in `${XDG_STATE_HOME:-~/.local/state}/agent-sessions/sessions.sqlite3`. Project review stays off until you enable that project.

## Project control

Run `agent-learn doctor` to check local setup. It does not grant a project permission.

Enable one project and name the canonical `~/usr` checkout:

```sh
agent-learn enable --project "$PWD" --usr-root "$HOME/usr"
```

`enable` stores permission to send bounded, sanitized excerpts from that project's future stable sessions to Codex. It does not change Codex trust settings. Limits are defined in the tools, rather than stored as a second configuration.

Run `agent-learn status` to see enabled projects, usage counters, observational effectiveness measurements, and scheduler state. `agent-learn findings` lists retained findings. `agent-learn show ID` opens one finding and its evidence.

Run `agent-learn disable --project "$PWD"` to stop future reviews for a project. It does not alter the Codex hook trust decision.

## Codex hook

The user-level Codex `Stop` hook runs `agent-learn hook`. It reads only the event name and working directory from hook input. It does not read transcripts, inspect Git, run a model, or create a database for a disabled session.

For an already enabled project, the hook updates one project-scoped SQLite hint. The scheduled runner checks hints later. `SubagentStop` events and sessions with `AGENT_LEARN_WORKER` set do not create hints.

The hook sits beside `codex-campaign-closeout.py` in `dotfiles/base/.codex/config.toml`. Codex may ask you to review and trust this unmanaged hook. Accept that prompt in Codex. The config does not add a trust record for it.

## Scheduler

On macOS, pass `--schedule` to enable project review and install the per-user LaunchAgent:

```sh
agent-learn enable --project "$PWD" --usr-root "$HOME/usr" --schedule
```

`com.josh.agent-learning` runs `agent-learn --state-dir PATH run --scheduled` every 15 minutes. It starts one process per run and does not keep a service running. `agent-learn status` reports whether the plist is configured and whether launchd has bootstrapped it.

Pass `--schedule` to `agent-learn disable --project "$PWD" --schedule` to unload and remove the user LaunchAgent. This stops scheduled reviews for every project. Without that flag, the timer remains configured.

Linux does not install a systemd unit. Run `agent-learn run --scheduled` manually or use a scheduler you manage. The normal dotfiles sync does not install or start the LaunchAgent.

## Retrieval and review

Run `agent-learn recall 'question' --project "$PWD"` to retrieve a bounded set of relevant retained findings. Check each result against current files and tests before using it.

The runner reviews at most two findings per run. Single incidents remain searchable candidates without invoking a model. Independent corroboration makes them eligible for review. The runner waits for at least 120 seconds of transcript stability, handles up to 100 stable sessions per project, and flags sessions over 2,000 events as incomplete. A review can include at most three evidence windows, five events per window, and 650 characters per event. Distinct originating sessions and repositories take priority over redundant subagent incidents. The Codex adapter caps serialized model context at 30,000 characters.

Project memory survives commits and ordinary branch changes. Its stored revision records where the advice originated; changing `HEAD` does not invalidate it. A memory can carry up to three tracked-file conditions, each requiring an exact source excerpt. Retrieval checks those conditions in the requesting worktree and suppresses contradicted advice. Unconditional historical advice remains advisory. Current code, tests, and instructions always take precedence. Explicitly superseded memories stop appearing. Existing approved memories migrate without acquiring a blanket expiry.

Transient network, authentication, and model outages use exponential backoff from five minutes to six hours. They do not consume a lifetime review budget. Malformed responses have a three-attempt budget for unchanged evidence. Unsafe proposals wait for new independent evidence; unsupported CLI capabilities wait for a changed CLI, adapter, or orchestration configuration. Valid proposals blocked by concurrent edits or locks retain their evidence and review. When the block clears and the owner guidance remains valid, retries can apply them without another model review. `agent-learn show ID` includes the reason, retry classification, and next retry time.

## Search sessions

Search defaults to the current Git repository, including its worktrees. Cross-project search requires `--all-projects`.

```sh
agent-sessions recent
agent-sessions search 'cargo test'
agent-sessions search 'permission denied' --kind tool-output
agent-sessions search 'actually|I meant|wrong' --kind user --regex
agent-sessions search verification --project .
agent-sessions search deadlock --since 14d
agent-sessions show SESSION --position BYTE_OFFSET
agent-sessions doctor
```

Use the full session ID and byte offset printed with a search hit. Context retrieval verifies original source bytes before displaying them. `agent-sessions doctor --rebuild-index` rebuilds derived search tables while preserving project grants and learning records. A corrupt database fails explicitly instead of discarding retained knowledge.

Codex search reads `$CODEX_HOME/sessions` and `$CODEX_HOME/archived_sessions`, with `~/.codex` as the fallback. Search indexes Codex. The shared normalizer also serves `skill-usage` for Claude, Muse, and Grok; those harnesses are not advertised as indexed search sources.

## Promotion policy

The Python applier accepts one contextual sentence appended to a paragraph in an existing allowlisted leaf skill. It also accepts a trigger insertion before an existing description's `Skip` clause, preserving the original description. Trigger insertions are limited to 120 characters. Model output cannot choose a shell command, arbitrary path, or new skill.

Two independent originating sessions in two explicitly enabled repositories must support a global skill edit. Recurrence in one repository establishes local usefulness; commands and conventions belong in project memory. Global proposals must explain applicability beyond the observed projects, and the independent reviewer must support that judgment. Generic wording alone grants no authority. A deterministic defect seen once remains a candidate for the authorized repair workflow. Descendants of the same session count once; unresolved ancestry cannot authorize a promotion. The reviewer sees current owner guidance and related approved findings.

The applier stages the change in an ignored `.work/wt/` worktree, runs the existing skill checker, and makes a local Conventional Commit. It integrates only into the clean, unchanged destination branch. Conflicts and local modifications hold the finding until repository state changes. Prepared proposals persist before Git integration so an interrupted job can recover its own commit. No job pushes.

Staging ownership is recorded in private Git worktree metadata. A name prefix alone never grants ownership. Cleanup refuses unknown, modified, staged, untracked, and ignored data. Interrupted clean staging work can resume; unfinished or unknown artifacts remain at the exact path reported in the finding. Cleanup never sweeps other registered worktrees or force-removes their contents.

Global instructions, routers, security and permission policy, dependencies, unrelated projects, and broad new skills cannot auto-promote. Structural improvements outside the narrow skill policy remain findings for an authorized implementation workflow. Project memory has the same policy boundary and never overrides repository instructions.

Invocation and recurring corrections are observational measurements. They do not establish that an edit caused improvement. The runner investigates repeated post-promotion incidents. Automatic rollback requires two new independent user reports explicitly attributing a regression to the added instruction, independent review, the exact inverse edit, and the promotion still being `HEAD`. A reversed finding cannot immediately promote again.

## Privacy and troubleshooting

State directories use mode `0700`; database files use `0600`. Original transcripts remain authoritative and are never modified or copied into Git. Ordinary results use heuristic secret redaction. Heuristic redaction cannot identify every credential or confidential source fragment. Enabling a project explicitly allows the bounded Codex service interaction; local indexing alone makes no model request.

Review workers use an empty scratch working directory, disabled tools and hooks, ignored user configuration, explicit read-only sandboxing, and ephemeral sessions. These settings reduce ambient access but do not establish VM isolation. Worker provenance also prevents recursive learning if a record survives unexpectedly. No transcript is sent to another decision provider.

Use `agent-learn doctor` for index integrity, static CLI capability, scheduler state, and the hook-trust limitation. `agent-learn doctor --probe-cli` runs an unpaid loopback diagnostic with a dummy credential and synthetic input. It verifies actual invocation, model and effort, JSON Schema requests, ignored user configuration, and advertised tools. It never contacts a model provider. Empty advertised tools do not prove that every unadvertised dispatch is impossible; the diagnostic reports that boundary and authenticated inference as unverified. A read-only sandbox also does not prevent every host read.

Check `/hooks` inside Codex for the actual trust decision. If model access fails, indexing and interactive coding continue. Errors and recovery conditions remain visible in findings. An ordinary no-op run makes no model call. Session roots are discovered once for all enabled projects, and unchanged file metadata avoids reopening transcript contents. Unindexed projects cache only header metadata; their transcript bodies stay outside model review.

Run the focused regression suites listed in [development](development.md). Use `python3 -I dotfiles/agent-sessions-bench.py --timings` for synthetic indexing and reconciliation measurements. Its resource counters report actual source metadata operations, content opens and bytes, Git launches, and SQLite changes. Timing evidence is valid only when the repository's host-readiness gate passes before and after each measurement.
