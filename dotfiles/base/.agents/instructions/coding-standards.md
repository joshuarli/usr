# Coding standards gate

Coding standards live in `~/.agents/standards/*.md`. Each declares the paths, shebangs, and added-line patterns that trigger it, so `standards select` chooses them from the change instead of from model judgment. Apply them once, at completion, without loading their text into the main session.

1. **Select.** Before reporting code changes done, run `standards select` in each repository you changed. It reads staged, unstaged, and untracked work against `HEAD`; add `--base REV` to include commits since `REV`. No output means no standard applies: stop here.
2. **Check in a reviewer.** Write the diff (`git diff REV` for the same range) to a file under the reviewer's worktree `.work/tmp/`, because a scout has no shell. Give one scout-tier reviewer, routed by `orchestrate`, that diff file, a one-line intent, and the listed standard file paths. The reviewer reads the standards' `## Code` sections and the diff and returns findings only, each with `file:line`, the rule it breaks, and a class:
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

The body needs a `## Code` section: the rules the gate applies to touched code. Put repository-wide work, such as adopting a tool or migrating every file, under `## Adoption`; only an explicit `/standardize` applies it. Run `standards check`, and `standards explain FILE` to see why a trigger matched or missed. Prefer a lint or test that rejects a violation mechanically; a standard covers what a tool cannot check.
