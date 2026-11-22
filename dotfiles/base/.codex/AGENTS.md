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
<!-- policy:begin delegation -->
<!-- Generated from tools/pi-subagent-bridge/src/policy.ts; run make generate. -->
- All scout/mechanic/worker coding subagents, in every harness and skill, MUST launch through `pi-subagent-bridge` MCP tools or its CLI shim except top-level Command Code, OpenCode, Devin and Antigravity parents; follow `orchestrate`. Expert assignments use harness-native subagents (including Command Code `usr-expert`, OpenCode's `expert` agent, Devin's `run_subagent`, Codex's native subagents, Pi's native `expert` profile, Claude Code's `opus` at `xhigh` effort); the bridge has no expert tier. A top-level OpenCode session delegates only through OpenCode native subagents; free top-level models require free tier models. A top-level Devin session delegates only through Devin native subagents. A top-level Command Code session delegates only through native pinned `usr-*` subagents (HY4-medium worker is opt-in). A top-level Antigravity CLI session delegates only through native `usr-*` subagents; never use the Pi bridge. No `god` tier exists. Never route to `gemini-3.8` or `gemini-4-argon` or `gemini-4-carbon` or `gpt-6-astra` or `gpt-6.1-astra` or `gpt-6.2-astra` or `claude-fable` or `fable`. On Antigravity, Gemini 3.8 is retired and Carbon is never a fallback; a manual Carbon session requires the owner's explicit request. Only scout/mechanic/worker may use tier-matched native subagents after bridge quota/backend exhaustion or when the environment sets `USR_DELEGATION=native`, with the same scope, worktree and independent parent review. The parent scopes, verifies, reviews and integrates.
<!-- policy:end delegation -->
- Before assigning nontrivial work to any coding subagent, follow the shared `orchestrate` routing contract even if that skill was not explicitly invoked. With already-verified, safe-to-share task evidence and meaningful tier uncertainty, use `decide route --guide` and one evidence-backed `decide route` advisory call before launch. Skip for direct work, trivial delegation, missing evidence, unsafe disclosure, high-risk work, or only one eligible tier. Clef-flash cannot override the deterministic tier, pinned model/provider, owner scope, permissions, or harness-specific restrictions; unavailable advice never blocks execution.
<!-- policy:begin direct-models -->
<!-- Generated from tools/pi-subagent-bridge/src/policy.ts; run make generate. -->
- Antigravity main: `gemini-4-neon-high` (`high`); direct god mode: `gemini-4-neon-xhigh` (`xhigh`). Native `usr-*` subagents only: scout `usr-scout` targets `gemini-4-hydrogen-low` (`low`); mechanic `usr-mechanic` targets `gemini-4-hydrogen-low` (`low`); worker `usr-worker` targets `gemini-4-hydrogen-high` (`high`); expert `usr-expert` targets `gemini-4-neon-high` (`high`). Never use `pi-subagent-bridge` from agy. Custom-agent `model: flash/pro` is only a tier selector, not an enforced exact model or effort pin. Allowed direct models: `gemini-4-neon-high`, `gemini-4-neon-xhigh`, `gemini-4-hydrogen-high`, `gemini-4-hydrogen-low`. Verify `agy models` and actual child runtime models before using lanes; fail closed for `gemini-3.8-flash` or `gemini-4-argon`, Carbon or mismatched tiers. Carbon (`gemini-4-carbon-high`) is manual owner-only, never an automatic fallback. Do not purchase API credits.
<!-- policy:end direct-models -->

## Contract changes

Always surface changes to APIs, types, schemas, permissions, invariants, or transaction boundaries to the user. Update code, tests, and docs together.

## Replies

Keep final replies short: what changed and anything I need to decide. Say what you verified and what you did not.

After long-running or delegated work, add one line each for **Goal**, **Done**, **Next**, **Needs you** (or "nothing") in place of a longer summary. **Needs you** carries forward every proposal, question, or manual step still awaiting the user from earlier in the session; an item leaves only when the user answers it, it is done, or it no longer applies, and never silently.

When the user grants run-until-done authority ("don't stop until it's done", "I'm going to sleep", `/sleep`), keep working until the objective is done or no authorized step remains. Settle choices inside that authority yourself and act on your own recommendation instead of asking for it; do not end a turn to report progress, ask whether to continue, or wait out a delay you can work around. Surfacing a contract change is part of the report, not a reason to stop. **Needs you** then lists only what a missing fact, credential, or effect outside the grant blocks, each with its unblock condition, and every independent step continues.

## Workflow Rules

- Do not run formatters. It's a waste of tokens and unnecessary churn.
- Commit as you go. Each commit is one coherent change that passes its checks; stage only your own changes and leave unrelated work out. Push completed, verified commits without waiting for a separate request; do not leave them unpushed. An agent-authored campaign plan does not authorize its own execution.
- Every commit message is a Conventional Commit: `type(scope): subject`, with `type` one of `feat`, `fix`, `perf`, `refactor`, `docs`, `test`, `build`, `ci`, `chore`, `revert`. The subject is imperative, lowercase, and at most 72 characters, with no trailing period. The body says why, not what. A contract change takes `!` after the type or a `BREAKING CHANGE:` footer. This holds for lane and campaign commits too.
- When a tool from the `joshuarli` or `laputa-systems` namespaces fails or lacks an operation the task needs, read `~/.agents/instructions/owned-tools.md` and follow it: file nonblocking problems in that tool's repository and continue; repair a blocker there under its standing authorization, then resume the task.
- Never open issues, pull requests, comments or reviews in repositories outside `joshuarli` and `laputa-systems` without Joshua's explicit consent for that post; a general grant of authority is not consent. For a defect in a third-party project, follow the third-party section of `~/.agents/instructions/owned-tools.md`: fix it in a `laputa-systems` fork, consume the fork, and leave an upstream draft there.
- Reserve release builds for final verification, or when performance is the primary concern.

## Environment

macOS and Linux. For shell search always use `rg` (never `grep`/`egrep`/`grep -r`) and `fd` (never `find`/`ls -R`). Prefer harness-native search tools over shell when available; they are `rg`/`fd`-backed. Use `jaq` for all JSON and YAML work, in place of `jq` and `yq` (`jaq --from yaml` reads YAML, `--to yaml` writes it). Use `fastermod` for renames across a tree, in place of scripted `sed`/`perl` (see Renaming). Rust builds go through the `kache` rustc wrapper, and Linux musl targets link with `mold`.

## Shell commands

Write POSIX sh for shell commands and scripts. Never rely on zsh or bash extensions: unquoted-variable word splitting, arrays, `${=var}`, `[[`, or `setopt` are not portable. Prefer Python when a command is more than a few lines or needs conditionals, loops, or parsing. Do not invoke `zsh` or `bash` explicitly; the tool shell already runs zsh with `SH_WORD_SPLIT` for agents.

## Structured data

Use `jaq --from FORMAT` and `--to FORMAT` for XML, TOML, CSV, and TSV instead of a parser script; file extensions select the input format, and `--slurp` collects records into one array. XML nodes use `.t` for the tag, `.a` for attributes, and `.c` for children. CSV and TSV records are arrays, and a header is an ordinary first row. Each output array becomes one CSV or TSV row, TOML output needs an object at the root, and XML output uses jaq's XML node representation.

## Renaming

Use `fastermod` to rename text or symbols across a tree instead of scripted `sed`/`perl`. `--rename` is binding-aware and fails closed on unresolved references; `--ident` rewrites identifier tokens syntactically; `-S` adapts the replacement's casing to each match. On a non-TTY it previews diffs and writes nothing without `--apply`; `--check` exits 1 when edits are pending, and `--json` emits a machine-readable result. See `~/.agents/instructions/fastermod.md` for worked examples.

## Working files

- Proactive cleanup sweeps run only when the system disk has strictly less than 16 GiB available space. Respond to `agent-disk-pressure` notices with the `cleanup` skill; never poll with model tool calls. On a harness without a pressure hook, run `agent-disk-pressure notify` after the first necessary shell command in the same tool call, preserving that command's exit status; do likewise after an out-of-space failure. Recheck `agent-disk-pressure status` before deleting a batch; at >=16 GiB or an unknown reading, stop the sweep. Ordinary retirement of your completed lanes and explicitly requested cleanup remain part of the task. Workers relay pressure to their coordinator; they never broaden scope to clean.
- Put every worktree and scratch file under `.work/` at the root of the repo you work in, never `/tmp`, `$TMPDIR`, or `/var/folders` (`/tmp` is often RAM-backed on Linux machines, so large trees there cause OOM kills). Use `.work/wt/<name>` for worktrees and `.work/tmp` for scratch. Make sure `.work/` is ignored through `.git/info/exclude`, not a tracked file, before the first write. Point `TMPDIR` at `.work/tmp` for commands that spill large files.
- `.work/` is strictly disposable: assume the entire directory can be deleted. Never store durable plans, handoffs, resume state, or required results there. Commit project records under tracked paths such as `docs/`, and make the handoff available in the primary checkout outside `.work/` before finishing. A commit reachable only through a scratch worktree, or a final link into `.work/`, does not deliver a handoff. Preserve necessary conclusions and reproduction instructions in the durable record; scratch artifacts are optional, regenerable evidence.
- Disposable is not permission to delete live or unknown work. Preserve active consumers, leases, parked lanes and unique changes; never sweep `.work/` recursively. The coordinator retires its exact stopped worktree after integration proof, even when the harness has a removal hook.
- Clone and work on repositories under `~/repos`, never `~/d` or another directory; `~/usr` stays where it is.
