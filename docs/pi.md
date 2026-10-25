# Pi

Pi uses the Google Gemini API, not Gemini CLI OAuth or OpenRouter. The parent and every orchestration tier select `google/gemini-3.8-flash`.

## Install and authenticate

Install Node.js 26.12.0+ and npm first. `make` syncs the profile and includes Pi in the normal `dl` tools. `sh dl pi` installs or updates only Pi, resolving the latest `@earendil-works/pi-coding-agent` release (1.4.0 when this profile was restored on 2026-10-24). It installs with lifecycle scripts disabled under `${XDG_DATA_HOME:-~/.local/share}/pi` and links `~/.local/bin/pi`. Existing unmanaged launchers or install directories are not overwritten.

The settings declare Nico Bailon's `pi-subagents` 0.82.0, the latest release checked on 2026-10-24, as `npm:pi-subagents@0.82.0`. Pi manages that package and its dependencies separately from the CLI. After reviewing `make plan` and syncing with `make`, reconcile the declared package without trusting the current project's configuration:

```sh
pi update --extensions --no-approve
pi --version
pi list
vault set GEMINI_API_KEY
vault GEMINI_API_KEY -- pi
```

`GEMINI_API_KEY` must be a Google AI Studio API key. An exported environment variable also works. The installer does not authenticate, make inference requests, or change `~/.pi/agent/auth.json`. Use an API project with the intended billing/quota policy: pinning a model does not itself guarantee free usage.

Use `sh dl pi` for CLI upgrades; the subagents version remains explicitly pinned in `dotfiles/base/.pi/agent/settings.json` until reviewed and updated there. Pi can write its own settings, so inspect tracked changes after using its configuration commands.

## Instructions and tiers

`~/.pi/agent/AGENTS.md` points to the canonical `~/.codex/AGENTS.md`; skills load from `~/.agents/skills`. Invoke shared skills with `/skill:<name>`, for example `/skill:orchestrate`. The five definitions under `~/.pi/agent/agents/` match the Pi column in the shared orchestration skill:

| Tier | Model | Thinking |
| --- | --- | --- |
| scout | `google/gemini-3.8-flash` | low |
| mechanic | `google/gemini-3.8-flash` | medium |
| worker | `google/gemini-3.8-flash` | high |
| expert | `google/gemini-3.8-flash` | high |
| god | `google/gemini-3.8-flash` | high |

`subagents.defaultModel` also covers unpinned built-in roles. The strict enforced `subagents.modelScope` rejects any other resolved provider/model, including per-run model overrides; `maxThinking` rejects efforts above high. There is no fallback to paid models or other providers. Expert and god are different assignments, not stronger models; god gets a fresh adversarial brief.

Scout has only `read`, `grep`, `find`, and `ls`. The other tiers additionally have `bash`, `edit`, and `write`. These explicit tool lists omit delegation tools; the parent owns all delegation and worktree lifecycle. Keep concurrency low when sharing a free API quota and report quota failures instead of starting retry storms.

`/subagents-models` displays the loaded role mapping. Reload Pi after changing definitions or settings. The user profile is not an immutable sandbox: trusted project settings and an operator's explicit model/config changes can override it. Do not add project overrides that weaken this profile. `enabledModels` narrows normal parent model selection; the strict enforcement described above applies to subagents.

## Restored history and state

The starting point was `dotfiles/base/.pi/agent/settings.json` at `0c9534f60c88b28210cbb3a6fbbdd2333b591b6c`. The dark theme, high-thinking default, quiet startup, hidden thinking, cache notices, disabled install telemetry, and always-trust preference are retained. The old OpenRouter default, generated changelog marker, and custom goal/cache extensions are not restored.

Unlike that historical configuration, `.pi/agent` is not a whole-directory `.sym-dir` link. Only tracked configuration and agent definitions are linked. Credentials, sessions, downloaded packages, and runtime state remain under the real home directory, outside the repository. `make uninstall` records the isolated CLI installation, not the entire `.pi` state directory. If an old whole-directory link still exists, preserve its state and resolve the conflict shown by `make plan` before syncing; the installer does not migrate or delete it.

`agent-sessions` and `agent-learn` index Pi transcripts (see [agent learning](agent-learning.md)). They are not yet part of `reset-agents`, and pi-subagents run artifacts are not read.

## Checks and upstream references

Run `python3 -I dotfiles/pi-test.py` for offline installer and profile checks (also included in `make check`). These use a scratch home under `.work/` and mock npm; they do not prove live provider access or run a real Pi/subagents session.

- [Pi installation](https://github.com/earendil-works/pi/tree/v1.4.0/packages/coding-agent)
- [Pi package configuration](https://github.com/earendil-works/pi/blob/v1.4.0/packages/coding-agent/docs/packages.md)
- [pi-subagents 0.82.0](https://github.com/nicobailon/pi-subagents/releases/tag/v0.82.0)
- [Subagent models and enforcement](https://github.com/nicobailon/pi-subagents/blob/v0.82.0/docs/models.md)
