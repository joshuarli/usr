# RFC: `mdtool`, read-only documentation checks for agents and skills

Status: draft. Written 2026-10-13 by Claude (Sonnet 5.5) at Josh's request, after a
`docs-refresh` of `~/d/aincrad2`. Nothing in this RFC is implemented.

## 1. Summary

Add one self-contained Python 3.9+ standard-library script, `mdtool`, that answers the
mechanical questions every docs-related skill keeps re-deriving with ad-hoc `grep` and
throwaway Python: do the links resolve, do the things the docs name exist, which docs does
code depend on, which comments point at docs, which paragraphs are duplicated, and what did
this change break that was fine before. It also checks that a repo follows the
documentation format `docs-refresh` prescribes (README for end users only, AGENTS.md a thin
router, detail split by topic under `docs/`; section 6.8). It never writes to the tree. It
is installed once, on `PATH`, from this repo, and the skills call it by name.

## 2. Motivation

The docs refresh of aincrad2 covered 123 tracked markdown files (about 30k lines) with one
lead and seven parallel workers. The semantic work (is this claim still true of the code)
needed judgement and no tool would have removed it. The mechanical work cost real time,
and in three cases nearly caused damage:

1. **Link and anchor checking was written from scratch, twice.** I wrote a relative-link
   script and a GitHub-slug anchor script in `.work/tmp`. Workers wrote their own, one
   under the same filename as mine. My later run executed the worker's version, printed a
   different format, and then crashed on a file I had just `git mv`'d. A trustworthy
   checker would have been run once by the lead and its findings handed to the workers.
2. **Docs that code depends on were found by luck.** `docs/content/card-format.md` is
   `include_str!`'d by `a2-cards` and asserted on by tests; `docs/battle/AUTHORING.md` has
   fenced blocks a test compiles; `docs/NUMERIC-ENVELOPE.md` is hashed into the engine
   identity by `tools/engine_identity.rs`; `battlelab check docs` parses the layout blocks
   of `AGENTS.md` and `docs/STRUCTURE.md`. I found these only because I happened to grep
   for `include_str!` and `read_to_string` before the workers started cutting. Missing one
   would have meant a worker "tidying" a load-bearing file.
3. **"Does the thing the doc names exist" was checked by eye.** Make targets, `-p CRATE`
   names, `scripts/x.sh` paths and `path:line` references are all checkable without
   judgement, and each worker re-did it by hand, differently.
4. **Comparing before and after used `git stash`.** To see whether the anchor check had
   regressed I stashed a tree that seven workers were still editing, then popped it. It
   restored cleanly, but only by luck of timing. A baseline comparison should read a
   revision, not mutate the working tree.
5. **The search tools were unavailable.** See section 11.
6. **Conforming a repo to the standard format needed three more throwaway checks.** When
   `docs-refresh` gained its standard format and aincrad2 was restructured to it, I wrote
   ad-hoc scripts to confirm that every doc under `docs/` is reachable from AGENTS.md in one
   hop, that the layout block still names every crate, and that no developer material
   remained in README. Moving content out of README and AGENTS.md also made the
   load-bearing rule (2) concrete: AGENTS.md and `docs/STRUCTURE.md` are read by a check
   that fails the gate if a crate is missing from their layout blocks.

A shared script fixes (1) to (4) and (6) once, for every skill that touches docs, and lets
each `SKILL.md` stay short. `skills-check.sh` already warns above 60 lines.

## 3. Goals and non-goals

Goals:

- One file, Python 3.9+, standard library only, runnable as `python3 -I mdtool ...` and
  directly via its shebang. macOS's system `python3` is 3.9, so 3.9 is the floor.
- Read-only. No writes, no network, no subprocess other than `git` (section 6.7).
- Deterministic: same tree, same bytes out. Sorted, no timestamps, no absolute paths.
- Findings carry a stable code and a `path:line` a harness can open.
- Fast enough to run on every refresh without thought (section 9).

Non-goals:

- It does not edit anything, fix anything or format anything. Repo rules ban formatters,
  and a checker that writes is a different tool.
- It does not judge prose, tone, length or whether a claim is true. It reports facts a
  skill can act on.
- It does not run the repo's binaries (no `--help` scraping). Whether `--flag` exists is
  left to the skill, which can run `--help` itself.
- No config file and no plugin API in v1. Flags only (section 5).
- Not a renderer. It models GitHub-flavoured Markdown only.

## 4. Where it lives and how skills get it

- **File:** `dotfiles/base/.local/bin/mdtool`, mode 0755, `#!/usr/bin/env python3`. `sym`
  links it into `~/.local/bin`, which is on `PATH` for Claude, Codex and pi alike. It is
  the single copy; no skill carries its own.
- **Skill text:** a skill names the command and its fallback in one line, for example
  "run `mdtool links` on the files you touched (without `mdtool`, grep for the link
  targets)". A skill must still work on a machine that has not yet run `make`.
- **Check:** `skills-check.sh` gains one rule beside the existing "names a skill that does
  not exist" check: a skill that writes `` `mdtool <word>` `` must name a subcommand that
  `mdtool commands` prints. A subcommand cannot be renamed under a skill silently.
- **Skills that call it:**

  | Skill | Subcommands |
  |---|---|
  | `docs-refresh` | `links`, `refs`, `consumers`, `anchors`, `router`, `--since` |
  | `comment-cleanup` | `pointers` |
  | `single-source-of-truth` | `dups` |
  | `ultrareview` (its docs lane) | through `docs-refresh` |
  | `campaign-preflight` | `refs`, `links` on the design doc it makes executable |

- **Subagent briefs:** `docs-refresh` (and `orchestrate`, when it fans docs work out) tells
  the lead to run `mdtool consumers` and `mdtool links` once, before dispatch, and to paste
  the findings into each worker's brief. Workers do not write their own checkers.

## 5. Interface

```
mdtool COMMAND [options] [PATH...]
mdtool commands            # one subcommand name per line, for skills-check.sh
mdtool selftest            # run the embedded tests (section 9)
```

`PATH` limits the scope to files or directories; with none, the scope is every tracked
doc. "Just the docs this change touched" is a normal invocation.

Common options:

| Option | Meaning |
|---|---|
| `--root DIR` | Repository root. Default: `git rev-parse --show-toplevel`, else the cwd. |
| `--untracked` | Also include untracked, non-ignored files. Default is tracked files only. |
| `--since REV` | Report only findings absent at `REV` (section 6.7). |
| `--json` | One JSON object per finding per line: `code`, `severity`, `file`, `line`, `col`, `message`, `target`. |
| `--ignore CODE` | Drop a finding code. Repeatable. |
| `--quiet` | No summary line. |

Output, one finding per line, grep-shaped so a terminal makes it clickable:

```
docs/CONTENT.md:99:5: error L001 missing-target: content/pack-prompt.template.md
```

The summary goes to stderr: `3 findings in 2 of 118 files`. Exit status: 0 no findings
at `error` severity, 1 at least one, 2 usage error or unreadable root. `note` and `warn`
never change the exit status.

File set rules (these exist because each one bit during the refresh):

- Start from `git ls-files -z`. **Skip a tracked path that is missing from the worktree**
  and print one `note` per skipped path, so a half-finished `git mv` or `rm` neither
  crashes the run nor hides a problem.
- Outside a git tree, walk the directory and skip dot-directories, `target`,
  `node_modules` and `.work`.
- Skip binary files (a NUL byte in the first 8 KiB) and files over 2 MiB.
- Decode as UTF-8 with `errors="replace"`; never raise on content.

## 6. Subcommands

### 6.1 `links`: do relative links and anchors resolve

Checks every markdown link and image in the doc set.

Forms handled: inline `[t](dest "title")`, `<dest>` destinations, reference links
`[t][ref]`, collapsed `[ref][]` and shortcut `[ref]` against `[ref]: dest` definitions,
autolinks, and raw `<a href>` / `<a id>` / `<a name>` anchors. Links inside fenced code,
indented code and inline code spans are not links. Destinations with a scheme
(`https:`, `mailto:`) and bare `#frag` links to the same file are handled; schemes are
never fetched.

| Code | Severity | Meaning |
|---|---|---|
| `L001` | error | Destination file or directory does not exist. |
| `L002` | error | File exists, but it has no heading or explicit anchor with that slug. |
| `L003` | error | Exists only under another letter case. macOS is case-insensitive and Linux is not, and both are in use here, so a link that passes on one machine can be dead on the other. |
| `L004` | error | A `path:N` or `path:N-M` reference in an inline code span names a line beyond the end of the file. |
| `L005` | error | `[text][ref]` with no `[ref]:` definition. |
| `L006` | warn | A `[ref]:` definition nothing uses. |

Slug rules (GitHub): lowercase; remove inline formatting characters and HTML tags; drop
everything that is not a letter, digit, space, hyphen or underscore (Unicode letters are
kept); spaces become hyphens; the n-th repeat of a slug within one file gets `-n`. ATX
(`#`) and setext (`===`, `---`) headings both count. `#` lines inside fences are not
headings. Percent-escapes in destinations are decoded before lookup.

### 6.2 `anchors FILE...`: what can I link to

Prints each heading as `line  level  slug  text`, so an author or worker writes
`file.md#slug` from the table instead of guessing. Uses the same slugger as `links`, so
the two cannot disagree. Exit status is always 0.

### 6.3 `refs`: do the things the docs name exist

Reads inline code spans and fenced `sh` blocks in the doc set and checks the claims that
need no judgement. A span containing placeholders (`<name>`, `NN`, `{a,b}`, `*`, `$VAR`,
`...`) is skipped, not reported.

| Code | Severity | Meaning |
|---|---|---|
| `R001` | warn | A span that looks like a repo path (contains `/`, or ends in a known source or doc extension) and names no tracked file or directory. Paths under a directory the repo does not track (`runs/`, `target/`) are skipped. |
| `R002` | warn | `make TARGET` where no Makefile in scope defines `TARGET`. Targets come from `^name:` lines and `.PHONY`. |
| `R003` | warn | `cargo ... -p NAME` or `--package NAME` where no `Cargo.toml` has `[package] name = "NAME"`. |
| `R004` | warn | A script invoked as `scripts/x`, `./x` or `sh x` that is not tracked. |

These are `warn`, not `error`: a doc may legitimately name something a reader is meant to
create. The point is that a skill sees the list and decides.

### 6.4 `consumers`: which docs does code depend on

Lists every tracked non-markdown text file that contains the repo-relative path of a
tracked doc (or data file living in a docs directory, such as `docs/*.tsv`) as a string
literal, and says how:

| Code | Severity | Meaning |
|---|---|---|
| `C001` | warn | **embeds**: the path is inside `include_str!`, `include_bytes!`, `include!`, `#include`, `embed`, or a language's equivalent. Editing the doc changes the binary. |
| `C002` | warn | **reads**: the path is a string literal in a call whose name contains `read`, `open`, `load` or `parse`. Editing the doc can break a test or a check. |
| `C003` | note | **lists**: the path is a literal anywhere else outside a comment, such as a path array or a Makefile rule. Editing it may matter to a hash or manifest. |

Resolution: a literal beginning with `.` is joined to the containing file's directory and
normalised before comparison, so `include_str!("../../../docs/x.md")` resolves. Other
literals are compared as repo-relative suffixes. A literal naming only a doc's basename
inside a read-like call is reported as `C002` with `(name only)`. Paths built at runtime
(`root().join("docs").join(name)`) cannot be resolved; the command says so in its summary
rather than claiming completeness.

Run before dispatching workers, the output is the "do not reshape these" list. It does
not decide how an edit affects a hash. That remains the reader's call, and `consumers`
exists so the reader knows to make it.

### 6.5 `pointers`: comments that point at docs or plans

For `comment-cleanup`. Extracts comments from source files (not strings, not markdown
prose) and reports references that would break if documentation were renamed or deleted.

Comment syntax by extension family: `//`, `///`, `//!` and `/* */` (rs, c, h, go, java,
js, ts, kdl); `#` (py, sh, toml, yaml, Makefile, rb); `--` (sql, lua); `<!-- -->`
(html); Python docstrings (a string that is a statement's first expression). A light
tokenizer tracks string literals, including Rust raw strings, so `//` inside a string is
not a comment. An unknown extension is skipped and counted in the summary.

| Code | Severity | Meaning |
|---|---|---|
| `P001` | error | Names a tracked doc by path or basename. |
| `P002` | warn | A section or clause reference: `§`, `section 4`, `clause 2`, `step 3 of`. |
| `P003` | warn | Matches a label shape. Built in: `M\d+`, `Phase \d+`, `#\d+`. Add repo-specific shapes with `--label REGEX` (aincrad2: `--label '\bD\d{2,3}\b'`). |

External citations (RFC numbers, spec names) are left alone; `P003`'s `#\d+` is `warn`
so a human decides between an issue number and a standard.

### 6.6 `dups`: the same paragraph in two places

For `single-source-of-truth` and the "give each fact one home" rule. Splits docs into
blocks (paragraphs, list items, table row groups), normalises whitespace, case and
markdown punctuation, and reports block pairs across or within files whose 8-word
shingle overlap is at least 0.8 and that are at least 40 words (or 3 table rows).

| Code | Severity | Meaning |
|---|---|---|
| `D001` | note | `fileA:lineA-lineA2` and `fileB:lineB-lineB2` say substantially the same thing. |

Fenced code is excluded by default (`--code` includes it); repeated shell snippets are
usually deliberate. Only reports; which copy is the home is the skill's decision.

### 6.7 `--since REV`: only what this change broke

Any subcommand takes `--since REV`. The tool runs the check against the tree at `REV`
(read through `git ls-tree -r -z` and `git cat-file --batch`, with no checkout and no
stash), runs it against the worktree, and prints only findings whose key
`(code, file, target text)` is new. Line numbers are not part of the key, so a finding
that merely moved is not "new".

This is the one use of a subprocess, and it is `git`, read-only. With `--since` and no
git, the command exits 2. It replaces my `git stash`-based comparison and is safe while
other agents are editing.

### 6.8 `router`: does the repo follow the standard format

For `docs-refresh`, which prescribes: README.md for end users only; AGENTS.md a thin router
(what the repo is, commands, one-line invariants, a map from topic to the doc that owns it);
`docs/` holding the detail, split by topic. Judging whether a split "makes sense" is the
skill's job. This command reports the parts that are mechanical.

| Code | Severity | Meaning |
|---|---|---|
| `T001` | warn | A tracked markdown file under `docs/` that AGENTS.md reaches neither by a link to the file nor by a link to a directory that contains it. A developer cannot get to it in one hop. |
| `T002` | note | AGENTS.md is longer than `--max-lines` (default 150), or has a section other than the map and the layout block longer than 30 lines. "Thin" is a judgement; this says where to look. |
| `T003` | note | README.md has a heading matching `build`, `develop`, `contribut`, `architecture`, `layout`, `internals`, `invariant` or `testing` (case-insensitive), or a fenced block running `make ci`, `cargo test` or `cargo xtask`. Developer material in an end-user file. |
| `T004` | warn | AGENTS.md or README.md names a doc path that does not exist (the same finding as `L001`, listed here so a router check does not need `links` as well). |
| `T005` | note | A doc is linked from AGENTS.md but is under 20 lines or is a stub that only links elsewhere, which suggests a split that did not need to happen. |

A repo with no `docs/` directory, or no AGENTS.md, gets one `note` and no `T001`. A router
may be a `CLAUDE.md` that imports or symlinks AGENTS.md; the tool resolves the symlink or
the `@AGENTS.md` import and reads the target. The format is global, so there are no
repo-specific options beyond `--max-lines`.

`router` does not know that a doc is load-bearing. Run `consumers` first and treat a
`C001`/`C002` doc's structure as fixed when acting on a `T001` or `T002` finding.

## 7. Failure and safety behaviour

- A file that cannot be read is a `note` and the run continues.
- A path that resolves outside `--root` after normalisation (`../../etc/passwd`) is
  reported as `L001` with the message `outside the repository` and is never opened.
- Symlinks are not followed outside the root. A symlink inside the root is read as the
  link target's content once and not walked recursively.
- The tool imports nothing from the current directory, so a planted `json.py` is not
  executed. It runs cleanly under `python3 -I`.
- Output paths are repo-relative with `/` separators on every OS.

## 8. Design choices worth recording

- **Subcommands in one file, not several scripts.** One slugger serves `links` and
  `anchors`; one file walker serves everything; one install target; one thing to test.
- **Heuristics say they are heuristics.** `consumers` and `refs` return `warn` and `note`,
  and each prints what it could not resolve. A false `error` would teach skills to ignore
  the tool.
- **No config file.** The only repo-specific knob is `--label`, because decision IDs
  (`D53`) are genuinely per-repo. Anything else is a flag a skill passes explicitly.
- **GitHub flavour only.** The docs here are read on GitHub and by agents. A second slug
  flavour can be added behind `--flavor` if another renderer matters.
- **Not a Markdown parser.** A line-oriented scanner with a fence state and an inline-code
  state handles every form above and stays under 800 lines. A full CommonMark parser is
  not stdlib and not needed.

## 9. Testing and performance

- `mdtool selftest` runs `unittest` cases embedded in the file against fixtures built in a
  temporary directory under `$TMPDIR` (which the repo rules point at `.work/tmp`).
  `dotfiles/mdtool-test.sh` wraps it in the numbered style of `sym-test.sh`, and `make
  check` runs it.
- The first cases are the incidents above: a duplicate heading getting `-1`; a `#` line
  inside a fence not being a heading; a case-only mismatch; a tracked-but-missing file
  skipped with a note; `include_str!("../../../docs/x.md")` classed `C001`; a setext
  heading; `path:N-M` past end of file; a finding that moved lines not being "new" under
  `--since`; and a `git mv` leaving no dangling link.
- The self-test parses the script with `ast.parse(source, feature_version=(3, 9))`, which
  rejects syntax newer than 3.9 (such as `match`). If a `python3.9` is on `PATH` the test
  also executes `python3.9 -I mdtool commands`.
- Performance target, as a gate in the self-test using CPU time, min of 5 runs: `links` on
  a 120-file, 30k-line doc tree in under 1 s; `consumers` over a few thousand tracked
  text files in under 3 s. Time gates follow the repo's `perf-gate-ready` rule and are
  deferred, never passed, when the host is busy.
- Dependencies: none. Build time and binary size do not apply; there is no build.

## 10. Rollout

1. **Phase 1:** `links`, `anchors`, `commands`, `selftest`, `--since`. This is everything
   the refresh re-implemented. Wire `docs-refresh` to it and add the `skills-check.sh`
   rule.
2. **Phase 2:** `consumers`, `refs` and `router`. Add the "run `consumers` before dispatch"
   step to `docs-refresh` and to the worker brief template; `router` is its conformance
   check for the standard format.
3. **Phase 3:** `pointers` (for `comment-cleanup`) and `dups` (for
   `single-source-of-truth`).

Each phase is usable on its own and each is a separate commit. Skills are updated in the
same change that adds the subcommand they call.

## 11. Related finding: `rg` and `fd` do not run on this host

Not part of `mdtool`, but it shaped this RFC because the lack of search tools is why
`consumers` is worth having at all. On this Linux machine `~/.local/bin/rg` and `fd` fail
with "required file not found". `file` shows both are dynamically linked against
`/lib64/ld-linux-x86-64.so.2` (glibc), and this host has only `/lib/ld-musl-x86_64.so.1`.
So `dl` installed the glibc release assets on a musl host. `AGENTS.md` already notes
musl-vs-glibc for `mold`; `dl` likely needs the same choice for `rg` and `fd`
(upstream publishes `x86_64-unknown-linux-musl` builds of both, to my knowledge; I did
not verify the release listing). I did not touch `dl`, which the repo
rules say not to run unprompted.

## 12. Open questions

1. **Name.** `mdtool` is short and unclaimed in `~/.local/bin`. `docs-check` reads better
   in a skill sentence but suggests it only checks. Preference?
2. **Should `dups` ship?** It serves `single-source-of-truth`, which is not only about
   docs. It could instead be a code-and-docs `dups` under another name later.
3. **Docs data files.** `consumers` treats non-markdown files in doc directories
   (`docs/ingredient-judgement.tsv` is `include_str!`'d by `a2-sim`) as docs. Is "lives
   under a directory containing tracked markdown" the right rule, or should the caller
   list them?
4. **Should `router` ever fail the exit status?** As specified it never does (`warn` and
   `note` only). A repo that wants the format enforced could wrap it in its own gate, as
   aincrad2's `battlelab check docs` already does for the crate list.
5. **Run `refs` in `--since` mode by default in `docs-refresh`?** Probably yes: a first
   run over a mature repo will be noisy, and the new findings are the actionable ones.
