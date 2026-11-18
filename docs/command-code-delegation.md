# Command Code native delegation

Top-level `cmd` sessions use the built-in `agent` tool and five tracked
`usr-*` agents under `dotfiles/base/.commandcode/agents/`, installed as
individual links by `sh sync`. They never route scout/mechanic/worker
through `pi-subagent-bridge`. Command Code remains a leaf executor in the
bridge for other parent harnesses.

| Role | Agent | Model | Effort |
| --- | --- | --- | --- |
| Scout | `usr-scout` | `thinkingmachines/inkling-2-small:free` | model default |
| Mechanic | `usr-mechanic` | `tencent/hy4-flash` | high |
| Worker | `usr-worker` | `deepseek/deepseek-v4.1-flash` | high |
| Worker pilot (explicit only) | `usr-worker-hy4` | `tencent/hy4` | medium |
| Expert | `usr-expert` | `tencent/hy4` | high |

The parent session stays on DeepSeek V4.1 Flash at max effort. Scout is
read-only. All native children are terminal (cannot spawn subagents).
Agent tools and maximum turns are defined in their authored frontmatter.

## Economics and evidence (November 18, 2026)

On GOAT, DeepSeek V4.1 Flash has $100 of model-specific monthly credits,
HY4 has $20, and HY4 Flash has $15. Inkling 2 Small Free is a promotional
200-requests/day offer, not a permanent entitlement. These are
model-specific credits with additional plan-wide limits.

Off-peak rates per million tokens (input/output/cache read):
- DeepSeek V4.1 Flash: $0.15 / $0.60 / $0.003; peak rates double on weekday windows
- Tencent HY4: $0.834 / $2.501 / $0.042
- Tencent HY4 Flash: $0.07 / $0.281 / $0.003

HY4 is 14 times more expensive on cache reads than DeepSeek off-peak, with
one fifth of its monthly GOAT allowance. Tencent-reported coding benchmarks
are mixed: DeepSWE v1.1 HY4 74.9 vs DeepSeek 73.8, SWE-Marathon v1.1
43.8 vs 46.3, Terminal-Bench 4.0 44.4 vs 40.0. These are not a
controlled Command Code comparison. Thus DeepSeek remains the default
worker and HY4-medium stays an explicit A/B pilot.

Sources:
- https://commandcode.ai/docs/plans/goat
- https://commandcode.ai/docs/agents
- https://commandcode.ai/models/hy4
- https://commandcode.ai/models/hy4-flash
- https://commandcode.ai/models/inkling-2-small-free
- https://www.tencent.com/tencent-launches-hy4-joining-the-ranks-of-the-worlds-leading-open-source-ai-models/

## Qualification and promotion

1. On the target host run `sh sync plan` and `sh sync`. Check
   `cmd --list-models` and `/agents`; verify that all native agents
   load and that the effective model and effort in a delegated tool-call
   match the pin. The `/model` picker lists the model-supported
   reasoning levels. Unsupported `reasoningEffort` silently falls
   back to model default, so mere profile parsing does not qualify a lane.
2. The native `agent` tool permits a per-call model override that beats
   frontmatter; the pin is not a security boundary. Do not override
   tier models in ordinary delegation. Do not silently substitute models
   or effort levels on quota exhaustion.
3. The parent must isolate writers in scoped worktrees, assign disjoint
   paths to parallel writers, specify proof and stop conditions, and
   independently review diff, untracked files, and relevant tests.
   Native children do not get the bridge's admission lease or Git
   scope containment. Optional `scope-check --register` / `--lane`
   checks Git scope, not ignored files or host writes.
4. Compare `usr-worker` versus `usr-worker-hy4` on 8–12 identical
   reproducible tasks across bugs, features and terminal workflows.
   Use separate clean worktrees, matching harness revisions/tools,
   randomized order, unchanged acceptance tests and blinded reviews.
   Track accepted results, defects, elapsed time, output/cache tokens
   and actual credits **per accepted change**.
5. Promote HY4-medium only on demonstrated accepted-work gain that
   justifies the higher bill and limited monthly allowance. Otherwise
   keep DeepSeek default and use HY4 for explicit exceptional cases.

No live signed-in Command Code dispatch, paid quota check, or effective-effort
check was performed during this policy change.
