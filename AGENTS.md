# Dotfiles (`~/usr`)

This repo is the source of truth for my home directory, plus my personal scripts and machine setup. Edit the repo, never `~`. Global agent instructions live in `dotfiles/base/.codex/AGENTS.md`; this file covers only work on this repo and is not installed anywhere.

## Layout

| Path | What it is |
| --- | --- |
| `dotfiles/base/` | Mirror of `$HOME`. `make` installs it. Holds shell/editor/terminal config under `.config/`, plus `.ssh`, `.cargo`, and the agent harness config (`.claude`, `.codex`, `.pi`, `.agents`). |
| `dotfiles/sym` | POSIX `sh` installer. Tests: `dotfiles/sym-test.sh`. Skill invariants: `dotfiles/skills-check.sh`. |
| `bin/` | My scripts, on `PATH`. Also holds downloaded binaries (`fd`, `rg`, `gh`, `ish`, ...), which are git-ignored. |
| `dl` | Downloads those binaries from GitHub releases into `bin/`, ad-hoc codesigns them, and installs the `mactop` app and LaunchAgent. |
| `macos/` | One-off macOS setup: `Brewfile`, `macos-lean.py` (disables services, needs sudo), Touch ID sudo, unbound DNS. |
| `.agents/skills/` | Skills for this repo only (`dotfiles-health`). `.claude/skills` links to it. |
| `skills` | Convenience link to the global skills, `dotfiles/base/.agents/skills`. |

## How files reach `~`

`sym` has three modes. Know which one a path uses before editing it.

- **Symlink (default):** each tracked file becomes a link into this repo, so editing either side edits the repo.
- **`.sym-dir` marker:** the whole directory is linked. Only `.pi/agent` does this, so its runtime state (`auth.json`, `sessions/`, `models-store.json`) physically lives in the repo directory and is kept out by `.gitignore`. Never stage it.
- **Synced copies:** `.agents/skills` and `.claude/agents` are real files on both sides, reconciled both ways, because those harnesses do not follow symlinks there. Deletions do not propagate.

## Commands

- `make check`: `sym` tests and skill checks (about 25 s). Run it after touching `sym`, skills, or agent definitions.
- `make plan`: dry run of the sync into `$HOME`. Read it before syncing; `OVERWRITE` and `DISCARD` lines mean content in `~` is about to be lost.
- `make`: sync into `$HOME`. This mutates the real home directory, so only run it when asked.
- Experiment with `sh dotfiles/sym -t <tmpdir> dotfiles/base`; its default target is `$HOME`.

## Agent configuration

- **Instructions:** `dotfiles/base/.codex/AGENTS.md` is the single copy. `.claude`, `.pi/agent`, and `.config/opencode` link to it, so edit that file and never the links.
- **Skills and subagents:** global skills are in `dotfiles/base/.agents/skills/`, Claude subagents in `dotfiles/base/.claude/agents/`. A skill the model must not trigger on its own is marked `disable-model-invocation: true` plus `agents/openai.yaml`; `skills-check.sh` enforces the pairing.
- **Enforced rules:** "never push" and "no formatters" are mirrored as deny rules in `.claude/settings.json` and prefix rules in `.codex/rules/default.rules`. A new hard rule gets its enforcement in the same change.
- **Codex:** `config.toml` (mode 0600, lists trusted projects) and `or.config.toml` (OpenRouter, used by `bin/codex-or`).
- **Skills to use:** `dotfiles-health` before finishing any change to the above. `ultrareview` for a whole-repo review and docs refresh, `review` for the current branch or task, `campaign-preflight` to make a campaign design doc executable unattended.

## Scripts and binaries

- `git ls-files bin` shows what is mine; the rest of `bin/` is ignored binaries. Do not `cat` or `rg` them. Add a new tool to `bin/.gitignore` before dropping its binary there.
- Four tracked links in `bin/` (`su-exec`, `wol`, `yt-dlp`, `zstd`) point at paths outside this repo and are dangling on a fresh machine.
- `claude-or` and `claude-ds` start Claude Code against OpenRouter or DeepSeek with `--dangerously-skip-permissions`, taking the key from `vault`. `codex-or` runs Codex with its `or` profile.
- `mdl`, `mpdl`, and `vdl` wrap `yt-dlp` through `uvx`.
- `reset-claude` and `reset-codex` delete everything in `~/.claude` and `~/.codex` except an allowlist. `reset-claude` keeps `AGENTS.md`, `agents`, `settings.json`, and `skills`; `reset-codex` keeps `AGENTS.md`, `config.toml`, `or.config.toml`, and `rules`. Do not run either unprompted.
- Do not run `dl`, `macos/*`, or `setup-*` without being asked. They download, codesign, install system services, or need sudo.

## Conventions

- Scripts are `#!/bin/sh` or `dash` and stay POSIX. `sym` must work under macOS `/bin/sh` (bash 3.2) and dash. Check scripts with `shellcheck -s sh`. Python scripts use only the standard library.
- Fix a `sym` bug with a failing numbered test in `sym-test.sh` first.
- My interactive shell is `ish` (`bin/ish`, config in `.config/ish`), not bash or zsh.
- Leave commits to me. Never push.
