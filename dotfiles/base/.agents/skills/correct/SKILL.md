---
name: correct
description: "Find the mistakes agents keep repeating in this repo and make each one impossible. Fix at the highest level that works: architecture, then types, then a lint whose error names the fix, then a test, docs last. Prove each check against a real past mistake. Use for /correct, or when the user corrects the same thing twice."
disable-model-invocation: true
---

# Correct

The same mistakes keep getting fixed by hand. Change the repo so the next agent cannot make them.

Assume every contributor is an agent that sees only the files it opened, copies the nearest example, and takes the shortest path that compiles. A change that looks right from one file must be right for the whole repo.

## Find the classes

Read recent commits and reverts, review comments, the `AGENTS.md` chain, comments that explain workarounds, and recent sessions under `~/.claude/projects/` for the user's corrections. Group mistakes into classes. A class counts once it has happened twice.

## Fix each at the highest level that works

1. **Architecture.** One owner per piece of state and one supported way per task. Hide internals so the wrong import fails. Replace hand-synced lists with one source. Delete the old way and the dead code an agent would copy.
2. **Types.** Make the bad state unwritable. If it still compiles, add a lint or check whose error names the file, type, or function to use instead. If the pattern is already common, fail only changes that add more of it.
3. **Tests** of behavior. Fix or delete any test that would pass if every function it calls returned nothing.
4. **Docs and agent rules last,** for judgment calls only. Nothing fails when an agent skips them.

Take the strongest mechanism available. A weaker guard becomes the next template that agents copy.

## Prove and record

Fix the most frequent classes now, one commit each. Prove each new check fails on a real past mistake by running it against the old code. Run the same command locally and in CI. Allow an exception only on the offending line, with a reason, an expiry, and a human's approval.

Keep a table in the agent instruction file pairing each rule with what enforces it. A rule nothing enforces is a repeat: fix it higher in the same change. Drop a rule once its mistake can no longer happen.

**Reply:** each class with its evidence, the level chosen, and why a higher level did not work.
