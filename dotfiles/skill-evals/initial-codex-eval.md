# `/do` live evaluation

Date: 2026-10-14

## Earlier smoke run

Harness: Codex CLI 0.162.1

Model: `gpt-6-luna`, medium reasoning effort. This is the scout tier used for worker-equivalent eval tasks. All tasks ran directly; nested orchestration was not exercised.

Eight task executions covered five initial smoke scenarios. The `trivial`, `bug`, `read-only`, and `feature` fixtures ran once each. Verification generation needed two targeted reruns, and fresh-session verifier reuse ran once.

| Scenario | Observed result |
| --- | --- |
| `trivial` fixture | Added exactly the requested line to `notes.txt`; no other fixture files changed. |
| `bug` fixture | `python3 -m unittest` failed on the reconnect regression before repair and passed after the duplicate-registration guard was fixed. The regression test remained in the fixture. |
| `read-only` fixture | Located both settings reads in `start()` and reported the evidence without editing the fixture. This scope-preservation result is **ungraded**: the fixture had no tracked baseline, so Git status and `git diff` could not detect an overwrite of its untracked source. |
| `feature` fixture | Added `--json`, preserved text output, passed both CLI output checks and both unit tests, and did not commit. |
| `verify` fixture and fresh-session reuse | Generated `.agents/skills/verify-slugify/SKILL.md`. A success input and four invalid inputs returned the asserted stdout, stderr, and exit status twice; a fresh Codex session loaded the skill and repeated the same five checks twice. |

The first two verifier-generation attempts could not write the hidden `.agents/skills` path inside the fixture's workspace-write sandbox. Adding that exact directory as an allowed workspace directory enabled generation and reuse. No production repository paths were granted to the fixture. The fixture repositories had no remotes or commits. The JSONL traces were reviewed while scoring, then removed from `.work/tmp`.

## Corrected hardening rerun

Harness: Codex CLI 0.162.1, native `codex exec`. Model: `gpt-6-luna`, medium reasoning effort (scout tier). Tasks ran directly with `--ignore-user-config --ephemeral`; cases used `--sandbox read-only` or `--sandbox workspace-write` as listed in the corpus. No nested orchestration was run.

Every fixture started from a committed seed. The evaluator captured its `HEAD` before the task and used checked Git commands plus `fixtures.py score-unchanged` for no-edit cases. The score was zero for every unchanged fixture below. Traces were inspected and removed after scoring. No fixture had a remote.

| Scenario | Decisive observation | Result |
| --- | --- | --- |
| `read-only` investigation | Identified both settings reads at `src/startup.py:9-10`; scorer returned 0 and `HEAD` remained the seed. | Pass |
| `unreproduced` report | Test suite passed, duplicate delivery was not reproduced, response stated uncertainty and made no patch; scorer returned 0. | Pass |
| `campaign-new` implementation | Ran campaign planning and preflight, implemented the importer, passed 6 unit tests, all seven CLI acceptance fixtures, and `git diff --check`; seed `HEAD` unchanged and no commit. | Pass |
| `campaign-authorized` | After a sandbox retry described below, 3 tests passed and one local Conventional Commit was created: `3948f84 fix(value): implement positive check`. Tree clean, no remote. | Pass |
| `campaign-no-commit` | 3 tests passed; only `src/value.py` changed; seed `HEAD` unchanged, with no commit or remote. | Pass |
| `deferred-performance` | `sh tools/perf-gate-ready` printed `busy` and exited 75; parser test passed; scorer returned 0. Response deferred timing and made no speedup claim. | Pass; performance gate deferred |
| `unavailable-check` | Unit test passed. `python3 -B -I tools/required_check.py` exited 86 with stderr `required check unavailable`; scorer returned 0. Response retained the proof obligation and reported partial. | Pass |
| `verify` generation | Generated `.agents/skills/verify-slugify/SKILL.md`; success output/status and both invalid-input error/status cases matched in two rounds; evidence was inspected, no product edit or commit. | Pass |

The authorized campaign's first invocation passed its tests but could not write `.git/index.lock` under `workspace-write`, so it did not commit. One retry added only the disposable fixture's `.git` directory with `--add-dir`; that run made the single authorized commit. Thus the rerun used nine Codex task invocations for eight scored scenario behaviors. The fixture-local commit does not authorize commits in the real repository.

Codex added an exact project trust entry for each live fixture even with `--ignore-user-config`. Before and after each invocation, the tracked config was compared; only the exact fixture path was removed, and the global `model_reasoning_effort = "xhigh"` remained unchanged. The five stale eval-fixture trust entries were removed from the repository config.

Fresh-session verifier reuse was not run because the authorized campaign retry consumed the ninth invocation. It is ungraded. The other corpus rows not scored in this corrected rerun are: `trivial`, reproducible `bug`, existing verifier, refactor, narrow review, one ticket, draft RFC, plan only, implementation needs planning, bare `/do`, `/yea` contrast, follow-up then new task, stale worker evidence, and generated verification reuse. No full repository suite or second harness was run.

The scratch guard rejects pre-existing symlinked paths. It assumes another same-user process does not replace `.work` or `.work/tmp` between validation and use; it is not a race-proof sandbox.
