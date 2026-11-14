# close-stale-prs

Find, and optionally delete, old remote branches associated with closed PRs. A branch is eligible only when its current tip is the final head of a merged pull request or an ancestor of the default branch; branches without that evidence are preserved. Branch deletion uses `git push --force-with-lease` with the tip OID observed during the snapshot, so GitHub's receive-pack refuses the delete when the branch has advanced; refused branches are reported and left for a later run. `gh` is used for all API reads; `git` is required only for `--delete`. The default behavior is a dry run. Installed on `PATH` as `close-stale-prs.py` via a shim in `dotfiles/base/.local/bin/close-stale-prs.py`.

```sh
close-stale-prs.py
close-stale-prs.py --delete
```

Run the stdlib test suite with:

```sh
TMPDIR="$PWD/.work/tmp" python3 -I tools/close-stale-prs/tests/test_close_stale_prs.py
```
