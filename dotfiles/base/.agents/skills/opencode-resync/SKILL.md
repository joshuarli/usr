---
name: opencode-resync
description: "Use for /opencode-resync to repoint OpenCode's native model after a free model is retired: verify the replacement's exposed efforts, update the policy source and top-level config, regenerate projections, and verify. Skip when no model ID changed."
disable-model-invocation: true
metadata:
  opencode/autoinvoke: "false"
---

# OpenCode resync

Repoint the OpenCode native model when a free model is retired or replaced. Explicit-only: a dead model ID breaks every tier agent, and guessing a replacement silently degrades the lane.

## Constraints

- The OpenCode native path never uses `pi-subagent-bridge`. Scout, mechanic, worker and expert run as native OpenCode subagents on the official client; free Zen models reject headless SDK traffic with `429 FreeUsageLimitError`. Do not route through the bridge or spoof the client's `User-Agent` to work around it.
- One model serves all four tiers, differentiated only by effort. Request only variants the model actually exposes: an unsupported effort silently falls back to the model default in OpenCode, which is a misconfiguration, not a tier. `opencode/hy4-flash-free` exposes `none` and `high`; all four tiers use `high` and the four-step ladder deliberately collapses. Its `none` variant is not in the policy `Effort` type and cannot be assigned without a contract change.
- Rejected free models: `opencode/tidepool-alpha-free` (alpha, unproven), `opencode/beam-free` and `opencode/flint-40b-free` (poor quality in review). `opencode/deepseek-v4.1-flash-free` exposes `low`/`high`/`max` but not `medium`; it is an alternative if an `expert#max` lane is required. Never pick by release date or name alone.
- `opencode/` (Zen) is the official-client-only lane; `opencode-go/` is the headless-capable lane used by the bridge. Do not mix them.

## Procedure

1. List the live catalog with `opencode models` and confirm status and effort variants for each `opencode/*-free` candidate. Drop deprecated or retired entries, then check repo evidence for quality (existing pins and benchmark notes) before comparing by capability.
2. Change `OPENCODE_NATIVE.model` in `tools/pi-subagent-bridge/src/policy.ts`. Leave `efforts` unchanged unless a tier's effort is no longer supported.
3. Change the root `"model"` in `dotfiles/base/.config/opencode/opencode.json` by hand. `make generate` rewrites only `agents.<tier>.model`, never the root field.
4. Run `make generate` and `make subagent-visualization`. They refresh `policy.generated.json`, the four agent pins, the generated policy blocks in `orchestrate`, `AGENTS.md` and lean instructions, and `docs/subagents.html`. Keep derived prose in generators such as `tools/policy/subagent-visualization.ts` tied to `POLICY.opencode`; never paste a literal model ID into generated output.
5. Leave historical prose alone. `docs/pi.md`'s "Why Zen is not a pin" names the model that was once pinned to establish the headless-429 finding, and does not establish the current OpenCode native pin.
6. Review the generated diff and run `rg <old-model>`; no stale ID may remain in active config or generated files. Update the candidate list in this skill when the free lineup changes.
7. Commit the change. `sh sync plan` previews home sync; do not run `sh sync` unless asked.

## Verification

- `make check-generated`
- `node --test tools/policy/generate.test.ts`
- `node tools/skills/skills.ts check` and `node tools/skills/skills.ts check --root .agents/skills`, plus `python3 -I tools/skills/test_usage.py` and `python3 -I dotfiles/skills-campaign-test.py` when this skill's metadata or index entry changed
- `python3 -I dotfiles/orchestrate-test.py`
- `python3 -I dotfiles/base/.local/bin/mdtool check --untracked` on changed Markdown
- Live proof needs a fresh OpenCode session: confirm `/model` shows the new ID and that each native tier agent reports the expected `model#effort`. A catalog entry alone is not proof the lane loads.

**Report:** name the old and new model, which effort variants the model exposes and how tiers map onto them, the rejected alternatives and the evidence behind the choice, checks and results, any stale reference deliberately kept as historical, and whether live OpenCode proof was performed.
