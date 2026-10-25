# pinact

A small, dependency-free GitHub Actions SHA pinner, bundled as `~/.local/bin/pinact` by `make sync`. Requires Python 3.10+ and Git. No GitHub API/token, configuration file, installer, or compiled binary.

```sh
pinact                         # pin tags in the current repository
pinact --check                 # offline CI check; never writes or uses network
pinact --refresh               # re-resolve tagged SHAs using their version comments
pinact --allow-branches        # opt in to pinning mutable branch refs
pinact --check path/to/ci.yml  # explicitly check a file
pinact run --check             # compatibility with the common upstream invocation
```

Without filenames, it discovers tracked and untracked (non-ignored) `.github/workflows/*.{yml,yaml}` and `action.{yml,yaml}` files anywhere in the Git checkout. Explicit files can be used outside a Git repository. The only online operation is `git ls-remote` for ref resolution, batched per repository. Existing 40-hex-character pins are left unchanged. For annotated Git tags, the peeled **commit** SHA is used, not the tag-object SHA. Tags take precedence only when no identically named branch exists; collisions fail instead of guessing. Branch refs require `--allow-branches`.

The source `uses: owner/repo[/path]@ref` becomes `uses: owner/repo[/path]@<40-character SHA> # ref`. Quotes, indentation, LF/CRLF, file modes, and other comments are preserved. For an existing comment, the version is appended as `[pin:ref]` so the comment's original prefix stays intact. `--refresh` explicitly re-resolves these annotations but does **not** select newer semantic versions. Upgrade version selectors with Renovate or manually before running the pinner.

Checks deliberately verify **pin coverage, not the upstream provenance** of already pinned hashes or their comments. Local `./` and `docker://` actions are skipped. Unsupported `uses` scalar forms and flow-style inline action mappings fail rather than being rewritten speculatively; block scalars such as `run: |` are not scanned. All files are scanned and all refs resolved before any write. Changes use atomic file replacement; Git ref/network failures and unsupported input leave files untouched.

```sh
python3 -I tools/pinact/test_pinact.py
```

Migration from the upstream binary is automatic during `make sync` **only** when both its old `dl` state marker and `make` ownership record are present. An unowned executable is never overwritten; remove or move it manually if a conflict is reported.
