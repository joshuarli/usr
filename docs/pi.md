# Pi

Pi runs on OpenCode Go through the OpenCode account already authenticated on this machine. The parent defaults to `opencode-go/muse-spark-1.3-contributor` at `high` thinking and every orchestration tier pins the same provider/model. Pi 1.4.0 ships the `opencode-go` provider in its built-in catalog, including that model: 1M context, 131k output tokens, the OpenAI Responses API, and thinking levels through `xhigh`. Billing is $0.10 per million input and $0.20 per million output tokens against the workspace's Go monthly allowance. The third-party `pi-opencode-provider` package is not required; it adds runtime model discovery but still requires its own login.

## Install and authenticate

Install Node.js 26.12.0+ and npm first. `sh sync` links the profile and includes Pi in the normal `dl` tools. `sh dl pi` installs or updates only Pi, resolving the latest `@earendil-works/pi-coding-agent` release (1.4.0 when this profile was updated on 2026-11-02). It installs with lifecycle scripts disabled under `${XDG_DATA_HOME:-~/.local/share}/pi` and links `~/.local/bin/pi`. Existing unmanaged launchers or install directories are not overwritten.

The settings declare Nico Bailon's `pi-subagents` 0.84.0, the latest release checked on 2026-10-29, as `npm:pi-subagents@0.84.0`. Pi manages that package and its dependencies separately from the CLI. After reviewing `sh sync plan` and syncing with `sh sync`, reconcile the declared package without trusting the current project's configuration:

```sh
pi update --extensions --no-approve
pi --version
pi list
```

Pi reads OpenCode credentials from `OPENCODE_API_KEY` or a stored credential in `~/.pi/agent/auth.json`. This profile reuses the existing OpenCode login instead of storing a second key. Put the following in `~/.pi/agent/auth.json`; the file is untracked and must stay private:

```json
{
  "opencode-go": {
    "type": "api_key",
    "key": "!opencode2 auth export opencode | jaq -r '.[] | select(.active) | .value.access'"
  }
}
```

Pi runs the command when it first needs the key and caches its standard output for the process lifetime. The command prints the active access token from `opencode2`'s credential store, so Pi shares the credential already used by `opencode2` rather than duplicating it. The token is an OAuth session credential and expires; OpenCode refreshes it as it is used. If Pi reports `credentials_not_configured` or an expired token, open `opencode2` once to refresh the session and retry. A Console personal API key exported as `OPENCODE_API_KEY` also works, but a stored `auth.json` credential takes precedence.

Verify the setup without relying on the default model resolution:

```sh
pi auth check --provider opencode-go --json
pi --list-models opencode-go
pi -p 'Reply exactly OK.'
```

Use `sh dl pi` for CLI upgrades; the subagents version remains explicitly pinned in `dotfiles/base/.pi/agent/settings.json` until reviewed and updated there. Pi can write its own settings, so inspect tracked changes after using its configuration commands.

## Instructions and tiers

`~/.pi/agent/AGENTS.md` points to the canonical `~/.codex/AGENTS.md`; skills load from `~/.agents/skills`. Invoke shared skills with `/skill:<name>`, for example `/skill:orchestrate`. The five definitions under `~/.pi/agent/agents/` match the Pi column in the shared orchestration skill:

| Tier | Model | Thinking |
| --- | --- | --- |
| scout | `opencode-go/muse-spark-1.3-contributor` | low |
| mechanic | `opencode-go/muse-spark-1.3-contributor` | medium |
| worker | `opencode-go/muse-spark-1.3-contributor` | high |
| expert | `opencode-go/muse-spark-1.3-contributor` | xhigh |
| god | `opencode-go/muse-spark-1.3-contributor` | xhigh |

The parent defaults to the same model at `high`. Pi's catalog maps `max` thinking to unsupported for this model, so `xhigh` is the ceiling and the settings reject higher requests with `maxThinking: xhigh`. `subagents.defaultModel` also covers unpinned built-in roles. The strict enforced `subagents.modelScope` rejects any other resolved provider/model, including per-run model overrides. There is no fallback to other providers. Expert and god are different assignments, not stronger models; god gets a fresh adversarial brief.

Scout has only `read`, `grep`, `find`, and `ls`. The other tiers additionally have `bash`, `edit`, and `write`. These explicit tool lists omit delegation tools; the parent owns all delegation and worktree lifecycle. OpenCode Go bills usage against per-model monthly dollar allowances, so keep concurrency conservative and report limit failures instead of starting retry storms.

`/subagents-models` displays the loaded role mapping. Reload Pi after changing definitions or settings. The user profile is not an immutable sandbox: trusted project settings and an operator's explicit model/config changes can override it. Do not add project overrides that weaken this profile.

## Restored history and state

The starting point was `dotfiles/base/.pi/agent/settings.json` at `0c9534f60c88b28210cbb3a6fbbdd2333b591b6c`. The dark theme, quiet startup, hidden thinking, cache notices, disabled install telemetry, and always-trust preference are retained. The former InferX Basic endpoint and its tracked `models.json` provider definition are removed; the built-in OpenCode Go catalog supplies the model metadata. The old OpenRouter default, generated changelog marker, and custom goal/cache extensions are not restored.

Unlike that historical configuration, `.pi/agent` is not a whole-directory `.sym-dir` link. Only tracked configuration and agent definitions are linked. Credentials, sessions, downloaded packages, and runtime state remain under the real home directory, outside the repository. `sh sync uninstall` records the isolated CLI installation, not the entire `.pi` state directory. If an old whole-directory link still exists, preserve its state and resolve the conflict shown by `sh sync plan` before syncing; the installer does not migrate or delete it.

`agent-sessions` and `agent-learn` index Pi transcripts (see `~/d/agent-memory/README.md`). They are not yet part of `reset-agents`, and pi-subagents run artifacts are not read.

## Git command guard

The shared profile syncs `~/.pi/agent/extensions/git-execution-guard.js`. For Pi `bash` tool calls that visibly invoke Git, it supplies noninteractive `GIT_EDITOR`, `GIT_SEQUENCE_EDITOR`, and `GIT_MERGE_AUTOEDIT` settings to avoid hanging on an editor, and rejects obvious `git --no-verify` hook bypass attempts. This is a convenience guard, **not a security boundary**: indirect shell commands and other agents are outside its scope. The Git pre-push hook remains the independent push control. Check the behavior offline with `node dotfiles/pi-git-guard-test.mjs`.

## Checks and upstream references

Run `python3 -I dotfiles/pi-test.py` for offline installer and profile checks (also included in `sh sync check`). These use a scratch home under `.work/` and mock npm; they validate the static provider/model/routing contract but do not prove live provider access or run a real Pi/subagents session. The `pi auth check` and short prompt above exercise the stored credential without changing the tracked profile. If the endpoint rejects tool calls or streaming, treat the integration as blocked, not permission to fall back.

- [OpenCode Go](https://opencode.ai/v2/docs/console/go)
- [OpenCode Go endpoints and Pi setup](https://opencode.ai/v2/docs/console/harnesses/pi/)
- [Pi custom models configuration](https://pi.dev/docs/latest/models-configuration)
- [Pi installation](https://github.com/earendil-works/pi/tree/v1.4.0/packages/coding-agent)
- [Pi package configuration](https://github.com/earendil-works/pi/blob/v1.4.0/packages/coding-agent/docs/packages.md)
- [pi-subagents 0.84.0](https://github.com/nicobailon/pi-subagents/releases/tag/v0.84.0)
- [Subagent models and enforcement](https://github.com/nicobailon/pi-subagents/blob/v0.84.0/docs/models.md)
- [pi-opencode-provider](https://pi.dev/packages/pi-opencode-provider) (optional runtime discovery; not used here)
