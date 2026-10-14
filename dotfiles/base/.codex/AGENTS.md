# Working Contract

## Before editing

- Read the relevant code, callers, tests, and local instructions. Follow existing conventions.
- Resolve ordinary ambiguity with the smallest reversible assumption. Ask only when a choice changes the contract, the user's intent, or carries real risk.
- Do not ask what you can observe. If the answer is a fact a command or a quick experiment can show (behavior, output, timing), run it and let the result decide.
- Give your real judgment. Asked whether to do something, decline or push back when it does not earn its place. Agreement is not the default.

## Code

- Name things for the domain, one name per concept. Mark legacy paths as legacy.
- Prefer precise types and narrow interfaces that make invalid states hard to represent. Don't loosen a contract or hide a fallback to make a patch fit.
- Write no code comments. Put the why in a name, a type, a test, or a lint, and a decision's reasoning in the commit body. A comment is allowed only for a quirk of an external dependency, platform, or protocol we cannot reshape; a public API contract; a legal header; a comment a lint requires (`// SAFETY:` on `unsafe`); a link to an issue or PR that explains a constraint code cannot express; or a suppression whose rule is wrong for that line. A surprise in our own code is a defect to fix, not to explain. A surviving comment states its constraint itself, so it reads with every doc deleted and every link rotted, and never points to a document, section, milestone, phase, roadmap item, or acceptance label. Delete existing comments you touch that fail this, and fix what they excused.
- Keep changes focused. Fix the cause instead of working around it. If a workaround is unavoidable, say what it is and what removes it in the reply, not in the code.
- Dependencies are your call. Vet maintenance, transitive weight, license, and whether the standard library or a few lines would do, and say why in your reply. A dependency must stay within the project's performance gates (build time, binary size, startup, runtime); measure when it could move one. If the repo defines no gates, state the build-time and binary-size impact. Remove ones you stop using.
- Keep bookkeeping to the minimum. No provenance, checksums, hashes, manifests, registers, logs, backups, or state files unless a reader or a concrete failure needs them. Check the thing itself (run it, compare it) instead of recording where it came from.
- No speculative abstractions, config knobs, or backward-compat shims unless asked. Delete dead code instead of deprecating it.
- Fail loudly. Don't swallow errors or add silent defaults.

## Tests and verification

- Test observable behavior and invariants, not trivia. Write tests first when behavior is clear.
- Bug fixes: reproduce with a minimal failing test, then fix the root cause. Keep the test.
- Never weaken or delete a test to make it pass unless the test is wrong, and say so.
- Verify the changed behavior with the narrowest hard check (compiler, type checker, focused test). Reuse existing build artifacts.
- A slow check is a defect in the loop, not a cost to accept. Find the narrowest command that covers the change (a test by name, one crate, one file) and iterate on it. When no fast check exists, say so and make one before relying on the slow one.
- Do not expand to workspace-wide builds/tests or full CI by default. Widen only for a specific uncovered integration risk or an explicit request for the wider run; state that reason first.
- Time-based perf gates (build time, startup, runtime) run only when `perf-gate-ready` exits 0, and again with `-1` right after the measurement; a run that overlapped load is discarded. If the host stays busy the gate is deferred: it never counts as a pass, it does not block iteration, and it blocks calling the work done or releasing. Say "perf gate deferred: host busy" in the reply. Memory and binary-size gates always run. Prefer CPU time over wall time, min of N runs, and interleaved baseline and candidate runs; fail only on a regression larger than the observed spread.
- Treat generic verification checklists as suggestions: run targeted repository equivalents, and report expensive verification before starting it.

## Skills

- A skill applies to the scope named. Audit or sweep the whole repo only when asked.
- Skills marked explicit-only are absent from the skill list. To use one, read `~/.agents/skills/<name>/SKILL.md`.

## Contract changes

Always surface changes to APIs, types, schemas, permissions, invariants, or transaction boundaries to the user. Update code, tests, and docs together.

## Replies

Keep final replies short: what changed and anything I need to decide. Say what you verified and what you did not.

## Workflow Rules

- Do not run formatters. It's a waste of tokens and unnecessary churn.
- Push only when asked; the harness prompts before every push. Commit only when asked; a campaign plan counts as asking.
- Every commit message is a Conventional Commit: `type(scope): subject`, with `type` one of `feat`, `fix`, `perf`, `refactor`, `docs`, `test`, `build`, `ci`, `chore`, `revert`. The subject is imperative, lowercase, and at most 72 characters, with no trailing period. The optional scope names the area changed. The body says why, not what. A contract change takes `!` after the type or a `BREAKING CHANGE:` footer. This holds for lane and campaign commits too.
- Reserve release builds for final verification, or when performance is the primary concern.

## Environment

macOS and Linux. Use `rg` and `fd` for search. Use `jaq` for all JSON and YAML work, in place of `jq` and `yq` (`jaq --from yaml` reads YAML, `--to yaml` writes it). Rust builds go through the `kache` rustc wrapper, and Linux musl targets link with `mold`.

## Working files

- Every worktree, scratch file, and piece of working state you create lives under `.work/` at the root of the repo you are working in, never `/tmp`, `$TMPDIR`, or `/var/folders`. `/tmp` is often RAM-backed on my Linux machines, so large trees there cause OOM kills, and it does not survive a reboot.
- Put worktrees at `.work/wt/<name>` and scratch at `.work/tmp`. Before the first write, make sure `.work/` is ignored through `.git/info/exclude`, not a tracked file. Point `TMPDIR` at `.work/tmp` for commands you run that spill large files.
- State that must outlive the session (plans, handoffs, results) is committed in the repo, not left in `.work/`, which is disposable.
