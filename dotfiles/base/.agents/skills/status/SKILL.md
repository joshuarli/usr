---
name: status
description: "Use for /status [repo ...]: compile a read-only report of outcomes and remaining gaps, campaign status, active work, roadmap position, next steps and owner decisions. Skip normal task work and unrequested status chatter."
disable-model-invocation: true
metadata:
  opencode/autoinvoke: "false"
---

# Status

Produce a read-only operator status report that explains progress toward the owner's goal and the gaps that remain. The report is the deliverable; you change nothing to produce it.

## Scope

- `/status` reports the current repository. `/status <name>...` reports the named repositories; resolve a bare name against the directories under `~/repos`, and say so when a name matches nothing.
- Read-only. No edits, commits, resets, retires, deletions, or permission changes. Evidence comes from read-only inspection (git, filesystem, `ps`) only.
- When the owner's latest request in this session is unfinished, open the report with one line on it (what was asked, how it stands) before the sections below.

## Evidence to gather per repo

Run the checks; never infer health.

1. `git status --short --branch` — branch, dirty paths, ahead/behind against the upstream when one is configured.
2. `git log --oneline -5`; compare HEAD to the upstream.
3. `git worktree list --porcelain`. For each non-primary checkout, run `git cherry <base> <head>` to split integrated work from lanes holding unique commits (`+`). Branches fully merged or patch-equivalent need no action; mark unique-work lanes. State which base you used (origin's default branch, or local `master`/`main`).
4. `git branch --no-merged <base>`, plus `parked/**` branches — note which hold unique commits.
5. Campaign and roadmap records when present: `TODO.md`, `docs/ROADMAP.md`, `docs/TODO*.md`, roadmap notes under `docs/`, and tracked campaign/status files (for example `STATUS.md`, `PLAN.md`, `*-closeout.md`). `.work/` is disposable scratch, never the canonical handoff or resume record. Read the latest durable result summaries and acceptance matrix needed to explain the material gaps. Record open ticket IDs with their priorities, the roadmap's current milestone, and blockers/deferred items — one line each.
6. Hazards: dirty or unpinned submodules; stale or zero-byte lock files under `.work/` when it exists; live processes or runs referencing the repo (`ps`, read-only) when a campaign may be active; `.work/` size and `df -h /`.
7. If a claim cannot be established, write `unknown` — never guess.

## Explain the outcome and gaps

Lead with the practical answer the owner would otherwise have to ask for: what is working best, where the product still falls short, and what prevents calling the goal achieved. Use the stated objective and reference product when one exists; do not invent a comparison for an unrelated repository.

Use existing evidence. Do not run new benchmarks or widen into an audit to fill unknowns.

- Summarize up to five material gaps in plain language, ranked by impact. Explain the user-visible consequence and the remaining work or proof. Git cleanliness, commits and completed infrastructure support this assessment; they do not establish product success.
- Separate demonstrated weaknesses from missing evidence. Distinguish measured wins, parity, losses, inconclusive or invalid results, and unmeasured areas. Keep diagnostic observations, proposed mechanisms and accepted results distinct.
- For a performance comparison, cover the relevant application, CPU, memory/idle, storage, recovery, durability and reliability dimensions. Group unknowns when useful; do not manufacture a result for every dimension. State the strongest supported result and the largest remaining performance and qualification gaps.
- Explain why the overall goal remains open. Aggregate wins, proxy fixtures, short pilots or passing tests do not close unmet per-dimension or long-run gates. Include numbers only when comparable evidence supports their interpretation; expose limitations beside the claim.

## The standard form

Use exactly these sections, in this order. One per repo.

```
## <repo> — <branch> @ <short-sha> — <clean|dirty> — <synced | ahead n | behind n | no upstream>

Your last ask: <one line — only when a request is in flight>

### Outcome and gaps
<one or two sentences: strongest supported result and biggest remaining gap to the objective>
- <material weakness or evidence gap, its consequence, and what remains>
(up to five concise bullets when warranted; cite the supporting evidence)

### Campaign status
| Campaign / lane | State | Evidence | Next |
(one row per active or parked campaign; write "none active" when there is none)

### Active work
- Worktrees: <n> — <path: branch (integrated | parked | unique work | dirty)>
- Uncommitted: <paths, or none>
- Submodules: <clean | checked out != pinned | dirty>
- Live runs / locks: <none | names>
- .work: <size, or none>

### Roadmap position
- Milestone / phase: <from ROADMAP/TODO, or "none found">
- Open: <IDs with priorities, one line each — or none>
- Blocked / deferred: <IDs + blocker — or none>

### Next steps
1. <the single best next action, bound to the evidence>
2. <follow-on>
3. <optional>

### Needs the owner
- <pending decision, approval, or manual step — or "nothing">
```

For multiple repos, append:

```
## Overall
- <repo>: <one line>
- Disk: <df -h summary; call out any .work over 50G>
- Cross-repo: <unpushed work, uncommitted pins, shared lanes — or none>
```

## Rules

- Every line carries its evidence: the command output or the doc path. No evidence, no claim.
- One screen per repo. Prioritize the outcome and gaps; compress worktree inventory and unrelated backlog detail to make room. Link paths; do not paste logs into the report.
- A missing roadmap or TODO file means "none found", not "no work".
- Do not widen scope: no other repositories, no fixes, no cleanup, no merges. Route actionable findings to the matching skill when the owner asks (for example `cleanup` for stale worktrees, `todo` to file tickets, `brainstorm` or `ultrareview` for backlog calls).
- Never delete, retire, reset, or move anything to produce the report.

**The test:** the owner can tell how close the product is to the stated goal without asking a follow-up; every status line names its evidence, every owner decision sits under "Needs the owner", and nothing was changed to produce the report.

**Report:** the standard form above, one block per repo, then **Overall**.
