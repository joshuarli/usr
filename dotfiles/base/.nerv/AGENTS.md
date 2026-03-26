# Reference Library

A curated coding reference lives at **`~/d/library`**. Consult it selectively — don't read files speculatively.

- **When writing a new file or doing substantial work in a language**: read `~/d/library/languages/{lang}/style.md`
- **When choosing a language for a new project**: read `~/d/library/languages/USAGE.md`
- **When adding a dependency**: read `~/d/library/philosophy/dependencies.md`
- **When using an unfamiliar CLI tool**: check `~/d/library/tools/{tool}.md`
- **For anything else**: start at `~/d/library/INDEX.md`

Key workflow rules (from `~/d/library/WORKFLOW.md` — don't re-read the file):
- Use quiet/silent flags for builds (`make -s`, `--quiet`, `--bail`). Fail fast.
- Verify incrementally: type check → specific failing test → full suite.
- Cap noisy output with `head`/`tail` rather than flooding context.

# Output

Never narrate actions ("Let me read...", "I'll now...") or confirm obvious
tool results ("The file has been updated."). DO summarize findings and
reasoning — those are useful context for later turns.

Never echo back content the user can already see: no printing diffs after edits,
no quoting file contents after reads, no repeating command output after Bash calls.
The UI already shows tool results — just state your interpretation or next step.

# Coding Style

Prefer the simplest correct solution. No premature abstraction, no unnecessary dependencies.
Vet every dependency before adding — fewer is always better.
Formatting and linting enforced by pre-commit hooks.
No banner/section-divider comments (e.g. `# ---- Section ----`). Use whitespace and
function ordering to convey structure. If a file needs section headers, it's too long — split it.
Never remove useful comments during refactors. Comments that explain *why* something
exists, document non-obvious constants, or clarify tricky behavior must be preserved.
Update them if the code changes, but don't silently drop them.

# CLI Tools

Use modern tools instead of POSIX equivalents. No exceptions. For detailed usage, see `~/d/library/tools/`.

| Instead of | Use |
|---|---|
| `grep` | `rg --color=never --no-heading --line-number` |
| `find` | `fd --color=never` |
| `ls`, `tree` | `eza --no-user --no-time --no-permissions --color=never` |
| `sed` | `sd` |
| `jq` | `jaq -r` |
| `curl` | `xh --pretty=none` |
| `ps` | `procs --color=disable` |
| `du` | `dua` (never `dua i`) |
| `yq` | `yq --no-colors` |

# Search Patterns

rg is NOT grep. It searches recursively by default. There is no `-r` flag for recursion (`-r` means `--replace`). There is no `--include` flag (use `-g "*.ext"` or `-t type` to filter files).

- Find files: `fd --color=never "pattern"`
- Search code: `rg --color=never --no-heading -n "pattern" .`
- Search specific file types: `rg --color=never --no-heading -n "pattern" -t rust .`
- Search with glob filter: `rg --color=never --no-heading -n "pattern" -g "*.rs" .`
- Find a symbol: `rg --color=never --no-heading -n "(def|class|function|fn|type|interface)\s+Name" .`
- Find usage/imports: `rg --color=never --no-heading -n "import.*Name|from.*Name|require.*Name" .`
- Map directory: `eza --no-user --no-time --no-permissions --color=never --tree -L 2 path/`
- Find config: `fd --color=never -e toml -e yaml -e json`
- AST search: `sg --color=never --lang LANG "pattern"`

# Git

All changes must pass pre-commit hooks. Never use `--no-verify`.
If a hook fails, fix the underlying issue — don't suppress it.
Never push to a remote. No `git push`, no `--force`. Leave pushing to the user.
