# Recurring failures and enforcement

Read this for stages 3 and 4, in `~/usr` or the repository named in `/audit-skills <repo>`. The goal is to change the repo so the next agent cannot make the mistake again.

Assume every contributor is an agent that sees only the files it opened, copies the nearest example, and takes the shortest path that compiles. A change that looks right from one file must be right for the whole repo.

## Find the classes

Read recent commits and reverts, review comments, the `AGENTS.md` chain, comments that explain workarounds (each is a defect class agents will copy), and recent sessions in the repo for the user's corrections (sources in [sessions](sessions.md)). Group mistakes into classes. A class counts once it has happened twice.

Corrections are not only "no, wrong". Approval nudges (`/yea`, a bare "continue") and stops after the owner granted run-until-done authority are a class of their own and can outnumber explicit corrections; `python3 -I ~/usr/tools/skills/usage.py stalls --json` lists each stop with the reply that preceded it. Separate stops that asked for an effect outside the grant (merge, deploy, push, remote deletion, paid calls) from routine ones: the former are the rule working, and the fix is a wider grant, not a guard. A Claude `Stop` hook that sent permission-asking stops back to work was replayed against 14 days of sessions (November 2026) and rejected: it missed most approval stops, and many it caught asked for exactly those effects. A narrower guard blocking only "Needs you: nothing" stops with a named next step, or stops waiting on a running job, was replayed against 147 turn ends a week later and also rejected: it caught 10 of 28 nudged stops and fired on 28 others, mostly Claude stops correctly waiting for a background-task notification. Most nudges answered a real question with `/yea` or followed a context reset, which no guard should block. Start from the window or a bounded recent sample; go further back only for a class the sample shows.

## Fix each at the highest level that works

1. **Architecture.** One owner per piece of state and one supported way per task. Hide internals so the wrong import fails. Replace hand-synced lists with one source. Delete the old way and the dead code an agent would copy.
2. **Types.** Make the bad state unwritable. If it still compiles, add a lint or check whose error names the file, type, or function to use instead. If the pattern is already common, fail only changes that add more of it.
3. **Tests** of behavior. Fix or delete any test that fails the Oracle Test in `test-audit`.
4. **Docs and agent rules last,** for judgment calls only. Nothing fails when an agent skips them.

Take the strongest mechanism available. A weaker guard becomes the next template that agents copy.

## Prove

Fix the most frequent classes first, one logical change per commit. Prove each new check fails on a real past mistake by running it against the old code. A check agents will not run is not a check, so keep it fast enough to run on every change. Allow an exception only on the offending line, with a reason, an expiry, and a human's approval.

A rule nothing enforces is a repeat: fix it higher in the same change. Drop a rule once its mistake can no longer happen.

## Recorded cutoffs

- **2026-11-22T21:09:56Z** (commit `ae123235`): zsh word splitting. Agents repeatedly wrote bash-style unquoted `$VAR` loops under zsh; failures surfaced as exit 127, "file name too long", no-op commits and false monitor alerts. Agent-context zsh now runs with `SH_WORD_SPLIT`, and the shared contract asks for POSIX sh and Python. When auditing whether the class is gone, count only sessions after this timestamp. A fatal refusal on direct shim calls was implemented and reverted the same day because it broke legitimate harness calls such as `pwd`; do not reintroduce it. Follow-up at **2026-11-22T21:16:19Z** (commit `7a507a29`) corrected the claim's scope to the darwin shim, removed the competing `CLAUDE_CODE_SHELL` setting, and added contract rules for `pkill -f` self-kills, overlong socket paths, minimal ssh `PATH` and shell state across tool calls; use that timestamp as the cutoff for those classes.
