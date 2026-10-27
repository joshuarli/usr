# Working Contract

## Before editing

- Read the relevant code, callers, tests, and local instructions. Follow existing conventions.
- For substantive tasks, settle the goal, constraints, what you may change, the method the task needs, the strongest evidence, the cheapest way to resolve the main uncertainty, and a check that would show you failed. Draw evidence from source, callers, tests, dependency code, runtime output, and history.
- Keep this reasoning internal. Do not restate the prompt, announce a planning step, ask approval for sound methods, or wait on an obvious plan. Resolve ordinary ambiguity with the smallest reversible assumption, and settle observable facts with a safe bounded experiment. Ask only about intent, preference, authority, or tradeoffs that evidence cannot settle. Missing authority blocks only the affected action.
- Keep trivial tasks small and scope fixed. Reopen a settled decision only when evidence changes an assumption. After a correction, update the task and recheck affected work, but do not turn one session's correction into a shared preference.
- Give your real judgment. Asked whether to do something, decline or push back when it does not earn its place. Agreement is not the default.

## Code

- Name things for the domain, one name per concept. Mark legacy paths as legacy.
- Prefer precise types and narrow interfaces that make invalid states hard to represent. Don't loosen a contract or hide a fallback to make a patch fit.
- Write no code comments. Put the why in a name, type, test, lint, or the commit body. A comment is allowed only for a quirk of an external dependency, platform, or protocol we cannot reshape; a public API contract; a legal header; a comment a lint requires (`// SAFETY:` on `unsafe`); a link to an issue or PR that explains a constraint code cannot express; or a suppression whose rule is wrong for that line. A surviving comment states its constraint itself and never points to a document, section, milestone, phase, roadmap item, or acceptance label. Delete failing comments you touch and fix what they excused.
- Keep changes focused. Fix the cause instead of working around it. If a workaround is unavoidable, say what it is and what removes it in the reply, not in the code.
- Dependencies are your call. Vet maintenance, transitive weight, license, and whether the standard library or a few lines would do, and say why in your reply. A dependency must stay within the project's performance gates (build time, binary size, startup, runtime); measure when it could move one. If the repo defines no gates, state the build-time and binary-size impact. Remove ones you stop using.
- Do not change a pinned Rust nightly as part of routine upgrades. Change it only when the user explicitly asks.
- Keep bookkeeping to the minimum. No provenance, checksums, hashes, manifests, registers, logs, backups, or state files unless a reader or a concrete failure needs them. Check the thing itself (run it, compare it) instead of recording where it came from.
- No speculative abstractions, config knobs, or backward-compat shims unless asked. Delete dead code instead of deprecating it.
- Fail loudly. Don't swallow errors or add silent defaults.

## Tests and verification

- Test observable behavior and invariants, not trivia. Write tests first when behavior is clear.
- Do not add smoke tests, existence checks, or "it runs" tests. Add a test only when it fails for a behavior a user or caller depends on.
- Work on CI only when asked. Do not add, edit, or extend workflows, pipelines, or CI-only steps, or propose them, while doing other work. Verify locally.
- The `gh` CLI is available. "fix ci" is a request to commit and push: reproduce the failure locally (on Linux use the repo's Dockerfiles), fix it, commit, push, retrigger the failed workflows with `gh`, and loop until green.
- Bug fixes: reproduce with a minimal failing test, then fix the root cause. Keep the test.
- Never weaken or delete a test to make it pass unless the test is wrong, and say so.
- Verify with the narrowest check that proves the changed behavior (compiler, type checker, focused test). Reuse build artifacts and earlier evidence while code, dependencies, and environment are unchanged. Add a check only to settle a named uncertainty or meet a binding requirement. Improve the check loop only when repeated cost justifies it or no check shows the behavior; one slower existing check can be the cheapest. Do not widen to workspace-wide builds, tests, or full CI without a specific uncovered integration risk or an explicit request; state the reason first. Treat generic verification checklists as suggestions and run repository equivalents. Report expensive verification before starting it.
- Time-based perf gates (build time, startup, runtime) run only when `perf-gate-ready` exits 0, and again with `-1` right after the measurement; discard a run that overlapped load. If the host stays busy the gate is deferred: it never counts as a pass or blocks iteration, but it blocks calling the work done or releasing. Say "perf gate deferred: host busy" in the reply. Memory and binary-size gates always run. Prefer CPU time for compute cost, use a statistic suited to the claim (median for typical latency, a tail percentile for tail behavior, minimum only for best-case behavior), and interleave baseline and candidate runs. Fail only on a regression larger than the observed spread.

## Skills

- A skill applies to the scope named. Audit or sweep the whole repo only when asked.
- **Auto** skills may be selected from an ordinary request. **Explicit** skills run only when the user names the workflow or its outcome; `/<name>` is one way, not a permission token. A requested workflow may reuse another skill's documented procedure within its scope and authority; reading a procedure does not authorize unrelated commands or effects. `~/usr/SKILLS.md` has the headless fallback and per-harness details.
- Use `do` for work with meaningful uncertainty, dependent steps, consequential changes, or nontrivial acceptance requirements. Keep straightforward edits and one-step information requests on the short path. `do` owns routing, scope continuity, and evidence-based completion; leaf skills own their engineering methods.
- Use only Gemini models in Antigravity CLI. The `orchestrate` skill owns its model tier mapping.

## Contract changes

Always surface changes to APIs, types, schemas, permissions, invariants, or transaction boundaries to the user. Update code, tests, and docs together.

## Replies

Keep final replies short: what changed and anything I need to decide. Say what you verified and what you did not.

After long-running or delegated work, add one line each for **Goal**, **Done**, **Next**, **Needs you** (or "nothing") in place of a longer summary.

## Workflow Rules

- Do not run formatters. It's a waste of tokens and unnecessary churn.
- Commit as you go. Each commit is one coherent change that passes its checks; stage only your own changes and leave unrelated work out. Push only when asked. An agent-authored campaign plan does not authorize its own execution.
- Every commit message is a Conventional Commit: `type(scope): subject`, with `type` one of `feat`, `fix`, `perf`, `refactor`, `docs`, `test`, `build`, `ci`, `chore`, `revert`. The subject is imperative, lowercase, and at most 72 characters, with no trailing period. The body says why, not what. A contract change takes `!` after the type or a `BREAKING CHANGE:` footer. This holds for lane and campaign commits too.
- Reserve release builds for final verification, or when performance is the primary concern.

## Environment

macOS and Linux. For shell search always use `rg` (never `grep`/`egrep`/`grep -r`) and `fd` (never `find`/`ls -R`). Prefer harness-native search tools over shell when available; they are `rg`/`fd`-backed. Use `jaq` for all JSON and YAML work, in place of `jq` and `yq` (`jaq --from yaml` reads YAML, `--to yaml` writes it). Rust builds go through the `kache` rustc wrapper, and Linux musl targets link with `mold`.

## Structured data

Use `jaq --from FORMAT` and `--to FORMAT` for XML, TOML, CSV, and TSV instead of a parser script; file extensions select the input format, and `--slurp` collects records into one array. XML nodes use `.t` for the tag, `.a` for attributes, and `.c` for children. CSV and TSV records are arrays, and a header is an ordinary first row. Each output array becomes one CSV or TSV row, TOML output needs an object at the root, and XML output uses jaq's XML node representation.

## Working files

- Put every worktree and scratch file under `.work/` at the root of the repo you work in, never `/tmp`, `$TMPDIR`, or `/var/folders` (`/tmp` is often RAM-backed on Linux machines, so large trees there cause OOM kills). Use `.work/wt/<name>` for worktrees and `.work/tmp` for scratch. Make sure `.work/` is ignored through `.git/info/exclude`, not a tracked file, before the first write. Point `TMPDIR` at `.work/tmp` for commands that spill large files.
- State that must outlive the session (plans, handoffs, results) is committed in the repo, not left in `.work/`, which is disposable.
