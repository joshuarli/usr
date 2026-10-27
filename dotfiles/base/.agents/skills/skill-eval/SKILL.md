---
name: skill-eval
description: "Use for /skill-eval: judge from existing sessions whether skills earn their place, and decide keep, retune, demote, fold, or delete."
disable-model-invocation: true
metadata:
  opencode/autoinvoke: "false"
---

# Skill Eval

A skill that reads well proves nothing. Read existing sessions to see whether it fires and whether the work was better or cheaper for it. A skill earns its place by supplying necessary knowledge, preserving a required contract, improving the result, or lowering its cost. Run no new experiments, and edit no skill until each decision has counts and outcomes.

## Data

`skill-usage` is read-only and scans `~/.claude/projects`, `~/.codex/sessions`, `~/.local/share/muse/sessions`, and `~/.grok/sessions`.

- `skill-usage [--days N] [--all]` prints each skill's kind (auto or explicit-only), the sessions that listed it, and the sessions that loaded it, for Claude, Codex, Muse, and Grok.
- `skill-usage --show NAME` prints each load with its date, harness, project, how it loaded, and a clipped excerpt of the preceding prompt.

`agent-learn status` adds before and after counts of relevant skill invocation and recurring corrections for automatic promotions. `agent-learn show ID` exposes evidence and follow-up assessments. Observational only; confirm against session records. Setup and limits live in `~/usr/docs/agent-learning.md`.

A load is a `Skill` tool call or slash command in Claude, a read of its `SKILL.md` in Codex or Grok, or Muse's recorded skill-read event. Grok saves no session skill catalog, so its listed count, firing rate, and listed-but-not-loaded skips are unavailable; judge it from load examples and session coverage. Explicit-only skills are never listed, so their numbers measure use, not firing. A skill is listed in every session whatever the task, so a low rate is expected for a narrow skill. Rate alone decides nothing.

## Steps

1. **Frame.** Name the skills in question (default: the auto-triggered ones) and the window.
2. **Count.** Run `skill-usage` and compute loaded over listed for each harness with saved listings. Under about 20 listed sessions is too little for a verdict.
3. **Read the loads.** For each skill, sample up to 5 from `--show`. Classify each as right (the task matched the description), wrong, or forced (a slash command or a brief that named it).
4. **Read the skips.** In Claude, Codex, and Muse, search the session directories with `rg -l` for phrases from the skill's description, and find sessions where the situation occurred, the skill was listed, and it did not load. Sample up to 5. Classify each as a costly miss (the work lacked knowledge or a contract the skill holds, produced a worse result, or spent avoidable effort) or a harmless skip (the work reached a sound result without it). Only costly misses are under-triggering.
5. **Check outcomes.** For a sample of loads, read what the session did next. Did the skill contribute something the work needed, or only add steps? Did the work follow the rules the skill sets? A skill that loads and is ignored needs a rewrite, not a better description. A skill that loads and is followed without improving the result or its cost is a fold or demote candidate.
6. **Decide each skill,** with its counts and one example:
   - **Keep:** loaded sessions show it contributed, or skipped sessions show it was needed.
   - **Retune:** name the situations with costly misses, or add a skip for the wrong loads.
   - **Demote** to explicit-only: it loads wrong more often than right, or its loads add cost without contributing. Low frequency alone is not a reason.
   - **Fold:** it always loads with another, or its content has an owner elsewhere.
   - **Delete:** no session needed it and none would have.
7. **Keep transcripts private.** Report counts, dates, and one-line paraphrases. Never paste prompts or code from a session into a skill, doc, or ticket.

Report the decisions and edit skills only when asked.

**The test:** every decision cites counts, a sampled session, and what the work gained or lost, and never treats a higher invocation rate as success. After a change, re-run to see whether outcomes in the situations moved, or say it is too soon to tell. Causal claims need a paired comparison, which needs separate authorization.

**Report:** the window and session counts; a table of skill, listed, loaded, and rate per harness (mark Grok listing and rate unavailable); costly misses and harmless skips; each decision with its evidence; skills with too little data; what to re-measure and when.
