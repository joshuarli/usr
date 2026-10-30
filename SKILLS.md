# Skills guide

Which meta skill to reach for, and why. Meta skills steer how the agent works: how it plans, delegates, reviews, and runs unattended. Language, stack, and engineering-method skills are left out. They live in `dotfiles/base/.agents/skills/`, and each one's `description` says when it applies.

Opt-in project retrieval and review metrics live outside skill routing. See [agent learning](docs/agent-learning.md).

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
| `yea` | Explicit | Accept every recommendation from the agent's last reply and have it do all of them in full, not the smallest version. |
| `hurry-up` | Explicit | Tell the agent to finish and cut verification. Run it with `/hurry-up`. |
| `sleep` | Explicit | Proceed unattended while you are asleep: keep working without stopping, decide within authority, park only owner-blocked work. |
| `resume-session` | Explicit | Continue a specific Codex, Claude, Muse, Grok, OpenCode, Pi, Command, Antigravity, DeepSeek, or fx session's unfinished work in this agent: `/resume-session <agent> <session-id>`. |
| `session-handoff` | Explicit | Export a redacted, portable brief from the current task or a named coding-agent session: `/session-handoff current` or `/session-handoff <agent> <session-id>`. |
| `correct` | Explicit | When you correct the same mistake twice: find the repeated mistakes and make each one impossible (architecture, then types, then a lint, then a test, docs last). |

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
| `ultratriage` | Explicit | Act as the owner: settle every open RFC and unresolved ticket, update docs and tickets, and report each decision with its reason and next action. |

Use `ultrareview` to find the work, `ultratriage` to decide it, and `burn-down-the-backlog` to implement it. Each can run on its own. `ultratriage` ends open to feedback or the choice to start burn-down; it continues straight into implementation only when you have already asked for both. Accepted designs remain open until implemented, and prerequisite work lands before its dependents.

## Verification

| Skill | Mode | Use it to |
| --- | --- | --- |
| `test-pyramid` | Explicit | Audit and improve a project's testing layers, smallest relevant correctness/performance/memory gates, host-aware measurements and concise reports. Also supports audit-only and campaign-planning requests. Full stays manual-only. |

## Campaigns

A campaign is a long, multi-lane effort run from a design doc. Use them in this order.

| Skill | Mode | Use it to |
| --- | --- | --- |
| `campaign-plan <goal>` | Explicit | Plan a campaign from a goal: survey, baseline, workstreams, and a command that proves each deliverable. |
| `campaign-preflight` | Explicit | Turn a draft campaign doc into a final plan an agent can run unattended. |
| `burn-down-the-backlog` | Explicit | Work the starting `TODO.md` queue through `orchestrate`, honoring prerequisites and priority, one commit per closed ticket, with unattended execution. |
| `accelerate` | Auto | Speed up a running campaign: measure where wall time went, then fix that one cause and land the next slice. |
| `campaign-winddown` | Explicit | Pause a running campaign cleanly: finish in-flight lanes, start nothing new, leave a handoff that survives a reboot. |
| `cleanup` | Auto | Remove campaign worktrees once their work is confirmed integrated. |

## Land and maintain

Repo upkeep and getting work merged.

| Skill | Mode | Use it to |
| --- | --- | --- |
| `pr-ready` | Explicit | Bring one open PR toward merge-ready with unattended execution: resolve conflicts, judge bot comments, reply on GitHub, and check required CI. It never merges. |
| `upgrade` | Explicit | Bump dependencies and pins to the newest stable versions, then run focused checks. |
| `docs-refresh` | Explicit | Bring docs up to date with the code and make them shorter. Edits docs and comments, never behavior. |
| `settle` | Explicit | Before moving to another computer: find unmerged and local-only work and separate what must travel from what regenerates. |

## Keep the skills themselves honest

| Skill | Mode | Use it to |
| --- | --- | --- |
| `skill-eval` | Explicit | Judge from real sessions whether each skill earns its place: keep, retune, demote, fold, or delete. |
| `create-verification-skill` | Explicit | Write or refresh a repo-local skill that checks a project's real user-facing behavior. `do` looks for one. |
| `todo` | Auto | Save work for later as a `TODO.md` ticket (P1 to P4) or an RFC. Ask for "save this as a todo". |

## Not listed

Skills for a language, stack, or engineering method are not in this index. Examples are `refactor-ts`, `rust-hash`, `rust-cli-lexopt`, `durable-state`, `error-model`, `root-cause`, and `make-it-fast`. Add a skill here only if it changes how the agent works rather than what it works on.
