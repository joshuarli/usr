# Coding standards gate

Coding standards live in `~/.agents/standards/*.md`. Each declares the paths, shebangs, and added-line patterns that trigger it, so `standards select` chooses them from the change instead of from model judgment. Apply them once, at completion, without loading their text into the main session.

1. **Select.** Before reporting code changes done, run `standards select` in each repository you changed. It reads staged, unstaged, and untracked work against `HEAD`; add `--base REV` to include commits since `REV`. No output means no standard applies: stop here.
2. **Check in a reviewer.** Give one scout-tier reviewer, routed by `orchestrate`, the repository path, the diff range, a one-line intent, and the listed standard file paths. The reviewer reads the standards and the diff itself and returns findings only, each with `file:line`, the rule it breaks, and a class:
   - **must-fix:** a clear violation in lines the change added or touched.
   - **consider:** a subjective improvement, or a violation in nearby code the change did not touch.
   - **skip:** the rule does not apply here, with the reason.

   A delegated worker, a review-only session, or a harness without delegation reads the listed standards and checks the diff directly instead.
3. **Apply.** Fix must-fix findings that are low-risk and in scope, then rerun the narrowest check that covers the edit. Report consider findings and any must-fix you did not apply, with the reason; do not widen the task to fix code the change did not touch.

A standard binds only the code a change touches. A repository's own instructions win where they are more specific.

## Adding a standard

Write `~/usr/dotfiles/base/.agents/standards/<name>.md` with frontmatter `name` (the file name), a one-line `summary`, and at least one list of `paths` (globs on the repository-relative path, also matched under any directory), `shebang` (regexes on the first line), or `content` (regexes on added lines). Run `standards check`. Prefer a lint or test that rejects the violation mechanically; a standard covers what a tool cannot check.
