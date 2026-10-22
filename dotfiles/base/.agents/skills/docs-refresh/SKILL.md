---
name: docs-refresh
description: "Use for /docs-refresh: bring a repository's docs up to date with its code and make them shorter. Scope is the whole repo, or only the docs a change touched. Edits docs and comments, never behavior."
disable-model-invocation: true
metadata:
  opencode/autoinvoke: "false"
---

# Docs Refresh

Make the docs true, short, and findable, in the standard shape below. Docs and comments are the only files you change, and a comment is only ever deleted, never added or reworded. Prose rots, so a doc claim that a type, test, or lint could enforce is reported as a candidate to enforce and then cut. When the code is what is wrong, leave it and report it.

## Standard format

Size the layout to the repo. A small repo, with under about 200 lines of docs or a few source modules, gets README and AGENTS.md and no `docs/`. Its developer detail sits in short AGENTS.md sections. Use `docs/` only when a topic would make README or AGENTS.md too long to scan.

- **README.md is for end users only:** what the thing is, how to get it, how to run or call it, its configuration and output, where to get help, the license. Building from source, layout, architecture, invariants, testing, and contributing are developer docs and do not belong in it. A library's users are the developers who call it, so its API usage is user docs and its internals are not.
- **AGENTS.md is a thin router,** not a manual: a line or two on what the repo is, the commands that build, test, and check it, each hard invariant in one line, and a map from topic or subsystem to the doc under `docs/` that owns it. In a larger repo, anything longer than a line moves to `docs/` and AGENTS.md points at it. It does not repeat the global instructions. Keep an existing AGENTS.md and CLAUDE.md arrangement.
- **`docs/` holds the detail, split by topic.** One file owns one topic a reader would look up by name: architecture, a subsystem, operations, testing, release, a format or protocol. Split a file whose sections are looked up independently or read by different people. Merge files that cannot be read apart. Name a file for its topic, never for a date or a campaign. The router in AGENTS.md is the index, so add no second one.
- **A whole-repo refresh restructures toward this;** a refresh of one change keeps the layout and files new material where this format puts it. Moving is not deleting: a fact displaced from README or AGENTS.md lands in its new home before it leaves, and every link to what moved is rewritten.

## Scope

Default to every doc surface in the repo: README, AGENTS.md and CLAUDE.md, `docs/`, contributing notes, `--help` text, config examples, and public API doc comments. When asked to refresh only a change, cover just the docs that change made stale or should have updated, and the comments it added or changed.

## Rules

- **The code is the truth.** Check each claim against it: commands, paths, flags, environment variables, versions, architecture, setup steps. Run the cheap checks (`--help`, a single narrow command) and read the code for the rest. Fix what drifted, and delete what is not worth keeping.
- **Prose follows `technical-writing` and `unslop`:** one mode per document, one reading per sentence, no AI tells. Apply them to what you touch, not to untouched prose.
- **Make it shorter.** Count Markdown lines in scope before you edit (`git ls-files -z '*.md' '*.mdx' '*.rst' | xargs -0 cat | wc -l`). The count goes down. A net increase needs a stated reason, such as a topic that had no doc. Cut what is outdated, duplicated, or restates what the code shows. Give each fact one home and link to it rather than copy it (`single-source-of-truth`). Keep the why, constraints, invariants, commands, and hazards. Do not reword for taste.
- **Point at code, do not copy it.** A list that mirrors one file, such as the env vars one function reads or a route table, becomes a pointer to that file. Setup steps the product already shows, on a home page or in `--help`, become a link.
- **A doc code reads is load-bearing.** Before you move, split, rename, or cut a doc, search source and build files for its path: embeds such as `include_str!`, tests that read or compile it, hashes, and checks of its layout. Report what you find to every writer, and leave such a doc's structure to the code that reads it.
- **Comments** go through `comment-cleanup` in its review mode. Only public API contract doc comments are doc surface; every other comment is a defect, not documentation. Rationale a deleted comment carried lands once in the `docs/` topic that owns it, never back in source.
- **Leave dated records alone** (changelog, ADRs, release notes), marking a superseded one rather than rewriting it. A completed RFC is not one of these: delete it per `todo`. For generated docs, edit the source and the generator input, not the output.
- **One writer** per file, so edits do not overlap. Create a doc file only for a topic that has no home and would make its nearest existing doc too long to scan.
- **Verify narrowly:** every `path:line` and link you kept resolves, and any doc check the repo has (a link checker, a doctest) runs on the files you touched.

When `mdtool` is installed, run one `mdtool check` for the refresh scope (`mdtool check PATH...` for selected docs, `--untracked` for drafts, `--since HEAD` for new findings only). It combines links, refs, consumers, pointers, duplicates, and routing with grouped output and anchor suggestions. Use `--verbose` or `--json` only when complete occurrence details are needed; use `mdtool anchors FILE...` only when you need a heading inventory. Without `mdtool`, use `rg -n '\[[^]]+\]\('` to find links, `rg -n '^#{1,6} '` to list headings, search backticked paths with `rg`, search source for each changed doc path to find consumers, and inspect AGENTS.md links and README headings by hand.

**The test:** an end user can install and use the thing from README alone, a developer reaches any topic in one hop from AGENTS.md, a newcomer can follow every command and reach the code each doc points to, no sentence is there only because it used to be true, and the docs are shorter than before unless a missing topic needed new text.

**Report:** the Markdown line count before and after, the files changed, moved, or removed and what was cut, claims you could not verify, and places where the code looks wrong rather than the doc.
