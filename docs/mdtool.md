# mdtool

`mdtool` is a read-only audit of a repository's Markdown, MDX, reStructuredText, and the code that depends on those docs. It is one standard-library Python 3.9+ file, installed from `dotfiles/base/.local/bin/mdtool`. The docs skills call `mdtool check`, and `dotfiles/skills-check.sh` rejects a skill that names a subcommand missing from `mdtool commands`.

## Use

```
mdtool [COMMAND] [options] [PATH...]
```

| Command | What it does |
| --- | --- |
| `check` (default) | Runs `links`, `refs`, `consumers`, `pointers`, `dups`, and `router`. |
| `links` | Resolves Markdown and RST links, anchors, site routes, reference links, `path:N` line references, and Sphinx labels and toctrees. |
| `anchors FILE...` | Lists each linkable heading as line, level, slug, and text. Needs a path. |
| `refs` | Checks literal paths, `make` targets, `cargo -p` names, package scripts, and invoked scripts in code spans and shell blocks. |
| `consumers` | Finds tracked code that embeds, reads, or lists a tracked doc. Runtime-built paths cannot be resolved. |
| `pointers` | Finds source comments that point at docs, sections, or plan labels. |
| `dups` | Finds near-identical documentation blocks. |
| `router` | Checks the mechanical parts of the AGENTS.md, README, and `docs/` format. |
| `commands`, `selftest` | Print the command names, or run the embedded tests. |

| Option | Meaning |
| --- | --- |
| `--root DIR` | Repository root. Defaults to the Git top level, or the current directory outside Git. |
| `--untracked` | Include untracked, non-ignored files. |
| `--since REV` | Drop findings already present at `REV`, read without a checkout. A finding is identified by code, file, and target, so a moved line is not new. Needs Git. Not valid for `anchors`. |
| `--json`, `--verbose` | One JSON object per finding, or one text finding per line. They are mutually exclusive. The default text output groups repeated findings. |
| `--quiet`, `--ignore CODE` | Suppress the summary line, or drop a code. An unknown code is a usage error. |
| `--label REGEX`, `--code`, `--max-lines N` | Extra `pointers` labels, `dups` over fenced code, and the `router` AGENTS.md limit (default 150). Each is rejected on a command that does not use it. |

With no paths, a command covers every tracked Markdown, MDX, and RST file. `check` and `consumers` read all tracked text files for context, and `PATH` filters what they report. `pointers` always reads every tracked text file. A standalone `router PATH` only discovers `AGENTS.md` and README files among the selected paths.

Exit status is 0 for no `error` findings, 1 for at least one, and 2 for a usage, root, or Git failure. Warnings and notes never change it.

## Bounds

Nothing is written, no network is used, and the only subprocess is read-only `git`. Outside Git it walks the root and skips `.git`, `.work`, `target`, `node_modules`, and other dot-directories. It skips files over 2 MiB or with a NUL byte in the first 8 KiB, never reads outside the root, and reads an in-root symlink once without recursing. An unreadable or missing file is an `IO01` note.

## Findings

| Code | Severity | Meaning |
| --- | --- | --- |
| L001 | error | Link destination is missing or outside the root. |
| L002 | error | File exists but has no such heading or anchor. |
| L003 | error | Path exists only with different letter case. |
| L004 | error | `path:N` reference is past the target's last line. |
| L005 | error | Reference link has no definition. |
| L006 | warn | Reference definition is unused. |
| L007 | error or note | Sphinx label is undefined; it is a note when intersphinx may resolve it. |
| L008 | warn | Sphinx document is in no toctree and is not marked orphan. |
| L009 | warn | Fragment matches a heading only when case is ignored. |
| R001 | warn | A code span or shell command names a repo path that is not tracked. |
| R002 | warn | A `make` target used in a command is declared in no Makefile. |
| R003 | warn | A `cargo -p` package used in a command matches no `Cargo.toml` package. |
| R004 | warn | An invoked script path in a command is not tracked. |
| R005 | note | A path or script likely belongs to another repo or is created by the reader. |
| R006 | warn | A package-manager script is not declared in `package.json`. |
| C001 | warn | A doc is embedded into built output. |
| C002 | warn | A doc is read by code or a test. |
| C003 | note | A doc is listed literally by other code. |
| P001 | note | Comment names a tracked doc by path or basename. |
| P002 | warn | Comment or Python docstring contains a section, clause, or milestone label, or a dotted numeric sequence. |
| P003 | warn | Comment cites a built-in `M1`, `Phase 1`, or `#1` label, or a `--label` match. |
| P004 | warn | Comment points to a missing document under a tracked docs directory. |
| D001 | note | Two blocks state substantially the same thing (8-word shingles, similarity at least 0.8, at least 40 words or 3 table rows). |
| T000 | note | The router checks found no AGENTS.md to check. |
| T001 | warn | A `docs/` file is not reachable in one hop from AGENTS.md. |
| T002 | note | AGENTS.md is over the line limit, or a heading's section extends over 30 lines before the next heading at the same or higher level. |
| T003 | note | README carries developer material (build, architecture, testing headings). |
| T004 | warn | AGENTS.md or README names a missing doc path. |
| T005 | note | A linked doc is under 20 lines or only links elsewhere. |
| IO01 | note | A tracked file needed for analysis is missing or unreadable. |

Run `consumers` before acting on a `router` finding that suggests moving a doc.
