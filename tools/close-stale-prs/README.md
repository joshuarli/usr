# close-stale-prs

Find, and optionally delete, old remote branches associated with closed PRs. Branch deletion uses `git push --force-with-lease` with the tip OID observed during the snapshot, so GitHub's receive-pack refuses the delete when the branch has advanced; refused branches are reported and left for a later run. `gh` is used for all API reads; `git` is required only for `--delete`. The default behavior is a dry run. Installed on `PATH` as `close-stale-prs.py` via a shim in `dotfiles/base/.local/bin/close-stale-prs.py`.

```sh
close-stale-prs.py
close-stale-prs.py --delete
```
