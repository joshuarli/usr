---
name: docs-refresh
description: "Use for /docs-refresh: bring a repository's docs up to date with its code and make them shorter. Scope is the whole repo, or only the docs a change touched. Edits docs and comments, never behavior."
disable-model-invocation: true
---

# Docs Refresh

Make the docs true, short, and findable. Docs and comments are the only files you change. When the code is what is wrong, leave it and report it.

## Scope

Default to every doc surface in the repo: README, AGENTS.md and CLAUDE.md, `docs/`, contributing notes, `--help` text, config examples, and doc comments. When asked to refresh only a change, cover just the docs that change made stale or should have updated, and the comments it added or changed.

## Rules

- **The code is the truth.** Check each claim against it: commands, paths, flags, environment variables, versions, architecture, setup steps. Run the cheap checks (`--help`, a single narrow command) and read the code for the rest. Fix what drifted, and delete what is not worth keeping.
- **Make it shorter.** Cut what is outdated, duplicated, or restates what the code shows. Give each fact one home and link to it rather than copy it (`single-source-of-truth`). Keep the why, constraints, invariants, commands, and hazards. Do not reword for taste.
- **AGENTS.md** holds commands, layout, and the conventions and hazards a newcomer cannot read from the code. It does not repeat the global instructions. Keep an existing AGENTS.md and CLAUDE.md arrangement.
- **Comments** go through `comment-cleanup`.
- **Leave dated records alone** (changelog, ADRs, release notes), marking a superseded one rather than rewriting it. For generated docs, edit the source and the generator input, not the output.
- **One writer,** so edits do not overlap. Create no new doc file unless something essential has no home.
- **Verify narrowly:** every `path:line` and link you kept resolves, and any doc check the repo has (a link checker, a doctest) runs on the files you touched.

**The test:** a newcomer can follow every command in the docs and reach the code each doc points to, and no sentence is there only because it used to be true.

**Reply:** the files changed or removed and what was cut, claims you could not verify, and places where the code looks wrong rather than the doc.
