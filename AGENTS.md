# Dotfiles (`~/usr`)

This repo is the source of truth for my home directory, plus my personal scripts and machine setup. Edit the repo, never `~`. Global agent instructions live in `dotfiles/base/.codex/AGENTS.md`; this file covers only work on this repo and is not installed anywhere.

## Layout

| Path | What it is |
| --- | --- |
| `dotfiles/base/` | Layer that applies on every OS: mirror of `$HOME` with config under `.config/`, `.ssh`, `.cargo`, `.local/bin` scripts, and the agent harness config (`.claude`, `.codex`, `.pi`, `.agents`). |
| `dotfiles/darwin/`, `dotfiles/linux/` | Layers that apply on that OS only. Same shape as `base`. |
| `dotfiles/sym` | POSIX `sh` installer. Tests: `dotfiles/sym-test.sh`. Skill invariants: `dotfiles/skills-check.sh`. |
| `bin` | Link to `~/.local/bin`, where scripts and downloaded binaries (`fd`, `rg`, `gh`, `ish`, ...) live together. Only the scripts are tracked, under `.local/bin` in a layer. |
| `dl` | Downloads those binaries from their newest GitHub release into `~/.local/bin` (`dl fd rg` for just those), ad-hoc codesigns them, and installs the `mactop` app and LaunchAgent. `fd` and `rg` come from their upstream projects; Linux uses their static musl archives, while macOS uses native Darwin archives. `mold` is installed on x86_64 Linux only (musl prerelease tarball; no macOS build yet). It is idempotent: it records each installed asset's ETag under `~/.local/state/dl` and downloads only when the newest asset differs. If it cannot check an installed tool (offline), it warns and keeps it. `make` runs it first. Other release downloads come from my release repos and `jaq`'s over TLS, with no additional verification. |
| `macos/` | Run by hand, not installed. `setup-macos` provisions a Mac: Homebrew, the package list, Touch ID sudo, a local DNS cache, each step idempotent (`setup-macos -n` previews). `macos-lean.py` disables macOS services; `setup-macos lean` runs it, and it is never part of the default run. |
| `.agents/skills/` | Skills for this repo only (`dotfiles-health`, `agent-config-refresh`). `.claude/skills` links to it. |
| `skills` | Convenience link to the global skills, `dotfiles/base/.agents/skills`. |

A path belongs to exactly one layer, so a second claim on it is a conflict. When a file must differ per OS, split it into per-OS commands or files (`notify-sound` exists in both OS layers and the shared hooks call it).

## How files reach `~`

`sym` links each tracked file of a layer into `$HOME` as a relative symlink, so editing either side edits the repo. A directory holding a `.sym-dir` marker is linked whole instead; use that only for directories the harnesses must read as one unit (`.agents/skills`, `.claude/agents`). Both harnesses follow those links, which was tested.

Anything a harness writes lives in the real `~/.claude`, `~/.codex`, `~/.pi/agent`, never in this tree. Because a linked directory is written through, the ones above carry an allowlist `.gitignore` that tracks skills or agent definitions and nothing else, and the root `.gitignore` blocks credentials, history, sessions, and databases by name.

## Bootstrap

On a new Mac, in this order: clone to `~/usr`; `macos/setup-macos`; `make` (which runs `dl`); `setup-kache` (every `cargo` build goes through the `kache` wrapper that `.cargo/config.toml` names). On Linux: `make`, `setup-kache`, and `setup-mold` for glibc; musl targets expect mold at `/usr/local/libexec/mold`.

## Commands

- `make check`: the `sym`, `agent-tier-gate`, and `mdtool` tests plus the skill checks (about 12 s). Run it after touching `sym`, skills, or agent definitions.
- `make lint`: `shellcheck -s sh` on every tracked or new shell script (`.sh` or a sh, bash, or dash shebang), so a bashism fails even under a bash shebang, then `uvx ruff check` on every Python script (`.py` or a python shebang) with the rules in `ruff.toml`.
- `make plan`: dry run of the sync into `$HOME`. A `CONFLICT` means a real file, or a symlinked directory, is in the way; resolve it by hand. A path claimed by two layers stops both `plan` and `make`.
- `make`: run `dl`, then sync into `$HOME`. This downloads binaries and mutates the real home directory, so only run it when asked. A `dl` failure does not stop the sync but fails the run. `plan` and `check` never run `dl`.
- Experiment with `sh dotfiles/sym -t <tmpdir> dotfiles/base`; its default target is `$HOME`.
- Deleting something from the repo leaves its link dangling in `~`; remove it there too, or run `sh dotfiles/sym -d` on the layer first.

## Agent configuration

- **Instructions:** `dotfiles/base/.codex/AGENTS.md` is the single copy. `.claude`, `.pi/agent`, and `.config/opencode` link to it, so edit that file and never the links.
- **Skills and subagents:** global skills are in `dotfiles/base/.agents/skills/`, Claude subagents in `dotfiles/base/.claude/agents/`. A skill the model must not trigger on its own is marked `disable-model-invocation: true` plus `agents/openai.yaml`; `skills-check.sh` enforces the pairing.
- **Enforced rules:** "no formatters" is mirrored as deny rules in `.claude/settings.json` and prefix rules in `.codex/rules/default.rules`; pushes are `ask`/`prompt` rules there, not denied. The global `pre-push` hook in `dotfiles/base/.config/git/hooks` also refuses any push without a terminal, which catches the forms the Codex prefix rules cannot see; `--no-verify` skips it. A new hard rule gets its enforcement in the same change.
- **Codex:** `config.toml` (mode 0600, lists trusted projects) and `or.config.toml` (OpenRouter, used by `codex-or`).
- **Config the tools rewrite:** Codex appends trusted projects to `config.toml` and Claude rewrites `settings.json` (for example on `/effort`), both through the symlink, so read `git diff` on those two files before committing.
- **Skills to use:** `dotfiles-health` before finishing any change to the above. `agent-config-refresh` to check the Claude and Codex setup against their current docs (explicit-only). `ultrareview` for a whole-repo review and docs refresh, `review` for the current branch or task, `campaign-preflight` to make a campaign design doc executable unattended, `docs-refresh` for docs alone. The rules `make check` enforces on skills are in `dotfiles-health`.

## Scripts

- `git ls-files dotfiles/*/.local/bin` shows what is mine; the rest of `~/.local/bin` is downloaded binaries and other tools' links. Do not `cat` or `rg` the binaries.
- `claude-or` and `claude-ds` start Claude Code against OpenRouter or DeepSeek with `--dangerously-skip-permissions`, taking the key from `vault`. `codex-or` runs Codex with its `or` profile.
- `mdl`, `mpdl`, and `vdl` wrap `yt-dlp` through `uvx`.
- `mdtool` is the read-only docs audit that the docs skills call; its reference is `docs/mdtool.md`.
- `skill-usage` counts which skills were listed and loaded across real Claude and Codex sessions; `skill-eval` reads its output to decide what each skill earns.
- `reset-claude` and `reset-codex` delete everything in `~/.claude` and `~/.codex` except symlinks into this repo (and directories holding one) and the login credentials (`.credentials.json`, `auth.json`). Do not run either unprompted.
- Do not run `dl` (or `make`, which runs it), `macos/*`, or `setup-*` without being asked. Test `dl` with `HOME` pointed at a scratch directory under `.work/`. They download, codesign, install system services, or need sudo.

## Conventions

- Scripts are `#!/bin/sh` or `dash` and stay POSIX. `sym` must work under macOS `/bin/sh` (bash 3.2) and dash. Check scripts with `shellcheck -s sh`. Python scripts use only the standard library.
- Fix a `sym` bug with a failing numbered test in `sym-test.sh` first.
- Deferred work is a ticket in `TODO.md` and a design is an RFC in `docs/rfc/`. The `todo` skill owns both formats.
- My interactive shell is `ish` (`~/.local/bin/ish`, config in `.config/ish`), not bash or zsh.
- Leave commits to me. Push only when I ask; the harness prompts first.
