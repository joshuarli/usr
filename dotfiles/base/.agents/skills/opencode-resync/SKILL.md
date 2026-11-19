---
name: opencode-resync
description: "Use for /opencode-resync to repoint OpenCode's native model after a free model is retired: choose a replacement covering all four tier efforts, update the policy source and top-level config, regenerate projections, and verify. Skip when no model ID changed."
disable-model-invocation: true
metadata:
  opencode/autoinvoke: "false"
---

# OpenCode resync

Repoint the OpenCode native model when a free model is retired or replaced. Explicit-only: a dead model ID breaks every tier agent, and guessing a replacement silently degrades the lane.

## Constraints

- The OpenCode native path never uses `pi-subagent-bridge`. Scout, mechanic, worker and expert run as native OpenCode subagents on the official client; free Zen models reject headless SDK traffic with `429 FreeUsageLimitError`. Do not route through the bridge or spoof the client's `User-Agent` to work around it.
- One model serves all four tiers, differentiated by effort only. The replacement must support `low`, `medium`, `high` and `max`. Today the free models covering all four are `opencode/tidepool-alpha-free`, `opencode/flint-40b-free` and `opencode/beam-free`. A model missing one effort blocks that tier; never substitute a different effort silently.
- Prefer the newest stable free model that covers every effort. If the newest candidate is an alpha or preview, say so and name the stable fallback before choosing it.
- `opencode/` (Zen) is the official-client-only lane; `opencode-go/` is the headless-capable lane used by the bridge. Do not mix them.

## Procedure

1. List the live catalog with `opencode models` and confirm status and effort variants for each `opencode/*-free` candidate. Drop deprecated or retired entries; keep only models covering all four efforts.
2. Change `OPENCODE_NATIVE.model` in `tools/pi-subagent-bridge/src/policy.ts`. Leave `efforts` unchanged unless a tier's effort is no longer supported.
3. Change the root `"model"` in `dotfiles/base/.config/opencode/opencode.json` by hand. `make generate` rewrites only `agents.<tier>.model`, never the root field.
4. Run `make generate` and `make subagent-visualization`. They refresh `policy.generated.json`, the four agent pins, the generated policy blocks in `orchestrate`, `AGENTS.md` and lean instructions, and `docs/subagents.md`. Keep derived prose in generators such as `tools/policy/subagent-visualization.ts` tied to `POLICY.opencode`; never paste a literal model ID into generated output.
5. Leave historical prose alone. `docs/pi.md`'s "Why Zen is not a pin" names the model that was once pinned to establish the headless-429 finding, and `docs/command-code-delegation.md` links the Command Code native scout model. Neither is an OpenCode native pin.
6. Review the generated diff and run `rg <old-model>`; no stale ID may remain in active config or generated files. Update the candidate list in this skill when the free lineup changes.
7. Commit the change. `sh sync plan` previews home sync; do not run `sh sync` unless asked.

## Verification

- `make check-generated`
- `node --test tools/policy/generate.test.ts`
- `node tools/skills/skills.ts check` and `node tools/skills/skills.ts check --root .agents/skills`, plus `python3 -I tools/skills/test_usage.py` and `python3 -I dotfiles/skills-campaign-test.py` when this skill's metadata or index entry changed
- `python3 -I dotfiles/orchestrate-test.py`
- `python3 -I dotfiles/base/.local/bin/mdtool check --untracked` on changed Markdown
- Live proof needs a fresh OpenCode session: confirm `/model` shows the new ID and that each native tier agent reports the expected `model#effort`. A catalog entry alone is not proof the lane loads.

**Report:** name the old and new model, why the new one covers every tier effort, the rejected alternatives, checks and results, any stale reference deliberately kept as historical, and whether live OpenCode proof was performed.
