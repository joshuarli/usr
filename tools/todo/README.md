# todo

`todo` manages the nearest `TODO.md` in the current directory or an ancestor. `--file NAME`, given before the subcommand, selects another backlog file name, such as `todo --file TODO-DESLOP.md list --json`; it is a file name, not a path, and each backlog keeps its own prefix and `Next`. It needs Python 3 and the synced dotfiles checkout. Create a backlog with `Prefix: ABC` and `Next: 1` on separate lines before filing its first ticket. The prefix is three or four uppercase letters. IDs never reuse a number.

`todo show CHB-10` also works outside the owning repository. It checks the nearest `TODO.md` first, then searches repository-root `TODO*.md` backlogs under `~/repos` and this tool's checkout. Set `REPOMOD_ROOT` to another absolute workspace directory. Discovery skips hidden directories, including `.work` worktrees, and follows repository symlinks once. Multiple matching global records fail with the candidate paths. Explicit `--file NAME` selects only the nearest named backlog. Show validates the requested record, so malformed unrelated tickets do not prevent reading it. Other commands operate on the selected local backlog.

```sh
todo list --json
todo list --priority P1,P2 --json
todo show ABC-1 --json
todo add --json - < ticket.json
todo edit ABC-1 --json - < changes.json
todo close ABC-1
todo check --json
todo fmt --check
todo fmt
```

List returns compact records; show returns all fields. Add accepts a JSON object with `priority`, `title`, `area`, `where`, `problem`, `recommendation`, `fix_with`, and `effort`, plus optional `design`. Values are nonempty single-line strings; priority is P1–P4 and effort is S, M, or L. Area is free text. Edit accepts a subset of these fields; `"design": null` removes the optional design. Add and edit print the resulting record as JSON. Check reports malformed records, duplicate IDs, a non-monotonic Next value, and priority/ID ordering. Invalid input exits nonzero without writing.

Changes use a lock covering the read–modify–write transaction and an atomic replacement in the backlog directory. Git checkouts keep the lock in their worktree-specific Git directory; other directories use `.todo.lock`. The lock serializes cooperating processes in one checkout, not different worktrees. A single integrator owns cross-worktree changes. The tool preserves text outside ticket fields and retains unchanged ticket text; formatting orders tickets by priority and ID. It does not commit changes or determine whether work is complete.
