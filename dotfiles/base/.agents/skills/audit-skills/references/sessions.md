# Session evidence

Read this for stage 2, and for the session sources stage 3 uses. A skill that reads well proves nothing; sessions show whether it fires and whether the work was better or cheaper for it. A skill earns its place by supplying necessary knowledge, preserving a required contract, improving the result, or lowering its cost. Run no new experiments, and edit no skill until each decision has counts and outcomes.

## Data (all read-only)

- Claude: `~/.claude/projects/*/<session>.jsonl`. Codex: `~/.codex/sessions/YYYY/MM/DD/rollout-*.jsonl` (the `session_meta` line carries `cwd` and `originator`). Muse: `~/.local/share/muse/sessions`. Pi: `~/.pi/agent/sessions/*/*.jsonl` (scan the first lines for `cwd`).
- OpenCode: `sqlite3 ~/.local/share/opencode/opencode.db`. Sessions from `session_v2` (`time_updated` is epoch ms); assistant turns from `session_message` (JSON `data.content` holds the tool calls); parts from `session_part` if the JSON layout differs.
- List candidates in a window with `fd -I -H --changed-within <window>`. Bridge state and qualification logs live under `.work/`, which is gitignored, so `-I` is required for those trees.
- Bridge state: `<repo>/.work/worker-bridge/usrw_*.json` (`tier`, `attempts`, `execution.selection`, `cancel_requested`) with sibling `*.codex.ndjson` / `*.codex.stderr`. Live qualification writes `.work/tmp/bridge-live-run*.log`.
- Filed friction: `rg -n 'USR-[0-9]+ ' TODO.md` and `git log --grep` in the owning repo.

Classify each session as parent or child: child cwds sit under `.work/wt/` or `.work/tmp/qualify-*`.

## Skill usage

A load is a `Skill` tool call or slash command in Claude, a read of its `SKILL.md` in Codex, or Muse's recorded skill-read event. Explicit-only skills are never listed, so their numbers measure use, not firing. A skill is listed in every session whatever the task, so a low rate is expected for a narrow skill. Rate alone decides nothing.

1. **Frame.** Name the skills in question (default: the auto-triggered ones) and the window.
2. **Count.** Compute loaded over listed for each harness with saved listings. Under about 20 listed sessions is too little for a verdict.
3. **Read the loads.** Sample up to 5 per skill. Note date, harness, project, and how it loaded, and classify each as right (the task matched the description), wrong, or forced (a slash command or a brief that named it).
4. **Read the skips.** Search the session directories with `rg -l` for phrases from the skill's description, and find sessions where the situation occurred, the skill was listed, and it did not load. Sample up to 5. Classify each as a costly miss (the work lacked knowledge or a contract the skill holds, produced a worse result, or spent avoidable effort) or a harmless skip (the work reached a sound result without it). Only costly misses are under-triggering.
5. **Check outcomes.** For a sample of loads, read what the session did next. A skill that loads and is ignored needs a rewrite, not a better description. A skill that loads and is followed without improving the result or its cost is a fold or demote candidate.
6. **Decide each skill,** with its counts and one example:
   - **Keep:** loaded sessions show it contributed, or skipped sessions show it was needed.
   - **Retune:** name the situations with costly misses, or add a skip for the wrong loads.
   - **Demote** to explicit-only: it loads wrong more often than right, or its loads add cost without contributing. Low frequency alone is not a reason.
   - **Fold:** it always loads with another, or its content has an owner elsewhere.
   - **Delete:** no session needed it and none would have.

## Delegation and qualification tooling

Judge `pi-subagent-bridge`, `agentctl`, and harness MCP registrations from what sessions did, not from how the tools read.

1. Per harness, pull calls and results mentioning `pi-subagent-bridge`, `worker_*`, the MCP bridge, or qualification. Count admissions, successes, `attempts > 1`, `fallback_reason`, `acceptance_blocked`, refused cancels or resumes, quota (429) answers, and stale MCP module errors; note repeats of one error across runs. Check filed friction for tickets it already produced.
2. Back each candidate friction with the log or job file that shows it. Confirm jobs share the host before reading retry storms as flakiness.
3. Tag each item defect, guard firing correctly, or operator papercut, and separate tool defects from host noise (a noisy machine, a wedged `agent-browser` daemon).

## Report rows

A table of skill, listed, loaded, and rate per harness; costly misses and harmless skips; each decision with its evidence. For tooling, a per-harness table of admissions, successes, retries, fallbacks and blocks, then friction ranked by severity with the evidence line or job id and its tag. Name what could not be verified.
