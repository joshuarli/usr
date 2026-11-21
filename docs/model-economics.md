# Model economics and controlled routing evaluations

Policy companion to `agent-config-refresh` and `orchestrate`. Research last performed **2026-11-20**. Prices, promotions, model identities, and entitlements are time-sensitive; refresh official sources **on each invocation** before recommending changes. This file is a methodology and initial baseline, **not** a quota or API-entitlement proof. No model switch occurs merely because it appears here.

## Decision hierarchy

1. Hard model/data-use bans, user constraints and runtime/effort attestation.
2. Is the model actually selectable, authenticated, within its quota, and permissible for the repository's confidentiality?
3. End-to-end acceptance: reproducible result, bounded corrections, tool reliability, and wall time for a realistic slice.
4. **Subscriber marginal economics**: which existing quota bucket is depleted, renewal date, effective rate multipliers, remaining capacity and the risk of hitting limits.
5. Public per-token API pricing, as a secondary comparator or when actually using a metered API.

The subscription fee is already committed within the billing period. This does **not** make all further calls 'free': they consume model-specific or shared allowances and have a shadow cost when remaining headroom is scarce. Flat-rate, metered, Contributor-mode and promotional free lanes are different products. Never reduce them to one token-price leaderboard. Never purchase additional API credits or silently switch plans.

## Baseline: subscription and allowance ledger

| Route | Subscription/allowance observation | Marginal evaluation |
| --- | --- | --- |
| Command Code GOAT | Public plan currently advertises **$10/month**, **$100/month DeepSeek V4.1 Flash**, **$20/month Tencent HY4**, **$15/month HY4 Flash** model-specific credits. Nominal allowance-to-plan-fee multipliers: **10×**, **2×**, **1.5×** respectively. | Credits and shared plan limits can bind differently. DeepSeek remains the default worker; test HY4 Flash as a mechanic alternative **without** interpreting its lower API rate as superior subscriber value. |
| Command Code Inkling 2 Small Free | Promotional **200 requests/day** while available. | Treat as potentially disappearing at any time; check active model catalog and rate limits at admission. No automatic paid replacement. |
| OpenCode Go | Subscription-backed with model-specific access and Contributor implications. Exact current caps and replenishment are **not verified here**. | Inspect signed-in account's current allowance and effective available model list; preserve the existing DeepSeek/Spark Pi routing until measured. |
| Muse Code | Subscription access for Spark 1.3 / Wonder 1.0; its SDK Contributor route can permit training on prompts/code/outputs. Exact current remaining usage is **not verified here**. | Compare subscription headroom to quality; do not substitute metered Meta API credentials. Exclude sensitive repo data. |
| Claude Code | Plan-governed model usage, native aliases and rate windows; exact user-specific quota **unknown**. | Opus remains the allowed frontier default; Fable is **prohibited**, notwithstanding its listing or historical pricing. |
| Codex | Signed-in account usage/rate windows (not assumed API billing); Sol 6.2 parent, Luna/Terra lower tiers. | Preserve current defaults and avoid user quota exhaustion; API token prices are not representative of account-backed Codex work. |
| Google AI Ultra / Antigravity | Subscription-governed Neon/Hydrogen native allocations; exact remaining entitlement **unknown**. | Never purchase API credits. Confirm actual concrete child model and effort: abstract `flash` and `pro` selectors do not guarantee exact pins. |
| Devin, FX / Vercel Gateway | Separate subscription, promotional or gateway-metered budgets; user-specific entitlement **unknown**. | Measure each separately and require approval before trying a newly paid route. FX Contributor models require a data-use guard. |

**Multiplier meaning:** $100 model-specific monthly credit / $10 GOAT monthly subscription = 10× *nominal credit face value relative to subscription fee*, **not** a 10× token discount. Credit exhaustion, rate multipliers, peak windows, overage settings and plan-wide caps may change the real work capacity. A model that burns $1 of its $15 bucket may be a worse default than one that burns $2 of a mostly untouched $100 bucket, depending on accepted-work throughput and renewal horizons.

## Measurement and accounting protocol

For each approved trial, record: date/time/timezone, repository/commit, task ID/acceptance proof, harness/provider, requested and *observed* concrete model, requested and *observed* effort, account plan, subscriber bucket, credit headroom before/after (if exposed), estimated API-equivalent input/output/cache billing, peak/off-peak window, retries, total turns, accepted/rejected, independent checks and wall-clock time. Record quota observations privately, not in tracked files. Never log credentials, prompts or private code in reports.

Calculate per route and task class:

- **Accepted slices / consumed allowance credit**, when credit debit can be measured.
- **Accepted slices / active wall-hour**, including review and retry.
- **Marginal headroom required until renewal**, incorporating other scheduled work and shared limits.
- **Paid overage dollars / accepted slice**, only when actual metered billing is enabled and known; otherwise mark unknown or disallowed.
- **Failure and escalation rate**, including refusals, reasoning-effort clamping and identity mismatches.

Avoid naive multiplication of API cost by the nominal plan multiplier. When a provider has free messages, rate limits rather than token credits, report requests, cooldown and acceptance per request. Treat cache-read discounts, variable provider billing, long context, and model-specific price bands separately. An unavailable model or unobservable effective effort is not an eval success.

Use `model-attest < receipt.json` after obtaining a **real** runtime receipt from an authenticated host; this is an offline field validator, not a probe. Banned families must fail closed. A repo may track `.agents/no-contributor` or set `USR_CONTRIBUTOR_MODE=deny` to suppress Contributor-backed Pi and FX worker routes. Other native clients must be controlled separately.

## Controlled next shootout (opt-in, no automatic promotion)

1. **Mechanic:** existing Muse Ember/Contributor Spark lanes vs Command Code HY4 Flash, matching edit scope and tool set. Only run on shareable code for Contributor routes.
2. **Worker:** DeepSeek V4.1 Flash baseline vs HY4-medium pilot, MiMo V2.6 Flash and GLM-5.3 Flash **only if present in an already subscribed or owner-approved model catalog**. Record model-specific subscriber debits, not just provider token list prices.
3. **Expert:** retain Claude Opus 5.5, Sol 6.2 and existing native allowed paths; no Fable, Astra, Carbon or Argon trials.
4. Use at least three independently accepted tasks per category drawn from Rust systems work, TypeScript services and Python tooling, with the same initial revision, exact acceptance gates, model effort, and independent review. Repeat where stochasticity materially affects ranking; cap cost and attempts *before* starting.
5. Promote only if improved **accepted output per scarce subscription allowance** and reliability are demonstrated on representative tasks. Otherwise preserve the known-good defaults. Require a fresh explicit user approval for a route change.

## Primary sources to refresh

- https://commandcode.ai/docs/plans/goat and https://commandcode.ai/models
- https://opencode.ai/docs/ and https://opencode.ai/changelog
- https://dev.meta.ai/docs/muse-code/configuration and https://dev.meta.ai/docs/muse-code/changelog
- https://code.claude.com/docs/en/ and https://docs.anthropic.com/en/docs/about-claude/pricing
- https://learn.chatgpt.com/docs/models and https://developers.openai.com/api/docs/models
- https://antigravity.google/docs/ and https://deepmind.google/models/model-cards/
- https://docs.devin.ai/ and https://vercel.com/docs/ai-gateway

The authenticated current plan and model catalog outrank unsourced secondary price comparisons. Every audit must state its timestamp, stale/unknown fields and the exact proposed change. **Research and recommendations are read-only by default; apply only an explicitly approved scope.**
