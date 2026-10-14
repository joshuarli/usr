---
name: skill-eval
description: "Use for /skill-eval: judge whether skills earn their place from real usage in existing Claude, Codex, Muse, and Grok sessions, and decide keep, retune, demote, fold, or delete."
disable-model-invocation: true
---

# Skill Eval

A skill that reads well proves nothing. Sessions you already ran show whether it fires and whether the work followed it, so read those. Run no new experiments, and edit no skill until each decision has counts behind it.

## Data

`skill-usage` is read-only and scans `~/.claude/projects`, `~/.codex/sessions`, `~/.local/share/muse/sessions`, and `~/.grok/sessions`.

- `skill-usage [--days N] [--all]` prints each skill's kind (auto or explicit-only), the sessions that listed it, and the sessions that loaded it, for Claude, Codex, Muse, and Grok.
- `skill-usage --show NAME` prints each load with its date, harness, project, how it loaded, and a clipped excerpt of the preceding prompt.

A load is a `Skill` tool call or slash command in Claude, a read of its `SKILL.md` in Codex or Grok, or Muse's recorded skill-read event. Grok does not save the session skill catalog, so its listed count is unavailable and its firing rate cannot be calculated. Explicit-only skills are never listed, so their numbers measure use, not firing. A skill is listed in every session whatever the task, so a low rate is expected for a narrow skill. The misses decide it.

## Steps

1. **Frame.** Name the skills in question (default: the auto-triggered ones) and the window.
2. **Count.** Run `skill-usage` and compute loaded over listed for each harness with saved listings. Under about 20 listed sessions is too little for a verdict. Grok has no saved listing count; evaluate its load examples and session coverage without inventing a firing rate.
3. **Read the loads.** For each skill, sample up to 5 from `--show`. Classify each as right (the task matched the description), wrong, or forced (a slash command or a brief that named it).
4. **Read the misses.** In Claude, Codex, and Muse, search the session directories with `rg -l` for phrases from the skill's description, and find sessions where the situation occurred, the skill was listed, and it did not load. Sample up to 5. These are under-triggering. Grok's saved history has no skill catalog, so it cannot establish listed-but-not-loaded misses.
5. **Check follow-through.** For a sample of loads, read what the session did next. Did the work follow the rules the skill sets? A skill that loads and is ignored needs a rewrite, not a better description.
6. **Decide each skill,** with its counts and one example:
   - **Keep:** it loads when it should.
   - **Retune:** name the missed situations, or add a skip for the wrong ones.
   - **Demote** to explicit-only: it rarely loads, or loads wrong more often than right.
   - **Fold:** it always loads with another, or its content has an owner elsewhere.
   - **Delete:** it never loads and no session needed it.
7. **Keep transcripts private.** Report counts, dates, and one-line paraphrases. Never paste prompts or code from a session into a skill, doc, or ticket.

Report the decisions and edit skills only when asked.

**The test:** every decision cites counts and a sampled session, and a re-run after the change shows the rate moved, or you say it is too soon to tell.

**Reply:** the window and session counts; a table of skill, listed, loaded, and rate per harness (mark Grok listing and rate unavailable); each decision with its evidence; skills with too little data; what to re-measure and when.
