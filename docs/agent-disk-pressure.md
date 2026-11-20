# Disk pressure and worktree cleanup

Proactive cleanup starts only when the system disk has **strictly less than 16 GiB available space**. A deterministic event hook measures space; agents do not poll, enumerate worktrees, or run `du` to decide whether a sweep is needed. Routine retirement of a stopped, accepted lane remains part of completing that lane. An explicit cleanup request also remains actionable on a healthy disk.

## Detection and cost

[`agent-disk-pressure`](../dotfiles/base/.local/bin/agent-disk-pressure) uses Python's standard-library `os.statvfs`. The measured path is `/` on Linux and `/System/Volumes/Data`, the writable boot volume, on macOS. Available blocks are those usable by the ordinary user, not blocks reserved for root. The threshold is absolute, not a share of the disk: `available < 16 * 2**30` in integer bytes, compared before display rounding. Exactly 16 GiB is healthy. `status` reports `threshold_bytes` alongside the informational `free_percent`. Invalid or unavailable counters do not authorize cleanup.

The ordinary healthy path performs one filesystem-capacity query and checks for an existing notice marker. It starts no subprocess, traverses no directory, runs no Git command, and creates no state. The hook has a Python interpreter startup cost, but consumes no model tool call or extra model turn. No daemon, timer, cron job, or systemd service is installed.

On this Linux development host, 30 interleaved samples measured a **29.4 ms median complete hook invocation** (36.5 ms p95), versus 6.3 ms for an empty isolated Python process. Both host-load gates passed. These are local implementation measurements, not a macOS or production latency guarantee. There are no new package dependencies.

On a low reading, a stable nonblocking `flock` and an atomically replaced timestamp admit one notice per user/host every 30 minutes across harnesses resolving the same state directory. The helper takes a fresh reading under the lock before emitting. Observed recovery to >=16 GiB clears the notice episode and rearms immediately. The lock inode stays in place. State is under `${XDG_STATE_HOME:-~/.local/state}/usr-disk-pressure/<host-hash>/`; different home or state roots have separate notice claims.

The shared timestamp deduplicates notices; it is not a lock around arbitrary manual cleanup commands. A failed/unwritable state claim produces no cleanup request. `notify` and `status` report failures on stderr with exit 2; hook failures leave the unrelated task running. Use those commands when diagnosing a missing notice. No transcript, tool arguments, credentials, or repository inventory is retained.

## Harness coverage

| Harness | Automatic boundary | Behavior |
| --- | --- | --- |
| Codex | `SessionStart`, `PostToolUse` for Bash and edits | Informational `additionalContext`; no `Stop` continuation or tool-result replacement |
| Claude Code | `SessionStart`, `PostToolUse`, `PostToolUseFailure` for Bash/Edit/Write | Same shared helper and cooldown |
| Pi | `before_agent_start` through the global extension | Adds one custom message only on pressure; never starts a new turn |
| Other harnesses, or disabled hooks | First necessary shell command and an out-of-space failure | Run `agent-disk-pressure notify` in the same tool invocation, preserving the existing command's exit status; no standalone polling loop |

For a simple existing command, the POSIX shell fallback preserves its output and exit status even if the notifier fails. Replace `work_command` with that already-needed command; retain the original error handling when adapting a longer script.

```sh
(work_status=0; work_command || work_status=$?; agent-disk-pressure notify || :; exit "$work_status")
```

Known `USR_SCOPED_WORKER=1` processes and hook events carrying a child `agent_id` do not claim notices. Not every harness reports native-child identity on every event. A worker that receives a notice must relay it to its coordinator without expanding scope. Only the coordinator performs cleanup.

These are event-driven checks, not continuous disk monitoring. Idle sessions and a long-running tool that has not returned generate no new check. Pi checks at run entry, not within a long autonomous run. Unsupported/disabled harness adapters use the explicit one-shot fallback; an ENOSPC failure is another reason to use that fallback. Do not claim automatic mid-run coverage where there is none.

Event contracts: [Codex hooks](https://learn.chatgpt.com/docs/hooks), [Claude hooks](https://code.claude.com/docs/en/hooks), and the pinned [Pi 1.5.0 extension API](https://github.com/earendil-works/pi/blob/v1.5.0/packages/coding-agent/docs/extensions.md).

## Cleanup protocol

The [`cleanup` skill](../dotfiles/base/.agents/skills/cleanup/SKILL.md) owns the bounded pass. A notification requests an assessment; it grants no permission to remove somebody else's work.

1. Run `agent-disk-pressure status` immediately before a proactive batch. Exit 1 and `below_threshold: true` mean pressure. Exit 0 means stop; exit 2 means no trustworthy decision. Recheck after the batch and before another.
2. Limit candidates to recorded owned worktrees and positively identified stale scratch in the current campaign. Verify that reclaiming them can relieve the system volume. Do not turn pressure into a home-directory or repository-fleet sweep.
3. Establish completion and quiescence independently. A clean checkout may still have a running build or agent. Preserve active, leased, locked, dirty, parked and unknown-owner lanes.
4. From the surviving integration checkout, preview `worktree-retire <lane> --into <integration-head> --dry-run`, then retire only after reviewing its integration evidence and ignored files. Use `--discard-ignored` only for individually reviewed disposable data. Never force removal or recursively delete a worktree.
5. Stop once free space is >=16 GiB, the reading is unknown, or no safe candidates remain. Report a blocker once and continue the original task where feasible. Do not repeatedly rescan the same fruitless inventory.

Completed-lane retirement is separate: review, integrate, verify, stop the worker, retire its exact checkout. Claude's [WorktreeRemove contract](https://code.claude.com/docs/en/hooks#worktreeremove) explicitly leaves hook-created subagent worktrees behind when the subagent finishes; the coordinator cannot delegate this responsibility to that hook.

The Codex campaign closeout guard has a separate job: accounting for explicitly named campaign lanes when ending a campaign. It must not infer ownership from every registered worktree or repeatedly manufacture cleanup turns. See [campaign closeout](../dotfiles/base/.agents/skills/orchestrate/references/campaigns.md).

## Installation and verification

After pulling `usr`, use the normal [sync workflow](sync.md). Preview with `sh sync plan`; apply with `sh sync` on the intended host. Review the new Codex hooks in `/hooks` and start a fresh session. Existing instruction-hook positions and trust records are preserved; new hook trust is not fabricated. Claude reads the new settings in a fresh session; Pi discovers its extension on startup or `/reload`.

Useful checks:

```sh
agent-disk-pressure status
agent-disk-pressure notify
python3 -I dotfiles/disk-pressure-test.py
node dotfiles/pi-disk-pressure-test.mjs
```

The tests cover strict lower/equal/upper thresholds, user-available blocks, the macOS volume choice, fresh recovery, concurrent processes, shared cooldown, corrupt/future state, symlink and FIFO refusal, unknown/error behavior, child suppression, actual configured command execution, fallback exit-status preservation, and Pi's silent/low/error paths. Linux fixture proof does not establish live macOS hook behavior or end-to-end model compliance. No test runs cleanup against a real home or repository.

For copy-on-write worktree choices and a bounded evaluation plan, see [worktree CoW research](worktree-cow.md).
