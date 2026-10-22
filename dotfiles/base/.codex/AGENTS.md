# Working Contract

## Before editing

- Read the relevant code, callers, tests, and local instructions. Follow existing conventions.
- For substantive tasks, establish the outcome, request mode, constraints, authorized effects, the professional method the outcome needs, the strongest relevant evidence, the cheapest way to settle important uncertainty, and observable acceptance that could disprove completion. Use source, callers, tests, dependency code, runtime output, captures, and decision history as the task requires.
- Keep that interpretation internal. Do not rewrite the prompt, announce a sharpening phase, seek approval for sound methods, or wait on an obvious plan. Resolve ordinary ambiguity with the smallest reversible assumption. Use a safe bounded experiment for observable facts. Ask only about intent, preference, authority, or tradeoffs that evidence cannot settle. Missing authority blocks only the affected action. Keep trivial tasks small and scope fixed. Reconsider settled decisions only when evidence changes an assumption. When corrected, update the active task and inspect affected work without changing shared preferences from one session.
- Give your real judgment. Asked whether to do something, decline or push back when it does not earn its place. Agreement is not the default.

## Code

- Name things for the domain, one name per concept. Mark legacy paths as legacy.
- Prefer precise types and narrow interfaces that make invalid states hard to represent. Don't loosen a contract or hide a fallback to make a patch fit.
- Write no code comments. Put the why in a name, a type, a test, or a lint, and a decision's reasoning in the commit body. A comment is allowed only for a quirk of an external dependency, platform, or protocol we cannot reshape; a public API contract; a legal header; a comment a lint requires (`// SAFETY:` on `unsafe`); a link to an issue or PR that explains a constraint code cannot express; or a suppression whose rule is wrong for that line. A surprise in our own code is a defect to fix, not to explain. A surviving comment states its constraint itself, so it reads with every doc deleted and every link rotted, and never points to a document, section, milestone, phase, roadmap item, or acceptance label. Delete existing comments you touch that fail this, and fix what they excused.
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
- Bug fixes: reproduce with a minimal failing test, then fix the root cause. Keep the test.
- Never weaken or delete a test to make it pass unless the test is wrong, and say so.
- Verify the changed behavior with the narrowest hard check (compiler, type checker, focused test). Reuse existing build artifacts.
- Reuse completed evidence while the relevant code, dependencies, environment, and acceptance assumptions remain valid. Add or repeat a check to resolve a named remaining uncertainty, cover relevant changed inputs, or satisfy a binding requirement. Stop when the requested result and applicable proof are complete.
- Use the narrowest sufficient existing check. Improve the loop when its expected repeated cost justifies that work, or when no existing check can establish the needed behavior. Running an existing slower check once may be the cheapest correct completion path.
- Do not expand to workspace-wide builds/tests or full CI by default. Widen only for a specific uncovered integration risk or an explicit request for the wider run; state that reason first.
- Time-based perf gates (build time, startup, runtime) run only when `perf-gate-ready` exits 0, and again with `-1` right after the measurement; a run that overlapped load is discarded. If the host stays busy the gate is deferred: it never counts as a pass, it does not block iteration, and it blocks calling the work done or releasing. Say "perf gate deferred: host busy" in the reply. Memory and binary-size gates always run. Prefer CPU time for compute cost, use a statistic suited to the claim (median for typical latency, a tail percentile for tail behavior, minimum only for best-case behavior), and interleave baseline and candidate runs. Fail only on a regression larger than the observed spread.
- Treat generic verification checklists as suggestions: run targeted repository equivalents, and report expensive verification before starting it.

## Skills

- A skill applies to the scope named. Audit or sweep the whole repo only when asked.
- Automatic eligibility allows the agent to select a method from an ordinary request when its conditions fit. An explicit workflow requires the user to request that workflow or outcome; a slash command is a convenient way to request it, not an authorization token.
- An already-requested workflow may reuse a documented procedure from another skill within its existing scope and authority. Reading a procedure does not authorize unrelated commands or effects.
- Automatically use `do` for work with meaningful uncertainty, dependent steps, consequential changes, or nontrivial acceptance requirements. Keep straightforward edits and one-step information requests on the short path. `do` owns routing, request mode, scope continuity, and evidence-based completion; leaf skills own their engineering methods.
- In Codex, skills marked explicit-only are absent from automatic selection. Read their procedure when the user requested that workflow or another active workflow directly references it within the same scope and authority.
- Antigravity CLI reads skill descriptions and may activate eligible skills automatically. Its documented skill frontmatter uses only `name` and `description`, so global instructions must keep explicit-only workflows out of automatic selection. The user may request one in plain language or with `/<skill-name>`; another already-requested workflow may reuse its procedure within the same scope and authority.
- Use only Gemini models in Antigravity CLI. The `orchestrate` skill owns its model tier mapping.

## Contract changes

Always surface changes to APIs, types, schemas, permissions, invariants, or transaction boundaries to the user. Update code, tests, and docs together.

## Replies

Keep final replies short: what changed and anything I need to decide. Say what you verified and what you did not.

## Workflow Rules

- Do not run formatters. It's a waste of tokens and unnecessary churn.
- Push only when asked. Commit only when asked or when a directly requested workflow documents local commits. An agent-authored campaign plan does not authorize execution or commits.
- Every commit message is a Conventional Commit: `type(scope): subject`, with `type` one of `feat`, `fix`, `perf`, `refactor`, `docs`, `test`, `build`, `ci`, `chore`, `revert`. The subject is imperative, lowercase, and at most 72 characters, with no trailing period. The optional scope names the area changed. The body says why, not what. A contract change takes `!` after the type or a `BREAKING CHANGE:` footer. This holds for lane and campaign commits too.
- Reserve release builds for final verification, or when performance is the primary concern.

## Environment

macOS and Linux. Use `rg` and `fd` for search. Use `jaq` for all JSON and YAML work, in place of `jq` and `yq` (`jaq --from yaml` reads YAML, `--to yaml` writes it). Rust builds go through the `kache` rustc wrapper, and Linux musl targets link with `mold`.

## Query structured data with jaq

Use jaq's `--from FORMAT` and `--to FORMAT` options to query XML, TOML, CSV, and TSV instead of writing a parser script. File extensions select the input format when you omit `--from`.

```sh
jaq --from xml '.. | select(.t? == "a") | .a.href' page.xml
jaq --from toml '.dependencies' Cargo.toml
jaq --from csv '.[0]' data.csv
jaq --from tsv '.[0]' data.tsv
```

XML elements use `.t` for the tag, `.a` for attributes, and `.c` for children. CSV and TSV records are arrays. A header is an ordinary first row. Use `--slurp` to collect all records into one array.

Use `--to FORMAT` to serialize filter results. Each output array becomes one CSV or TSV row. TOML output needs an object at the root. XML output uses jaq's XML node representation.

```sh
jaq --from xml --to xml '(.. | select(.t? == "em") | .t) = "i"' page.xml
jaq -n --to toml '{name: "jaq"}'
jaq -n --to csv '[["name", "count"], ["jaq", 1]][]'
```

Replace `csv` with `tsv` to write tab-separated rows.

## Working files

- Every worktree, scratch file, and piece of working state you create lives under `.work/` at the root of the repo you are working in, never `/tmp`, `$TMPDIR`, or `/var/folders`. `/tmp` is often RAM-backed on my Linux machines, so large trees there cause OOM kills, and it does not survive a reboot.
- Put worktrees at `.work/wt/<name>` and scratch at `.work/tmp`. Before the first write, make sure `.work/` is ignored through `.git/info/exclude`, not a tracked file. Point `TMPDIR` at `.work/tmp` for commands you run that spill large files.
- State that must outlive the session (plans, handoffs, results) is committed in the repo, not left in `.work/`, which is disposable.
