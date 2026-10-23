# Campaign: add advisory decision models to usr

## Status

- **Status:** Complete. P0 through D4 accepted; the closeout acceptance gate passes.
- **Goal:** Add a local `decide` command backed by Cloudflare Workers AI, an opt-in `orchestrate` consultation, and a bounded evaluation path.
- **Deliverables:** 1. Typed, credential-safe REST client. 2. Offline tests for all client behavior. 3. Optional shadow/advisory tier consultation. 4. JSONL evaluation and concise setup documentation.
- **Last accepted checkpoint:** D4 setup documentation, repository review, and the focused closeout gate pass.
- **Provisional work:** None. Optional P3 real-data qualification needs separately authorized, owner-provided data and live calls.
- **Current ruling:** One executor in the current checkout, no parallel lanes or concurrent validation. Memory budget is not applicable. Keep API client, orchestration policy, and evaluator in sequence. Accept each item only with its named proof.
- **Next substantive milestone:** None in this campaign. P3 qualification remains optional and owner-authorized.

## Charter

This document is a plan, not implementation or commit authorization. Start the campaign only when the owner separately asks to execute it. Once started, make only the repository changes listed here and run the targeted checks below. Do not commit or push.

Use the current checkout. If the owner directs a separate worktree, place it at `.work/wt/decision-models`. Put scratch files under `.work/tmp`; confirm `.work/` is ignored through `.git/info/exclude` before the first scratch write. Never use `/tmp`, run `make`, `dl`, setup or reset scripts, install files into `~`, or change harness permissions.

Do not call Cloudflare during implementation tests. Use mocked HTTP transport. Do not run live inference without a later, explicit owner authorization. The configured Workers AI token and a plan are not inference authorization. Do not change Cloudflare billing, enable Workers Paid or AI Gateway credits, deploy resources, or modify R2.

Keep `decide` advisory. The parent agent owns the final tier and continues with existing policy on every unavailable result. No new dependency, service, database, telemetry, cache, provider system, or background activity is in scope. Python standard library only. No code comments. Do not optimize before feature and test parity.

For a failing check, establish the cause before changing code. Make at most two root-cause-directed fixes to the same failure, each based on new evidence. Then park that item with its command, output, cause, and a condition for retry; continue independent work. Do not repeat an unchanged failing attempt.

The parent records the baseline and each accepted milestone in this document. At each milestone, compare substantive progress with remaining obligations and inspect one representative diff. If five attempts finish without a milestone, steer before starting more work. Cap provisional work at one item. Revise methods within this charter, never owner requirements or proof obligations.

## Decisions

### Owner-decided

- **2026-10-22 — Workers AI only.** The user said “Workers AI only; leave R2 alone.” Scope billing and runtime setup to Workers AI. Leave the existing R2 Paid subscription unchanged.
- **2026-10-22 — Cloudflare setup permitted.** The user authorized setup through `cf`, with the requirement to stay within Workers AI Free. An account-scoped token named `usr-decision-models` was created with Workers AI Read and Workers AI Write permissions, expires 2027-10-22, and is stored in the local `vault`. The account ID is also in `vault`. The token value is not in this document or repository. Do not recreate or print it.

### Prescribed

- Use `@cf/cloudflare/clef-flash` by default. Permit only `--model clef-flash` and `--model clef`. Do not add endpoint overrides.
- Call the official Workers AI REST endpoint with `CLOUDFLARE_ACCOUNT_ID` and `CLOUDFLARE_API_TOKEN`. `cf auth login` is CLI authentication and does not provide the runtime bearer token.
- The CLI reads those variables once, sends a direct REST request, and never invokes `cf` or `vault`. A caller may prefix it with `vault` to inject the variables.
- Parse the Cloudflare REST envelope (`success`, `errors`, `messages`, `result`). Require `success: true`, no provider errors, and a valid `result` matching the published model schema. Reject an HTTP 200 whose envelope reports failure.
- Read no more than 12,288 bytes from stdin. Accept `state` as a string, object, or array. Require 1–64 questions. IDs use letters, digits, `_`, `.`, or `-`, up to 100 characters. `choice` has 2–255 options with string, object, array, or null descriptions; `score` has 2–10 ordered string, object, or array levels. `noul` instructions are a nonempty string or structured JSON and may include optional true/false criteria. Reject media and non-finite JSON numbers. Limit JSON nesting to 32 levels.
- Allow one request with a 10-second timeout and no automatic retry. Treat latency as a measured result, not a pass condition.
- Emit exactly one JSON object on stdout. Use `ok`, `unavailable`, or `invalid` status. `ok` and handled `unavailable` outcomes exit 0 so callers can continue; invalid input exits 2. `unavailable` has a compact stable reason code. Map missing configuration, timeout, DNS/TLS, authentication, quota, rate limit/capacity, provider failure, and invalid provider response to distinct reason codes. `doctor` is local-only, sends no request, checks only local credential/configuration presence, exits nonzero when values are missing, and never prints secrets.
- Preserve provider values. Validate answer IDs and types. `noul` has type `noul` and a finite `.noul` probability in `[0,1]`. `choice` has type `choice`, a permitted maximum-probability `.choice`, finite `.confidence` in `[0,1]`, and a probability for every option. `score` has type `score`, a finite `.score` in `[0, level-count - 1]`, `.legend` and probability keys for every level index, and finite `.confidence` in `[0,1]`. All distributions contain values in `[0,1]` and sum to 1 within rounding tolerance. Validate a model name matching the selected model. Require nonnegative integer `input_tokens` and `output_tokens`; never invent missing usage. Compute `elapsed_ms` with a monotonic clock. A malformed or incomplete provider response is unavailable advice.
- Clef-flash has a 24,576-token context. The byte limit does not prove token-level nontruncation. If provider usage reaches that limit or the response indicates truncation or omission, treat the advice as unavailable.
- Keep transport effects behind one injectable standard-library HTTP function. Test decision and validation behavior without network, clock, credentials, or provider calls. Do not add a framework or separate provider layer.
- `orchestrate` owns tier policy. Do not hardcode its mappings in `decide`. Keep `god` ineligible for automatic model selection and preserve all existing model, permission, and `agent-tier-gate` rules.
- Keep the live evaluator opt-in and bounded to at most 50 calls per run. Keep examples explicitly labeled and grouped by source so development cases cannot leak into held-out evaluation. The evaluation-only tier order mirrors `orchestrate` and never controls runtime routing. Do not store prompts or results automatically.
- Do not add a local daily usage counter; it cannot enforce the account-wide Workers AI quota across callers or machines.
- The only acceptable product-performance gate is evidence from actual agent sessions. Do not claim savings from classifier accuracy or token list prices.
- No added dependency means no dependency, build-time, binary-size, or startup impact.
- Keep the repo's no-formatter rule. Apply `dotfiles-health` to the `orchestrate` change and use its focused checks. Do not change agent permission posture.
- The `correct` lens is available at `dotfiles/base/.agents/skills/correct/SKILL.md` and was included in closeout review. The earlier preflight note that it was unavailable was stale.

### Delegated within bounds

- Keep the evaluator as `decide eval`; do not add another executable. Offline mode reads recorded prediction fields and makes no requests. Live mode takes labeled cases without recorded predictions and calls the same client path. Choose private helpers and exact fixture organization to keep the CLI readable. Keep the design understandable from `decide`, its focused tests, the short `orchestrate` change, and setup docs.
- Use a tolerance no wider than 0.01 when checking provider probability sums for JSON rounding. A selected choice must be among the maximum-probability options.
- The evaluator reports median latency and nearest-rank p95 only for at least 20 successful cases; otherwise tail latency is `unknown`. It reports exact and acceptable-tier agreement, confusion matrix, wrong down-tier choices, unnecessary escalations, abstentions, unavailable outcomes, confidence grouped by correctness, request count, known input-token use, and model identity. Report unavailable usage and cost as `unknown`.
- If `USR_DECIDE_TIER` is set to an unsupported value, show a short configuration error, make no request, and continue with existing routing.

## Baseline and timing

At preflight, `decide` and its tests do not exist. No relevant implementation tests or code-loop baseline exist, and no tests were run. The repository contains no existing `decide` consumer to preserve. The proposed reference is Cloudflare’s published Clef-flash input/output schema and REST envelope, plus the current `orchestrate` policy.

The final preflight documentation loop, `mdtool check --untracked campaign-decision-models.md`, took 0.38 seconds wall and 0.33 seconds CPU while checking 247 files. It reported nine expected `R001` warnings for the future paths `dotfiles/base/.local/bin/decide` and `dotfiles/base/.local/bin/decide-test.py`; it reported no errors. This is not a code-loop timing. At P0, record the first focused CLI test and lint timings before fixing their output. Reuse them while inputs remain unchanged. If a focused loop exceeds 120 seconds and blocks delivery, make one bounded loop repair and return to the next item.

No baseline product latency, live model quality, agent-session cost, or savings are known. Do not invent values. Treat live model integration and savings as unverified and outside campaign completion.

### P0 record — 2026-10-22

- `git rev-parse HEAD`: `964472855fb9d5d8196be8a94a3a773782d28fc0`; `git status --short`: clean.
- `rg --files dotfiles/base/.local/bin` confirmed that `decide` and its test were absent. `rg -n 'decide|USR_DECIDE_TIER' dotfiles/base/.agents/skills docs` found no consumer or existing runtime setting; its hits were unrelated words and skill text.
- `sh dotfiles/skills-check.sh dotfiles/base/.agents/skills` passed with exit 0 and no output.
- `.work/` is excluded by `.git/info/exclude:7`. The active Cloudflare token is present in `vault`; `cf user tokens verify` reports it active through 2027-10-22. No Cloudflare inference was run.
- First behavioral test run: 0.48 seconds wall, 0.38 CPU, 0.05 system. The extensionless executable import was corrected after an initial 0.14-second loader setup failure. The behavioral run found two issues: overlong provider bodies were misclassified, and the test expected a narrower missing-configuration object than the contract requires.
- First Ruff run: 1.56 seconds wall, 0.09 CPU, passed. Ruff was fetched into the tool cache; no project dependency was added.

### D1 accepted — 2026-10-22

- Added the executable standard-library CLI and mocked transport boundary. It validates the three typed question forms, provider envelope and result schemas, request/response bounds, stable failure reasons, and local-only diagnostics.
- The first post-fix focused run passed 16 offline tests; Ruff passed. `sym` installed the command into `.work/tmp/decision-models-home`; `decide --help` worked from that path, and the saved vault configuration passed `decide doctor` without a network request.
- No live model call was made. Linux behavior remains unverified on this macOS host.

## Sequence

### P0 — Ground the baseline

**Item P0, small.** Record the starting revision and scoped working-tree state. Confirm the missing CLI and no existing decision-model consumer. Run the baseline agent-skill structural check and record existing failures, if any. Establish `.work/` safety before any scratch writes. Capture the first focused test and lint timings when those commands exist; do not use a network request as a baseline.

**Files:** none.

**Proof:** `git rev-parse HEAD`; `git status --short`; `rg --files dotfiles/base/.local/bin`; `rg -n 'decide|USR_DECIDE_TIER' dotfiles/base/.agents/skills docs`; `sh dotfiles/skills-check.sh dotfiles/base/.agents/skills`. Record command results and timing in this section. An existing baseline failure remains inherited until shown to block an item.

### P1 — Deliver the typed CLI and offline contract tests

**Item D1, medium.** Add executable `dotfiles/base/.local/bin/decide` and focused tests. Use Python 3 standard library only and direct `urllib.request` REST calls. Use a portable `#!/usr/bin/env python3` entry point and avoid platform-specific APIs. Preserve the single shared command surface: `decide < request.json`, `decide --model clef < request.json`, `decide doctor`, and `decide --help`.

Support the documented `choice`, `noul`, and `score` inputs. Match Cloudflare’s 1–64 questions, question ID grammar, 2–255 nonempty choice option IDs, and 2–10 score levels. Choice descriptions accept string, object, array, or null. Score levels accept string, object, or array. Validate JSON before network access, bound nesting and size, reject unsupported fields/media and non-finite numbers, and keep errors free of credentials, request bodies, response bodies, and headers.

Validate the response envelope, selected model, exact question IDs and types, `noul` probability, choice options/probabilities/confidence, score/legend/probabilities/confidence, and required usage. Never infer missing fields. Classify missing configuration, timeout, DNS/TLS, authentication, quota/rate limit, provider failure, malformed JSON, and invalid provider schema as unavailable. Return invalid for caller input errors. Preserve TLS verification. Do not retry. Test on the available host; report Linux execution as unverified if no Linux environment is available.

Test the actual client with an injected mock HTTP transport. Cover valid requests of all three types; request serialization and model selection; envelope success/failure; missing, extra, malformed, non-finite, wrong-ID, wrong-type, wrong-model, or inconsistent answers; invalid IDs/criteria/models and unsupported media; byte and nesting bounds; missing credentials; timeout and transport errors; HTTP 401/403, 429, and 5xx; malformed provider JSON; secret-free output; fail-open status/exit behavior; and offline `doctor`. No test may require credentials, internet, or inference.

**Files:** `dotfiles/base/.local/bin/decide`, `dotfiles/base/.local/bin/decide-test.py`.

**Proof:** `TMPDIR="$PWD/.work/tmp" python3 -I dotfiles/base/.local/bin/decide-test.py`; `uvx ruff check dotfiles/base/.local/bin/decide dotfiles/base/.local/bin/decide-test.py`. Create `.work/tmp/decision-models-home`, then run `TMPDIR="$PWD/.work/tmp" sh dotfiles/sym -t "$PWD/.work/tmp/decision-models-home" dotfiles/base` and invoke `decide --help` with that home’s `.local/bin` prepended to `PATH`. Check test duration and stdout/stderr behavior. Keep the focused loop under 120 seconds; if it exceeds that, fix the cause once before continuing.

### P1 — Add opt-in tier advice

**Item D2, small.** After D1, edit only `dotfiles/base/.agents/skills/orchestrate/SKILL.md`. Add short instructions for `USR_DECIDE_TIER=shadow|advisory`, constructing one compact sanitized question after the parent writes a concrete brief, and invoking `decide` through `vault`. Unset means no network request and current policy remains unchanged. Shadow records advice without changing the parent’s choice. Advisory may inform the parent’s choice but does not transfer authority. The parent must justify any different choice against existing policy.

Call only when current policy leaves a meaningful, bounded ambiguity and a wrong choice has real cost. Call at most once for an unchanged brief. Offer only eligible `scout`, `mechanic`, `worker`, or `expert` choices assembled from current tier definitions. Exclude `scout` for mutating work. Never offer `god`. Preserve user model/thinking choices, authority, permission mode, provider mappings, explicit escalation, known required methods, verification, and completion requirements. On unavailable advice, continue with the original policy.

Send only a compact brief with objective, read-only or mutating effect, known facts, remaining uncertainty, scope/coupling, and acceptance. Never send raw transcripts, diffs, source files, environment variables, secret-bearing traces, or whole session histories. If the useful state cannot be separated from sensitive data, skip the call. Add no secret detector. The parent prepares the safe input.

Review concrete cases: unset; shadow recommendation differs; advisory recommendation differs; read-only versus mutating eligibility; user-specified model or escalation; unavailable result; unchanged versus materially changed brief. Do not add source-text tests or change `agent-tier-gate`.

**Files:** `dotfiles/base/.agents/skills/orchestrate/SKILL.md`.

**Proof:** `sh dotfiles/skills-check.sh dotfiles/base/.agents/skills`; manually trace the named cases against the updated skill and existing `orchestrate` rules. Run one sequential, read-only independent consistency review of the D2 diff, as `dotfiles-health` requires. The parent resolves findings and retains final acceptance. Report that this instruction flow is reviewed, not runtime-enforced.

### P1 — Add bounded labeled evaluation

**Item D3, medium.** After D1, add `decide eval`. Read explicitly supplied JSONL cases with stable case ID, source group, sanitized state and question, independently assigned expected tier or acceptable tiers, optional split, optional existing-policy choice, and optional recorded prediction.

Default evaluation requires recorded predictions and must not make network calls. Live mode accepts cases without predictions, requires an explicit `--live` flag and an explicit `--max-calls` from 1 to 50, rejects datasets larger than that maximum, and uses the same validated client path as `decide`. A campaign run must not invoke live mode without later owner authorization. Never add a traffic generator or persistent telemetry. Ship only small clearly synthetic fixtures for aggregation tests; do not claim they are historical cases.

Report the metrics in Prescribed decisions. Separate rubric-development and held-out groups; do not split one source group across both. Compare against the existing `orchestrate` choice when supplied, never an always-most-expensive baseline. Preserve disagreement for adjudication; accuracy is not end-to-end value.

**Files:** `dotfiles/base/.local/bin/decide`, its focused test, and a small synthetic fixture if needed.

**Proof:** focused offline tests for acceptable and exact agreement, confusion matrix, down-tier and escalation counts, abstention/unavailable handling, confidence groups, missing usage/cost, and bounded live-flag validation; rerun D1 tests and Ruff on changed Python files.

### P2 — Document, harden, and close

**Item D4, small.** Update `docs/agent-setup.md` with a concise usage section. Document the runtime variables, account-limited Workers AI Read/Write token scope, `vault` invocation, `cf` versus REST authentication, generic `choice` and `noul` examples, local `doctor`, opt-in controls and fallback, offline tests, bounded evaluator, privacy limits, Free-tier limit, and absence of demonstrated savings. State that no Worker deployment is needed. Do not add a new `SKILLS.md` entry.

Use the exact short setup command below. Do not write credentials to files or arguments:

```sh
vault CLOUDFLARE_API_TOKEN CLOUDFLARE_ACCOUNT_ID -- decide doctor
```

The saved vault entries are already present. Do not print, replace, or copy their values into repository files. If either entry is absent or expires, park credential-dependent work for the owner; local tests remain executable. The setup docs should also show the explicit opt-in `decide eval --live --max-calls 30 cases.jsonl` syntax and state that live evaluation needs separate owner authorization.

At close, remove only dead code introduced by this campaign. Run the repo-wide `ultrareview` required by campaign-preflight. Refresh docs and file evidenced findings through `TODO.md` and `docs/rfc/` as that skill directs; fix its P1/P2 findings. Do not activate shadow/advisory mode or call live inference. Do not claim the token is live-tested for inference.

**Files:** `docs/agent-setup.md` and any in-scope fixes from review.

**Proof:** `TMPDIR="$PWD/.work/tmp" python3 -I dotfiles/base/.local/bin/decide-test.py`; evaluator tests; `uvx ruff check` on changed Python files; `sh dotfiles/skills-check.sh dotfiles/base/.agents/skills`; `mdtool check --untracked campaign-decision-models.md docs/agent-setup.md`; review the complete diff. The exact same targeted checks form the close gate. Do not run `make check` or unrelated suites.

### P3 — Optional qualification and optimization

Do not block local completion on this phase. After implementation, the owner may provide 30–50 representative real historical briefs, independently label and sanitize them, group them by source, and authorize at most 50 live calls per run. Keep rubric-development and held-out sources disjoint. One small nonsensitive live inference may verify the real response schema only after separate owner authorization. Otherwise report inference as unverified. Report classifier quality separately from value in real sessions.

Only after classification review, ask the owner to authorize a matched-session comparison on real coding tasks: current routing versus advisory routing. Compare task success, applicable verification, total wall latency, retries and recovery, and full primary-model usage including normal input, cache reads/writes, and output. Include added decision-call/context overhead. Subscription quotas are not list-price API costs. If usage or price inputs are incomplete, report cost as `unknown`; claim no savings until observed evidence supports it.

## Acceptance

1. `decide` is installed through the existing tracked `.local/bin` structure and is callable from each configured native harness without harness-specific plugins.
2. It uses standard-library code to call the documented Workers AI endpoint and correctly handles the Cloudflare REST envelope and all three typed question forms.
3. Invalid caller input is distinguishable from unavailable advice. Malformed or unsuccessful provider results cannot become `ok`; errors do not expose credentials or request/response content.
4. `doctor` is local-only, reports missing configuration without exposing values, and never sends a request.
5. With `USR_DECIDE_TIER` unset, `orchestrate` behavior and network activity are unchanged. Shadow never changes the original tier. Advisory can inform judgment only within existing policy and authority.
6. `orchestrate` never offers `god`, never assigns read-only `scout` to mutating work, and preserves all provider and `agent-tier-gate` rules.
7. Offline client and evaluator tests pass without network, credentials, or inference. Live inference is not a completion gate.
8. The evaluator can produce a reproducible report from explicitly supplied labeled JSONL cases, rejects unbounded live runs, identifies unavailable metrics as `unknown`, and does not call synthetic fixtures real traffic.
9. `docs/agent-setup.md` explains setup, usage, fallback, privacy, costs, and limitations. No new dependency or harness permission change is introduced.
10. No campaign change modifies Cloudflare account billing, activates a paid plan or credits, touches R2, or deploys a resource. No measured savings are claimed.

## Execution boundary and contract changes

The owner started the campaign on 2026-10-22 and authorized its listed repository edits, closeout `ultrareview`, and targeted local checks. Live inference, live evaluation, account billing changes, commits, pushes, and publication remain outside this authorization.

The campaign changes a local CLI contract and adds the `USR_DECIDE_TIER` environment control. It may edit the target CLI, its focused tests/evaluator, `orchestrate`, `docs/agent-setup.md`, `TODO.md`, and `docs/rfc/` for findings produced by closeout `ultrareview`. It does not change the shared global contract, default model settings, permissions, `agent-tier-gate`, or Cloudflare account configuration.

The Workers AI account currently has no Workers Paid subscription. Workers AI Free includes 10,000 Neurons daily, resets at 00:00 UTC, and rejects further operations after the allowance. Exceeding the free allocation requires Workers Paid, where excess usage is billed. The user selected Workers AI only; leave R2 Paid untouched. Do not add an account-wide budget alert: Cloudflare says alerts notify but do not cap usage, and they include all usage-based products. Do not upgrade Workers or enable AI Gateway credits. [Workers AI pricing](https://developers.cloudflare.com/workers-ai/platform/pricing/) · [Budget alerts](https://developers.cloudflare.com/billing/manage/budget-alerts/).

Cloudflare setup completed: `cf auth whoami` succeeded; the scoped token is active and stored in `vault`; a Workers AI read-only listing call succeeded with zero records. No live inference was sent. Token write permission and the actual model response remain unverified without inference. No Cloudflare Worker or AI Gateway resource was created, and no billing setting or R2 configuration changed.

## Non-goals

No MCP or harness adapters, hooks, router skill, new tier hierarchy, main-model switching, skill injection, browser automation, transcript/diff compression, risk or security classification, test-pass or completion certification, media input, Jev/OpenRouter, AI Gateway, custom Worker, service, telemetry, database, persistent result cache, provider framework, or configuration framework. Do not change harness permission posture. These do not help prove the initial tier-advice path.

## Reference and code map

- `dotfiles/base/.agents/skills/orchestrate/SKILL.md` owns existing tier policy, provider mappings, default `worker`, and explicit `god` escalation.
- `dotfiles/base/.agents/skills/do/SKILL.md` owns task interpretation and workflow selection.
- `dotfiles/base/.agents/skills/skill-eval/SKILL.md` owns evaluation of skill effectiveness; do not duplicate it.
- `dotfiles/base/.local/bin/agent-tier-gate` owns existing Claude/Grok tier-order enforcement; leave it unchanged.
- `dotfiles/base/.local/bin/decide` will own transport, input/response validation, local diagnostics, and the optional evaluation entry point.
- `docs/agent-setup.md` owns user setup and operating instructions. `dotfiles/sym` installs the tracked bin directory.
- Cloudflare schema reference: [Clef-flash input schema](https://developers.cloudflare.com/workers-ai/models/clef-flash/schema-input.json), [output schema](https://developers.cloudflare.com/workers-ai/models/clef-flash/schema-output.json), and [REST API](https://developers.cloudflare.com/workers-ai/get-started/rest-api/).
- Cloudflare also documents [Clef-flash](https://developers.cloudflare.com/workers-ai/models/clef-flash/), [Clef](https://developers.cloudflare.com/workers-ai/models/clef/), [Workers AI pricing](https://developers.cloudflare.com/workers-ai/platform/pricing/), [Workers AI errors](https://developers.cloudflare.com/workers-ai/platform/errors/), and the [`cf` CLI](https://developers.cloudflare.com/cf/).

## Decision and campaign log

- **2026-10-22:** Replaced the draft’s request to “implement now” with a sequenced campaign plan because the requested workflow was preflight and did not start execution.
- **2026-10-22:** Owner started execution, authorized listed repository changes and local closeout checks, and prohibited live inference and commits.
- **2026-10-22:** User narrowed billing protection to Workers AI and explicitly said to leave R2 alone. Current Free allocation is the Workers AI hard stop; no alert or paid-plan change is appropriate.
- **2026-10-22:** Created and verified a one-account Workers AI token using `cf`; stored the token and account ID in `vault`. Verified token status and a non-inference read. No model call was made.
- **P0 accepted:** Initial tree and CLI absence confirmed. `.work/` is ignored. Recorded initial offline-test and Ruff timings in the P0 notes.
- **D1 accepted:** The standard-library client and its 16-test offline contract suite pass. Ruff passes. Scratch `sym` installation, CLI help, and vault-backed local `doctor` pass. No inference was sent.
- **D2 accepted:** Added opt-in shadow/advisory guidance to `orchestrate`. `skills-check.sh` exits 0 with the existing over-12,000-byte warning. Manual traces cover unset and unsupported values, shadow and advisory decisions, read-only and mutating eligibility, user choices, unavailable advice, sensitive state, and brief changes. The independent review found missing fail-open and policy-justification wording; both are fixed. This is reviewed instruction flow, not runtime enforcement.
- **D3 accepted:** Added `decide eval` with offline recorded predictions, development and held-out grouping, split leakage rejection, exact and acceptable agreement, confusion matrix, down-tier and escalation counts, abstentions, unavailable results, confidence groups, current-choice comparison, known token use, model identity, and latency metrics. Live mode requires `--live` and an explicit 1–50 `--max-calls`, rejects larger datasets before making requests, and uses the validated D1 client. Twenty offline tests and Ruff pass. A synthetic CLI report runs through the source tree and scratch `sym` installation with credentials unset; both report zero requests. The live path was tested only with mocked transport.
- **D4 accepted:** Added setup and usage guidance to `docs/agent-setup.md`, including a repeatable `cf` token command scoped to one account and Workers AI Read/Write, vault storage, runtime invocation, privacy, evaluator, and Free quota behavior. The token command was checked with `cf --dry-run` using dummy IDs. No billing setting, paid product, R2 setting, Worker, or AI Gateway resource changed.
- **Closeout review:** Refreshed the README's `macos lean` side-effect guidance and documented `claude-api` raw-log sensitivity. Removed internal narration comments from `dl`, `dotfiles/sym`, `macos/lean.py`, and `claude-api`, retaining protocol, platform, and lint-required comments. Filed `USR-16` P3 for raw logs inheriting permissive umask permissions. Reverified existing `USR-5` P2 and `USR-14`/`USR-15` P3 tickets; `USR-5` remains open with owner decisions in its RFC. No new P1/P2 finding was filed.
- **Acceptance gate:** `python3 -I dotfiles/base/.local/bin/decide-test.py` passed all 20 tests; Ruff passed for `decide`, its tests, and `macos/lean.py`; ShellCheck passed for the four changed shell scripts; `skills-check.sh` exited 0 with its existing over-12,000-byte warning. `mdtool check --untracked campaign-decision-models.md docs/agent-setup.md` reported 0 findings across 249 files. Whole-repository `mdtool check` reported 22 findings (0 errors, 4 warnings, 18 notes), one fewer note than the earlier 23-finding baseline. `git diff --check` passed. No `make`, inference, live evaluation, commits, or pushes were run.

## For the owner

The campaign report must name implementation and architecture, integration and failure behavior, exact verification and unavailable checks, measured economics, operational setup, the smallest real-data follow-up, contract changes, and repository state.

Execution is complete in the current checkout. The `cf` token and account ID are in the local vault. One synthetic Clef-flash request verified the live REST envelope and the `choice`, `noul`, and `score` answers. It used 346 input tokens, 0 output tokens, and 214 ms. Live task evaluation, Linux behavior, real-data quality, and measured economics remain unverified. No live evaluation, commits, or pushes were run.
