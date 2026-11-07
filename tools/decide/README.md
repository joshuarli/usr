# decide

A small standard-library CLI for **bounded advisory classification** with Cloudflare's **Clef-flash only**. No Worker to deploy, no agent framework, and no authority over tool permissions or execution. Installed as `decide` through `dotfiles/base/.local/bin/decide`.

## Authentication

Sign in once using `cf auth login`, then simply invoke `decide route` or `decide`. Your `cf` CLI resolves the selected OAuth profile and account, and refreshes credentials automatically. `decide` delegates inference to `cf ai run @cf/cloudflare/clef-flash --body @/dev/stdin`: request data stays on stdin, not in process arguments or temporary files. Use a recent cf release with `ai run` support.

Check login with `cf auth whoami`. `decide doctor` only checks local configuration or cf's presence; it cannot verify OAuth is currently valid. If several accounts are accessible, select the intended account through cf first. Explicit `CLOUDFLARE_API_TOKEN` and `CLOUDFLARE_ACCOUNT_ID` still take precedence and retain the direct REST path. Missing or failing cf authentication returns an unavailable advisory result and never blocks your existing deterministic router.

## Routing tasks (default in orchestrate)

`decide route` is an **agent-facing advisory tool**: it accepts a bounded, typed
`TaskBrief` rather than a task title. The self-describing local contract is the
single entry point for agents learning how to call it:

```sh
decide route --guide
```

The guide explains when to call or skip, the exact JSON fields and limits, an
example that passes the validator, and what the output means. The caller first
builds the brief from **existing, verified facts**; do not invent evidence or
perform extra expensive research merely to justify another inference call.

Example using a **synthetic** CI scenario (not an observed Niceforge incident):

```sh
decide route --baseline worker <<'JSON'
{
  "objective": "Fix an intermittent runner join timeout without weakening tests.",
  "mode": "write",
  "scope": ["runner lifecycle", "runner integration tests"],
  "evidence": [
    {
      "observation": "The synthetic regression test intermittently times out on join.",
      "source": "synthetic-fixture:test_runner_join"
    }
  ],
  "unknowns": ["Is the underlying cause a race or environment instability?"],
  "method": "unknown",
  "acceptance": ["Reproduce the failure, implement a fix, and pass a regression test."],
  "constraints": ["Do not silence failures or simply increase the timeout."],
  "risk": "moderate"
}
JSON
```

The `mode` reflects **existing permission scope**, not requested permissions.
`scope`, `evidence`, and `acceptance` may be empty when unknown; that yields a
local `skipped / insufficient_context` result without sending anything to
Cloudflare. An evidence entry has an `observation` and a `source` anchor (e.g.
test name, run ID, source file reference); a source anchor does not prove the
fact by itself. Risk `high` also abstains locally. Never include credentials,
source code, private logs, complete prompts, personal data, or transcripts.

`--baseline` overrides the tier selected by the deterministic policy. With
no override, read-only briefs use `scout` and write briefs `worker`. `--tiers`
can restrict choices: `scout` is allowed only when the brief is read-only,
and `god` is never eligible. A valid model request includes an
`abstain` option. An unavailable, abstaining, or low-confidence answer leaves
the baseline untouched. A recommendation changes the tier only at confidence
>= 0.80, margin >= 0.20, and within additional protections (no down-tier from
expert, no downgrade by more than one tier). These gates are **uncalibrated**,
not assurances; compare against labeled historic routing cases before expanding
influence.

Calls are limited to one per distinct, meaningful delegated task. Never place
`decide route` in a tool-loop or retry it to seek a different decision. A
plain-text input such as `echo "Fix tests" | decide route` is now rejected
rather than assigned an arbitrary tier. On errors, or with `DECIDE_ROUTING=off`,
use the existing deterministic policy.

## Generic decision and offline evaluation

```sh
decide doctor
decide <<'JSON'
{"state":"A sanitized brief","questions":{"urgent":{"type":"noul","instructions":"Is this urgent?"}}}
JSON
decide eval cases.jsonl
# Live evaluation must have an explicit, bounded request budget:
decide eval --live --max-calls 5 cases.jsonl
```

Only `@cf/cloudflare/clef-flash` can be invoked. The generic input validates `noul`, `choice`, and `score` question types; evaluation compares labeled routing data against an existing deterministic policy. All provider errors fail open with bounded timeouts and no request-body echo.

Note: `decide eval --live` currently uses the direct REST-credential path. Ordinary `decide` and `decide route` use your cf login when explicit credentials are absent.

See [agent setup](../../docs/agent-setup.md) for the credential boundary and [orchestrate](../../dotfiles/base/.agents/skills/orchestrate/SKILL.md) for the delegation policy.
