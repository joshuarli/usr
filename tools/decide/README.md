# decide

A small standard-library CLI for **bounded advisory classification** with Cloudflare's **Clef-flash only**. No Worker to deploy, no agent framework, and no authority over tool permissions or execution. Installed as `decide` through `dotfiles/base/.local/bin/decide`.

## Route delegated work (enabled by default in orchestrate)

Send **only a short, sanitized task summary** on stdin, not code, credentials, complete prompts, logs, transcripts, or private customer information. One task means at most one remote decision; do not put this in an inner tool loop.

```sh
printf '%s\n' 'Update known schema fixtures; acceptance test is specified.' |
  vault CLOUDFLARE_API_TOKEN CLOUDFLARE_ACCOUNT_ID -- decide route --baseline worker

# Include scout only for read-only work, or restrict tiers for a harness ceiling.
printf '%s\n' 'Find the source of the failed assertion; no edits.' |
  vault CLOUDFLARE_API_TOKEN CLOUDFLARE_ACCOUNT_ID -- decide route --baseline scout --tiers scout,mechanic,worker,expert
```

A successful response includes `recommended_tier`, `selected_tier`, `baseline_tier`, confidence, margin, and usage. `selected_tier` differs from the baseline only if confidence is at least 0.80, the lead over the runner-up is at least 0.20, and the recommendation passes hard safeguards: no down-tier from expert, no downgrade by more than one tier, no automatic `god`. These are conservative, **uncalibrated** adoption heuristics; use `decide eval` against held-out cases to measure whether Clef actually improves routing. The selected tier is advisory: `orchestrate` owns all harness-specific model, effort, permissions, escalation, and execution decisions.

The default eligible tiers are `mechanic,worker,expert` and baseline is `worker`. An unavailable response (missing credentials, quota, timeout, etc.) returns `selected_tier=baseline_tier` with exit 0 and no sensitive echo. Invalid local input exits 2. Opt out for a session with `DECIDE_ROUTING=off`. Never send a sensitive task to external inference just to get a routing suggestion.

## Generic decision and offline evaluation

```sh
decide doctor
vault CLOUDFLARE_API_TOKEN CLOUDFLARE_ACCOUNT_ID -- decide <<'JSON'
{"state":"A sanitized brief","questions":{"urgent":{"type":"noul","instructions":"Is this urgent?"}}}
JSON
decide eval cases.jsonl
# Live evaluation must have an explicit, bounded request budget:
vault CLOUDFLARE_API_TOKEN CLOUDFLARE_ACCOUNT_ID -- decide eval --live --max-calls 5 cases.jsonl
```

Only `@cf/cloudflare/clef-flash` can be invoked. The generic input validates `noul`, `choice`, and `score` question types; evaluation compares labeled routing data against an existing deterministic policy. All provider errors fail open with bounded timeouts and no request-body echo.

See [agent setup](../../docs/agent-setup.md) for the credential boundary and [orchestrate](../../dotfiles/base/.agents/skills/orchestrate/SKILL.md) for the delegation policy.
