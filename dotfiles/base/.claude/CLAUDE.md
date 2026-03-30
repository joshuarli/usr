# Output

- Never narrate actions ("Let me read...", "I'll now...") or confirm obvious tool results ("The file has been updated."). DO summarize findings and reasoning.
- Never echo back content the user can already see: no printing diffs after edits, no quoting file contents after reads, no repeating command output after Bash calls. The UI already shows tool results — just state your interpretation or next step.

# Coding Style

- Prefer the simplest correct solution. No premature abstraction, no unnecessary dependencies.
- Vet every dependency before adding — fewer is always better.
- Never add banner/separator comments (`// ---`, `# ====`, `// ── Section ──`, etc.). No exceptions.
- Never remove useful comments during refactors. Comments that explain *why* something exists, document non-obvious constants, or clarify tricky behavior must be preserved. Update them if the code changes, but don't silently drop them.

# Building

- Never build release binaries (`cargo build --release`).

# Committing

- Do NOT run pre-commit hooks. User verifies commits independently.
- Never push to a remote. No `git push`, no `--force`. Leave pushing to the user.
