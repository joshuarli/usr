# Initial `/do` live evaluation

Date: 2026-10-14

Harness: Codex CLI 0.162.1

Model: `gpt-6-luna`, medium reasoning effort. This is the scout tier used for worker-equivalent eval tasks. All task runs used this setting directly; nested orchestration was not exercised.

Eight task executions covered the five initial smoke scenarios. The `trivial`, `bug`, `read-only`, and `feature` fixtures ran once each. Verification generation needed two targeted reruns, and fresh-session verifier reuse ran once. The five initial smoke behaviors passed; this does not grade the other corpus rows.

| Scenario | Observed result |
| --- | --- |
| `trivial` fixture | Added exactly the requested line to `notes.txt`; no other fixture files changed. |
| `bug` fixture | `python3 -m unittest` failed on the reconnect regression before repair and passed after the duplicate-registration guard was fixed. The regression test remained in the fixture. |
| `read-only` fixture | Located both settings reads in `start()` and reported the evidence without editing the fixture. |
| `feature` fixture | Added `--json`, preserved text output, passed both CLI output checks and both unit tests, and did not commit. |
| `verify` fixture and fresh-session reuse | Generated `.agents/skills/verify-slugify/SKILL.md`. A success input and four invalid inputs returned the asserted stdout, stderr, and exit status twice; a fresh Codex session loaded the skill and repeated the same five checks twice. |

The first two verifier-generation attempts could not write the hidden `.agents/skills` path inside the fixture's workspace-write sandbox. Adding that exact directory as an allowed workspace directory enabled generation and reuse. No production repository paths were granted to the fixture.

The fixture repositories had no remotes and no commits. The JSONL traces were reviewed while scoring, then removed from `.work/tmp`; this report preserves the scored observations, not the raw traces.

The other 15 corpus scenarios were not run live. No second harness or nested orchestration was tested.
