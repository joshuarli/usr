---
name: be-ambitious
description: "Use for /be-ambitious <task> or when asked to deepen a prompt to expert standards without expanding its scope. Skip task execution, feature ideation, and cosmetic prompt polishing."
disable-model-invocation: true
metadata:
  opencode/slash: "true"
  opencode/autoinvoke: "false"
---

# Be Ambitious

Rewrite the user's task to demand better evidence, methods, and verification for the *same outcome*. Ambition is depth, not additional features, deliverables, permissions, or side quests. This is an explicit prompt-rewrite workflow, not a standing order to expand work.

Use the task after `/be-ambitious`, or the most recent user task if none follows. If neither exists, ask for the task and stop. Preserve its intent, constraints, request mode, and existing authority.

## Raise the bar

Name the discipline and the decision or result the task serves. In a few concrete sentences, establish:

1. **Expert moves:** two or three actions an excellent practitioner would take that are missing from the original request, such as resolving a competing explanation or measuring a baseline.
2. **Primary evidence:** the raw logs, source, data, artifacts, specifications, field observations, or original research to consult rather than a secondhand summary. Name actual locations when known; never invent them.
3. **Method:** the specific experiment, instrument, analysis technique, or tool suited to that evidence, including why it resolves the important uncertainty.
4. **Independent oracle:** an observable test, external benchmark, reproduction, comparison, measurement, or real-world outcome that could falsify the result. State what passing and failing look like.

Remove proposals that merely enlarge the assignment. If the best method cannot be identified confidently, say what must be established rather than guessing. For software tasks, preserve the repository's established checks and invariants instead of stacking generic verification rituals.

## Rewrite

Return one copy-ready prompt in a fenced code block. Ask it to start from the primary evidence, apply the named method, and finish with the independent pass/fail criterion. Keep it no longer than necessary and in the user's voice. Do not execute the prompt or change files unless the user separately requests that work.

**The test:** the rewritten task retains the same scope and authority but makes the strongest source, method, and independent proof explicit.

**Report:** the four improvements and the rewritten prompt.
