# Recurring failures and enforcement

Read this for stages 3 and 4, in `~/usr` or the repository named in `/audit-skills <repo>`. The goal is to change the repo so the next agent cannot make the mistake again.

Keep the caller's mode: an audit proposes guards and their acceptance evidence; implementation applies them only within the requested scope. `ultrareview` uses this procedure to file findings, not to change code or CI.

Assume every contributor is an agent that sees only the files it opened, copies the nearest example, and takes the shortest path that compiles. A change that looks right from one file must be right for the whole repo.

## Find the classes

Read recent fixes and reverts, review comments, the `AGENTS.md` chain, workaround comments, and recent sessions in the repo for the user's corrections (sources in [sessions](sessions.md)). Group human and agent mistakes by their cause. A recurring class needs two independent occurrences; a fix and its review are one occurrence. Cite the incidents and check whether the current code still permits the mistake. A comment alone is a lead, not proof of a defect.

Corrections are not only "no, wrong". Approval nudges (`/yea`, a bare "continue") and stops after the owner granted run-until-done authority are a class of their own and can outnumber explicit corrections; `python3 -I ~/usr/tools/skills/usage.py stalls --json` lists each stop with the reply that preceded it. Separate stops that asked for an effect outside the grant (merge, deploy, push, remote deletion, paid calls) from routine ones: the former are the rule working, and the fix is a wider grant, not a guard. A Claude `Stop` hook that sent permission-asking stops back to work was replayed against 14 days of sessions (November 2026) and rejected: it missed most approval stops, and many it caught asked for exactly those effects. A narrower guard blocking only "Needs you: nothing" stops with a named next step, or stops waiting on a running job, was replayed against 147 turn ends a week later and also rejected: it caught 10 of 28 nudged stops and fired on 28 others, mostly Claude stops correctly waiting for a background-task notification. Most nudges answered a real question with `/yea` or followed a context reset, which no guard should block. Start from the window or a bounded recent sample; go further back only for a class the sample shows.

## Fix each at the highest level that works

1. **Architecture.** One owner per piece of state and one supported way per task. Hide internals so the wrong import fails. Replace hand-synced lists with one source. Delete the old way and the dead code an agent would copy.
2. **Types.** Make the bad state unwritable; keep an expected-error check that fails if a forbidden program starts compiling.
3. **Lint or check.** If the mistake still compiles, reject it with an error naming the file, type, or function to use instead. If the pattern is already common, fail only changes that add more of it.
4. **Behavior checks.** Use the smallest independent oracle that detects the violation. Apply [test-audit](../../test-audit/SKILL.md) before replacing coverage; prove the replacement first. Preserve tests guarding security or legal behavior.
5. **Docs and agent rules last,** for judgment calls only. Nothing fails when an agent skips them.

Take the strongest mechanism available. A weaker guard becomes the next template that agents copy.

## When a model earns its cost

Use a formal model for an evidenced concurrency, retry, crash-recovery, or state-transition failure, or a consequential invariant that simpler checks cannot settle. Start with one bounded lifecycle and an invariant from a contract or incident, not a transcription of the implementation. State why architecture, types, or a focused executable check leave a gap. Reuse the project's tooling; concurrency alone does not justify a new framework or skill.

Require the historical counterexample, repaired model, and implementation connection described in [verifier assessment](../../do/references/verification.md#formal-models). A model supplements real implementation checks: exercise the actual storage or public boundary where relevant. It does not justify replacing useful unit/property, integration, or end-to-end tests wholesale. Keep exhaustive exploration separate from the fast change check and respect the existing verification budget.

## Prove

Prioritize by impact and recurrence, one defect class per independently verifiable change. Follow the repository's commit and publication workflow; a finding does not authorize a PR or push. Prove the guard against the actual historical code in a disposable checkout or fixture, then run the same oracle against the repair. The negative control must fail for the intended violation, not a missing tool or unrelated build error; the repair must pass without weakening the invariant. If the old revision cannot run, tie a minimized reproduction to the incident and state that limit. A synthetic mutation demonstrates sensitivity, not historical replay.

Put the proof in the existing ticket's acceptance, then the commit or PR evidence; do not create another tracker. Include:

- **Class and witness:** incident links or revisions, independent occurrences, and the forbidden behavior.
- **Enforcement:** the owning boundary, chosen mechanism, and why a stronger level does not work.
- **Negative and positive controls:** exact commands, revisions or fixtures, exit results, and the decisive failure and success.
- **Execution:** the normal required check that invokes the guard, measured cost and budget, and any missing integration.
- **Limits:** assumptions, bounds, uncovered behavior, and unavailable proof.

Keep checks fast enough for the relevant change path and wire them into its existing required command. Change CI only when authorized; an unrun or manual-only check is not an enforced CI gate. Keep unavailable replay or required integration open rather than claiming the class is eliminated. Types can reject construction; a bounded model or test establishes only what its scope covers. Allow an exception only on the offending line, with a reason, an expiry, and a human's approval.

A rule nothing enforces is a repeat: fix it higher in the same change. Drop a rule once its mistake can no longer happen.

## Recorded cutoffs

- **2026-11-22T21:09:56Z** (commit `ae123235`): zsh word splitting. Agents repeatedly wrote bash-style unquoted `$VAR` loops under zsh; failures surfaced as exit 127, "file name too long", no-op commits and false monitor alerts. Agent-context zsh now runs with `SH_WORD_SPLIT`, and the shared contract asks for POSIX sh and Python. When auditing whether the class is gone, count only sessions after this timestamp. A fatal refusal on direct shim calls was implemented and reverted the same day because it broke legitimate harness calls such as `pwd`; do not reintroduce it. Follow-up at **2026-11-22T21:16:19Z** (commit `7a507a29`) corrected the claim's scope to the darwin shim, removed the competing `CLAUDE_CODE_SHELL` setting, and added contract rules for `pkill -f` self-kills, overlong socket paths, minimal ssh `PATH` and shell state across tool calls; use that timestamp as the cutoff for those classes.
