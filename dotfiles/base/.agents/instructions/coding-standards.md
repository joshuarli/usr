# Coding standards gate

Coding standards live in `~/.agents/standards/*.md`. Each declares the paths, shebangs, and added-line patterns that trigger it, so `standards select` chooses them from the change instead of from model judgment. Apply them once, at completion, without loading their text into the main session.

In Claude Code and Codex, a PostToolUse hook (`standards hook`) names each standard the first time an edit in the session triggers it, so you can follow its `## Code` rules while writing. Other harnesses rely on the gate alone. A standard name in backticks, such as `lifecycle-concurrency`, means `~/.agents/standards/<name>.md`.

1. **Select.** Before reporting code changes done, run `standards select --base BASE` in each repository you changed, where `BASE` is the revision before your work (`@{upstream}` when your commits are not pushed yet). It covers those commits plus staged, unstaged, and untracked work; without `--base` it compares against `HEAD` and misses work you already committed. No output means no standard applies: stop here.
2. **Check in a reviewer.** A scout has no shell and reads only its worktree, so hand it files. Commit the work locally (fold any gate fixes in before pushing), create `git worktree add --detach .work/wt/standards-gate HEAD`, and in it write `git diff BASE HEAD` to `.work/tmp/standards-gate/change.diff`, where `BASE` is the revision before your work, then copy each listed standard next to it. Give one scout-tier reviewer, routed by `orchestrate`, that directory and a one-line intent. Its brief must name the read tools and the limits: use the harness-native `read`, `grep` and `glob` directly, never through a code-execution tool; a scout has no `shell` or `edit`. Reviewers that probe for tools spend turns before reading the diff. Retire the worktree with `worktree-retire` afterwards. The reviewer reads the standards' `## Code` sections and the diff and returns findings only, each with `file:line`, the rule it breaks, and a class:
   - **must-fix:** a clear violation in lines the change added or touched.
   - **consider:** a subjective improvement, or a violation in nearby code the change did not touch.
   - **skip:** the rule does not apply here, with the reason.

   A delegated worker, a review-only session, or a harness without delegation reads the listed standards and checks the diff directly instead.
3. **Apply.** Fix must-fix findings that are low-risk and in scope, then rerun the narrowest check that covers the edit. Report consider findings and any must-fix you did not apply, with the reason; do not widen the task to fix code the change did not touch.

A standard binds only the code a change touches. A repository's own instructions win where they are more specific.

## Adding a standard

Write `~/usr/dotfiles/base/.agents/standards/<name>.md`. The file opens with TOML frontmatter between `+++` lines:

```toml
name = "<name>"                 # the file name
summary = "One line."

[[trigger]]                     # a standard fires when any trigger fires
paths = ["*.py", "!*_pb2.py"]   # gitignore rules: last match wins, "/" anchors, "**" spans directories, a trailing "/" means a directory
content = ['\bargparse\b']    # conditions in one trigger must all hold: paths, shebang (first line), content (added lines)

[examples]                      # standards check proves these
match = ["tools/cli.py", { path = "bin/run", text = "#!/bin/sh\n" }]
skip = ["gen/a_pb2.py", "README.md"]
```

`content` regexes run in multiline mode over a file's added lines (its whole text for untracked files and `--tree`), so `^` and `$` anchor at line boundaries; prefer `[ \t]` over `\s` where a match must not cross a line break. `paths` are matched against the repository-relative path. A broad code trigger should exclude data files (`!*.json`, `!*.jsonl`, `!*.log`, and similar) so fixtures and logs do not select it.

The body needs a `## Code` section: the rules the gate applies to touched code. Put repository-wide work, such as adopting a tool or migrating every file, under `## Adoption`; only an explicit `/standardize` applies it. Run `standards check`, and `standards explain FILE` to see why a trigger matched or missed. Prefer a lint or test that rejects a violation mechanically; a standard covers what a tool cannot check.

### Out of scope

The owner has ruled these out. Do not write standards for them, and do not fold their rules into another standard:

- C and C headers.
- Python packaging and project layout: `pyproject.toml` project metadata, build backends, and source layouts. The `python` standard's ty and Ruff configuration stays in scope.
