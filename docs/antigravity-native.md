# Antigravity native Neon / Hydrogen tiers

Google AI Ultra, November 18, 2026. A top-level `agy` session delegates **exclusively** to native `invoke_subagent` with the tracked global `usr-*` agents. No Pi bridge, external coding harness or paid API fallback. Other harnesses keep their policies.

| Assignment | Intended model | Effort | Native agent | Custom-agent tier hint |
| --- | --- | --- | --- | --- |
| Main | `gemini-4-neon-high` | `high` | primary session | n/a |
| God | `gemini-4-neon-xhigh` | `xhigh` | primary session | n/a |
| scout | `gemini-4-hydrogen-low` | `low` | `usr-scout` | `flash` |
| mechanic | `gemini-4-hydrogen-low` | `low` | `usr-mechanic` | `flash` |
| worker | `gemini-4-hydrogen-high` | `high` | `usr-worker` | `flash` |
| expert | `gemini-4-neon-high` | `high` | `usr-expert` | `pro` |

The `god` label is a direct parent-session mode; it does not create a new bridge tier or a god subagent. Start `agy --model gemini-4-neon-high` for normal sessions, or explicitly `agy --model gemini-4-neon-xhigh` for the highest-effort parent. Run `agy models` to verify model availability with the authenticated Google AI Ultra account; inspect `/agents` for the custom agent roster.

## Per-agent model selection limitation

The [documented native agent schema](https://antigravity.google/docs/subagents?tab=cli) supports only `model: inherit`, `flash`, or `pro`; there are no documented per-agent `gemini-4-*` ID pins or effort fields. Thus `flash` and `pro` are **abstract hints, not hard model or effort pins**. The table expresses the desired routing, not verified child behavior. At the first invocation of each native agent, inspect the resolved child model and effort in the installed CLI. If a Hydrogen child resolves to Gemini 3.8 Flash (or another unapproved model), **block that lane** rather than silently accepting the fallback. Do not claim verified runtime tier compliance based only on the YAML file. When exact native pinning is documented, migrate after testing on a live host.

Gemini 3.8 (including Flash) and Gemini 4 Argon are retired for agy. Carbon is excluded from automated delegation and remains banned in the shared automatic model policy; `gemini-4-carbon-high` is an operator-only selection for unusual long-horizon challenges, requiring explicit owner direction. Google's [Neon model card](https://deepmind.google/models/model-cards/gemini-4-neon/) says Neon was adapted from Carbon, while [Antigravity's release announcement](https://antigravity.google/blog/gemini-4-neon-in-google-antigravity/) still identifies Carbon as particularly strong for deep long-running work. There is no evidence Carbon is strictly inferior in every task.

## Native orchestration

Give children explicit writable paths, a worktree when they will write, a decisive acceptance check and a stopping condition. Scouts are read-only. Mechanics perform narrow deterministic edits. Workers implement scoped deliverables. Experts independently review difficult architecture or correctness. The parent owns worktree isolation, review, rerun of decisive checks and integration; native subagents do not inherit the Pi bridge's admission enforcement or durable fallback accounting. No automatic downgrades on quota exhaustion.

The small `~/.gemini/config/rules/neon.md` rule tunes evidence-grounded use without pretending to replace the model's built-in instructions. The user may explicitly select Antigravity's Orchestrator mode, which pairs Neon planning with Hydrogen execution, but that mode is not an exact per-tier custom-agent pin.

After pulling, review `sh sync plan`, resolve any conflicts, then run `sh sync` and start a fresh agy session. Antigravity rewrites its own untracked `~/.gemini/antigravity-cli/settings.json`; do not commit or overwrite that state. Inspect actual native child model identity and effort before relying on each tier.
