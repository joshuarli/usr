decide itself works, and USR_DECIDE_TIER=advisory is set (2026-10-24) in dotfiles/base/.config/ish/config.ish and dotfiles/base/.claude/settings.json env, so orchestrate may now consult it. 40 sessions with 320 delegations before that never consulted it.

Learning stays off for now.

To turn it back on later:
agent-learn enable --all-projects --usr-root ~/usr --schedule

Two things are still open, for when you want to pick this up:
- Stop-condition gap: the learner can drop "do not run the mutating command when the preflight blocks" when it generalizes, and the held-out test showed the agent ignoring the edit as a result.
- USR_DECIDE_TIER: set to advisory (see line 1); watch transcripts for decide consultations vs routing outcomes before trusting it further.
