# Rules

- Never narrate actions ("Let me read...", "I'll now...") or confirm obvious tool results ("The file has been updated."). DO summarize findings and reasoning — those are useful context for later turns.

- Never echo back content the user can already see: no printing diffs after edits, no quoting file contents after reads, no repeating command output after Bash calls. The UI already shows tool results — just state your interpretation or next step.

- Prefer the simplest correct solution. No premature abstraction, no unnecessary dependencies.

- Never remove useful comments during refactors. Update them if the code changes, but don't silently drop them.

- Never use `git push`.

- Never do release builds (`cargo build --release`), always dev.
