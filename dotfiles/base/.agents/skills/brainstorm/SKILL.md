---
name: brainstorm
description: "Use for /brainstorm [focus]: survey a repository's real state and surface the top evidence-grounded ideas for what to do next — new work, deferred fixes, or unstarted decided work. Skip implementation, audits (use ultrareview), ticket triage (use ultratriage), and generic idea generation without repo evidence."
disable-model-invocation: true
metadata:
  opencode/slash: "true"
  opencode/autoinvoke: "false"
---

# Brainstorm

Surface what the owner should do next when they are out of ideas. The output is a ranked shortlist grounded in the repository's own evidence, not a menu of plausible features. This is an ideation pass: change nothing in the repository.

## Rules

- **Survey before ideating.** Never propose from the outside in. Every idea in the shortlist must trace to something in the repository.
- **Cite evidence.** Each idea names its source: a file, commit, open ticket, RFC, campaign document, unchecked checklist item, benchmark, or doc limitation. No source, no idea.
- **Separate decided from undecided.** Work that is designed and approved but not started (an accepted RFC, a specced campaign, a parked milestone) is a legitimate top answer; present it as such, not as a novel thought. An attractive idea that contradicts a recorded decision is wrong, not bold.
- **Rank, don't enumerate.** Pick a single top recommendation and order the rest. Do not hand back eight peers and let the owner re-decide.
- **Honest zero.** If the survey turns up nothing worth doing, say so and show what was checked. Filler ideas disguised as ambition are a failure mode, not a service.
- **No implementation.** Do not file tickets, edit code, or start work. End by offering the next step (`todo` for filing, `ultratriage` for deciding, direct execution) and let the owner pick.

## Survey

Read the repository instructions first, then walk the cheap signals in order; stop when the picture is clear enough to rank, not when everything is read.

1. **Purpose and constraints.** Instructions, README, and architecture docs: what the project is for, what it refuses to be, and the invariants a good idea must respect.
2. **The backlog.** Open tickets, RFCs (draft, accepted-but-unimplemented, rejected), and campaign documents. Note decided-but-unstarted work separately.
3. **Recent history.** `git log` for the last weeks: finished workstreams suggest natural continuations; stalled ones suggest their blockers; reverted or red work suggests what not to retry.
4. **Known limits.** "Known gap", "Needs owner", unchecked checklists, documented limitations, stale cross-references, and TODO comments pointing at tickets that no longer exist.
5. **Health signals the repo already tracks.** Benchmark and budget docs, security tickets, coverage and policy notes, dashboards, and whatever `make` targets measure. A regression or overrun worth fixing tops most features.
6. **Owner-blocked work.** Items waiting on the owner (approvals, credentials, hosted-runner capacity, first releases) are not the agent's to do; name them as blocked, not as backlog.

## Generate

Walk lenses, not categories; skip any lens the evidence does not light up:

- **Finish what is decided** — specced campaigns, accepted designs, known gaps.
- **Close exposure** — security, integrity, and data-loss risks with concrete fixes recorded or implied by the code.
- **Scale pain** — costs that grow with registry/repo/fleet/audience size, with the growth knob named.
- **Remove toil** — repeated manual steps the repo already automates partway, or incidents caused by a missing check.
- **Visibility** — a decision the owner makes routinely with no chart, page, or number behind it.
- **Debt with interest** — stale docs, dead paths, and dependencies the end of their usefulness is evident.
- **New capability** — only with evidence that a user, the fleet, or an operation already wants it.

For each surviving candidate record: a one-line pitch, the evidence, what done would look like, rough effort (S/M/L), and risks or unknowns. Discard candidates without evidence now rather than at ranking time.

## Rank

Order by evidence of value weighed against cost and risk. Prefer ideas whose evidence includes an internal pain (a slow path, a repeated operation, an open exposure) over symmetrical speculation. State the shape of the shortlist when it matters: one big unstarted decision plus two small closes out is different from three comparable fixes, and the owner should see that.

## Report

Default shortlist size is 3 unless the user named another number. For each: the idea, why now (the evidence), rough effort, what done looks like, and the main risk or unknown. Then:

- **Honorable mentions**: one line each, with their missing evidence or blocker.
- **Wrong ideas** (when any arose): attractive-sounding candidates the evidence rejects, and why.
- **Survey coverage**: what was read and what was not, so the shortlist's blind spots are visible.
- Ask which, if any, to pursue; offer `todo` to file it, `ultratriage` to decide the broader backlog, or starting the work directly.
