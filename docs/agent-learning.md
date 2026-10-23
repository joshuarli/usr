# Agent learning

`agent-learn` records project-scoped review state and retained findings in `${XDG_STATE_HOME:-~/.local/state}/agent-sessions/sessions.sqlite3`. Project review stays off until you enable that project.

## Project control

Run `agent-learn doctor` to check local setup. It does not grant a project permission.

Enable one project and name the canonical `~/usr` checkout:

```sh
agent-learn enable --project "$PWD" --usr-root "$HOME/usr"
```

`enable` stores project permission, review limits, and model-spend controls in the SQLite database. It allows bounded model review for that project's stable sessions. It does not change Codex trust settings.

Run `agent-learn status` to see enabled projects, stored review and model-spend limits, usage counters, and scheduler state. `agent-learn findings` lists retained findings. `agent-learn show ID` opens one finding.

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

The runner reviews at most two findings per run and attempts each finding at most three times. It waits for at least 120 seconds of transcript stability, handles up to 100 stable sessions per project, and flags sessions over 2,000 events as incomplete. A review can include at most two evidence windows, five events per window, and 650 characters per event. The Codex adapter caps serialized model context at 30,000 characters.

Promotions require independent evidence and review. The promotion engine accepts only an improvement to its explicit skill allowlist. A retained memory applies only to the exact repository `HEAD` it records.
