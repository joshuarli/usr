# Campaign: pinact as self-contained GitHub Actions linter/autofixer, integrated into repomod

Status: parked at the final verification boundary. The authorized code and docs are pushed; the
full `make` gates remain unrun under the repository's explicit restriction.

Deliverables:

- D1. `usr` `pinact` remains one executable, self-contained: YAML-aware pinning, `lint`, and `fix`
  with stable JSON, offline guarantees, and no runtime dependency on PyYAML-from-site,
  `jactionlint`, `actionlint`, or globally installed packages.
- D2. Vendored pure-Python YAML with provenance and license; source-positioned analysis replaces the
  line scanner; unrelated bytes (comments, quoting, line endings, anchors) preserved by fixes.
- D3. Bounded expression analyzer (lexer + Pratt parser + interpolation scanner + conservative context
  table) with proven errors distinguished from unknown/dynamic cases.
- D4. High-confidence security rules (unpinned uses, checkout credentials, permissions, high-risk
  triggers, template injection, credential exposure) with negative tests; second-tier rules only with
  context that avoids false positives.
- D5. Optional approved-pin catalogs (`--catalog`, compatible with the useful subset of
  `repomod/actions.toml`) with strong safety invariants (no silent major bumps, no SHA-as-proof).
- D6. `repomod` validates and fixes GitHub Actions files through `pinact` only: `lint --format=json`
  findings and `fix` plans replace every `jactionlint` call path, test, and doc.
- D7. `jactionlint` retired: `install_jactionlint` removed from `usr/dl`, all `_jactionlint_*` paths and
  `jactionlint` docs removed from `repomod`, after differential gates pass.
- D8. Parity evidence: weighted common-defect recall >= 90%, near-zero false positives on the valid
  corpus, no destructive autofix, no high-severity miss inside claimed coverage; gaps documented.
- D9. Docs: `usr/tools/pinact/README.md`, architecture note, rule reference, compatibility/coverage
  report, repomod integration notes, vendored-provenance file. `make check` / `make lint` (usr) and
  `make test` / `ruff` / `ty` (repomod) green.

Last previously accepted checkpoint: U8 docs and C1 retirement code are pushed: usr `7053e07` on
`campaign-pinact-u1`; repomod `efcfe5b` on `campaign-pinact-r1`.
Follow-up: review repairs are on usr and repomod `campaign-pinact-followup`; they are locally
committed and merged into each repository's default branch, and remain unpushed.
Current steering decision: the consumer profile, reported correctness defects, and duplicate
repomod implementation have been repaired on local branches. The selected corpus uses the
consumer's `default` profile and includes nine valid workflows, but its 31 labelled defects do not
establish fleet-wide parity. Broad local gates pass; the CI workflow itself has not run.
Next milestone: publish usr before repomod so repomod CI checks out the matching Pinact launcher.

## 1. Charter

- Decide, log the call, keep going. Inside the grant, choose methods and proceed without waiting.
  A plan never grants missing permission: park anything needing authority outside section 6 and run
  all remaining authorized work to done or parked.
- Hard stops (each parks the item with evidence): irreversible or outside-the-repo effects; a boundary
  in section 6; a loop that cannot check anything; pushing outside the granted branches; touching
  repomod canonical checkouts or the live catalog; mutating the owner's home outside scratch HOME.
- Fix on the way only what is egregious, in its own commit: a loop command over 10 minutes with no
  narrower equivalent; a regression over 2x the section-3 baseline wall on the same inputs; a baseline
  red that blocks the item. Record anything else seen and leave it.
- Parity before optimization. Until D8 gates pass, performance work is measured and logged, gating
  only on section-5 egregious limits. Repairs to the edit-to-acceptance loop are allowed earlier only
  to unblock a named deliverable, with the exit test in the item.
- Keep bookkeeping minimal. Reuse evidence whose revision, inputs, dependencies, environment, and
  assumptions still match; record revision plus qualifying inputs with the result. No second ledger.
- Lane width follows ownership, shared services, and acceptance capacity. `.work/wt/<lane>` is the
  only writable tree per parallel writer; all scratch and worktrees live under `.work/` in the repo
  being changed, never `/tmp` or `$TMPDIR` outside it; set `TMPDIR` to `<repo>/.work/tmp`.
  Follow the orchestrate worktree lifecycle: record exact path and branch, integrate or park with
  review, remove only the recorded path after proof, never force-delete branches or trees.
- The parent steers after every validation wave, on resume, and after five attempted items when no
  wave completes: reconcile against D1-D9, sample one accepted and one rejected/parked diff, classify
  the obstruction (regression, newly exposed debt, invalid measurement, agent-authored gate defect,
  environment prerequisite, owner-only decision), rule (continue, reorder, batch, reduce width,
  repair one prerequisite, pause), record it in section 10, update sections 0-1, notify lanes.
  Correct an unproductive method before the owner would notice; never waive proof or owner rules.
- Every commit is a Conventional Commit (`type(scope): subject`, imperative, <= 72 chars, no period;
  body says why). Item ID goes in the body, never the subject. No comments cite this doc.
- Failing items obey root-cause: reproduce small and fast, one hypothesis at a time, fix at origin,
  keep the repro as the regression test. Time-box at 3 attempts, then park with evidence, the named
  prerequisite, and the retry condition. Shared environment blockers get one owner and are not
  rediscovered per item.

## 2. Decisions

Owner-decided (2026-10-25, with the preflight recommendation accepted):

- O1. Two-repo grant. Executor may read, edit, commit, and push branch work in both `~/usr`
  (`main`) and `~/d/repomod` (`master`). Short-lived branches from the recorded base only, one
  worktree per writer under that repo's `.work/wt/<lane>`. Push only to those branches, never
  direct to `main`/`master`, never force-push, never push outside the two repos. Owner lands.
- O2. `jactionlint` exit. Keep `dl`'s `install_jactionlint` and repomod's `_jactionlint_*` paths
  working through the campaign. Swap repomod to `pinact` behind the section-5 gates, then delete
  all of it in the close phase: `install_jactionlint` in `usr/dl`, `_validate_workflows`'s
  `jactionlint` path, `_jactionlint_findings`, `_jactionlint_fixable_rule_ids`,
  `_jactionlint_fix_rules`, `_jactionlint_severity`, related tests/mocks, and `jactionlint` docs.
- O3. Catalog ownership. `~/d/repomod/actions.toml` stays the canonical fleet policy; `pinact`
  takes an explicit `--catalog path` only, with no bundled default and no silent selection.
  Offline catalog resolution beats network; never auto-upgrade or auto-downgrade across majors.
- O4. Close gate. Binding: >= 90% detection recall on the predefined weighted common-defect corpus
  with raw denominators reported; near-zero false positives on the representative valid corpus;
  full regression coverage for every implemented rule; no known destructive autofix; no known
  high-severity miss inside claimed coverage. If unreachable without unsound complexity, document
  the gaps and park the item instead of inventing parity or weakening tests.

Prescribed (settled from code and principles; reverse only on stated evidence):

- P1. Single `pinact` executable, no second binary. Keep legacy `pinact`, `pinact run`, `pinact
  --check`, `pinact run --check`, `--refresh`, `--allow-branches` behavior byte-identical except
  where section 4 explicitly reimplements the scanner on the YAML AST. Reason: repomod parses
  `pinact run --check` stderr (`_pinact_findings`, `_PINACT_CHECK_LINE`, `_PINACT_FILE_ERROR`,
  `_PINACT_PATH_ERROR`) and the existing 11 tests lock the behavior. Reverse if repomod drops the
  stderr contract for JSON everywhere first.
- P2. Vendor PyYAML 6.0.3 (or newer only with verified provenance, compatibility, security status),
  pure-Python, no C extension, no runtime `pip`/`uv`, no site-packages import, MIT license kept,
  provenance file with upstream release, source URL, SHA-256. Start from
  `yaml.compose(..., Loader=yaml.BaseLoader)` and verify `on:` stays a string. Reason: current
  `python3` has no `yaml` module (verified), and the tool must run under `python3 -I`.
  Reverse only if a smaller proven parser covers the section-8 YAML test list.
- P3. Never serialize fixes with `yaml.dump`. Edits are source spans against original bytes, sorted,
  overlap-rejected unless a proven merger handles them, expected-bytes-checked, alias/anchor-safe,
  externally-changed-file-rejected, re-parsed and re-linted before write, atomic per-file replace,
  idempotent. Reason: comments, quoting, line endings, anchors, and shell blocks must survive.
- P4. Unknown stays unknown. Dynamic `fromJSON`, unknowable matrix values, unfamiliar third-party
  inputs, custom runners, and future GitHub syntax are never hard errors. Closed-world checks apply
  only where the valid universe is actually closed, each backed by a doc reference and tests.
  Reason: false positives are the top trust risk for unattended fleet use.
- P5. Network boundary: `lint` and default `fix` are fully offline; only explicit pin resolution
  (`pin`, `fix --pin`, catalog-miss refetch) may call `git ls-remote`, batched per repo.
  Reverse only if the owner grants a new online check explicitly.
- P6. JSON stays the repomod contract: array of records with stable rule IDs, deterministic order,
  repo-relative paths, `filepath`, `line`, `column`, `id`, `severity`, `message`, `fixable`; no
  progress text on stdout in JSON mode; no SARIF unless a demonstrated consumer needs it. Reason:
  repomod's `_jactionlint_findings` already consumes this shape; the swap must be mechanical.
- P7. Exit codes: legacy pinning codes preserved; new commands use 0 clean, 1 lint/fixable findings
  remain (diff mode documents whether pending edits set it), 2 operational/invalid-use/unreadable.
  Invalid workflow YAML is a structured syntax diagnostic, never a bare traceback.
- P8. Performance is logged, not gated, until D8: parse once per file, share jobs/steps/refs/deps/
  contexts/expression locations across rules, batch `git ls-remote`, no per-rule re-parse, bound
  alias recursion, no full-document copies. Egregious limits that do gate: single-file `lint` over
  5 s, 50-file corpus over 60 s, or resident memory over 500 MB on the section-3 corpus machine.
- P9. Deletion rule: the old line scanner goes only when the AST scanner passes the full pinning
  regression plus the new YAML suite; `jactionlint` paths go only at O2's close gate with liveness
  proof (no callers, no tests, no docs, no `dl` installer). Otherwise quarantine nothing.

Delegated (executor decides inside the bound with the smallest reversible assumption, logs the call):

- G1. Module split within `usr/tools/pinact/src/pinact/` (draft layout is guidance). Bound: one
  concept per module, no plugin framework/DI/DSL/daemons/caches/services. Tie-break: fewer modules.
- G2. Exact diagnostic wording and column conventions. Bound: IDs stable, order deterministic,
  repomod parsing unbroken. Tie-break: match the underlying-defect grain of the reference, not its
  message strings.
- G3. Which P3-expression builtins beyond the required twelve get argument checks first.
  Bound: only high-confidence, tested checks ship; the rest stay unknown, not errors. Tie-break:
  catch the mistake most likely to break a real workflow.
- G4. Corpus sampling for development loops. Bound: full corpus runs at the named gates; sampled
  runs name the sample and never claim the gate. Tie-break: fastest sample that still covers the
  touched area.

## 3. Baseline

Repos and revisions (re-verify at launch; changed base invalidates reused evidence):

- `~/usr`, branch `main`, HEAD `317d681` (Bundle minimal GitHub Actions SHA pinner). Clean except
  untracked `campaign-pinact.md`. Workflows: `.github/workflows/test.yml`. `dl` installs
  `jactionlint` (`install_jactionlint`, `install_github_archive`); no `pinact` clause in `dl`.
  `make check` runs `tools/pinact/test_pinact.py`, `pinact --check`, plus repo suites; `make lint`
  runs shellcheck + ruff. `mdtool check --untracked campaign-pinact.md`: 0 errors.
- `~/d/repomod`, branch `master`, HEAD `1fb86e9` (pinact). `actions.toml` holds ~24 approved pins
  (e.g. `actions/checkout` channel `v7` version `v7.0.1`). Integration points verified in
  `src/repomod/rules/actions.py`: `_pinact_findings` shells `pinact run --check -- <files>` and
  parses stderr; `_validate_workflows`, `_jactionlint_findings`, `_jactionlint_fixable_rule_ids`
  shell `jactionlint`; the fixer (~`_tool_relative_path` region through the scratch-worktree flow)
  requires both tools, runs `jactionlint --fix` plus `pinact run` in a scratch worktree sibling of
  the root, then collects changed paths. `workflow_files`/`read_workflow_sources` live in
  `src/repomod/rules/workflows.py`; workflow-settings fixer in `rules/workflow_settings.py`
  reuses `_validate_workflows`. Tests: `tests/test_actions_release.py` (31 tests, mocks both tools),
  `tests/test_fix.py`, `tests/test_github_policy.py`. Constraints: `catalog.toml` curated user data;
  never `fix` the live catalog; canonical checkouts never reset/stashed/cleaned; rules read-only,
  fixers are validated file plans; no DB/workers/frameworks/PR creation.

Known behavior (do not mistake for regressions):

- `usr` pinact (293 lines) pins via line scanner, peels annotated tags, rejects tag/branch
  ambiguity, batches `git ls-remote`, preserves comments/quotes/CRLF/modes, fails closed on flow
  mappings, block scalars in `uses`, and `with:`/`env:` scopes (locked by 11 tests).
- `python3` on the build machine has no `yaml` module: vendoring is required, not optional.
- `jactionlint 2.3.0` is installed via `dl` and runs: it is the development-time oracle, never a
  runtime dependency of the finished `pinact`.
- repomod's GitHub Actions scratch worktree currently sits beside the root
  (`root.parent / .{name}-gha-<uuid>`); the campaign moves all such scratch under
  `<repo>/.work/tmp` with `TMPDIR` set accordingly.

Loop timings (same machine, cold enough to be comparable; re-baseline on a named change only):

- `python3 -I tools/pinact/test_pinact.py`: 11 tests OK, ~7.1 s wall.
- `python3 -I dotfiles/base/.local/bin/pinact --check` (usr repo): ~0.2 s.
- repomod `.venv/bin/pytest tests/test_actions_release.py -x -q`: 31 passed, ~0.9 s test,
  ~1.4 s wall.
- Full gates run only at named milestones: usr `make check` + `make lint`; repomod `make test`
  (`uv run pytest tests/`), `uv run ruff check src tests`, `uv run ty check`. Do not run bare
  `make`, `make sync`, `dl`, or host setup scripts against the real machine.

## 4. Sequence

Conventions: each item lists prerequisites, owned files, and acceptance proof. A lane takes whole
items end to end; initial width 2 (lane-usr, lane-repomod), provisional cap 2 items per lane.
Cross-workstream prerequisites are written on the item. First `printf '/.work/\n' >> .git/info/exclude`
(or verify) and `mkdir -p .work/tmp .work/wt` in each repo before writing.

Phase 0 — ground and pilot (first wave; loop repair only if it blocks U1):

- U1. Parsing foundation + pinning parity. Prereq: none. Owns: `usr/tools/pinact/src/pinact/**`
  (new package), `usr/dotfiles/base/.local/bin/pinact` (launcher only),
  `usr/tools/pinact/tests/**`, `usr/tools/pinact/README.md` (pinning chapters),
  vendored `usr/tools/pinact/src/pinact/_vendor/yaml/**` + provenance file. Work: vendor pure-Python
  YAML; package the tool with the launcher resolving its source location, working through the
  `make sync` symlink under `python3 -I` with no `PYTHONPATH`/installed dist, any cwd; keep
  managed-install migration; implement source-positioned parsing (`compose`+`BaseLoader`
  investigation recorded) preserving positions, quoting, anchors/aliases, flow style, literal/
  folded blocks, CRLF/LF, Unicode/BOM, duplicate-key visibility, original bytes; reimplement `pin`,
  `--check`, `--refresh`, `--allow-branches`, discovery (workflows + `action.yml/yaml`), SHA
  peeling, ambiguity/branch guards, batched `ls-remote`, version comments, atomic replace, symlink/
  concurrent-modification refusal. Proof: existing 11 tests pass unchanged in behavior; new YAML
  suite covers the section-5 YAML list including anchors, recursive aliases, merge constructs, `on:`
  as string, multi-doc/empty docs; `python3 -I` with empty site packages; no network in `--check`.
- R0. repomod probe (no behavior change). Prereq: U1 JSON shape draft. Owns: nothing committed
  (scratch test only) except optional `repomod/.work/tmp/` artifacts (ignored). Work: run the new
  `pinact lint --format=json` on repomod's own workflows/fixtures in a scratch copy and compare
  against `_jactionlint_findings` output by underlying defect, proving the swap surface is real.
  Proof: probe script + defect-by-defect table; no repomod source changed.

Phase 1 — parity and completeness (breadth before depth; every behavior gets a failing-first test):

- U2. Structural lint + `lint` CLI. Prereq: U1. Owns: same package plus `rules.py`/`workflow.py`/
  `model.py`/`source.py`. Work: file set from section 8 (malformed YAML, duplicate keys, top-level
  schema, types, unknown keys in core locations, jobs/steps/IDs, `needs` incl. cycles/duplicates,
  matrix, cron, events/filters, permissions, malformed `uses:`); scope-aware `uses:` (job, step,
  composite `runs.steps`, local reusable workflows, `action.yml` NOT workflow-rooted); closed-world
  tables only for truly closed enums, each with doc reference. CLI: `lint [path]`,
  `--profile=correctness|default|strict` (default `default`), `--format=json`, `--select`,
  `--catalog`; exit 0/1/2 per section 2; structured syntax diagnostics. Proof: rule-by-rule
  regression tests incl. the `env.uses`-is-not-an-invocation and block-scalar cases.
- U3. Expression analyzer. Prereq: U1 (may start once U1's node model is stable; security rules may
  pull it earlier but stay coherent). Owns: `expressions.py` + tests. Work: lexer + Pratt parser for
  the section-8 grammar; `${{ }}` interpolation scanner that respects quotes/delimiters (never a
  naive next-`}}` regex); conservative context table (jobs/steps IDs, `needs`, static matrix keys,
  declared inputs/outputs, per-location availability); builtins `contains startsWith endsWith format
  join toJSON fromJSON hashFiles success failure cancelled always` with case-insensitivity and
  per-field legality; high-confidence type/arity/property errors only; explicit
  valid-unknown vs unsupported vs proven-error representation with unsupported-rate tracking.
  Proof: section-5 expression matrix incl. nesting, escaping, whitespace, missing delimiters,
  static vs dynamic matrix, `needs`/`steps`/inputs, multiline shell interpolation.
- U4. Security rules. Prereq: U2, U3-scanner (coordinate, do not duplicate traversal). Owns:
  `rules.py` additions + tests. Work: first priority only — unpinned uses (share the pinning `uses`
  representation), unsafe checkout credentials (`persist-credentials` report by default, autofix
  only under explicit policy), permissions (missing vs provably excessive, all scopes), high-risk
  triggers with permissions/checkout/untrusted-execution context, template injection from known
  untrusted sources into `run:` sinks with quoting awareness, credential exposure with non-naive
  matching. Second-priority items only with proven context. Proof: per-rule vulnerable / safe /
  lookalike-safe / unknown-dynamic / multi-job / privilege-scoped cases; explicit negatives.
- U5. Autofix engine + catalogs. Prereq: U1-U2 (edits), U4 (which fixes are safe). Owns:
  `fixes.py`, `pinning.py` catalog support, `fix` CLI. Work: span edits, sort, overlap/expected-bytes/
  alias-ambiguity/serialization/external-change/symlink/path validation; in-memory reparse, finding
  resolved, no new correctness errors, idempotence, then per-file atomic write via target-dir
  tempfiles preserving modes; non-destructive formatting guarantee; safe fixes from the
  section-8 list (SHA pinning, comment normalization, unambiguous config repairs, permission/
  timeout blocks only under explicit configured policy, obsolete workflow commands with known
  semantics, generic workflow-settings capabilities without hardcoding repomod fleet strings);
  `fix [--diff] [path]`, `fix --pin` (only pin path may network); `--catalog` validation per
  section-8 (channel/version/sha shape, major consistency, ambiguous/unlabeled-SHA refusal,
  no silent downgrade, subpath preservation, missing-approval reporting, offline-first).
  Proof: per-fix 10-step verification from section 5 (diagnostic, diff-only mode, bytes, reparse,
  resolved, no new errors, idempotent, lint-clean, ambiguous-input-unchanged) plus overlap/symlink/
  read-only/concurrent-change/catalog-failure/networkSilence cases; fuzz/property tests over edit
  invariants with stdlib randomness.
- R1. repomod validation swap. Prereq: U2 JSON stable. Owns:
  `repomod/src/repomod/rules/actions.py` (`_pinact_findings` extension, `_jactionlint_findings`
  replacement, `_validate_workflows` jactionlint path), `tests/test_actions_release.py`,
  `tests/test_github_policy.py`, `docs/policy-development.md` (gha-syntax chapter),
  `docs/design.md` (affected paragraphs). Work: validate changed files with
  `pinact lint --profile=correctness --format=json` offline (same flags family as the old
  `jactionlint --profile=correctness --no-online --format=json` invocation), keep severity mapping
  (`shellcheck SC...:` handling preserved), keep operational findings when the tool is missing until
  R4. Proof: mocked-tool unit tests updated; live probe on repomod fixtures shows same-defect
  agreement; `pytest tests/test_actions_release.py tests/test_github_policy.py`, `ruff`, `ty`.
- R2. repomod fixer swap. Prereq: U5 `fix` + R1. Owns: `repomod/src/repomod/rules/actions.py`
  (fixer flow), `src/repomod/rules/workflow_settings.py` (only its `_validate_workflows` call),
  `src/repomod/fix.py` (only if the plan protocol needs it; otherwise untouched),
  `tests/test_fix.py`, fixtures under `tests/`. Work: replace the `jactionlint --fix` +
  `pinact run` two-tool scratch sequence with `pinact fix` (+ `pinact fix --pin` only where pin
  updates are intended) in a scratch worktree under `.work/tmp` (not beside the root); preserve
  the plan protocol (fixer produces plan, plan validated, scope-checked, introduced errors rejected
  via re-lint, remaining fixables reported); never touch canonical checkouts or the live catalog;
  keep fleet policy (exact concurrency group, shell string) in repomod, generic analysis in `pinact`.
  Proof: `pytest tests/test_fix.py` plus end-to-end fixer tests on copied catalogs; no live-catalog
  mutation; scratch cleanup verified.
- R3. repomod catalog + policy wiring. Prereq: U5 catalog, R2. Owns: `repomod/actions.toml`
  (read-only except explicit `pins refresh` flows owned by existing code), catalog-passing
  call sites, `docs/tagging.md`/`docs/design.md` paragraphs that describe pins. Work: pass the
  approved catalog explicitly to `pinact --catalog`; preserve subpath refs, version-comment checks,
  unlabeled-SHA and major-change refusals; keep `refresh_pins`/`load_pins` semantics in repomod.
  Proof: copied-catalog mutation tests incl. major-bump refusal, ambiguous annotation refusal,
  newer-explicit-version never downgraded.

Phase 2 — hardening (runs with Phase 1 findings, not after everything):

- U6. Differential corpus + remediation. Prereq: U2-U4. Owns: `usr/tools/pinact/tests/fixtures/**`
  (small, checked in), corpus scripts/docs (reproduce the broad comparison without copying huge
  upstream trees), coverage table. Work: build the 7-source corpus (usr workflows, repomod
  workflows+fixtures, selected `repomod/catalog.toml` repos via temp/read-only checkouts, upstream
  actionlint + jactionlint fixtures, zizmor fixtures, custom edge cases); harness runs
  `jactionlint --profile=correctness --no-online --format=json` vs
  `pinact lint --profile=correctness --format=json`, normalizes by underlying defect (never message
  strings), tracks true positives/misses/false positives/unsupported families/location accuracy/
  fix safety; populate the section-5 table with raw denominators; remediate misses and false
  positives per section-8 priority order P0-P4 (expression work may precede P2 only as U3 already
  provides). Proof: coverage report with numbers; every implemented rule has regression tests.
- R4. (No separate item; part of close.) Gate check that R1-R3 plus U6 meet O4 before any deletion.

Phase 3 — optimization and polish (only after D1-D6 work end to end; move any earlier optimization
here unless it unblocks a feature):

- U7. Waived by the owner on 2026-10-25: performance is not an issue for this campaign. No U7
  optimization was retained and no speedup is claimed.
- U8. Docs + installation. Prereq: U5-U6, R1-R3 behavior frozen. Owns: `usr/tools/pinact/README.md`,
  architecture note, rule reference (ID/description/severity/profile/fix/limits), compatibility report,
  repomod integration notes (replaces the old migration guide: how repomod calls `lint --format=json`
  and `fix`, passes `--catalog`, keeps PR/worktree orchestration), provenance file, `Makefile` test
  target updates, launcher docs. Work: keep `make sync` symlink mechanism; no downloader binary, no
  installer, no release build. Proof: `mdtool links/refs` clean on touched docs; install behavior
  tested only with scratch HOME under `.work/` per repo conventions.

Phase 4 — close (single wave; no new behavior):

- C1. Delete dead paths, run the adversarial review, write the final report. Prereq: O4 gates met.
  Owns: `usr/dl` (`install_jactionlint` removal), `usr` superseded scanner deletion, repomod
  `_jactionlint_*` + `jactionlint` fixer path + doc mentions, both repos' docs. Work: prove
  liveness-dead with caller/test/doc/script search; delete implementation, tests, config, docs,
  exports, and gates for the dead side in the same change (no tombstones); conduct the section-8
  adversarial review (parsing, expressions, security, autofix, architecture, testing) and fix P1/P2
  findings; run full gates: usr `make check` + `make lint`, repomod `make test` + `ruff` + `ty`;
  write the final report (section 5, item 11). Proof: full green on the exact trees; `which`
  searches show no live `jactionlint` reference except the historical report.

## 5. Acceptance

Each deliverable passes only on its proof. Nothing waits on a person. Documented limitation beats
unsound approximation; never weaken or delete a test to pass, and never fabricate coverage.

- D1-D2 (pinning + YAML): `python3 -I tools/pinact/test_pinact.py` green (~7 s baseline);
  `python3 -I dotfiles/base/.local/bin/pinact --check` clean on the repo (~0.2 s); new YAML suite
  green under `python3 -I` with emptied site packages; explicit `--catalog` absent by default.
- D3 (expressions): expression suite green incl. all section-8 cases; unsupported-rate metric
  reported; no proven-error misclassified as valid in the suite.
- D4 (security): per-rule vulnerable/safe/lookalike/unknown suites green; zero known false positive
  on the valid corpus; every finding cites its trust model.
- D5 (catalogs): catalog suite green (invalid records, major-bump refusal, unlabeled-SHA refusal,
  no silent downgrade, subpath preservation, offline-first with network stubbed to fail).
- D6 (repomod swap): `.venv/bin/pytest tests/test_actions_release.py tests/test_github_policy.py
  tests/test_fix.py -q` green; `uv run ruff check src tests` and `uv run ty check` green; live
  scratch-checkout probe shows defect-level agreement with the old path before it is removed.
- D7 (retirement): `rg -n jactionlint usr/dl repomod/src repomod/tests repomod/docs` shows only the
  historical closeout report; `dl` still installs everything else; repomod suites green without any
  `jactionlint` binary on PATH.
- D8 (parity): coverage report with raw denominators meets O4; corpus reproduction scripts rerun the
  harness on a fresh checkout; no destructive fix in the suite; `pinact` has no runtime dependency
  on `jactionlint` (run gates with it absent from PATH).
- D9 (docs + gates): usr `make check` and `make lint` green; repomod `make test`, `ruff`, `ty`
  green; `mdtool check` on touched docs clean; final report lists: (1) commit SHAs in both repos,
  (2) architecture + module sizes, (3) vendored size + provenance, (4) CLI commands, (5) rules by
  correctness/security/policy, (6) safe autofixes, (7) differential results, (8) unsupported
  behavior, (9) false positives/regressions found and fixed, (10) runtime + test performance
  (waived with U7),
  (11) exact outstanding work for the fleet to rely on `pinact` (should be none, or named parks).
- Offline proof: `lint` and default `fix` suites pass with all network helpers stubbed to fail.
- Idempotence proof: every fix test asserts second-run no-change plus diff-mode writes nothing.

## 6. Execution boundary

Authorized (owner grant O1-O4, 2026-10-25): read, edit, run, and test in `~/usr` and `~/d/repomod`;
create lanes' worktrees/branches under each repo's `.work/wt/`; push those branches; run `git
ls-remote` only for explicit pin resolution in tests and pilot runs; create scratch checkouts and
fixtures under `.work/tmp` with `TMPDIR` pointed there; run the named check/lint/test commands.

Forbidden: direct commits or pushes to `usr/main` or `repomod/master`; force-push; any push outside
the two repos; running `make`, `make sync`, `dl`, `setup-linux`, `macos/*`, or reset scripts against
the real home; testing install behavior against the real `$HOME` (use scratch HOME under `.work/`);
resetting, stashing, cleaning, switching, or discarding changes in repomod canonical checkouts;
running `fix` against the live catalog; network access from `lint`/default `fix`; adding package
installers, release builds, daemons, caches, services, PR creation, or Python user-rule scripts;
claiming intermediate commits were globally verified.

Contract changes made by this campaign (for the owner): `pinact` gains `pin`, `lint`, `fix`
subcommands, three profiles, exit 0/1/2 for new commands, and the section-2 JSON shape (new public
interface); repomod's GitHub Actions validation/fixing switches from `jactionlint` to `pinact`
(tool contract change, user-visible only in messages and fix behavior); `dl` drops `jactionlint`
at close (installer contract change). No other public contracts change.

## 7. Non-goals

Another Git host; general CI execution; GitHub API workflow simulation; a complete shell interpreter;
a general static type checker; a full `jactionlint` copy; every zizmor audit; exhaustive shell taint;
AI-agent policy; cross-repo dependency execution graphs; full JavaScript analysis; plugin ecosystems;
config DSLs; user-defined Python rule scripts; SARIF/LSP/TUI/language server/persistent cache or
database/always-on process; remote mutation; PR creation; autonomous updates; dependency dashboards;
formatting or reserializing unrelated YAML; online advisories; registry scanning; repository-takeover
detection. A new subsystem for a marginal gain is omitted. `repomod` keeps fleet policy, approved
versions, worktrees, commits, and PR orchestration; `pinact` never owns those.

## 8. Reference

Verified code map (all paths confirmed at the base revisions; upstream files are specifications and
test sources, not architectures to copy):

- usr: `dotfiles/base/.local/bin/pinact` (293-line scanner + resolver + atomic writer, the behavior
  to preserve); `tools/pinact/test_pinact.py` (11 tests, ~7 s); `tools/pinact/README.md`;
  `dotfiles/migrate-pinact.sh`; `Makefile` (`check` runs the pinact suite + `pinact --check`;
  `lint` runs shellcheck + ruff); `dl` (`install_jactionlint` + `install_github_archive`);
  `.github/workflows/test.yml` (CI runs `make` then `make check`/`make lint` in a scratch home).
- repomod: `src/repomod/rules/actions.py` (pin catalog `load_pins`/`refresh_pins`, `_scan_source`-family
  regex parsing, `_pinact_findings`, `_jactionlint_findings`, `_validate_workflows`, fixer flow
  requiring both tools in a scratch worktree); `src/repomod/rules/workflows.py`
  (`workflow_files`, `read_workflow_sources`); `src/repomod/rules/workflow_settings.py` (fleet
  concurrency/shell/trigger fixers reusing `_validate_workflows`);
  `src/repomod/workflow_policy.py` (`is_fork_workflow`); `src/repomod/fix.py` (`_write_plan`,
  path validation, plan-then-validate); `src/repomod/github.py` (tag resolution);
  `actions.toml` (~24 approved pins); `tests/test_actions_release.py`, `tests/test_fix.py`,
  `tests/test_github_policy.py`; `docs/design.md`, `docs/policy-development.md`,
  `docs/audit.md`, `docs/tagging.md`; `Makefile` (`test`, `lint` via `uv`); `catalog.toml`
  (curated user data).
- Upstream specs: `jdx/jactionlint` (`parse.go`, `expr_lexer.go`, `expr_parser.go`, `expr_sema.go`,
  `rule_job_needs.go`, `rule_expression.go`, `rule_template_injection.go`, `rule_artipacked.go`,
  `rule_permissions.go`, `rule_workflow_call.go`, `docs/rules.md`, `docs/checks.md`),
  `actionlint/docs/checks.md`, selected zizmor audits, current GitHub workflow/expression/action-
  metadata docs. Use for rule intent and test cases only.

Essential design (compressed from the draft; executor follows these, rationale lives here, not in
code comments):

- Reuse difficult parsing: vendor mature YAML; no custom YAML/shell parsers, no execution
  simulators, no JS/Python/shell semantics. Compiler-style structure (real nodes, nesting, source
  spans, key validity, dependency edges, expression boundaries, script-vs-config distinction) with
  regexes only for bounded local matching after structure is known.
- Plain functions, small dataclasses, immutable results, explicit edit plans, simple registration,
  deterministic order, one CLI process, no state. No frameworks, DI, dynamic loading, config
  inheritance, visitor hierarchies without need, rule DSLs, workers, daemons, DBs, or services.
- Narrow autofixes only: a fix ships only when it is defensible without guessing intent; behavior-
  changing repairs become diagnostics or explicit opt-ins. Never silently change majors, triggers,
  credentials, quoting, multiline commands, privileges, or swap one untrusted expression for another.
- Analysis model: source document (bytes, text, node tree, locations, mapping/sequence relations,
  path, line endings, alias/span metadata); diagnostic (stable ID, file, line, column, severity,
  explanation, fixable flag, optional edits); edit (exact range, expected original, replacement,
  origin, policy-choice marker). Rules are pure functions of the document.
- Structure checks (§7 of the draft, items 1-20), scope-aware `uses:` (job/step/composite/local
  reusable; never `env:`/`with:`/script text), small upstream-referenced tables for keys/enums.
- Expressions (§8 grammar list) with quoted/escaped/multiline support, conservative contexts,
  twelve common builtins with case-insensitivity and per-field legality, and the four-way
  valid-unknown / unsupported / syntax-error / semantic-error distinction.
- Security (§9): first priority as listed; second priority only with false-positive-proof context;
  the §9 leave-out list stays out without demonstrated demand.
- Pinning (§10): keep full-SHA, peeling, ambiguity/branch guards, batching, comments,
  offline-check, no auto-upgrade, determinism; AST-backed `uses:` when the regression suite passes;
  `--catalog` semantics per O3 and the §10 validation/refusal list.
- Edit engine (§11): the 8-step pre-apply rejections, post-edit reparse/verify/idempotence protocol,
  per-file atomic writes (no multi-file atomicity claims), byte-identical unrelated source, the
  safe-fix priority list, and the unsafe-fix refusal list.
- Coverage order P0 structure, P1 pinning/editing, P2 security, P3 expressions (may precede P2 via
  U3 as needed), P4 autofix expansion + parity refinement; rule-selection matrix
  (implement / partial / delegate / defer / exclude) ranked by likelihood, severity, reliability,
  fix ease, complexity, and maintenance — never by ease of writing.
- Differential method (§14): 7-source corpus, same-input both-tools harness, defect-level (not
  message-level) comparison, true-positive/miss/false-positive/unsupported/location/fix-safety
  tracking, the §14 category table with raw denominators, the §14 suggested gates now bound by O4.

Superseded draft requirements (owner-directed, 2026-10-25): `repomod` read-only references,
"must not modify `repomod`", "do not move fleet policy into `usr`", downstream-migration-guide-only
(§12, §17, §22 "repomod remains unchanged"), and "do not remove `jactionlint`" as a permanent rule
(§17) are replaced by D6-D7/O2: actively integrate `pinact` into `repomod` and retire `jactionlint`
at the close gate. Never-implement-migration (§18) is replaced by R1-R3. Direct-to-`main` commits
(§20) are replaced by O1 branch work. All `/tmp` or bare-tempdir scratch is replaced by
`.work/wt/` + `.work/tmp` with `TMPDIR` set. Everything else from the draft remains actionable via
sections 4-5 or the non-goals above.

## 9. Logs

Decision log:

- 2026-10-25 owner: two-repo branch-only grant (O1), retire-`jactionlint`-at-close (O2), catalog
  ownership (O3), binding parity gate (O4).
- 2026-10-25 preflight: prescribed P1-P9 from code evidence and the unattended/trust principles;
  delegated G1-G4 to the executor inside stated bounds; sequenced per orchestrate phases with
  parity before optimization; moved all scratch to `.work/`; superseded the read-only-`repomod`
  constraints per the owner's new direction.
- Foundation proofs (ran, not inferred): 11-test pinact suite green (~7.1 s) locking the scanner
  behaviors the AST must reproduce; `pinact --check` on usr ~0.2 s; repomod
  `test_actions_release.py` 31 green (~1.4 s wall); `python3` has no `yaml` (vendoring required);
  `jactionlint 2.3.0` runs as the differential oracle; repomod's `pinact`+`jactionlint` call sites
  enumerated and bounded to `rules/actions.py` plus its two consumer files.

Campaign log: no waves run. R0 probe accepted 2026-10-25 (scratch only, lane worktree clean):
38 jactionlint-default findings vs 13 pinact unpinned lines on the 9-file scratch set, 13 true
agreements at file+line, 23 jactionlint-only across 6 classes R1 must cover. Retry when lane-usr
publishes `lint --format=json`: re-run `.work/tmp/r0-probe/run_probe.sh` plus the new subcommand.
Wave 1 (pilot) accepted 2026-10-26: U1 verified in-worktree (11 pinact + 26 YAML suites green,
`--check` clean, `-S` clean); lint-column retry run by parent — new `lint --format=json` yields the
same 13 file+line defects with P6 keys/columns; lane-usr deliberate
divergences (quoted flow strings/comments no longer fail; forward aliases fail closed) accepted as
fewer-false-positive corrections with tests.
Wave 2 (U2+U3) accepted 2026-10-26: 11+26+40+24 suites green under `-I` and `-S`; probe still
13/13 unpinned-uses at correctness profile; structured `yaml-syntax`/`missing-key` verified by
parent sampling. Notes for U6: model+scan double-parse deferred to U7 perf pass; unknown
`--select` IDs currently match nothing (rc 0) — confirm or reject as invalid usage in U6.
Steering: keep lane-usr worktree/branch for U4+U5; repomod lane unparked for R1 (U2 JSON stable).
Wave 3 partial (R1) accepted 2026-10-26: `_validate_workflows` + new `_pinact_lint_findings` shell
`pinact lint --profile=correctness --format=json`; 106 tests + ruff + ty rerun green by parent;
severity remap kept (proven unexercised by pinact output); dependabot/lock files scoped out of the
new path (old jactionlint rules had no pinact equivalent yet); `_validate_workflows` still passes
`changed` unfiltered — R2 must scope fixer outputs. Known gap carried: gha-syntax reports strictly
less than the old path until U4/U6 fill it; O4 gates the close.
Wave 3 complete (U4+U5) accepted 2026-10-26 at `b97e849`, pushed to `campaign-pinact-u1`:
security, catalog, and fix commands; 11 pinning + 26 YAML + 40 lint + 24 expression + 46 security +
39 fix tests passed on Python 3.13 with `-I`; launcher `--check` and Ruff passed. Independent review
found and the lane fixed pinned-SHA approval bypass, same-major catalog downgrades, shell-agnostic
fixes, job permission inheritance, and boolean-expression taint false positives. U5 also refuses
shell expansion rewrites and policy YAML injection, preserves CRLF and file modes, and reports
unapproved pinned SHAs. Steering: accept U4+U5; R2 is unblocked on the existing repomod lane.
Wave 3 R2 accepted 2026-10-26 at `f568a44`, pushed to `campaign-pinact-r1`: Pinact is the sole
GitHub Actions fixer in the disposable `.work/tmp` worktree; changed-file validation and fixer
arguments now include only workflows and `action.yml`/`action.yaml`. The scratch test verifies the
plan and cleanup. `pytest tests/test_actions_release.py tests/test_github_policy.py tests/test_fix.py`
passed (128); Ruff and `ty` passed project-wide. A disposable repository run with the actual Pinact
launcher rewrote the deprecated output command and returned a plan; scratch cleanup was verified.
Steering: accept R2; R3 catalog/policy wiring is unblocked.
Wave 3 R3 accepted 2026-10-26 at `63d71a3`, pushed to `campaign-pinact-r1`: Pinact lint and fix
receive the repomod actions catalog explicitly; fixes use catalog-only resolution and do not
request network resolution. Catalog-backed checks keep repomod's own major/version/SHA checks.
The real Pinact run against a copied catalog verified approved v7 pinning, the version comment,
major-bump refusal, and scratch cleanup. One integration defect surfaced and was corrected on the
Pinact lane at `ddb7886`: nested `[actions."owner/repo"]` tables now normalize into action records.
Pinact suites passed (187 total across six suites) and Ruff passed; repomod's 128 scoped tests,
Ruff, and `ty` passed, with a real Pinact catalog-lint run against the disposable repository.
Docs and `actions.toml` were unchanged because no pin policy or catalog values needed editing.
Steering: accept R3; U6 differential corpus/remediation is next.
Wave 4 U6 accepted 2026-10-26 at `2aecbff`, pushed to `campaign-pinact-u1`: the checked-in corpus
has 18 fixtures across seven source families and 31 labelled defects (weight denominator 63).
Pinact detected all 31 at the labelled locations (63/63 weighted); jactionlint 2.3.0 detected
57/63 weighted. The three valid fixtures had zero correctness errors in both tools. `fix --diff`
left all 18 inputs byte-identical. Actionlint and zizmor-derived cases are documented examples;
those executables were unavailable and were not independently run. The reviewer found a dynamic
matrix context bug, fixed with regression coverage. U6 also rejects unknown `--select` rule IDs
with invalid-use status 2. Focused suites passed: 26 YAML, 45 lint, 26 expression, 47 security,
40 fix, and 11 integration tests; launcher `--check`, Ruff, and `mdtool` passed.
R4 O4 gate accepted before optimization: weighted recall exceeds 90%, valid corpus has zero
correctness false positives, no destructive `fix --diff` result, and no high-severity misses inside
the labelled coverage.
Wave 5 U8 docs accepted at usr `67c8b25` and repomod `b37f1ad`; Pinact now documents command
contracts, rule profiles, architecture, compatibility limits, and corpus coverage. repomod describes
the explicit catalog, validation, and detached-worktree fix plan. `make check` now includes the five
Pinact unit suites and keeps their scratch under `.work/tmp`; touched documentation passed `mdtool`.
Owner waived U7 on 2026-10-25: performance is not an issue, and the unmeasured parse-reuse candidate
was discarded.
Wave 6 C1 retirement code accepted at usr `7053e07` and repomod `efcfe5b`: the downloader no longer
offers or records jactionlint; repomod's dead checker/fixer adapters, mocks, and old differential
probe were removed. Its remaining tree has no jactionlint reference; usr retains only its
development-time parity corpus. `dotfiles/dl-test.sh` passed with scratch HOME/TMPDIR. Repomod's 126
focused tests passed with jactionlint absent from `PATH`; Ruff and ty passed; the completion review
found and removed the now-orphaned `install_github_archive` helper. Full `make check`, `make lint`,
and repomod `make test` were not run because the root instructions prohibit `make` without an explicit
request. The campaign is parked at those final broad gates.

## 10. For the owner afterwards

Read the compatibility/coverage report and skim the rule reference for IDs your fleet configs
mention. The follow-up commits are merged into the local default branches and remain unpushed; the
updated repomod CI workflow needs a run after publishing usr first.

## Review follow-up

The owner reopened the campaign after review of the latest `usr` and `repomod` heads. Pinact now
accepts expression-valued matrices as dynamic, rejects malformed YAML before pinning, validates
declared `needs` and step IDs, checks cron field ranges and steps, and requires Python 3.11 for
`tomllib`. Its corpus score now uses the `default` profile consumed by repomod; five real repomod
release workflows were added to the valid set. The latest local run covers 23 files, 31 labelled
defects, and nine valid workflows. Pinact has 63/63 weighted recall on those labels and zero errors
on the valid set; the report explicitly limits that claim to the selected corpus and records
jactionlint's dynamic-matrix false positives.

Repomod now routes action lint and fixing through one `gha-syntax` rule with Pinact's default
profile. Its duplicate action scanner, cross-major rewriting path, and second Pinact check adapter
were removed; `actions.toml` refresh remains. This removes the `gha-pin` and `gha-version` rule IDs.
The repomod test workflow checks out `usr` and runs an isolated real-launcher integration that
asserts security findings and catalog-backed same-major fixing.

Follow-up verification: usr `make check` and `make lint` passed; repomod `make test` passed all 313
tests with the isolated real-launcher CLI integration enabled, and repomod `make lint` passed. The
205 Pinact tests across its documented suites and catalog regression, corpus runner, Pinact launcher
check, and `mdtool` with zero errors also passed. Ruff now excludes the vendored PyYAML tree that
caused the broad lint target to fail. The CI workflow itself was not run. Follow-up commits are
merged into the local default branches and remain unpushed.
