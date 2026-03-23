# AGENTS

## Output Token Optimization
- Default to concise responses.
- Prefer short, high-level summaries of what changed and why.
- Do not include command transcripts, long logs, diffs, or file dumps unless explicitly requested.
- Mention blockers, failures, and required follow-up actions when relevant.
- Ask clarifying questions only when needed to avoid risky assumptions.

## Reference Library
A curated coding reference lives at `~/d/library`. Consult it selectively.

- For substantial language work: read `~/d/library/languages/{lang}/style.md`
- For language selection: read `~/d/library/languages/USAGE.md`
- Before adding dependencies: read `~/d/library/philosophy/dependencies.md`
- For unfamiliar CLI tools: read `~/d/library/tools/{tool}.md`
- Otherwise start at: `~/d/library/INDEX.md`

Workflow defaults from `~/d/library/WORKFLOW.md`:
- Prefer quiet/fail-fast build and test flags.
- Verify incrementally: type check, targeted test, then full suite.
- Cap noisy output with `head`/`tail`.

## Coding Principles
- Prefer the simplest correct solution.
- Avoid premature abstraction and unnecessary dependencies.
- Treat dependency additions as high-friction decisions.
- Preserve existing project conventions unless there is a strong reason to change them.

## Tooling Defaults (Codex)
- Prefer `rg` for text search and `rg --files` for file listing.
- Prefer modern CLI tools (`fd`, `eza`, `sd`, `jaq`, `xh`, `procs`, `dua`) when available.
- If a preferred tool is missing, use a standard fallback without blocking progress.
- Avoid flooding context with large command output.

## Editing and Safety
- Do not revert or overwrite unrelated local changes.
- If unexpected external edits appear during work, stop and ask how to proceed.
- Avoid destructive commands unless explicitly requested.
- Keep edits minimal, targeted, and reviewable.

## Delegation and Subagents
- Do not spawn subagents unless the user explicitly requests delegation/parallel work, or the task is a large mechanical refactor.
- Keep critical-path reasoning and implementation in the main agent.
- If delegating, assign clear ownership and integrate results carefully.

## Git and Commits
- Never bypass hooks to force a commit.
- Fix root causes when checks fail.
- Do not push to remote unless explicitly requested.
- Do not amend commits unless explicitly requested.

## No Routine Narration
- Do not announce routine operations (staging, committing, pushing, running tests).
- Execute routine non-destructive git operations directly when requested.
- Report only the final outcome for routine operations, unless there is a blocker or failure.
- Do not ask for confirmation for routine non-destructive commands unless runtime approval policy requires it.
