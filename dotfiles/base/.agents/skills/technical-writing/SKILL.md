---
name: technical-writing
description: "Apply when writing or reviewing docs, READMEs, design docs, or PR descriptions: one reader mode per document, one reading per sentence. Skip code comments, product copy, and chat replies."
---

# Technical Writing

Write so a tired engineer understands on the first read. The codebase is the word list: use the real symbol, file, flag, or command name, never a synonym. Cut every word that does no work, and when a rule makes a sentence worse, fix the sentence another way. Run `unslop` over the result; it owns word choice, sentence-case headings, and keeping articles.

## Pick the mode first

One document, one mode. Two questions choose it: does it inform doing or thinking, and does it serve learning or work?

- **Tutorial** (doing, learning): say what the learner will build. Every step shows a visible result and the output to expect. One clause of explanation and a link.
- **How-to** (doing, work): a goal the reader has, in steps, assuming competence. Action only, with forks as "If you want x, do y." Title it by the task.
- **Reference** (thinking, work): facts for lookup, dry, complete, unhedged. Mirror the structure of the thing described, and generate it from code where possible.
- **Explanation** (thinking, learning): one bounded topic with the design decisions, constraints, and alternatives. Opinion belongs here and nowhere else.

Never mix modes. Split and link.

## Sentences

- Address the reader as "you", in the present tense. Write instructions as commands: "Click Submit."
- Put the condition before the instruction and the common case before the exception.
- One instruction per sentence. Split an instruction past about 20 words and any other sentence past about 25.
- Say who acts. Passive only when the actor is unknown or beside the point.
- Give each thing one name everywhere. Call an action by one verb throughout.
- Keep "only" and "not" next to the word they change. Break long noun strings into a phrase with a verb.
- Make every "it", "this", and "they" point to one obvious noun. Never use "this" or "which" for a whole clause.
- Use periods, not semicolons. No slashes ("a, b, or both", not "and/or"), no "(s)", no idioms or Latin abbreviations.
- Headings carry the point. A task heading is a verb phrase. Numbered lists for sequences, bullets for the rest, each introduced by a full sentence.
- Link with words that say where it goes. Never "click here". Never "simply" or "easy" in a procedure.
- Vary sentence length on purpose and be specific: not "schema changes can cause issues" but "a column rename fails the build".

## PR descriptions

A PR body is a briefing a reviewer reads in under a minute: what changed, why, how it was verified, what the reviewer must decide. Do not paste logs, SHA lists, or metric tables; link them. Every number or file-tree claim must match the code at the commit that lands the PR.

Before: "Configuration of the budget script is performed via budget.json. Note that it's important to remember that running with --write should only be done when lowering it."

After: "`budget.mjs` reads the committed budget from `budget.json` and fails CI when the file count exceeds it. Run `budget.mjs --write` only to lower the budget."

**The test:** a reader who knows only the codebase can act on each sentence with one reading, and the document answers one kind of question.

**Report:** the mode chosen for each document, what you cut, and any claim you could not check against the code.
