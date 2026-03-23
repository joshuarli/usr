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

# CLI Tools

Use modern tools instead of POSIX equivalents. No exceptions. For detailed usage, see `~/d/library/tools/`.

# Agents — ALMOST NEVER

Do not spawn agents (Explore, general-purpose, Plan, etc.) unless the user explicitly
asks for parallel/background work, or for bulk mechanical refactors across many files.
Do all searching, reading, and reasoning yourself in the main conversation. Slower is fine.

The only acceptable agent use: user-requested parallelism or menial bulk operations
(e.g., "rename X across 40 files"). Even then, use `model: "haiku"`.

# Search Recipes

Use these directly — never via agents:
- Find a file: `Glob "**/*partial_name*"`
- Find a symbol: `Grep "(def|class|function|fn|type|interface)\s+Name"`
- Find usage/imports: `Grep "import.*Name|from.*Name|require.*Name"`
- Map a directory: `Bash "eza --tree -L 2 path/"`
- Find config files: `Glob "**/*.{toml,yaml,yml,json,cfg,ini}"`

| Instead of | Use |
|---|---|
| `grep` | `rg` |
| `find` | `fd` |
| `ls`, `tree` | `eza` |
| `sed` | `sd` |
| `jq` | `jaq` |
| `curl` | `xh` |
| `ps` | `procs` |
| `du` | `dua` (never `dua i`) |

# Committing

- All changes must pass pre-commit hooks. Never bypass with `--no-verify`.
- If a hook fails, fix the underlying issue — don't suppress it.
- Never push to a remote. No `git push`, no `--force`. Leave pushing to the user.
