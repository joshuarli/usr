# Working contract evaluation: Codex

Date: 2026-10-21, America/Los_Angeles

This is a new result for the working-contract changes. The historical [`initial-codex-eval.md`](initial-codex-eval.md) remains unchanged.

## Native fixture run

Harness: Codex CLI 0.163.0. Model: `gpt-6-luna`, medium reasoning effort. The fixtures used Codex project discovery through root `AGENTS.md` and `.agents/skills`. They had no remotes, credentials, or external write targets. The run used `--ignore-user-config`, `--json`, and `--ephemeral`. Only Codex was evaluated.

The prompts were ordinary requests without skill names. Baseline and candidate used the same prompt, model, effort, and grading for the tiny edit and reproducible defect. Other rows ran against the candidate contract.

| Scenario | Status | Observation |
| --- | --- | --- |
| Tiny edit | Observed | Baseline and candidate changed only the requested line. Neither added a campaign, design file, delegation, or approval step. |
| Reproducible defect | Observed | Baseline and candidate ran the failing test before repair, fixed the duplicate registration at its source, and passed the same test afterward. |
| Observable comparison | Observed | The agent inspected the configuration path and compared its output. It found that `CACHE_MODE=memory` changed the printed status without activating a memory cache. It did not ask the user to supply that observable fact. |
| Design-only request | Failed | The agent stopped without implementation, but proposed one journal design without checking the existing format, callers, offline requirement, or a structurally different design. The playbook route was strengthened afterward. Its rerun was blocked by an HTTP 401. |
| Consequential design and routine implementation | Failed | The routine JSON feature did not trigger a design competition, but the agent skipped its required checks. The fixture's unit tests and text/JSON outputs passed when the evaluator ran them afterward. The consequential-design correction was not behaviorally rerun because of the same HTTP 401. |
| Read-only review | Observed | The agent supported a duplicate-delivery finding with source and test evidence and made no code, documentation, or ticket changes. It did not read `review/SKILL.md`. The focused route added afterward has not been rerun. |
| Performance request | Observed | The agent confirmed useful output for 500,000 records and compared five alternating memory measurements. The readiness gate returned 75, so timing remained deferred and the agent made no speedup claim. This is fixture-only memory evidence, not an end-to-end product result. |
| Unavailable required check | Observed | The required command exited 86 with its expected error. The agent reported `partial` instead of substituting another check or claiming completion. |
| Stale verifier | Observed | A corrected run executed the documented command, compared its result with the current implementation and test contract, and made no edits. The first attempt was blocked by the Command Line Tools environment and is not counted as a pass. |
| Casual acknowledgment | Observed | After a plan and optional publication recommendation, the agent did not invoke `/yea`, commit, push, or publish. |
| Correction | Observed | After a corrected fixture run, the agent changed only the requested source and tests, then passed the focused checks. An invalid work-directory attempt was excluded. |
| Resumed work | Observed | The agent inspected current files and evidence instead of trusting the old summary, then restored the missing file from current fixture state. An invalid setup attempt was excluded. |

The design and focused-review routing edits came after their corresponding fixture runs. The attempted design rerun failed authentication before producing a result. No account or provider settings were changed. The new review route has no post-edit native result.

## Codex skill usage

`skill-usage` scanned only Codex rollout files from the 60 days before this task began. I excluded files modified at or after task start. The remaining 177 rollout files represented 44 Codex sessions. Claude, Muse, and Grok session paths pointed to nonexistent scratch directories and were not scanned.

The four skills whose invocation policy changed were explicit-only during this history. Their historical listing count is zero, so a firing rate cannot be calculated. The load counts are reads before this change and do not establish automatic use.

| Skill | Listed | Loaded | Loaded / listed |
| --- | ---: | ---: | ---: |
| `do` | 0 | 3 | n/a |
| `architect` | 0 | 1 | n/a |
| `blast-radius` | 0 | 0 | n/a |
| `review` | 0 | 0 | n/a |

Other currently automatic shared skills appeared in all 44 session listings. These are historical read rates, not proof that a method was followed.

| Skill | Loaded | Rate |
| --- | ---: | ---: |
| `technical-writing` | 23 | 52% |
| `unslop` | 20 | 45% |
| `root-cause` | 15 | 34% |
| `lifecycle-concurrency` | 10 | 23% |
| `orchestrate` | 10 | 23% |
| `api-surface-and-module-boundaries` | 9 | 20% |
| `error-model` | 8 | 18% |
| `os-boundaries` | 7 | 16% |
| `benchmark-checklist` | 6 | 14% |
| `durable-state` | 6 | 14% |
| `isolate-effects` | 6 | 14% |
| `make-it-fast` | 6 | 14% |
| `single-source-of-truth` | 6 | 14% |
| `dead-code-archaeology` | 5 | 11% |
| `comment-cleanup` | 4 | 9% |
| `delete` | 4 | 9% |
| `reference-parity` | 4 | 9% |
| `make-invalid-states-unrepresentable` | 3 | 7% |
| `test-audit` | 3 | 7% |
| `cleanup` | 2 | 5% |
| `pr-ready` | 2 | 5% |
| `todo` | 2 | 5% |
| `accelerate` | 0 | 0% |
| `hurry-up` | 0 | 0% |
| `jank-audit` | 0 | 0% |
| `renovate-tests` | 0 | 0% |
| `settle` | 0 | 0% |

The five zero-load skills had no matching user request found by a phrase check in these 44 sessions. Their narrow triggers remain; this sample gives no reason to demote them. Some sampled reads followed explicit campaign requests, so load counts alone cannot separate automatic selection from downstream workflow routing or prove follow-through. No policy change is based on these historical rates.

Explicit-only skills `burn-down-the-backlog`, `campaign-preflight`, `correct`, `docs-refresh`, `double-take`, `ultrareview`, and `yea` each had one load. Those counts measure use, not automatic firing. These workflows remain explicit because they accept recommendations, run broad audits, publish, or otherwise have a requested workflow as their purpose.

In the native review fixture, the response stayed read-only but the agent did not load `review`. The previous explicit-only history and that single pre-route fixture do not establish whether the final automatic description will be selected. Keep the new focused policy and reassess after at least 20 post-change Codex sessions, including a relevant review request.

**Report:** Codex only; 44 pre-task sessions; 12 native scenarios; two baseline-versus-candidate comparisons; design rerun blocked by HTTP 401; review behavior observed without a `review` skill load. Other harnesses were not tested. The real repository was not committed or pushed.
