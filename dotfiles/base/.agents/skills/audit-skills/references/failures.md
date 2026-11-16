# Recurring failures and enforcement

Read this for stages 3 and 4, in `~/usr` or the repository named in `/audit-skills <repo>`. The goal is to change the repo so the next agent cannot make the mistake again.

Assume every contributor is an agent that sees only the files it opened, copies the nearest example, and takes the shortest path that compiles. A change that looks right from one file must be right for the whole repo.

## Find the classes

Read recent commits and reverts, review comments, the `AGENTS.md` chain, comments that explain workarounds (each is a defect class agents will copy), and recent sessions in the repo for the user's corrections (sources in [sessions](sessions.md)). Group mistakes into classes. A class counts once it has happened twice.

Corrections are not only "no, wrong". Approval nudges (`/yea`, a bare "continue") and stops after the owner granted run-until-done authority are a class of their own and can outnumber explicit corrections; `python3 -I ~/usr/tools/skills/usage.py stalls --json` lists each stop with the reply that preceded it. Separate stops that asked for an effect outside the grant (merge, deploy, push, remote deletion, paid calls) from routine ones: the former are the rule working, and the fix is a wider grant, not a guard. A Claude `Stop` hook that sent permission-asking stops back to work was replayed against 14 days of sessions (November 2026) and rejected: it missed most approval stops, and many it caught asked for exactly those effects. Start from the window or a bounded recent sample; go further back only for a class the sample shows.

## Fix each at the highest level that works

1. **Architecture.** One owner per piece of state and one supported way per task. Hide internals so the wrong import fails. Replace hand-synced lists with one source. Delete the old way and the dead code an agent would copy.
2. **Types.** Make the bad state unwritable. If it still compiles, add a lint or check whose error names the file, type, or function to use instead. If the pattern is already common, fail only changes that add more of it.
3. **Tests** of behavior. Fix or delete any test that fails the Oracle Test in `test-audit`.
4. **Docs and agent rules last,** for judgment calls only. Nothing fails when an agent skips them.

Take the strongest mechanism available. A weaker guard becomes the next template that agents copy.

## Prove

Fix the most frequent classes first, one logical change per commit. Prove each new check fails on a real past mistake by running it against the old code. A check agents will not run is not a check, so keep it fast enough to run on every change. Allow an exception only on the offending line, with a reason, an expiry, and a human's approval.

A rule nothing enforces is a repeat: fix it higher in the same change. Drop a rule once its mistake can no longer happen.
