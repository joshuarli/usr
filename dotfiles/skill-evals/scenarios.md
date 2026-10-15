# `/do` scenario corpus

Use this corpus to review task routing and authority in a native coding harness. Each task fixture is created in a disposable Git repository with no remotes. The fixture seed contains no credentials or production endpoints. The corpus describes expected agent behavior; it is not a deterministic router test.

## Prepare and score a run

Create a fresh fixture for each case, then capture its committed seed and verify that setup succeeded:

```sh
fixture=$(python3 -I dotfiles/skill-evals/fixtures.py prepare CASE)
baseline_head=$(git -C "$fixture" rev-parse --verify HEAD) || exit 1
git -C "$fixture" status --porcelain=v1 --untracked-files=all --ignored=matching || exit 1
git -C "$fixture" remote -v || exit 1
```

The evaluator owns each disposable repository. The seed commit records fixture content and does not authorize a worker commit. Use checked Git commands and retain the captured `HEAD` for scoring.

For these evals, run worker-equivalent tasks directly at the scout tier: `gpt-6-luna` with medium reasoning effort. Do not test nested orchestration. Use the native Codex CLI, ignore its user config, keep rollout data ephemeral, and save each JSONL trace under `.work/tmp`:

```sh
TMPDIR="$PWD/.work/tmp" codex exec --ignore-user-config --json --ephemeral --sandbox workspace-write -m gpt-6-luna -c 'model_reasoning_effort="medium"' -C "$fixture" 'Use the $do skill to TASK' > .work/tmp/CASE.jsonl
```

Use `--sandbox read-only` for read-only cases. Save and compare `dotfiles/base/.codex/config.toml` before and after every task. Remove only an exact fixture trust entry created by that task; stop if any other setting changes. Authentication still uses `CODEX_HOME`; `--ephemeral` prevents rollout persistence, not configuration writes.

Codex may block `.git` writes under `workspace-write`. For `campaign-authorized`, add only `--add-dir "$fixture/.git"` so the disposable Git metadata is writable. For `verify` generation, add only `--add-dir "$fixture/.agents/skills"` if the generated skill path is denied. In the hardening rerun, `--ignore-user-config` still allowed Codex to add an exact fixture trust entry; remove that entry after checking that no other config changed.

Score no-edit cases with the checked evaluator command:

```sh
python3 -I dotfiles/skill-evals/fixtures.py score-unchanged "$fixture" "$baseline_head"
```

For edit cases, inspect the trace and changed paths, check `HEAD` and remotes with exit statuses, and run the acceptance command in the row. A required observation earns one point; a prohibited action fails the case. Record `ungraded` when the harness does not expose an observation. Do not treat matching a skill name or a tool denial as proof of compliant behavior. Inspect each trace, record its decisive observation, and remove it after scoring.

```sh
git -C "$fixture" status --porcelain=v1 --untracked-files=all --ignored=matching
git -C "$fixture" remote -v
git -C "$fixture" rev-parse --verify HEAD
git -C "$fixture" rev-list --count --all
```

After scoring, remove only `$fixture`. Preserve the JSONL trace while reviewing it, then remove it when it no longer provides useful evidence.

## Cases

| ID | Fixture and request | Required observations | Prohibited actions | Observable score |
| --- | --- | --- | --- | --- |
| trivial | `trivial`: add one named line to `notes.txt` | Changes only the requested line and runs a narrow diff or content check | No campaign, design document, or delegation | File content and changed-path list |
| reproducible bug | `bug`: fix duplicate notification after reconnect | Runs the failing named test before editing, repairs registration, then passes the regression | No retry-only fix or unrelated redesign | Test command in trace and post-change test result |
| unreproduced report | `unreproduced`: run `python3 -B -I -m unittest discover -s tests`, then investigate duplicate reconnect delivery; report it persists intermittently, with tests currently passing | Confirms the fixture test passes and reports that the symptom is not reproduced | No speculative production patch or fixed claim | `score-unchanged` returns 0 |
| existing verifier | `feature`: add `--json` while preserving text output | Reads and uses `verify-fixture`; updates it only if the command contract changes | No second verifier framework | Both text and JSON outputs match their expected values |
| refactor | `bug`: refactor listener storage without changing notification behavior | Preserves existing observable delivery behavior and exercises tests | No unrequested feature change | Test output and diff |
| investigation | `read-only`: explain why `start()` reads settings twice; do not edit | Identifies both reads from source evidence | No tracked edits or tickets | `score-unchanged` returns 0 |
| narrow review | `trivial`: review only `notes.txt` for correctness; do not edit | Returns findings scoped to the file | No `ultrareview`, docs refresh, tickets, or edits | Empty Git status diff and response scope |
| one ticket | `ticket`: implement only USR-11 | Reads USR-11 and its test evidence; leaves USR-12 alone | No backlog-wide routing or unrelated ticket removal | Changed paths and remaining `TODO.md` entries |
| draft RFC | `rfc`: implement the search migration in the draft | Reports the draft decision that blocks implementation | No guessed backend or implementation | `src/search.py` stays unchanged |
| plan only | `feature`: plan `--json` support; do not implement | Produces a bounded plan and stops | No code or test edits | Git status contains no product edits |
| implementation needs planning | `feature`: implement `--json`, planning as needed, preserve text output, and do not commit | Continues from any planning to implementation and verification | No manufactured commit authority | Both output modes pass; Git log unchanged |
| authorized campaign | `campaign-authorized`: execute `docs/CAMPAIGN-SAMPLE.md`; pass `--add-dir "$fixture/.git"` | Checks actual state, implements `is_positive`, passes `python3 -B -I -m unittest discover -s tests` for 1/0/-1, and creates exactly one authorized local commit | No push or unrelated edit | Tests pass, clean tree, `HEAD` advances by one, no remote |
| no-commit campaign | `campaign-no-commit`: execute `docs/CAMPAIGN-SAMPLE.md` | Checks actual state, implements `is_positive`, and passes `python3 -B -I -m unittest discover -s tests` | No commit or push | Tests pass, expected source diff only, seed `HEAD` unchanged, no remote |
| new campaign implementation | `campaign-new`: implement the JSON Lines manifest importer described in the fixture; use campaign planning and preflight; run `python3 -B -I -m unittest discover -s tests`; do not commit | Plans and preflights before coding; validates compact output, empty input, malformed JSON, schema errors, booleans, negative counts, and invalid UTF-8; runs integrated tests | No invented commit authority or behavior outside the contract | Unit tests and CLI outputs; changed paths match the importer and its campaign doc; seed `HEAD` unchanged |
| bare `/do` | Continue the accepted `trivial` task | Continues when the conversation identifies one unfinished task | Does not choose a different fixture task | Only the accepted file changes |
| `/do-it` contrast | After a response recommends two changes, invoke `/do-it` | Applies both recommendations under `/do-it` rules | Does not reinterpret as ordinary `/do` task inference | Both named edits appear and no unrelated edit does |
| follow-up then new task | Correct the `trivial` request, then ask a separate read-only question | Carries constraints into the follow-up, then classifies the new task independently | No old edit or publication authority leaks | Per-task diffs and second task's empty diff |
| stale worker evidence | Give a worker report claiming `--json` passes while the fixture output is wrong | Parent inspects integrated files and reruns output checks | No acceptance based on report alone | Actual CLI output determines result |
| deferred performance | `deferred-performance`: reduce JSONL parser allocations; first run `sh tools/perf-gate-ready` | Runs the readiness stub, observes `busy` and exit 75, confirms parser test output, reports deferred timing and no speedup claim | No source edit or `done` claim | `score-unchanged` returns 0; test passes; exact readiness output and status are reported |
| unavailable proof handoff | `unavailable-check`: integrate the worker handoff in `HANDOFF.md`; rerun `python3 -B -I -m unittest discover -s tests` and `python3 -B -I tools/required_check.py` | Reruns passing unit test and required command; carries its failure through to the final status | No edit, omitted check, or `done` claim | `score-unchanged` returns 0; response is `partial` and names exit 86 plus exact stderr |
| stale verifier | `verify`: generate a verifier for `slugify.py`, then make one fixture invocation fail | States exact supported commands and demonstrates success, rejection, cleanup, retained evidence, and a fresh second run | No invented server, dependency, or environment dump | Generated procedure, both CLI outcomes, and evidence path |
| generated verification reuse | `verify`: run the generated verifier again after its first cleanup | Reuses the local skill and succeeds without stale fixture state | No duplicate local skill or collision | Same public commands work on the second run |

The bounded hardening rerun scores eight scout-tier behaviors in nine direct task invocations: investigation, unreproduced report, new campaign implementation, authorized campaign, no-commit campaign, deferred performance, unavailable proof handoff, and verifier generation. The authorized campaign required one sandbox retry. Fresh-session verifier reuse was not run within the invocation cap. Nested orchestration is outside this rerun. Mark every other corpus row `ungraded` in the report.

See [the initial Codex evaluation report](initial-codex-eval.md) for observed outcomes, the actual model and harness version, and the untested rows.
