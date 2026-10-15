# Implement `/do`: outcome-driven workflows for `usr`

You are working in `joshuarli/usr`, normally checked out at `~/usr`.

**Implement this specification. Do not respond with another proposal or stop after writing a plan.** Build the skills, make the necessary integration changes, exercise them, inspect the result, and repair defects until the acceptance conditions are met or a concrete environmental or authorization blocker remains. Complete independent work before reporting a blocker. Never label unexecuted verification as passing.

## 1. Goal and limits

Give the owner one entrypoint, `/do`, that takes responsibility for an outcome and selects the smallest sufficient workflow over the skills already in this repository. Add a reusable way to create and maintain repository-local verification skills, so the workflow knows how to demonstrate behavior in each project.

The intended experience is:

```text
/do fix the duplicate notification on reconnect
/do add --json without changing the existing text output
/do investigate the startup regression; don't change code
/do implement USR-11
/do burn down the backlog
/do plan the search migration; don't implement it
/do execute docs/CAMPAIGN-SEARCH.md
/do reduce parser allocations without changing behavior
```

These are examples of the interface, not tasks to execute while implementing it. `/do` is the public name; document the actual native invocation syntax for each supported harness rather than pretending their command parsers are identical.

This is a compositional skill layer, not a software-factory runtime. Do not build a scheduler, daemon, database, task protocol, provider gateway, quota router, dashboard, general evaluation framework, or new agent harness. Do not import pstack. Do not replace the existing skill collection with rewritten copies of the same principles.

**Success means less owner choreography, not more mandatory process.** A trivial edit must remain trivial. Substantial work must retain scope, authorization, and acceptance through planning, delegation, verification, and follow-up.

## 2. Authority for this implementation

This prompt authorizes repository-local implementation, tests, documentation, and minimal edits to existing skill owners needed to integrate the design. It does not authorize installation into the real home directory, system changes, commits, pushes, PR creation, publication, deployments, or changes to model/provider/permission settings.

Work unattended on reversible implementation decisions. Read facts from the checkout instead of asking the owner. Preserve unrelated modifications and never reset, stash, overwrite, or clean the owner's work. Keep the result uncommitted. If delegation would require commits, use read-only delegates, disjoint patch handoffs, or direct implementation instead.

Follow the repository's current instructions. In particular, edit the tracked source tree rather than installed files in `~`; use POSIX `sh` and Python's standard library; do not run formatters. Put scratch repositories, temporary homes, worktrees, and test output under the repository's ignored `.work/`, not system temporary directories. Ensure the existing ignore convention is satisfied before writing there.

Do not run default `make`, `dl`, platform setup scripts, reset scripts, or home installation. Test installation behavior only through the existing safe scratch-target procedures. Do not change unrestricted harness settings or attempt to settle the unrelated push-approval RFC. Skill instructions are behavioral rules, not a new security boundary.

Local deterministic tests are authorized. A bounded live evaluation through an already available native coding harness is also authorized, using only its existing authentication and a disposable fixture checkout. Do not purchase credits, add credentials, switch to a separately billed API route, install a harness, or fall back to an unapproved model. Missing capability is a reportable limitation, not permission to improvise access.

## 3. Orient before editing

The planning review used `main` at `9498e6357e07b4148732646d3551908d29695212`. That is a navigation reference, not a required checkout. Work from the actual current tree and reconcile any intervening implementation rather than overwriting it.

Read:

- `AGENTS.md`, `docs/agent-setup.md`, `docs/development.md`, `docs/sync.md`, `docs/mdtool.md`, `Makefile`, and `.agents/skills/dotfiles-health/SKILL.md`.
- The canonical working contract at `dotfiles/base/.codex/AGENTS.md`, its existing consumers, and explicit-only metadata such as `dotfiles/base/.agents/skills/do-it/agents/openai.yaml`.
- `do-it`, `orchestrate` and its campaign reference, `campaign-plan`, `campaign-preflight` and its procedure, `campaign-winddown`, `todo`, `burn-down-the-backlog`, `root-cause`, `architect`, `reference-parity`, `make-it-fast`, `benchmark-checklist`, `test-audit`, `skill-eval`, and relevant documentation skills under `dotfiles/base/.agents/skills/`.
- `dotfiles/skills-check.sh`, the existing test conventions, and the relevant current TODO/RFC entries.

Inspect the actual skill inventory for existing equivalents of `/do` and verification generation before adding anything. Reuse or complete equivalents instead of creating synonyms. Learn the current link/allowlist arrangement for shared skills; do not add a duplicate installation path.

Run the narrow applicable baseline checks, time them, and distinguish pre-existing failures from your changes. Inspect what checks execute before running them: test fixtures must not accidentally mutate real home configuration or trigger network installation.

Upstream ideas are background, not dependencies or authority. Use the references at the end only when helpful. If harness syntax needs confirmation, inspect the installed version's help and current official documentation. Do not infer support from a generic skill standard.

## 4. Architecture and ownership

Start with this shape, adapting only to existing equivalent owners:

```text
dotfiles/base/.agents/skills/do/
    SKILL.md
    agents/openai.yaml
    references/playbooks.md

dotfiles/base/.agents/skills/create-verification-skill/
    SKILL.md
    agents/openai.yaml
    references/...                 # only if actually needed

.agents/skills/verify-usr/
    SKILL.md                       # or extend a genuinely equivalent local skill
    agents/openai.yaml
    scripts/...                    # only reusable, exercised helpers
```

Keep evaluation fixtures and checks beside the repository's existing test machinery, not in the runtime skill entrypoint. Select the smallest clear layout; this diagram is not an instruction to create empty directories.

`/do` owns task interpretation, workflow selection, scope continuity, stage composition, and completion. Existing leaf skills own their engineering methods. `orchestrate` alone owns delegation, models, effort, and worktree mechanics. Existing ticket/campaign skills own their file formats. The verification generator owns the repository-verification procedure shape; each project owns its concrete implementation.

Write compact entrypoints in the existing house style: a thesis, operational rules, steps, `**The test:**`, and `**Reply:**`. Keep each new global `SKILL.md` below the existing 8,000-byte warning threshold without deleting obligations. Put detailed workflows in a directly linked reference. Load only the selected workflow and relevant leaves; do not front-load the entire skill library.

Make `/do` and the generator explicit-only. Follow the checked-in convention of `disable-model-invocation: true` and `policy.allow_implicit_invocation: false` in `agents/openai.yaml`. Preserve any additional fields required by the actual checkout. Do not claim these flags have identical support in every harness.

Do not build a keyword classifier, YAML workflow DSL, or second machine-readable route registry. Routing is model judgment constrained by short playbooks. Tests should validate this design, not introduce a second implementation of its policy.

## 5. `/do` semantics

### Resolve the request, not an imagined larger project

`/do <task>` acts on that task and the applicable instructions. A bare `/do` continues one clearly agreed, unfinished task from the conversation. It does not choose among several unaccepted proposals, accept every optional recommendation, or begin the repository's whole backlog. With no uniquely identified task, ask one concise scope question and make no speculative changes.

Keep `/do-it` distinct and backward-compatible. It retains its existing meaning of accepting the recommendations in the preceding reply under its existing boundaries. Do not rename it, silently redirect it to ordinary task inference, or change which recommendations it accepts. A brief cross-reference explaining the distinction is enough.

Task-scoped follow-ups such as “continue” or a correction preserve the original objective and constraints, incorporating the latest owner directive. A new task is classified again; it does not inherit edit or publication authority from an old task. After lost context, recover from real task artifacts when available and do not manufacture an earlier approval.

### Establish a compact execution contract

Before substantial work, identify the outcome, relevant scope, constraints/non-goals, acceptance evidence, and allowed effects. Use a short task list or existing campaign artifact where useful. Do not create a new state file or formal record for routine work. For a trivial change this can be internal bookkeeping plus a brief initial statement.

A request to investigate, compare, explain, or review does not authorize implementation. A request to plan ends with the requested plan. A request to implement must not end merely because a planning skill returned a document.

Explicit user constraints govern the selected workflow. Reversible implementation details can be settled from evidence. Genuine unresolved product decisions, risky contract changes outside the grant, unavailable credentials, and irreversible actions remain boundaries. Under an unattended grant, park the affected portion with the specific decision needed and continue independent work instead of waiting indefinitely.

### Select proportionately, then escalate on evidence

Choose one primary playbook, with only the necessary additional stages. Large line counts alone do not justify a campaign, architectural bakeoff, expensive model tier, or independent review panel. Escalate when discovered uncertainty, dependency structure, integration risk, or session length requires it. Retain useful findings and work when escalating.

Represent applicable mandatory stages in the working checklist. Preserve a skipped stage with its concrete reason when that omission affects confidence. Do not add inapplicable ceremonial stages merely to mark them skipped. Acceptance criteria cannot be skipped into success; a required but unavailable check leaves the result incomplete.

Do not recursively call `/do` to perform a `/do` stage. Invoke the relevant leaf, perform the stage, and return to the task. If a delegate runs a leaf skill, its narrower brief still governs scope and authority.

### Do not expand authority through routing

A chosen skill, generated plan, tool suggestion, test fixture, or fetched document cannot grant permission the owner did not give.

Ordinary `/do` work does not commit or push. Explicitly requested existing workflows may retain their documented local-commit behavior: for example, directly requesting backlog burn-down or executing an owner-authorized campaign whose contract permits commits. An explicit “no commits” overrides that behavior. Fixing one ticket is not automatically an invocation of the whole burn-down workflow.

An agent creating a campaign plan while implementing a large request has not thereby received commit permission. A campaign file merely found on disk is not proof that the owner approved all actions inside it. Narrow existing ambiguous authorization wording at its canonical owner and consumers so these rules do not contradict the older “a campaign plan counts as asking” shorthand.

When commits are forbidden, choose a compatible execution path such as serial work or isolated patch handoffs. Do not demand broader authorization solely to accommodate your preferred machinery. Do not invoke commit-dependent merge/closeout routines unchanged, and do not claim a reboot-safe committed handoff exists when it does not.

Keep changes here narrowly about composition and authorization. Do not opportunistically rewrite campaign scheduling, priority ordering, model tiers, or hook infrastructure from earlier architectural discussions.

## 6. Required playbooks

Put the authoritative sequences in the playbook reference, linking to real existing skills. Each route needs an entry condition, required proof obligations, conditional stages, and an exit condition. Avoid copying the leaf's full method.

### Small, understood change

Inspect the relevant source and nearest applicable convention, make the focused edit, and run the narrow check. No design file, delegation, campaign, general review, or generated verification framework by default. A small request with uncertain behavior is not eligible for this shortcut merely because the eventual diff might be small.

### Defect repair

Establish the original failure and a usable feedback loop. Invoke `root-cause` when the cause is uncertain; use the known cause directly when already established by evidence. Repair the origin, preserve a regression check, and rerun the original reproduction plus relevant existing focused tests. Architecture work is conditional on a consequential design change, not simply crossing a function boundary. An unreproduced symptom cannot be reported fixed; distinguish a proven related defect from the unverified original report.

### Feature

Inspect the existing behavior and define observable acceptance before implementing. Use `architect` for consequential new boundaries, invariants, or structures; once invoked, follow its actual method rather than a diluted copy. Implement a complete vertical slice and applicable error cases. Exercise the user-facing surface or the library's public API, update affected docs, and finish only when the requested behavior is demonstrated.

### Refactor or migration

Identify the behavior and contracts that must remain invariant and the changes actually authorized. Establish appropriate baseline/parity checks, choose the target design when needed, migrate coherent units, verify callers, and delete obsolete paths once their replacement is proven. Do not preserve speculative compatibility layers. Do not turn a refactor into a product change.

### Performance

Use `make-it-fast` and `benchmark-checklist` as the owners. Establish correctness, a meaningful baseline, and comparable measurement conditions; test hypotheses; retain the change only when the result justifies it within other budgets. Follow the existing busy-host policy. Deferred timing evidence is not a measured improvement or a pass. Do not duplicate conflicting rules for medians/minima, gating, or resource readiness in `/do`.

### Investigation or review

Read relevant sources, conduct authorized read-only experiments, and produce an evidence-grounded answer or findings. A well-supported negative finding can complete the task. Do not automatically fix what was found or file/commit tickets unless requested or already authorized. Do not route a narrow or strictly read-only review into unmodified `ultrareview`, whose complete workflow also edits documentation; reuse relevant lenses within the requested boundary instead.

### Ticket or backlog

Read the selected ticket, linked decisions, and current implementation. Check whether it is already resolved or blocked. Route a single eligible ticket into its actual work type. Delete/close it only when its own acceptance is met and ticket mutation is authorized. Reuse `burn-down-the-backlog` only for the requested backlog scope, preserving its eligibility and invocation contract. Draft RFCs remain blocking decisions, not invitations to guess the owner's preference.

### Campaign and custom work

A named existing campaign is read and checked against actual branches, changes, prerequisites, and acceptance. Do not blindly restart it. A request only to plan stops after planning/preflight; a request to execute continues past a ready plan under the actual authorization. Use existing campaign mechanics and winddown when their preconditions apply.

Compose an unusual task from a small number of grounded stages rather than minting a permanent playbook for every novelty. A blocked portion does not prevent independent useful work, but “all remaining work parked” is not equivalent to delivering the requested outcome.

## 7. Delegation, verification, and completion

Delegate only when specification and inspection cost justify it, following `orchestrate`. A brief carries the outcome, relevant facts, writable boundaries, excluded work, acceptance, allowed effects, and learned failures. Do not duplicate provider/model settings in `/do`. Children cannot authorize their own commits, further scope, or external actions.

The parent owns integration and the final verdict. Inspect the actual diff and evidence, and exercise the relevant integrated result. Avoid wastefully rerunning identical checks on an unchanged artifact when trustworthy evidence is available, but invalidate affected evidence after edits or integration. Existing focused regression tests are legitimate worker checks, not only tests that the worker authored. Where current owner text forbids those, make a narrow, explicit correction rather than introducing contradictory `/do` guidance.

Use repository-local verification before inventing a new procedure. Compilation, mocked behavior, and unit checks are sufficient only for what they actually demonstrate. Choose the public behavior/surface relevant to the claim. Do not require browser automation for a library or an irrelevant end-to-end stack for a pure function.

Final task status is `done`, `partial`, or `blocked`:

- `done`: the requested deliverables and applicable acceptance obligations are satisfied.
- `partial`: useful requested work is completed, but a named deliverable or required check remains.
- `blocked`: no further authorized, useful progress is possible; name the concrete missing fact, access, decision, or environment.

Report changed behavior, decisive checks and results, remaining limitations, relevant contract changes, and commit/push state. Do not dump internal playbooks, cite every principle, repeat an agent roster, or present a plan as implementation. Stop when the task is complete; optional improvements are not an endless work queue.

## 8. Build the verification-skill generator

Implement `/create-verification-skill` as a reusable global skill, unless an equivalent existing owner can be completed. Invocation authorizes creating or updating verification instructions and narrowly necessary helpers in the target repository, not arbitrary product repair, dependencies, home installation, or external writes.

### Discover and reuse

Inspect the target's agent instructions, documented entrypoints, build/test commands, existing local skills, fixtures, runtime boundaries, and available drivers. Identify what a consumer actually uses: CLI/TUI, web/desktop UI, API/service, mobile target, or library interface. Reuse the project's existing harness before introducing a tool.

Find and extend an existing verification owner instead of generating a duplicate. Do not overwrite hand-maintained content blindly. For an unsupported environment or broken baseline outside scope, state the precise blocker. Do not fabricate successful launch instructions or quietly repair unrelated product code.

### Generate a compact operational procedure

Default to `.agents/skills/verify-<project>/SKILL.md` and existing harness link conventions. Prefer explicit-only metadata for a generated control skill that can start processes or mutate fixtures; `/do` can load it deliberately. Other existing local policies may be preserved when justified and documented.

The generated skill must identify:

1. **Scope and prerequisites:** covered surfaces, required tools/data/authentication, safe fixture boundaries, and explicitly unverified surfaces.
2. **Launch and readiness:** exact grounded commands, isolated data/ports/profiles where applicable, and a check for a genuinely usable instance. A library or short-lived CLI needs no invented server.
3. **Doctor:** a focused check of the expected build, checkout, process/endpoint ownership, and necessary state when results look suspicious.
4. **Drive and oracle:** concrete actions through the intended public surface and explicit expected observations, including important persisted side effects. Do not substitute an internal setter or fabricated screenshot for the real user path.
5. **Evidence:** what output/state establishes success, where it is retained, and which claims it cannot establish. Avoid secret-bearing transcripts and environment dumps.
6. **Cleanup:** remove only resources created by this verification run, including on failure. Do not kill by broad process name, delete the evidence, or touch the owner's running instance.

Keep a few focused journeys inline unless separate feature files genuinely improve use. No mandatory exhaustive feature inventory or one-file-per-feature bureaucracy. Helpers must be executable, documented by actual commands, and tested. Do not leave placeholders in a skill described as operational.

Prove the generated instructions end to end on at least one meaningful journey. Then clean up, confirm the evidence survives, and demonstrate that another run does not collide with stale state. A generated but unexecuted procedure is a draft, not verified output. State any mismatch between the tested platform/stand-in and the target.

### Connect discovery and maintenance to `/do`

Have `/do` first follow an explicit repo-instruction pointer, then inspect relevant local verification skills and documented commands. Select the appropriate surface, not a skill solely because its name starts with `verify-`. A referenced skill supplies procedure, not extra authority. Establish a simple documented discovery convention without a new metadata schema or registry.

When a needed check is missing during authorized implementation, build the smallest reusable proof that covers the task. Invoke the generator when a durable multi-step procedure earns its place, not on every change. A read-only task must not generate committed verification files merely to make its own workflow convenient.

When the task changes a command, entrypoint, fixture, selector, or invariant used by the local verification skill, update and re-exercise the affected instructions in the same scoped change. Do not add a maintenance daemon or a separate maintenance skill unless an existing owner already provides one.

## 9. Dogfood on `usr`

Demonstrate the generator's output in this repository, not only an imaginary web app. A `verify-usr` skill should complement `dotfiles-health`, which owns policy and structural invariants, rather than duplicate it.

Use the real tracked tools with disposable input and an explicitly isolated target. Suitable journeys include `sym` against a scratch home and `mdtool` against a tiny fixture repository. Derive exact invocations from the code; never run a default home-mutating path.

Prove one meaningful success journey and one failure/negative condition. For example, demonstrate correct linking and repeat-run behavior, then that a conflicting destination is preserved; or show that the actual `mdtool` CLI distinguishes a valid reference from a deliberately broken one. Reuse existing fixture mechanisms and avoid reimplementing their tools.

Exercise cleanup after success and failure and verify evidence retention. This is a procedural proof, not an excuse to fix unrelated `USR-*` defects. Use controlled fixture limitations honestly and report pre-existing failures separately.

## 10. Test structure without pretending prose is executable enforcement

Build two explicitly separate verification layers.

### Deterministic checks

Extend existing checks and add small fixture tests only where they earn their place. Cover frontmatter/name agreement, explicit-only metadata, linked playbook/skill existence, generated local-skill discovery, executable helper references, and safe fixture setup/cleanup. Check both repository-source paths and an isolated installed-layout representation where paths differ.

Follow real links in the new router/reference structure, not only one specially formatted table that happens to be checked today. Keep scope narrow; do not turn `skills-check.sh` into a universal Markdown parser. Use the existing `mdtool` where it already owns a check.

Test the tests: a broken skill reference, missing invocation flag, absent helper, deliberately wrong CLI outcome, or leaked fixture resource must fail the appropriate check. A known-good fixture must pass. Verify real filesystem/process/output observations for executable helpers rather than only searching their source for reassuring words.

Do not claim that grepping “do not push” proves authorization behavior, that matching a heading proves routing, or that a fake-worker test demonstrates a real model followed the instructions. Those are structural checks only. Do not build a deterministic keyword router merely to obtain green routing unit tests.

Keep the ordinary checks offline and cheap. Integrate them into the existing appropriate test target; no live model runs in default `make check` or lint.

### Behavioral scenario corpus and live evaluation

Add a small, readable corpus with fixtures, expected behavior, prohibited actions, and observable scoring criteria. Keep evaluator expectations out of the worker's task context. Include these cases, combining fixture implementations where sensible:

| Case | Required observation |
| --- | --- |
| Trivial edit | Focused diff/check; no campaign or unnecessary architecture/delegation. |
| Reproducible bug | Original failure observed, retained regression, post-fix pass. |
| Unreproduced report | No unsupported “fixed” claim or speculative production patch. |
| Feature with existing verifier | Existing verification reused; no duplicate framework. |
| Refactor | Intended observable behavior preserved; no unrequested product change. |
| Read-only investigation | Answer/findings; no tracked edits or ticket mutation. |
| Narrow read-only review | No `ultrareview` side-effect expansion. |
| Single ticket among others | Only selected scope addressed; unrelated tickets remain. |
| Draft RFC | Affected work remains blocked; approval is not invented. |
| Plan-only request | Plan produced; implementation does not start. |
| Implementation requiring planning | Continues after a ready plan without manufacturing commit authority. |
| Explicitly authorized campaign | Respects actual charter, existing state, and latest constraints. |
| Explicit no-commit backlog/campaign | No new commits, pushes, or permission laundering. |
| Bare `/do` | Continues an unambiguous task; asks once when ambiguous. |
| `/do-it` contrast | Accept-all semantics remain distinct. |
| Follow-up then new task | Constraints persist within the task, not as blanket authority afterward. |
| Stale/false worker evidence | Integrated artifact determines acceptance; false success rejected. |
| Deferred performance check | No measured win or `done` claim based on deferred evidence. |
| Stale verifier or unavailable driver | Precise limitation; no fabricated command, output, or success. |
| Generated verification | Real journey and negative condition, safe cleanup, retained evidence, repeatability. |

For dangerous-action probes, use fixtures with no real remotes, credentials, or production endpoints. Observe attempted actions where the harness exposes them; do not provide genuine publication capability merely to test whether the instructions restrain it. A tool denial proves the environment denied an action, not that the model obeyed.

Provide exact fixture setup and scoring commands. A small optional live-run helper is acceptable, but not a cross-provider adapter framework. Use native supported harness facilities; verify current flags. Record the actual harness/version/model, fixture, observed actions, artifacts, decisive checks, and verdict. Report unsupported observations as ungraded rather than inferred passes.

Run a bounded initial live smoke on one available configured harness: at least trivial edit, bug repair, read-only work, no-commit planning/implementation, and verification generation/reuse. Budget at most eight task executions initially, including up to three targeted reruns after defects are corrected. Evaluate a second harness only when already available and within that same budget. Do not install anything or silently spend through an API fallback.

If no native harness can be invoked, complete the corpus, deterministic checks, and an exact live-run procedure. A fresh delegate manually reading the skill can provide limited composition evidence, but is not a native discovery/invocation test. Report the live acceptance gap explicitly. Keep `skill-eval`'s existing observational-only contract unchanged; this new corpus serves a different purpose.

## 11. Execution sequence

**Ground and baseline.** Inspect the owners, authorization interactions, existing equivalents, and safe test paths. Identify known failures. Establish the scenario corpus and deterministic negative fixtures before declaring the new behavior.

**Ship the router.** Implement the entrypoint and concise playbooks. Preserve `/do-it`. Reconcile the narrowly relevant contradictions at their owners, including agent-authored-plan authorization and relevant focused worker checks. Test composition and references before growing the scope.

**Ship verification.** Implement the generator, discovery convention, maintenance behavior, and grounded local dogfood. Execute success/failure/repeatability journeys and fix unsafe cleanup or misleading claims.

**Evaluate and harden.** Run structural and fixture tests, then bounded live evaluation where available. Use a fresh reviewer for scope/authorization loopholes and another focused pass for excessive process, duplication, and missing verification. Where fresh reviewers are unavailable, state that limitation and perform the same artifact-based checks yourself. Triage every finding; do not accept review suggestions without evidence.

**Document and close.** Update the existing docs owners with invocation examples, `/do` versus `/do-it`, playbook overview, verifier discovery, maintenance, native-harness differences, and exact checks. Keep root agent instructions a small pointer, not another copy of the router. Re-run affected checks after the final edit.

Use focused checks during iteration. Existing commands to verify against the current checkout include:

```sh
sh dotfiles/skills-check.sh dotfiles/base/.agents/skills
sh dotfiles/skills-check.sh .agents/skills
python3 -I dotfiles/base/.local/bin/mdtool check --untracked --since HEAD
```

Also run the new focused fixture/evaluation checks and available linters on changed executable files. Do not let `--since HEAD` hide unchanged baseline failures: retain the initial baseline separately. Inspect broader checks for real-home/temp/network effects before a final integration run. Do not launch an installer to obtain a missing lint tool; record the limitation.

## 12. Acceptance and final handoff

The implementation is complete only when:

1. The explicit-only `do` skill is present in the shared source arrangement, resolves its real references, and has verified or honestly documented native invocation behavior.
2. Playbooks preserve requested intent, use existing owners, support a genuine fast path, and do not end implementation at planning.
3. `/do-it` retains its distinct meaning, and task continuation does not leak scope or authorization into unrelated work.
4. Routing, planning, delegates, and local verification cannot legitimately expand permission under the written contracts; conflicting canonical wording is reconciled without changing harness security settings.
5. The verification generator creates or updates a usable, minimal project-local procedure, and the `usr` dogfood has exercised real behavior safely.
6. Structural checks and executable fixture oracles pass, their intentional-negative tests fail as expected, and the scenario corpus covers the specified boundaries.
7. Available bounded live evaluation is reported with actual evidence. Any missing live coverage remains an explicit acceptance gap, not a structural-test “pass.”
8. Docs and commands match the final tree. There is no unrequested factory runtime, duplicated routing/model policy, unnecessary dependency, or routine-task paperwork.
9. No real-home installation, system mutation, commit, push, PR, or publication occurred. All created processes and disposable resources are accounted for; useful evidence remains available.

Do not close unrelated TODOs or mark this complete merely because the files exist. If an acceptance condition remains blocked, report `partial` with the exact missing proof after completing everything else possible.

The final handoff should state the files and user-visible behavior changed; a few realistic invocation examples; checks run with outcomes and timings; live coverage versus structural coverage; any compatibility or authorization changes; and the exact remaining blockers. State that the working tree is uncommitted and nothing was installed or pushed. Do not ask whether to implement the next phase: execute the phases above within the granted scope.

## Background references

The local checkout and applicable owner instructions are authoritative. These references explain the inspiration and packaging conventions, not additional implementation scope:

- Repository: https://github.com/joshuarli/usr
- Poteto Mode overview: https://flaviocopes.com/poteto-mode/
- Upstream router: https://github.com/cursor/plugins/blob/main/pstack/skills/poteto-mode/SKILL.md
- Upstream verification generator: https://github.com/cursor/plugins/blob/main/pstack/skills/create-verification-skill/SKILL.md
- Agent Skills format: https://agentskills.io/specification
- OpenAI skill documentation entrypoint: https://developers.openai.com/codex/skills/

Use original concise instructions tailored to `usr`. Do not copy upstream branding, permission grants, provider-specific orchestration, publishing defaults, or large prose sections.
