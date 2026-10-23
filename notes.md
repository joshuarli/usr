decide itself works, but USR_DECIDE_TIER isn't set anywhere and 40 sessions with 320 delegations never consulted it. Setting USR_DECIDE_TIER=shadow is yours to do, since it changes your environment.

Learning stays off for now.

To turn it back on later:
agent-learn enable --all-projects --usr-root ~/usr --schedule

Two things are still open, for when you want to pick this up:
- Stop-condition gap: the learner can drop "do not run the mutating command when the preflight blocks" when it generalizes, and the held-out test showed the agent ignoring the edit as a result.
- USR_DECIDE_TIER: it isn't set anywhere, which is why decide is never consulted.
