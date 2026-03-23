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

Use modern tools instead of POSIX equivalents. No exceptions. For detailed usage, see `~/d/library/tools/`.

# Search & Exploration — TOKEN BUDGET IS CRITICAL

**NEVER spawn an Explore agent as a first resort.** Explore agents are expensive (thousands of tokens). Before spawning one, you MUST first try at least two direct searches using Grep/Glob. Only escalate to Explore if those searches returned nothing useful AND you have no other leads.

**Search recipes — use these directly, not via agents:**
- Find a file: `Glob "**/*partial_name*"`
- Find a symbol (function/class/type): `Grep "(def|class|function|fn|type|interface)\s+Name"`
- Find usage/imports: `Grep "import.*Name|from.*Name|require.*Name"`
- Map a directory: `Bash "eza --tree -L 2 path/"`
- Find config files: `Glob "**/*.{toml,yaml,yml,json,cfg,ini}"`
- Find entry points: `Grep "^(func main|if __name__|def main)" --type py,go,rs`

**Before ANY agent spawn, ask yourself:**
1. Do I already know which files are involved? → Read them directly.
2. Can I name the symbol/string I'm looking for? → Grep for it.
3. Can I guess the filename pattern? → Glob for it.
4. Did the user or git history already point me to the right area? → Go there directly.

If all four answers are "no", THEN an Explore agent is justified — but use `model: "haiku"` to minimize cost.

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
