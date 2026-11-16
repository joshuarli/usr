# Renaming with fastermod

Use `fastermod`, not scripted `sed`/`perl`, to rename text or symbols across a tree. macOS and Linux only. Installed by `sh sync tools`; check `fastermod --version` and `fastermod --languages` for coverage.

Pick the narrowest mode:

- Binding-aware rename, the default for symbol renames:
  `fastermod --rename OldName NewName src/`
  Renames one resolved binding and its references. Fails closed (exit 3) when any relevant reference cannot be resolved — dynamic dispatch, unknown receiver, ambiguous target — and never falls back to a textual guess. `--at FILE:LINE:COL` (1-based line, 1-based UTF-8 byte column) selects among same-named bindings. Coverage is per language; `--languages` prints the capability matrix.
- Identifier tokens, syntactic, not binding-aware:
  `fastermod --ident oldName newName .`
  Replaces every identifier token spelled `oldName` regardless of binding. Use when every spelling should change or binding resolution is unavailable.
- Case-preserving textual rename:
  `fastermod -S tansu2 tansu .`
  With no uppercase letters in OLD, matches case-insensitively and adapts NEW's casing per match: `tansu2`→`tansu`, `TANSU2`→`TANSU`, `Tansu2`→`Tansu`. Text mode rewrites comments and strings too.
- Literal search text:
  `fastermod -F -S 'a.b(c)' 'a.b(d)' .` treats OLD as a literal string; `-F` avoids regex escaping.
- Structural rewrite:
  `fastermod --rewrite 'helper($$$ARGS)' 'renamed($$$ARGS)' .` uses AST patterns with `$VAR`/`$$$ARGS` metavariables; the replacement is an ast-grep template. Matches code, not comments.

Writing:

- On a non-TTY stdin (agents, CI) without `--apply`, fastermod previews diffs and exits 0 without writing; it never hangs. Pass `--apply` (legacy spelling `--accept-all`) to write unattended.
- `--dry-run` previews on a TTY; `--check` exits 1 when edits are pending and never writes; `--json` emits a machine-readable result; `--print-changed-files` lists paths written.
- Exit codes: 0 ok or preview, 1 pending changes (`--check`), 2 usage, 3 analysis could not complete safely, 4 I/O failure or stale plan.
- `--plan FILE` previews and saves a versioned plan without touching sources; `--apply-plan FILE` revalidates fingerprints and applies atomically, rejecting stale plans (exit 4).

Agent workflow:

1. `fastermod --rename Old New .` on a non-TTY previews; or read the diff with `--dry-run` on a TTY.
2. Exit 3 means the rename is unsafe, not that it needs more force: narrow with `--at FILE:LINE:COL`, or use `--ident` only if a syntactic rename is actually wanted. Never silence the failure by switching to regex.
3. `fastermod --rename Old New --apply .` to write.
4. Verify with the repository's own checks.
