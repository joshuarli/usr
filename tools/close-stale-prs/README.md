# close-stale-prs

Find, and optionally delete, old remote branches associated with closed PRs. The only external command used is `gh`. The default behavior is a dry run. Installed on `PATH` as `close-stale-prs.py` via a shim in `dotfiles/base/.local/bin/close-stale-prs.py`.

```sh
close-stale-prs.py
close-stale-prs.py --delete
```
