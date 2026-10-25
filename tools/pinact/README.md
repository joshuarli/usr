# pinact

A self-contained GitHub Actions SHA pinner, bundled as `~/.local/bin/pinact` by `make sync`. Requires Python 3.10+ and Git. No GitHub API/token, configuration file, installer, compiled binary, runtime `pip`/`uv`, or site-packages import; the tool runs under `python3 -I`.

```sh
pinact                         # pin tags in the current repository
pinact pin                     # same as above, explicit subcommand
pinact --check                 # offline CI check; never writes or uses network
pinact --refresh               # re-resolve tagged SHAs using their version comments
pinact --allow-branches        # opt in to pinning mutable branch refs
pinact --check path/to/ci.yml  # explicitly check a file
pinact run --check             # compatibility with the common upstream invocation
pinact lint --format=json      # provisional: machine-readable findings (see below)
```

Without filenames, it discovers tracked and untracked (non-ignored) `.github/workflows/*.{yml,yaml}` and `action.{yml,yaml}` files anywhere in the Git checkout. Explicit files can be used outside a Git repository. The only online operation is `git ls-remote` for ref resolution, batched per repository. Existing 40-hex-character pins are left unchanged. For annotated Git tags, the peeled **commit** SHA is used, not the tag-object SHA. Tags take precedence only when no identically named branch exists; collisions fail instead of guessing. Branch refs require `--allow-branches`.

The source `uses: owner/repo[/path]@ref` becomes `uses: owner/repo[/path]@<40-character SHA> # ref`. Quotes, indentation, LF/CRLF, file modes, and other comments are preserved. For an existing comment, the version is appended as `[pin:ref]` so the comment's original prefix stays intact. `--refresh` explicitly re-resolves these annotations but does **not** select newer semantic versions. Upgrade version selectors with Renovate or manually before running the pinner.

Checks deliberately verify **pin coverage, not the upstream provenance** of already pinned hashes or their comments. Local `./` and `docker://` actions are skipped. `uses:` keys under `with:`, `env:`, and the other non-action scopes, plus `run: |` block bodies, are not scanned. Unsupported `uses` scalar forms and flow-style inline action mappings fail instead of being rewritten speculatively. All files are scanned and all refs resolved before any write. Changes use atomic file replacement; Git ref/network failures and unsupported input leave files untouched.

## Layout

- `dotfiles/base/.local/bin/pinact`: launcher only. It resolves its own source path (through the `make sync` symlink), prepends `tools/pinact/src`, and dispatches. No `PYTHONPATH`, no installed distribution, works from any directory.
- `src/pinact/pinning.py`: `uses:` discovery, SHA resolution, atomic rewrite, pin CLI.
- `src/pinact/lint.py`: findings model and `lint` CLI (provisional surface, see below).
- `src/pinact/cli.py`: subcommand dispatch (`pin` default, `lint`; `fix` arrives later).
- `src/pinact/_vendor/yaml/`: pure-Python PyYAML 6.0.3 with MIT `LICENSE` and `PROVENANCE.txt`.
- `tests/test_yaml.py`: YAML regression suite (scalar styles, flow, blocks, comments, CRLF/LF, Unicode/BOM, anchors/aliases, merge keys, duplicate keys, `on:`, multi-doc/empty docs, odd indentation, invalid refs).

`uses:` discovery parses each file with vendored `yaml.compose_all(..., Loader=yaml.BaseLoader)` and walks the node tree, so source positions come from compose marks. A `uses` key inside a flow mapping or sequence fails closed; values that are not plain scalars fail as unsupported; keys under non-action scopes are skipped. An identical legacy line scan remains as the fallback for files the composer rejects, except undefined aliases, which fail closed. Symbolic links are refused, and a file that changed while refs resolved aborts before writing.

## Provisional `lint --format=json`

`pinact lint [--format=text|json] [files ...]` is a provisional surface for the repomod probe: the record shape (`filepath`, `line`, `column`, `id`, `severity`, `message`, `fixable`), stable rule IDs, deterministic ordering by file/line/column/id, repo-relative paths, and exit codes (0 clean, 1 findings remain, 2 operational failure) are already the repomod contract. Rule coverage is not: only `unpinned-uses` (fixable) and `invalid-uses` (malformed `uses`, unfixable) exist so far. JSON mode writes only the array to stdout.

```sh
python3 -I tools/pinact/test_pinact.py
python3 -I tools/pinact/tests/test_yaml.py
```

Migration from the upstream binary is automatic during `make sync` **only** when both its old `dl` state marker and `make` ownership record are present. An unowned executable is never overwritten; remove or move it manually if a conflict is reported.
