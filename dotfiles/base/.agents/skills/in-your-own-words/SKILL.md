---
name: in-your-own-words
description: "Restate in your own words what the user is trying to achieve and why, so a misread surfaces before any work starts. Use for /in-your-own-words."
disable-model-invocation: true
---

# In Your Own Words

Prove you understood the request before acting on it. Do not edit files, run builds, or start delegated work in this turn. Reading code, tests, and local instructions to ground the restatement is fine.

Restate, in your own words and not the user's phrasing:

- **Goal:** the outcome they want, and the problem or pain behind it.
- **Done:** the observable result that would tell them it worked, and the narrowest check you would run to confirm it.
- **Scope:** what is in, what you are deliberately leaving out, and which files, callers, or contracts it touches.
- **Assumptions:** each smallest reversible guess you are making to resolve ambiguity.
- **Open questions:** only those whose answer changes the contract, the user's intent, or carries real risk. Recommend an answer for each. If there are none, say so.

Cite what you read for any claim about the code. Flag where your reading and the literal request differ, since that gap is what the user needs to correct. Keep it short enough to confirm or correct in a few seconds.

Then stop and wait for the user to confirm or correct. Do not begin the work.

**Report:** the restatement under those five headings, nothing else.
