---
name: skill-eval
description: "Test whether a skill or prompt change actually changes agent behavior, blind. Use for /skill-eval, or to decide whether a skill is worth keeping or promoting."
disable-model-invocation: true
---

# Skill Eval

A skill that reads well proves nothing. Measure whether it changes what an agent does.

## Blinding

- Keep `eval`, `test`, `judge`, `rubric`, `score`, `benchmark`, `candidate`, and `variant` out of every directory, file, slug, and prompt the candidate sees.
- The candidate prompt is an organic request: the goal, not the experiment. Do not ask it to list which skills or rules it applied.
- Candidates do not know other arms exist. The judge sees outputs by sanitized label, never by arm.
- Grade rule-following from evidence in the transcript (files opened, skills loaded, shape of the code), not from what the candidate says it did.

## Steps

1. **Frame.** Name the variant (skill added, edited, or removed) and the behavior that counts as success. Write 3 to 6 concrete criteria for the judge only.
2. **Sandbox.** Make one throwaway copy of the same starting repo per run (a git worktree or temp clone with a project-shaped name). Install the variant there under a neutral name, or omit it for the baseline. Check that the global skills directory does not also supply it, or the baseline is contaminated.
3. **Prompt.** Write one task a user would really type, chosen so the rule should matter. Use the identical prompt in every arm.
4. **Run** each arm at least 3 times in separate headless sessions (`claude -p` inside the sandbox), alternating arms. One run measures noise.
5. **Judge.** One separate session scores all outputs in a single pass on one scale, against the rubric, on labels only.
6. **Check the evidence.** Read the transcripts yourself: did the arm with the skill load it and follow it? Compare each judge score with your own read. Disagreement means an ambiguous rubric or a biased judge.
7. **Decide:** promote, edit, or delete. A skill that does not move the rubric over the baseline is a deletion candidate, however good it reads.

**Reply:** variant, rubric, per-run notes, judge scores, your synthesis, and a recommendation. Say plainly if there were too few or too noisy runs to conclude.
