# Working Contract — lean

## Preferences and boundaries

- Keep scope fixed; no repo-wide sweeps unless asked. Surface changes to APIs, types, schemas, permissions, invariants, and transaction boundaries; update affected code, tests, and docs together. An agent-authored plan does not authorize execution.
- Prefer precise domain names/types and narrow interfaces. No speculative abstractions, backward-compatibility shims, silent defaults, or bookkeeping without a concrete consumer or failure to address. Delete dead code. Vet dependencies for maintenance, transitive weight, license, and performance cost; explain the choice and remove unused dependencies.
- Do not run formatters, change pinned Rust nightlies, or work on CI unless explicitly asked. "fix ci" authorizes reproducing locally (repo Dockerfiles on Linux), committing, pushing, retriggering with `gh`, and iterating until green.
- No code comments except external constraints, public API contracts, legal/lint/safety requirements, justified suppressions, or explanatory issue/PR links. State the constraint directly, never through roadmap/phase references; remove failing comments you touch. Explain unavoidable workarounds and their removal conditions in the reply.

## Execution

- Use task-specific skills when useful; do not load `do` solely because work is substantive. Honor requested workflows and their procedures. Explicit skills require the named workflow or outcome; reading a procedure grants no additional scope or authority.
- Before delegation, read `orchestrate` and use `pi-subagent-bridge` for every tier. Expert and god are pinned to Antigravity `gemini-4-carbon-high` with no fallback; Gemini 4 Argon is forbidden. Only scout/mechanic/worker may use native subagents if the bridge runs out of quota or has no available backend, with unchanged scope and independent parent review. With verified, safely shareable evidence and meaningful tier uncertainty, consult `decide`; unavailable advice does not block. Hydrogen replaces Gemini 3.8 Flash in explicit Antigravity selections when available.
- Test behavior, not existence or "it runs". Keep a regression test for fixes; never weaken a correct test. Use the narrowest decisive check and reuse still-valid evidence. Widen verification only for a named integration risk or an explicit request; announce expensive checks first. Reserve release builds for final verification or performance work.
- Before performance measurements or adding dependencies, read `~/.agents/instructions/performance.md`. Deferred required gates block completion/release, not useful iteration.

## Environment and changes

- macOS/Linux: prefer native search, otherwise `rg`/`fd`, not `grep`/`find`. Use `jaq`, not `jq`/`yq` or parser scripts, for structured data. For non-JSON formats read `~/.agents/instructions/structured-data.md`. Rust uses `kache`; Linux musl links with `mold`.
- Scratch and worktrees belong in repo `.work/tmp` and `.work/wt/<name>`, never system temp. Ignore `.work/` through `.git/info/exclude` before writing; set `TMPDIR` accordingly. Commit durable plans, handoffs, and results outside scratch.
- Commit and push completed, verified changes without waiting for another request; stage only your work. Use Conventional Commits: `type(scope): subject`, types `feat|fix|perf|refactor|docs|test|build|ci|chore|revert`, lowercase imperative subject at most 72 characters, no final period. The body explains why; contract changes use `!` or `BREAKING CHANGE:`.

## Replies

Be direct; disagree when warranted. Keep replies short: result, verification gaps, and decisions needed. After long-running or delegated work use Goal / Done / Next / Needs you, carrying forward unresolved user decisions and manual steps. Do not turn a one-session correction into a shared preference.
