# Skills guide

Which meta skill to reach for, and why. Meta skills steer how the agent works: how it plans, delegates, reviews, and runs unattended. Language, stack, and engineering-method skills are left out. They live in `dotfiles/base/.agents/skills/`, and each one's `description` says when it applies.

**Auto** skills may be selected from an ordinary request. **Explicit** skills run only when you name them or their outcome (`/<name>`); the harness injects the body, and the model must not self-load one. A rejection there is the manual-only gate working. A requested workflow may reuse an explicit skill's documented procedure within its scope and authority. Read an explicit skill's references with normal file reads.

With no slash injection (Muse Code API, `muse serve`, `muse exec`), after an explicit request and a disabled-skill rejection, read `~/.agents/skills/<name>/SKILL.md` (project skills: `.agents/skills/`) directly instead of substituting a generic workflow. In every other harness and in interactive Muse Code, do not bypass the gate. Codex omits explicit-only skills from automatic selection; read one directly only when requested. Install and host details: [agent setup](docs/agent-setup.md).

## Default

You rarely need to name a skill. `do` loads on its own for work with real uncertainty, dependent steps, or consequential changes, and routes to the others.

| Skill | Mode | Use it to |
| --- | --- | --- |
| `do` | Auto | Run a substantial task end to end, keeping scope and authority fixed and checking the outcome with evidence. `/do <task>` forces it. |
| `orchestrate` | Auto | Split work across subagents to cut cost, isolate context, or parallelize. `do` calls it when delegation pays. |
| `architect` | Auto | Compare structurally different designs before a consequential, uncertain change. Skipped for routine edits. |

## Steer the agent

| Skill | Mode | Use it to |
| --- | --- | --- |
| `in-your-own-words` | Explicit | Make the agent restate what you want and why, before it starts. Use it when you suspect a misread. |
| `eli5` | Explicit | Give a short, simple, technically correct version of the topic, or of your last reply, without dumbing it down. |
| `self-contained-prompt` | Explicit | Draft a prompt another agent can follow without this conversation's context. |
| `be-ambitious` | Explicit | Raise the professional bar of an existing task using primary evidence, specific methods, and independent proof, without enlarging the assignment. |
| `yea` | Explicit | Approve everything in the agent's last reply: it continues, does every recommendation in full, and settles each open question as it recommended. Nothing the reply did not name is approved. |
| `hurry-up` | Explicit | Tell the agent to finish and cut verification. Run it with `/hurry-up`. |
| `sleep` | Explicit | Proceed unattended while you are asleep: keep working without stopping, decide within authority, park only owner-blocked work. |
| `resume-session` | Explicit | Continue a specific Codex, Claude, Muse, OpenCode, Pi, Command, Antigravity, DeepSeek, fx, or Devin session's unfinished work in this agent: `/resume-session <agent> <session-id>`. |
| `session-handoff` | Explicit | Export a redacted, portable brief from the current task or a named coding-agent session: `/session-handoff current` or `/session-handoff <agent> <session-id>`. |

## Review

These four overlap on purpose. They differ in what they touch and how wide they look.

| Skill | Mode | Touches files | Scope | Use it when |
| --- | --- | --- | --- | --- |
| `review` | Auto | No | The change you name: a diff, branch, or finished high-risk work | You want a verdict with evidence on any change, including one you did not write. |
| `double-take` | Explicit | Trivial fixes only | This session's last change or review, then the wider repo if you say yes | The agent just finished something and you want it to look again. It names the pattern, finds what still contradicts it and where the same defect recurs, and fixes the trivial ones. It then asks whether to search the rest of the repo for other places the change applies. |
| `debloat` | Explicit | Only what you confirm | A repo, path, or change | You want to know what to delete, inline, or merge: each mechanism's cost against what it buys. |
| `ultrareview` | Explicit | Docs, tickets, RFCs | One whole repository | A thorough audit that refreshes docs and files ranked findings in `TODO.md` and `docs/rfc/`. |

Rule of thumb:
- **Read a change** with `review`.
- **Re-check your own just-finished work, and spread the fix** with `double-take`. Answer its widening question yes to search the wider repo.
- **Cut weight** with `debloat`.
- **Audit everything** with `ultrareview`.

`review` never edits. Everything else in the table can.

## Decide the backlog

| Skill | Mode | Use it to |
| --- | --- | --- |
| `brainstorm [focus]` | Explicit | Survey a repository's real state and surface the top evidence-grounded ideas for what to do next, when you are out of ideas. |
| `ultratriage` | Explicit | Act as the owner: settle every open RFC and unresolved ticket, update docs and tickets, and report each decision with its reason and next action. |

Use `brainstorm` to find candidate work, `ultrareview` to find defects, `ultratriage` to decide the ticket queue, and `burn-down-the-backlog` to implement it. Each can run on its own. `brainstorm` proposes; only the owner picks what happens next. `ultratriage` ends open to feedback or the choice to start burn-down; it continues straight into implementation only when you have already asked for both. Accepted designs remain open until implemented, and prerequisite work lands before its dependents.

## Maintenance

| Skill | Mode | Use it to |
| --- | --- | --- |
| `pi-update` | Explicit | Update Pi, the SDK and Pi extensions in `pi-build`, publish a verified release, then bump the `usr` pin after proving offline setup. |
| `opencode-resync` | Explicit | Repoint OpenCode's native model after a free model is retired: pick a replacement covering all tier efforts, regenerate policy, and verify. |

## Verification

| Skill | Mode | Use it to |
| --- | --- | --- |
| `test-pyramid` | Explicit | Audit and improve a project's testing layers, smallest relevant correctness/performance/memory gates, host-aware measurements and concise reports. Also supports audit-only and campaign-planning requests. Full stays manual-only. |
| `bench-pyramid` | Explicit | Audit a project's benchmarks and profiling for representative workloads, metric coverage and observability, then add one full-suite entrypoint with a preflight and tiered selective runs. Full stays manual-only. |
| `refactor-benchmarks` | Auto | Restructure benchmarks around representative user workflows, realistic multi-tier fixtures, macro user journeys, and allocation tracking instead of synthetic micro-loops. |

## Campaigns

A campaign is a long, multi-lane effort run from a design doc. Use them in this order.

| Skill | Mode | Use it to |
| --- | --- | --- |
| `campaign-plan <goal>` | Explicit | Plan a campaign from a goal into `docs/roadmap.md`: survey, baseline, workstreams, and a command that proves each deliverable. |
| `campaign-preflight` | Explicit | Turn a draft campaign in `docs/roadmap.md` into a final plan an agent can run unattended. |
| `burn-down-the-backlog` | Explicit | Work the starting `TODO.md` queue through `orchestrate`, honoring prerequisites and priority, one commit per closed ticket, with unattended execution. |
| `deslop` | Explicit | Work one repository's `TODO-DESLOP.md` from the fleet deslop campaign: ground, diagnose, types, tests with coverage and mutation, dead code, findings, report. |
| `accelerate` | Auto | Push a running campaign to feature completion: count what is done, measure where wall time went, cut work that moves no feature toward done, fix the dominant cause, and land the next slice. |
| `campaign-winddown` | Explicit | Pause a running campaign cleanly: finish in-flight lanes, start nothing new, leave the handoff in `docs/roadmap.md` **Status**, ready for "resume the roadmap". |
| `cleanup` | Auto | Always runs a bounded sweep when the user invokes it explicitly, regardless of disk pressure; on automatic disk-pressure notices below 16 GiB free, reclaim only owned completed lanes and known stale scratch. |

## Land and maintain

Repo upkeep and getting work merged.

| Skill | Mode | Use it to |
| --- | --- | --- |
| `green` | Explicit | Get CI green for where you stand, with unattended execution: on a feature branch, bring its open PR to merge-ready (conflicts, bot comments, required CI); on the default branch, fix its CI. It never merges. |
| `upgrade` | Explicit | Bump dependencies and pins to the newest stable versions, then run focused checks. |
| `standardize [standard...] [path...]` | Explicit | Bring a repo or paths up to every applicable coding standard in `~/.agents/standards/`; a whole-repo run also does each standard's adoption work (tool pins, floors, stack migrations). |
| `docs-refresh` | Explicit | Bring docs up to date with the code and make them shorter. Edits docs and comments, never behavior. |
| `settle` | Explicit | Make the default branch the cutting edge: merge every open and partial branch, pull request and lane into it, push what remains, then prune merged local branches with `git-branch-consolidation --delete`. |
| `linux-capsule` | Explicit | Prove a fresh Linux host can set up the repo from scratch: run its bootstrap and full checks in a pristine container from a clean clone, and fix what breaks. |

## Keep the skills themselves honest

| Skill | Mode | Use it to |
| --- | --- | --- |
| `audit-jstack` | Explicit | Improve the agent system from evidence: audit instructions, judge from sessions whether each skill earns its place, and make repeated mistakes impossible (architecture, then types, then a lint, then a test, docs last). `/audit-jstack past 2h` reads recent sessions; `/audit-jstack <repo>` targets the mistakes agents repeat in that repo, for example after you correct the same one twice. |
| `create-verification-skill` | Explicit | Write or refresh a repo-local skill that checks a project's real user-facing behavior. `do` looks for one. |
| `todo` | Auto | Save work for later as a `TODO.md` ticket (P1 to P4) or an RFC. Ask for "save this as a todo". |

## Not listed

Skills for a language, stack, or engineering method are not in this index. Examples are `rust-hash`, `rust-cli-lexopt`, `root-cause`, and `make-it-fast`. Rules for how code must look are standards in `~/.agents/standards/`, not skills. Add a skill here only if it changes how the agent works rather than what it works on.
