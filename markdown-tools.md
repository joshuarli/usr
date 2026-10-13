# Campaign: `mdtool`, read-only documentation checks

Status: ready. This campaign adds one Python 3.9+ standard-library command, `mdtool`, for mechanical Markdown and documentation checks used by repository skills. No implementation exists at the campaign base; the behavior below is the specification.

Deliverables:

1. A deterministic `mdtool` command with read-only check commands covering links, anchors, references, code consumers, comment pointers, duplicate documentation blocks, and docs-router conventions.
2. Embedded behavioral tests, a numbered test wrapper, and a `make check` entry.
3. Skill instructions that use the command with a working fallback, plus a guard that rejects unknown `mdtool` subcommands in skills.
4. A measured, documented verification loop and a close review with no unresolved campaign item except items explicitly parked with evidence.

## Charter

- Decide within the bounds below, add a one-line decision-log entry when the call would otherwise surprise a reader, and continue. Never ask, wait for approval, or send a check-in. Stop only when deliverables are met or remaining work is parked behind a hard stop.
- Hard stops: an action outside the repository; any write by a check command to scanned repository content or outside `.work/tmp`; a path escape or symlink policy violation; or no runnable check for an item. Park only the affected item and continue with independent work. Never push.
- Check commands are read-only: no writes, network, or subprocess except the documented read-only `git` operations for `--since` and tracked-file discovery. `selftest` may create and remove fixtures under `.work/tmp` and use Git to initialize, stage, commit, and query its temporary comparison repository. It may inspect untracked paths only when `--untracked` is supplied.
- Finish functional parity and tests before optimization or polish. Record performance during parity; do not gate feature work on it.
- Fix on the way a plainly broken check, a baseline failure that blocks an item, or a command over two minutes that blocks the campaign, each in a separate Conventional Commit. Record lesser issues and leave them. Time-box a failing item to three root-cause experiments; after three refutations, recheck assumptions, then park it with the repro, evidence, and next useful check.
- Keep bookkeeping to the decision log and one short campaign-log line per phase. Do not add provenance, hashes, inventories, or other state files.
- Use one serial executor and no child agents or lane worktrees. Keep scratch under `.work/tmp`, set `TMPDIR` there, and keep measured peak RSS below 512 MiB. `.work/` is already ignored in `.git/info/exclude`.
- Commit each completed phase as a Conventional Commit with the area as scope; item IDs go in the body. Never push. Code comments explain local behavior and never cite this plan.

## Decisions

### Owner-decided — answered 2026-10-13

- **Command name:** `mdtool`. The owner chose the recommended short name; it covers more than link checking.
- **`dups`:** include in v1, limited to documentation blocks. Code duplication analysis is out of scope.
- **Consumer file set:** include non-Markdown tracked files in a directory containing tracked Markdown, so embedded or parsed documentation data is discoverable.
- **`router` exit status:** findings remain warnings and notes; repo-specific enforcement belongs in a separate gate.
- **Execution shape:** one serial executor, with no child agents or lane worktrees. The owner chose this bounded workflow.

### Prescribed

- **One file and no dependencies:** implement the command as `dotfiles/base/.local/bin/mdtool`, Python 3.9+, standard library only. The requested command is small enough for one file, and one slugger and walker can serve multiple subcommands. No config file or plugin API. Reverse this only if the full specified behavior cannot remain understandable within the 800-line ceiling; if so, park the split as a design finding rather than adding an unreviewed module system.
- **Full-scope default:** with no paths, inspect all tracked docs; `--since` is explicit, never an implicit default. This avoids hiding pre-existing findings. Change-only callers pass `--since HEAD` explicitly.
- **Git is the oracle for tracked files and revisions:** use `git ls-files -z`, `git ls-tree`, and `git cat-file --batch` without a checkout or stash; invoke Git with an argument vector, never through a shell. Outside a Git tree, walk the requested root using the exclusions below. `--since` without Git exits 2.
- **Error and output contract:** findings sort by file, line, column, code, then target, with repo-relative `/` paths. Text goes to stdout one finding per line; summaries go to stderr as `N findings in N of N files`. Exit 0 means no `error` findings, 1 means at least one, and 2 means usage, unreadable-root, or Git-operation failure. File-read failures are `note`s and continue. JSON emits one object per finding per line with `code`, `severity`, `file`, `line`, `col`, `message`, and `target`; all fields are present. `--quiet` suppresses only the summary. An unknown `--ignore CODE` is a usage error.
- **Platform and path safety:** support macOS and Linux with Python 3.9+. Decode Markdown as UTF-8 with replacement. Do not follow symlinks outside the root; read an in-root symlink target once and do not recurse through it. Confine resolved targets before opening and use directory-relative no-follow opens for each path component so a symlink swap cannot escape between check and read. Outside-root destinations are `L001` and are never opened. Output paths always use `/`.
- **File bounds:** tracked missing paths are skipped with a `note`; skip binary files with a NUL in the first 8 KiB and files larger than 2 MiB. Outside Git, skip dot-directories, `target`, `node_modules`, and `.work`. `--untracked` adds untracked, non-ignored files.
- **No legacy parity target:** this is greenfield. The RFC behavior tables and numbered examples below are the oracle; no throwaway script or prior output is a compatibility contract. Every behavior row has a literal-output or literal-exit behavioral test, including negative controls that prove the test fails when behavior is wrong.
- **`refs` invocation:** do not hide old findings by default. In `docs-refresh`, use `--since HEAD` when checking only the current worktree change; use the full-scope form for a whole-repo refresh.
- **Skill command validation does not depend on installation:** `skills-check.sh` invokes the checked-in `dotfiles/base/.local/bin/mdtool commands` through `python3 -I`, resolving the repository root from its own path. This keeps `make check` working before a home sync.
- **Test effects:** keep decision logic callable against explicit roots and file sets. Real filesystem tests use a temporary directory under `.work/tmp`; Git comparison tests use a small temporary repository there. No network, clock, or subprocess seam is needed beyond the explicit read-only Git boundary.
- **No persisted state, concurrency, retry, or transaction contract:** the tool is a synchronous read-only process. Do not add these abstractions.
- **Performance and size:** no dependency means no dependency maintenance, build-time, or binary-size impact. Keep the script under 800 lines and 64 KiB; keep peak RSS under 128 MiB on the representative consumer workload. After parity, measure `links` on 120 files / 30,000 lines below 1 CPU second and `consumers` on a few thousand tracked text files below 3 CPU seconds, minimum of five runs. Interleave baseline and candidate measurements; require `perf-gate-ready` to return 0 before and `-1` immediately after each time measurement. A busy host defers the time gate and it is not a pass. Memory and source-size gates still run.
- **No formatter:** preserve repository formatting conventions by hand.

### Delegated within bounds

- The executor chooses the smallest line-oriented parsing helpers that meet the forms enumerated below; do not add a Markdown parser dependency or support an unlisted renderer dialect.
- The executor may choose exact diagnostic wording, provided codes, severities, fields, ordering, and exit behavior remain fixed. Add a literal test for every stable diagnostic shape.
- Choose how `skills-check.sh` obtains the command list, provided there is one authoritative list from `mdtool commands` and invalid skill references fail with the skill and unknown subcommand named.

## Baseline

- Base is greenfield for `mdtool`: no source file, callers, or tests exist. Existing scripts establish the installation and check patterns: `dotfiles/sym` links tracked files into a target; `Makefile` `check` runs the numbered tests and both skill trees; `dotfiles/skills-check.sh` checks skill routing tables.
- Foundation proof: `sh dotfiles/sym -t "$PWD/.work/tmp/sym-proof/home" dotfiles/base` installed the real base layer into scratch; the resulting `shift_srt.py` symlink resolved and was executable. This proves the planned executable script can reach the PATH location through the existing installer. The tracked mode of `shift_srt.py` is 100755.
- Foundation proof: `sh dotfiles/skills-check.sh dotfiles/base/.agents/skills` exited 0. Its current skill-reference check is at `dotfiles/skills-check.sh:26-31`; `mdtool` validation belongs alongside it.
- Measured loop command: base skill check, 0.63 s wall / 0.16 s CPU. The repository describes `make check` as about 25 s; it was not run for this documentation preflight. The current full command timings and known failures are unknown until P0; the executor records them before editing code. The new command has no baseline implementation to time.
- A read-only `sym --dry-run` against the repository root reported the expected conflict at `.agents/skills`, because that link already exists. It made no change and is not an installer failure.
- No release build exists or is needed. Performance is measured after parity against the thresholds above, not as an early feature gate.

## Sequence

Each item lists its size, prerequisites, owned files, and acceptance proof. Execute every item serially in this order. Keep campaign changes on the active campaign branch; do not create child agents or worktrees.

### P0 — Ground

**G0 · Record the baseline** (small; no prerequisite). The executor owns no source files. Record `git status`, known failures, available Python versions, memory headroom, and wall / CPU times for the current `make check`, `sh dotfiles/skills-check.sh dotfiles/base/.agents/skills`, and `sh dotfiles/skills-check.sh .agents/skills`. Confirm `.work/` is ignored via `.git/info/exclude`, adding that local ignore rule if needed before scratch writes. Run only these existing checks; do not run `make` or any setup/download command. If `make check` exceeds two minutes, isolate the slow check and fix the loop before feature work. Acceptance: the baseline entries are recorded in the campaign log with exact command, result, and timing; existing reds are named and `.work/` is ignored before M1.

### P1 — Parity and completeness

**M1 · Implement the complete tool, tests, and skill wiring** (large; prerequisite G0). One serial executor owns `dotfiles/base/.local/bin/mdtool` (mode 0755, `#!/usr/bin/env python3`), `dotfiles/mdtool-test.sh`, `Makefile`, `dotfiles/skills-check.sh`, and the skill files for `docs-refresh`, `comment-cleanup`, `single-source-of-truth`, `ultrareview`, and `campaign-preflight`. Deliver all commands and behaviors in the Reference section together; do not ship a partial phase. Use a single file walker and shared GitHub slugger. Tests are embedded `unittest` cases and run via `mdtool selftest`; the wrapper follows the numbered-output convention of `dotfiles/sym-test.sh`. Each skill names the relevant command and a useful fallback for machines without `mdtool`; `campaign-preflight` uses `--untracked` for an untracked design doc. The checker extracts literal backticked `mdtool <subcommand>` references and rejects names absent from `mdtool commands`, identifying the skill and bad name; invoke the checked-in command through `python3 -I` so `make check` works before a home sync. Acceptance: `python3 -I dotfiles/base/.local/bin/mdtool selftest`, the numbered wrapper, both skill checks, and `make check` pass; `make lint` passes for the new POSIX wrapper; temporary scratch skill inputs containing valid and invalid names prove success and failure respectively; every mapped skill command has a working fallback; `mdtool commands` emits the exact command set; the script parses with Python 3.9 grammar; no external import is required.

Skill command map: `docs-refresh` uses `links`, `refs`, `consumers`, `anchors`, and `router`; use `--since HEAD` for a change-only refresh. `comment-cleanup` uses `pointers`. `single-source-of-truth` uses docs-only `dups`. The docs lane in `ultrareview` routes through `docs-refresh`. `campaign-preflight` uses `links` and `refs --untracked` for a not-yet-tracked design doc.

P1 gate: `make check` proves the new wrapper and command guard are wired into the repository loop; `make lint` checks the new POSIX wrapper. Do not begin hardening or optimization if a feature or its behavior test is missing.

### P2 — Hardening

**H1 · Close boundary and cross-platform cases** (medium; requires M1). Own `mdtool` and its embedded tests. Cover symlink escape, outside-root paths, permission/read errors, case-only mismatches, percent decoding, malformed options, duplicate references, missing tracked files, non-UTF-8 names where supported, and Python 3.9 execution when available. Every failure must retain its specified code, severity, and exit status. Acceptance: focused named selftests pass; Python 3.9 runs `commands` when installed; Linux and macOS path rules are exercised by platform-specific tests or explicitly logged as unverified where a runner is unavailable.

P2 gate: run `mdtool selftest` and the numbered wrapper because H1 changes tool behavior and boundary handling. Report any baseline failure separately. Fix root causes; do not retry a red without a new hypothesis.

### P3 — Optimization and polish

**O1 · Measure the bounded workloads** (medium; requires P1 and P2). The serial executor owns `mdtool` and selftests. Capture the parity baseline before optimization. Measure the specified 120-file / 30k-line link corpus and few-thousand-file consumer corpus with CPU time, at least five interleaved runs, `perf-gate-ready` bracketing, and correctness checks on every run. Report minimum, median, and range; answer the benchmark-checklist questions about limiter, tuning, errors, and completed work. Check peak RSS and source bytes regardless of host load. Fix only measured excess over the targets; preserve behavior tests. Acceptance: command outputs remain identical, source stays under 800 lines / 64 KiB, peak RSS is at most 128 MiB, and workload targets pass. If host load prevents a time measurement, log `perf gate deferred: host busy`; leave O1 and campaign close incomplete until the gate can be measured.

### P4 — Close

**C1 · Review, clean, and report** (medium; requires all landed items). The serial executor verifies all deliverables and no dead fallback/test-only code remains, runs final `make check` and `make lint`, applies `dotfiles-health` because skills are part of agent setup, then performs a whole-repo `ultrareview` as its final consistency pass. Do not spawn a reviewer; the owner chose a single serial executor. Fix P1/P2 findings in scope; park other findings with evidence. Acceptance: all checks and time gates pass except individually named baseline failures that do not block an item; campaign log states outcome, contract changes, metrics, and unverified platforms. A deferred time gate means the campaign is not complete.

## Acceptance

Every deliverable has a check, and campaign completion never waits on a person.

| Deliverable | Proof |
|---|---|
| Read-only CLI and all named commands | `python3 -I dotfiles/base/.local/bin/mdtool selftest`; test each exit class and output in embedded tests |
| Python 3.9 compatibility | `ast.parse(source, feature_version=(3, 9))`; if available, `python3.9 -I .../mdtool commands` |
| Skills call valid commands and work without installation | `sh dotfiles/skills-check.sh dotfiles/base/.agents/skills`; `sh dotfiles/skills-check.sh .agents/skills`; fallback paths checked in updated skill text |
| Numbered wrapper is in the routine loop | `sh dotfiles/mdtool-test.sh`; `make check` includes it |
| No POSIX shell regression | `make lint` |
| Time and size limits | P3 workload commands and measurements in O1; time gate only counts when pre/post readiness checks pass |
| Close review | P4 campaign-scoped ultrareview; fix P1/P2 findings and record remaining hard-stopped work |

## Contract changes

Pre-authorized: a new executable command and its subcommands, flags, output codes / severities, and exit statuses exactly as specified; one added `skills-check.sh` rule; skill text updates; a `make check` entry; and test-fixture writes under ignored `.work/tmp`. These are additive and do not alter existing command contracts. The executable is installed through the existing base layer; no home-directory sync is run by this campaign.

Forbidden: writes or formatting to scanned repository content; network access; running non-Git subprocesses; reading outside `--root`; adding third-party dependencies; changing `sym`, installer behavior, existing skill invocation policy, or the meaning of existing `make` targets. Any extension beyond the pre-authorized command contract is parked for owner review.

No schema, persisted data, wire format, transaction, retry, or concurrency changes are in scope.

## Non-goals

- Rendering Markdown or checking remote URLs.
- Judging prose, tone, truth of claims, or whether a docs split is sensible.
- Editing, formatting, or fixing documentation.
- Scraping binaries' help output, plugin APIs, configuration files, or code-wide duplicate analysis.
- Supporting Markdown dialects beyond the listed GitHub-flavored forms.
- Changing docs-refresh's broader workflow or restructuring the skills tree.

## Reference

### Design and verified code map

- The current branch has no `mdtool`; the command contract below is the source of truth for this greenfield addition.
- `dotfiles/base/.local/bin/` is the shared PATH-script layer. `dotfiles/sym` installs each tracked file as a relative symlink; its install pass is at `dotfiles/sym:263-287`.
- `Makefile:39-43` owns `make check` and runs both base and top-level skill checks. `dotfiles/skills-check.sh:26-31` validates skill-router references; add the mdtool command check next to this rule.
- `dotfiles/base/.agents/skills/docs-refresh/SKILL.md` owns docs-refresh's general policy. The other command consumers are `comment-cleanup`, `single-source-of-truth`, `ultrareview`, and this campaign-preflight skill.

### CLI contract

```
mdtool COMMAND [options] [PATH...]
mdtool commands
mdtool selftest
```

Commands: `links`, `anchors`, `refs`, `consumers`, `pointers`, `dups`, and `router`. `commands` prints one command name per line. `selftest` runs embedded tests. `PATH` limits scope to files or directories; without paths, inspect every tracked Markdown file. `anchors` requires at least one path. `--root DIR` defaults to `git rev-parse --show-toplevel`, or the current directory outside Git; it and `--untracked` apply to all scanning commands. `--untracked` includes untracked, non-ignored files. `--since REV` filters findings absent at that revision and applies only to finding commands, not `anchors`, `commands`, or `selftest`. `--json`, repeatable `--ignore CODE`, and `--quiet` apply to finding commands; `anchors` prints its heading table. Subcommand flags are `--label REGEX` for `pointers`, `--code` for `dups`, and `--max-lines N` for `router`. Reject a flag not supported by the selected command. Options may appear before or after command paths. Usage errors exit 2.

Output is sorted and stable. Text findings use `path:line:col: severity CODE message: target`; summaries go to stderr. JSON has one object per finding per line with the exact fields named above. `note` and `warn` never change exit status.

### Behavior specification

**`links` — resolve links and anchors.** Handle inline `[text](dest "title")`, angle destinations, reference `[text][ref]`, collapsed `[ref][]`, shortcut `[ref]` when a matching definition exists, autolinks, raw `<a href>`, `<a id>`, and `<a name>`. Ignore links inside fenced, indented, or inline code; independently inspect inline-code spans for L004. Do not fetch schemes (`https:`, `mailto:`); resolve bare `#frag` against the same file. Percent-decode destinations before lookup. Heading slugs: lowercase; remove HTML tags and Markdown syntax markers while retaining visible text; keep Unicode letters, digits, spaces, hyphens, and underscores; drop other characters; convert spaces to hyphens; suffix repeated slugs `-1`, `-2`, etc. ATX and setext headings count, but fenced headings do not.

| Code | Severity | Meaning |
|---|---|---|
| L001 | error | Missing destination or outside-root destination; never open outside-root paths. |
| L002 | error | File exists but fragment has no heading or explicit anchor. |
| L003 | error | Path exists only with different letter case. |
| L004 | error | `path:N` or `path:N-M` inline-code reference exceeds target line count. |
| L005 | error | Reference link has no definition. |
| L006 | warn | Reference definition is unused. |

**`anchors FILE...` — list linkable headings.** Print each heading as line, level, slug, and text; use the same slugger as `links`. Exit 0.

**`refs` — check literal references.** Inspect inline-code spans and fenced `sh` blocks. Skip spans with placeholders such as `<name>`, `NN`, `{a,b}`, `*`, `$VAR`, or `...`.

| Code | Severity | Meaning |
|---|---|---|
| R001 | warn | A span containing `/` or ending case-insensitively in `.md`, `.markdown`, `.txt`, `.rs`, `.toml`, `.yaml`, `.yml`, `.json`, `.py`, `.sh`, `.c`, `.h`, `.go`, `.ts`, or `.js` looks like a repo path but names no tracked file or directory; skip paths beneath untracked `runs/` or `target/`. Do not duplicate R002–R004 findings as R001. |
| R002 | warn | `make TARGET` has no target in an in-scope Makefile's target or `.PHONY` declarations. |
| R003 | warn | `cargo ... -p NAME` / `--package NAME` has no matching `[package] name` in any `Cargo.toml`. |
| R004 | warn | Invoked `scripts/x`, `./x`, or `sh x` is not tracked. |

These are warnings because docs can name files readers are expected to create.

**`consumers` — find code depending on docs.** Inspect tracked non-Markdown text files for tracked Markdown and for data files whose parent directory also contains tracked Markdown. Classify literal path matches outside comments as `C001` embeds (`include_str!`, `include_bytes!`, `include!`, `#include`, `embed`, or language equivalent), `C002` reads (a call containing `read`, `open`, `load`, or `parse`), or `C003` lists (other literal uses). Resolve `.`-prefixed literals relative to the containing file; compare others as repo-relative suffixes. Basename-only read-like matches are `C002 (name only)`. State in the summary that runtime-built paths cannot be resolved; do not claim completeness. Consumers are warnings or notes, never exit failures.

| Code | Severity | Meaning |
|---|---|---|
| C001 | warn | Embedded documentation changes can affect built output. |
| C002 | warn | Read documentation can affect a test or check. |
| C003 | note | Other literal consumers may affect a hash, manifest, or rule. |

**`pointers` — find comments that point to docs/plans.** Inspect source comments, not strings or Markdown prose. Recognize `//`, `///`, `//!`, `/* */` (Rust, C-family, Go, Java, JS/TS, KDL); `#` (Python, shell, TOML, YAML, Makefile, Ruby); `--` (SQL, Lua); HTML comments; and Python docstrings. Use a light string-aware tokenizer, including Rust raw strings. Skip and count unknown extensions.

| Code | Severity | Meaning |
|---|---|---|
| P001 | error | Comment names a tracked doc by path or basename. |
| P002 | warn | Comment uses a section or clause reference. |
| P003 | warn | Comment matches a built-in `M\d+`, `Phase \d+`, or `#\d+` label, or repeatable `--label REGEX`. |

Leave external citations alone. `--label` is the only repo-specific heuristic option.

**`dups` — find repeated documentation blocks.** Split docs into paragraphs, list items, and table-row groups; normalize whitespace, case, and Markdown punctuation. Report pairs within or across files with Jaccard similarity of 8-word shingles at least 0.8 and at least 40 words, or at least three table rows. Exclude fenced code unless `--code` is supplied.

| Code | Severity | Meaning |
|---|---|---|
| D001 | note | Two source ranges state substantially the same thing. |

**`router` — check the mechanical parts of the docs format.** AGENTS.md (or a CLAUDE.md import/symlink to it) is a thin router; README.md is for end users; detail is in `docs/`. Judgement of a split stays with the skill.

| Code | Severity | Meaning |
|---|---|---|
| T001 | warn | Tracked Markdown under `docs/` is not reachable in one hop from AGENTS.md by file or containing-directory link. |
| T002 | note | AGENTS.md exceeds `--max-lines` (default 150), or a non-map/layout section exceeds 30 lines. |
| T003 | note | README has a heading matching `build`, `develop`, `contribut`, `architecture`, `layout`, `internals`, `invariant`, or `testing` (case-insensitive), or a fenced `make ci`, `cargo test`, or `cargo xtask`. |
| T004 | warn | AGENTS.md or README names a missing doc path. |
| T005 | note | A linked doc is under 20 lines or only links elsewhere. |

With no docs directory or AGENTS.md, emit one note and no T001. A docs-refresh skill must run `consumers` before acting on `router` findings.

### Safety, tests, and measurement details

- Never follow symlinks outside root. A symlink inside root is read once as a file and never recursively traversed. Lexical `..` escape is rejected before any read. Open through root-relative directory handles with no-follow semantics so a concurrent path swap cannot bypass the confinement check.
- `--since` compares worktree findings with revision findings read via `git ls-tree -r -z` and `git cat-file --batch`; no checkout or stash. Finding identity is `(code, file, target text)`, excluding line numbers.
- The first test cases cover duplicate heading suffixes, fenced fake headings, case-only paths, tracked-but-missing files, `include_str!` consumer classification, setext headings, out-of-range line refs, moved findings under `--since`, and links after a `git mv`. Add representative cases for every behavior row and each exit class.
- There is no renderer/parser dependency. The line-oriented scanner is capped at 800 lines; a full CommonMark parser and extra slug flavors are out of scope.
- Tests build fixtures only under `.work/tmp`; the wrapper runs the embedded tests and prints numbered cases in the repository's existing style.

## Decision log

- 2026-10-13 — Keep `mdtool`, include docs-only `dups`, include docs data alongside Markdown, and keep router findings non-failing; owner selected all four recommended choices.
- 2026-10-13 — Keep `--since` opt-in so default runs expose the whole tracked baseline; change-only skill runs must name `--since HEAD`.
- 2026-10-13 — Keep this as one standard-library Python file; one file walker and slugger reduce drift across related commands, and the 800-line ceiling bounds the choice.

## Campaign log

- P0 — Existing base skill check passed in 0.63 s wall / 0.16 s CPU; `mdtool` has no baseline. Full check baselines are recorded by G0.

## For the owner afterwards

- Read `dotfiles/base/.local/bin/mdtool`, its numbered test wrapper, and `dotfiles/skills-check.sh` for the implementation and CLI/skill contract.
- Review the campaign log and P3 measurements. No cherry-pick is needed when running on the campaign branch; do not push unless separately asked.
