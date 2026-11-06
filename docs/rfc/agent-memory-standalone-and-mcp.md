# Plan: split `agent-memory` into `~/d/agent-memory` (+ `~/usr` install) and add an MCP frontend later

Status: **plan committed; execution not started.** MCP design is **provisional and out of scope** for Phase 1. User approved the recommendations.

## Current state (important)

- `~/usr/agent-memory/` is the source of truth in the dotfiles repo: 103 tracked files, clean working tree for that path (`git -C ~/usr status -- -- agent-memory`).
- `/Users/josh/d/agent-memory/` exists and was **partially populated during discovery** (tracked sources copied in; `node_modules`/`__pycache__`/`.wrangler`/`.cloudflare` excluded) and a one-off script modified `tests/` + `eval/` path calculations there. Treat it as **scratch/staging, not authoritative**. Phase 1 Step 0 rebuilds it cleanly so the move is reviewable.
- Pre-existing oddity (do not “fix” opportunistically): `/Users/josh/usr/tools/agent-memory/src` exists, which is why `tools/skill-usage/src/skill_usage.py:18`’s `parents[2]/"agent-memory"/"src"` resolves today. The real package is `~/usr/agent-memory/`. Phase 1 must not depend on that stray path and should leave it for separate cleanup.
- `~/d/agent-memory` has no `.git` yet; `~/d/stats` is the model for a standalone project/repo shape.

## Goals

### Phase 1 — in scope (this move)
- `~/d/agent-memory` becomes a standalone, properly packaged project (own git repo) in the spirit of `~/d/stats` where applicable: Python core/package + `cloudflare/` worker, plus `tests/`, `eval/`, `docs/`.
- The package exposes real console entrypoints (`agent-learn`, `agent-sessions`, `agent-sessions-serve`) via `pyproject.toml` `[project.scripts]` (with a minimal `[build-system]`). **No `sys.path` hacks** in installed/launcher wiring.
- `~/usr` (dotfiles) **installs/hosts the CLI entrypoints** and keeps scheduling integration working, by invoking the packaged project (recommended: thin shims that run via `uv` against `~/d/agent-memory`’s project), not by importing from `~/usr/agent-memory/src`.
- `tools/skill-usage` (a `~/usr` consumer of `agent_memory`) is rewired to the packaged/located dependency without relying on the broken relative path; its documented selftest invocation remains valid.
- All `~/usr` wiring that referenced `~/usr/agent-memory/` (launchers, skill-usage, Makefile, `sync`, `ty.toml`, dev docs, AGENTS/docs refs, launchd, audit-skill ref) is updated or deliberately relocated. No dangling actionable paths. `~/usr/agent-memory/` is removed from the dotfiles repo after the new wiring is verified.

### Phase 2 — provisional, out of scope (later, after Phase 1 is green)
- Add `agent_memory.mcp` as a **thin local MCP frontend** (stdio) over the stabilized core, sharing the same state/locking/verification/redaction/tiering. Proposed v1 surface (read-safe by default): `recall`, `inspect`, session `search`/`recent`/`show`, `status`/`doctor` summary. Write/maintenance/sync/review/promotion ops stay CLI-driven unless explicitly designed in.
- MCP **does not** replace local persistence, transcript adapters/indexing, archive/object store, background scheduling/hooks, mirror/transfer/backup/serve, or crypto/review logic. CLI remains first-class for humans, cron/LaunchAgent/hooks, scripting, and ops.
- Phase 2 requires: a stabilized core API boundary, MCP tool contracts that preserve “lead vs instruction”/abstention/evidence semantics, and dotfiles/MCP host config — all deferred.

## Non-goals / constraints (Phase 1)

- No host-altering actions beyond file edits/commits in these repos (`sync` apply, launchctl load/bootstrap/bootout, deploy, package publishing) unless explicitly requested later.
- Keep behavior stable: same CLI names/flags/semantics, same state dir (`~/.agent-sessions`), same CF worker behavior/config, same test coverage intent. Refactor only what the layout/packaging move requires (plus the `--usr-root` default fix).
- Follow repo rules: no `/tmp` for scratch; no formatters; Conventional Commits, one coherent change per commit, stage only relevant files.
- `~/usr` promotion remains supported (the tool is still used against `~/usr`); the implementation becomes location-agnostic.

## Target layout

```text
~/d/agent-memory/                 (git repo)
  .gitignore
  README.md
  pyproject.toml                  # [build-system] + [project.scripts]
  src/agent_memory/...
  tests/...
  eval/...
  docs/
    cost.md
  cloudflare/                     # CF worker subproject (kept as-is structurally)
    .gitignore
    package.json / package-lock.json
    tsconfig.json
    cloudflare.config.ts
    migrations/ src/ test/ scripts/ bench/ perf.sh dev-age.sh
```

Model note vs `~/d/stats`: agent-memory is Python-package-centric plus a `cloudflare/` subproject, not a pnpm/Cargo monorepo. Keep it simple; do not introduce pnpm/Cargo structure.

## Decisions (accepted recommendations)

1. **`--usr-root` / promotion default** (`src/agent_memory/learning.py`): default to `Path.home() / "usr"` (optionally overridable by env, e.g. `USR_ROOT`, if useful) instead of `Path(__file__).resolve().parents[3]`. Validation becomes layout-agnostic (usable path/repo as intended), not monorepo-relative. Normal `~/usr` workflows keep working.
2. **Checks location**: agent-memory Python suites/eval selftests/worker checks live with the standalone project and are documented/run there. Remove agent-memory test/worker execution from `~/usr/sync` and agent-memory-specific targets from `~/usr/Makefile`; update `~/usr/docs/development.md` to point at `~/d/agent-memory`. (`~/usr` may keep `skill-usage selftest` wiring, but that check must still work.)
3. **Packaging & CLI install into `~/usr` (no `sys.path` hacks)**: add `[build-system]` and `[project.scripts]` console entrypoints in `pyproject.toml` (`agent-learn = "agent_memory.learning:main"`, `agent-sessions = "agent_memory.sessions_cli:main"`, `agent-sessions-serve = "agent_memory.serve:main"` — verify module:function names during execution). `~/usr` dotfiles launchers become thin shims that delegate via `uv run --project "$HOME/d/agent-memory" <entrypoint> ...` (preserving args/exit status; `uv` satisfies the Python>=3.15 requirement). No `sys.path.insert` to `.../agent-memory/src`.
4. **`tools/skill-usage` dependency**: make resolution explicit and correct (no `parents[2]/agent-memory/src`). Preferred: run/invoke in an environment where `agent_memory` is available (e.g. via `uv run --project ~/d/agent-memory -- python ...` for the selftest/check path) and keep the module importable; update `skill-usage` help/README paths to `~/d/agent-memory`. Because `python -I` ignores `PYTHONPATH`/user site, the documented selftest command in `docs/development.md`/any sync hook must be updated to an invocation that provides `agent_memory` (detail resolved in B2).
5. **`~/usr` campaign/TODO refs**: update actionable/current paths and test commands to `~/d/agent-memory`; handle historical narrative carefully (accurate path updates or a clear “moved to `~/d/agent-memory`” note) without fabricating history.
6. **Stray `~/usr/tools/agent-memory/`**: out of scope except ensuring nothing points at it; separate cleanup.

## Detailed change inventory (Phase 1)

### A. `~/d/agent-memory` (standalone project)

#### A1. Populate cleanly (tracked sources only)
- Rebuild from `git -C ~/usr ls-files -z -- agent-memory` into `~/d/agent-memory` (or equivalent) so `~/d/agent-memory` contains the `agent-memory/` contents at its root. Exclude `node_modules`, `__pycache__`, `*.pyc`, `.wrangler`, `.cloudflare` build artifacts. Discard/reset the current WIP staging contents first.
- Add root `.gitignore` (Python + node/CF + local): `__pycache__/`, `*.pyc`, `.work/`, `.pytest_cache/`, `.ruff_cache/`, `node_modules/`, `.cloudflare/`, `.wrangler/`, `dist/`, `*.egg-info/` (and keep/confirm `cloudflare/.gitignore`).
- `git init` and coherent Conventional Commits.

#### A2. Packaging / entrypoints
- `pyproject.toml`: add a minimal `[build-system]` (pick a simple, available backend; avoid unnecessary deps), keep `requires-python = ">=3.15"`, add `[project.scripts]` for the three CLIs (verify targets against `learning.main`, `sessions_cli.main`, `serve.main`). Ensure src layout is discoverable by the chosen backend.
- Confirm `python -m agent_memory...` / console scripts resolve with the project layout.

#### A3. Source (`src/agent_memory/`) — standalone-safe
- `src/agent_memory/learning.py`
  - `~345`: `--usr-root must name the tracked usr source` — make validation layout-agnostic (check the path is suitable for the intended promotion/usr-root use) rather than monorepo-relative.
  - `~1688`: `parents[2]/'README.md'` resolves to repo root in this layout — **no change expected** (verify).
  - `~1707`: `--usr-root` default `parents[3]` -> `Path.home() / "usr"` (or env-aware default). Update help text.
  - `~1806`: `repository = Path(__file__).resolve().parents[3]` -> use the resolved/configured usr root (or `Path.home()/"usr"`) so probe/doctor behavior remains correct for `~/usr` without assuming monorepo parents.
- `src/agent_memory/sessions_cli.py:984`: `parents[2]/"README.md"` — **no change expected** (verify).
- Grep gate: no `parents[3]`/hardcoded `~/usr/agent-memory` path assumptions in `src/` except intentional, documented ones.

#### A4. Tests (`tests/`) — repo-local paths
Current pattern: `ROOT = Path(__file__).resolve().parents[2]` (=`~/usr`) and `ROOT/"agent-memory"/...`. New: `ROOT = Path(__file__).resolve().parents[1]` (=`~/d/agent-memory`) and drop the `agent-memory/` segment.

Careful/manual review (special cases):
- `tests/test_learning_review.py`: `SCRIPT = ...parents[2] / "agent-memory/src/agent_memory/learning_review.py"`, `REPOSITORY = SCRIPT.parents[3]`, `TMP_ROOT = REPOSITORY/...`, and any doc/path expectations. Rework to repo-local (script under `ROOT/"src/agent_memory/learning_review.py"` or relative to file; repo root = `ROOT`).
- `tests/test_mirror.py`: many `ROOT/"agent-memory/cloudflare"` and `ROOT/"agent-memory/tests/fixtures/..."` refs plus `sys.path.insert` — update to `ROOT/"cloudflare"` and `ROOT/"tests/fixtures/..."` / `ROOT/"src"`. Verify worker-spawn paths/cwd assumptions.
- `tests/test_sessions.py`, `test_recall.py`, `test_recovery.py`, `test_learning.py`, `test_learning_review.py`, `test_learning_promote.py`, `test_learning_ops.py`, `test_transfer.py`, `test_identity.py`, `test_archive.py`, `test_mirror_crypto.py`: standard rewrites.

Do **not** trust the earlier staging auto-fix blindly; re-derive from a clean copy and verify file-by-file.

#### A5. Eval/bench (`eval/`) — repo-local paths + strings
- `eval/bench_{mirror,recall,sessions}.py`, `eval/live_{learning,recall}.py`, `eval/test_live_{learning,recall}.py`: `ROOT/REPOSITORY = parents[2]` -> `parents[1]`; `ROOT/"agent-memory/src"` -> `ROOT/"src"`; `ROOT/"agent-memory/cloudflare"` -> `ROOT/"cloudflare"`; `ROOT/"agent-memory/eval/..."` -> `ROOT/"eval/..."`.
- `eval/live_recall.py:72`: `~/usr/agent-memory/README.md` -> `~/d/agent-memory/README.md` (or a resilient equivalent).
- `TMP_ROOT` under `REPOSITORY/".work"/...` remains fine.

#### A6. Cloudflare (`cloudflare/`)
- Keep under `~/d/agent-memory/cloudflare/`. `package.json` `name` is `usr-memories-worker` (private) — cosmetic rename to `agent-memory-worker` is optional; confirm nothing keys on it.
- Verify from `cloudflare/`: `npm run check && npm run lint && npm run build && npm test` (per existing project checks; `npm ci`/network only as needed/available).

#### A7. Project docs
- `README.md`: rewrite commands to run from project root `~/d/agent-memory` (drop the `agent-memory/...` prefix that assumed the `~/usr` monorepo). Keep semantics identical. Document CLI installation/use from `~/usr` (the packaged console scripts + dotfiles shims / `uv run --project`), and note Phase 2 MCP is planned, not implemented.
- `docs/cost.md`: verify refs.

#### A8. Standalone verification gate
- Python suites (repo-local): `mkdir -p .work/tmp && TMPDIR="$PWD/.work/tmp" uv run --no-project --python '>=3.15' python -I tests/test_sessions.py` and `test_archive.py`, `test_transfer.py`, `test_identity.py`, `test_recovery.py`, `test_learning.py`, `test_learning_review.py`, `test_learning_promote.py`, `test_learning_ops.py`, `test_recall.py`, `test_mirror.py`, `test_mirror_crypto.py` (order/grouping flexible; note failures with evidence).
- Eval selftests (no inference): `TMPDIR="$PWD/.work/tmp" uv run --no-project --python '>=3.15' python -I eval/test_live_learning.py`, `eval/test_live_recall.py`.
- Worker: `cd cloudflare && npm run check && npm run lint && npm run build && npm test`.
- Scoped `uvx ruff check` / `uvx ty check` on changed Python if clean to run. Perf gates: follow existing rules (defer if host busy; never fake a pass).

### B. `~/usr` — install CLIs, rewire consumers, remove old tree

#### B1. Launchers (CLI installed into `~/usr`, no `sys.path`)
Rewrite to thin shims delegating to the packaged entrypoints via `uv` (recommended), preserving args/stdin/stdout/exit code and the Python>=3.15 guarantee:
- `dotfiles/base/.local/bin/agent-learn`
- `dotfiles/base/.local/bin/agent-sessions`
- `dotfiles/base/.local/bin/agent-sessions-serve`

Example shape (finalize flags during execution): `exec uv run --project "$HOME/d/agent-memory" agent-learn "$@"` (or a small Python shim using `os.execvp("uv", [..., "--project", ..., "agent-learn", *sys.argv[1:]])` if argument/quoting control is preferred). Remove all `sys.path.insert` references to `agent-memory/src`. Keep the commands discoverable/synced as before.

#### B2. `tools/skill-usage` (consumer)
- `tools/skill-usage/src/skill_usage.py:18`: remove the broken `parents[2]/"agent-memory"/"src"` hack. Make `agent_memory` resolution correct: prefer normal import when available; if an explicit fallback is kept for local dev, it must point to `Path.home()/"d"/"agent-memory"/"src"` (or `AGENT_MEMORY_SRC`) — but note `python -I` ignores `PYTHONPATH`/user site, so fallback behavior under `-I` is limited. The robust fix is to ensure the test/run environment provides the package.
- `tools/skill-usage/src/skill_usage.py:489` and `tools/skill-usage/README.md`: update “Full context”/links to `~/d/agent-memory/README.md`.
- `dotfiles/base/.local/bin/skill-usage` launcher: keep working; if needed, run with agent-memory available (e.g. via `uv run --project ~/d/agent-memory -- python` invoking the tool) — choose the least surprising form consistent with `~/usr` conventions.
- `docs/development.md` (`skill-usage selftest`) and any `sync` reference: update the command so it passes with `agent_memory` resolvable (e.g. `TMPDIR="$PWD/.work/tmp" uv run --project ~/d/agent-memory -- python -I dotfiles/base/.local/bin/skill-usage selftest`, or an equivalent verified form). Confirm the selftest still runs 6 tests OK.

#### B3. Launchd / scheduling
- `dotfiles/launchd/com.josh.agent-learning.plist.in`
- `dotfiles/launchd/com.josh.agent-sessions-mirror.plist.in`
- `dotfiles/launchd/com.josh.agent-sessions-sync.plist.in`
- Review for explicit `~/usr/agent-memory` paths; they primarily invoke synced launchers, so changes should be minimal. Update any baked paths and `plutil -lint` the results.

#### B4. Build/test wiring in `~/usr`
- `ty.toml:3` `extra-paths`: replace `"agent-memory/src"` (relative to `~/usr`, now wrong) with a robust reference to `~/d/agent-memory/src` or remove it and type-check agent-memory in its own project. Prefer a portable/home-aware approach if supported; do not leave a broken path.
- `sync:144-151`: remove the agent-memory suite/eval test runs (they move to `~/d/agent-memory`). Keep `sync` coherent; retain/fix `skill-usage selftest` if it belongs in sync’s checks.
- `Makefile:11,15,17,77-89`: remove/relocate agent-memory + worker/perf targets (`WORKER_DIR`, `PERF`, `CAMPAIGN_PYTHON`, `perf-*`, agent-memory `test`/`worker-test` wiring, `mdtool check` entries referencing `agent-memory/README.md`). Add a `Makefile` in `~/d/agent-memory` only if useful for its own checks; `~/usr/Makefile` must not reference a removed `agent-memory/` tree.
- `.agents/skills/audit-skills/SKILL.md:40`: correct `tools/agent-memory/eval/test_live_recall.py` (stale path) to `~/d/agent-memory/eval/test_live_recall.py`.

#### B5. Docs and references in `~/usr`
Update actionable paths/commands to `~/d/agent-memory`:
- `AGENTS.md:18-19,27-28` (table rows + campaign refs).
- `docs/development.md:12-27,69` — rewrite agent-memory/worker rows to `cd ~/d/agent-memory && ...` (and update skill-usage check per B2).
- `docs/agent-setup.md:38`, `docs/sync.md:23`, `docs/pi.md:64`, `SKILLS.md:5`.
- `TODO.md:17,26,35,37,44`.
- `audit.md:11` (now `~/d/agent-memory/src/agent_memory/mirror_crypto.py` or an appropriate ref).
- `docs/CAMPAIGN-AGENT-ARCHIVE.md`, `docs/CAMPAIGN-AGENT-MEMORIES-CLOUDFLARE.md`: many path/command refs — update accurately (run-from `~/d/agent-memory`), preserve historical meaning, and keep `mdtool check` passing on touched docs.
- `tools/skill-usage/README.md` (above).

#### B6. Remove old tree from `~/usr`
- `git -C ~/usr rm -r agent-memory` (103 tracked files). Focused commit.
- Grep gate: `rg -n 'agent-memory/' ~/usr` (and targeted checks) returns no actionable stale refs (only intentional, clearly-marked historical mentions if any remain).

## Sequencing (Phase 1, commit as you go)

1. **Rebuild `~/d/agent-memory` cleanly** from `~/usr` tracked sources (discard WIP staging), add `.gitignore` + `[build-system]`/`[project.scripts]`, apply A2-A7. `git init` + coherent commits in `~/d/agent-memory`. No `~/usr` changes yet.
2. **Verify standalone** (A8): Python suites + eval selftests + worker checks; fix layout/packaging issues found. Report anything deferred with evidence (e.g. perf-gate host busy, missing optional deps).
3. **Rewire `~/usr` CLIs/consumers** (B1-B3): launchers, `skill-usage`, launchd review. Smoke: `agent-learn --help`, `agent-sessions --help` resolve via the new path/packaging; `skill-usage selftest` passes under the updated invocation.
4. **Rewire `~/usr` tooling/docs** (B4-B5): `ty.toml`, `sync`, `Makefile`, dev/agent docs, TODO/audit/skill refs, campaign docs. Narrow checks: `sh -n` (touched shell), `plutil -lint` (touched plists), doc checks as used by the repo, scoped Python checks where prescribed.
5. **Remove `~/usr/agent-memory`** (B6), commit, run grep gate, fix leftovers.
6. **Final report**: commits in each repo, what moved/rewired, verification run vs deferred (and why), Phase 2 still out of scope, follow-ups (stray `~/usr/tools/agent-memory`, any packaging polish).

## Verification checklist

- [ ] `~/d/agent-memory` has no generated/vendor artifacts committed; `.gitignore` covers them; console scripts resolve.
- [ ] `rg 'parents\[3\]' ~/d/agent-memory/src` clean (or intentionally justified); `--usr-root` defaults to `~/usr` and works.
- [ ] `rg '"agent-memory"/(src|tests|cloudflare|eval)|agent-memory/(src|tests|cloudflare|eval)' ~/d/agent-memory/tests ~/d/agent-memory/eval` clean.
- [ ] Standalone Python suites + eval selftests pass (or failures explained with evidence).
- [ ] `cd ~/d/agent-memory/cloudflare && npm run check && npm run lint && npm run build && npm test` pass.
- [ ] `~/usr` launchers invoke packaged CLIs (no `sys.path` hacks) and smoke-test OK.
- [ ] `skill-usage` selftest passes under the updated, documented invocation.
- [ ] `~/usr` has no tracked `agent-memory/` tree; no broken `ty.toml`/`sync`/`Makefile` refs; actionable grep gate clean.
- [ ] Touched plists lint; touched docs pass repo checks.

## Risks / watch-outs

- **`python -I` + `skill-usage`**: `-I` ignores `PYTHONPATH`/user site, so `agent_memory` must be importable via the chosen invocation/environment, not a cwd-relative accident. Update the documented command, don’t just the source path.
- **`uv run --project` shim behavior**: confirm flags (`--no-sync`/frozen/dir) don’t surprise day-to-day use or offline/scheduled runs; LaunchAgent jobs must still resolve `uv` and the project path.
- **`test_mirror.py` / worker-coupled tests**: sensitive to paths/cwd and to built worker artifacts.
- **`learning.py` usr-root validation/probe**: keep compatible with real `~/usr`.
- **Campaign docs volume**: mechanical edits can mangle meaning — update carefully, run doc checks.
- **`ty.toml` portability**: avoid a machine-brittle broken path; keep usr typing coherent.
- **Two-repo commits**: never mix staged state across repos; report clearly.
- **Stale WIP in `~/d/agent-memory`**: rebuild clean before relying on it.

## Rollback

- Before B6, `~/usr/agent-memory` remains recoverable from `~/usr` git history and exists rebuilt in `~/d/agent-memory`. Reversal = revert usr wiring/removal commits (restore `agent-memory/`), and keep or discard `~/d/agent-memory`. No `~/.agent-sessions` data migrations.
