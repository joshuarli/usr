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

# Coding Style

Prefer the simplest correct solution. No premature abstraction, no unnecessary dependencies.
Vet every dependency before adding — fewer is always better.
Formatting and linting enforced by pre-commit hooks.

# CLI Tools

**When an agent has built-in search/glob tools, prefer those for basic queries.**

Only use the Explore agent when you genuinely don't know where to look. When prior context (commit diffs, earlier reads, user hints) already identifies the relevant files, use Read/Grep directly.

Use modern tools instead of POSIX equivalents. No exceptions. For detailed usage, see `~/d/library/tools/`.

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
