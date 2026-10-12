---
name: dotfiles-health
description: "Apply when changing anything in dotfiles/ that configures AI agents (skills, subagent definitions, AGENTS.md, Claude or Codex settings and rules) or the sym installer, and before calling that work done. Also use to audit the setup."
---

# Dotfiles Health

`~/usr` is the source of truth, and `make` makes the home directory match it. Edit the repo, never `~`.

## Map

- **Instructions:** `dotfiles/base/.codex/AGENTS.md`, shared with Claude and pi by symlink.
- **Skills:** `dotfiles/base/.agents/skills/`. Real files synced both ways by `sym`, because symlinked skills are not followed.
- **Claude subagents:** `dotfiles/base/.claude/agents/`, synced the same way. They are the only place a child's model and effort are set.
- **Enforcement:** `dotfiles/base/.claude/settings.json` (deny rules) and `dotfiles/base/.codex/rules/default.rules` (prefix rules). Codex config is `dotfiles/base/.codex/config.toml`.
- **Installer:** `dotfiles/sym`, its tests `dotfiles/sym-test.sh`, and the skill invariants `dotfiles/skills-check.sh`.

## Commands

`make check` runs the sym tests and the skill checks. `make plan` is a dry run. `make` syncs. Read the plan before syncing: `OVERWRITE` means a home edit is about to be lost, `DISCARD` means files go with a replaced directory, `EXTRA` is a home-only file left alone. Deletions do not propagate, so a skill or agent deleted from the repo stays live in `~` until you delete it there too (or run `sym -d`).

## Invariants

- **Skill frontmatter:** `name` equals the directory, and `description` exists. An explicit-only skill carries `disable-model-invocation: true` and an `agents/openai.yaml` with `allow_implicit_invocation: false`, since each harness ignores the other's flag. `skills-check.sh` enforces both.
- **Descriptions and shape:** an auto-triggered description names its situations and a skip clause, because a broad one fires on every task. Skills stay dense: a thesis, bold rules, a closing `**The test:**`, and a `**Reply:**`.
- **Model and effort live once.** Claude's are in `agents/*.md`, and `orchestrate` names the agents without repeating them. Codex's sit in the `orchestrate` table and `config.toml`. The default model and effort in settings belong to the owner; do not change them unprompted.
- **A rule that must hold is enforced, not just written.** "No push" and "no formatters" in AGENTS.md are mirrored as deny rules and prefix rules. When you add such a rule, add its enforcement in the same change.
- **Test Codex rules** with `bash -c 'codex execpolicy check --rules FILE -- git push'`, because zsh will not split the command. A Codex prefix rule misses `git -C dir push`; the Claude deny list covers it.
- **Check tool behavior against current docs, not memory.** Established so far: Claude agent files take `model` and `effort` and hot-reload, deny rules beat allow even in `auto` mode, and the rule form is `Bash(cmd *)`. Codex skills use `agents/openai.yaml`, and Codex rules use `prefix_rule(..., decision = "forbidden")`.

## sym

- Never run `sym` without `-t <tmpdir>` while experimenting; the default target is `$HOME`.
- Fix a bug by adding a failing numbered test to `sym-test.sh` first, then the fix.
- Properties the tests pin: sync never follows a symlinked directory; a sync root that resolves to its source is fatal; a failure exits nonzero without advancing the marker; file times have one-second resolution, so a tie counts as changed; `--force` makes the repo win but names every overwrite and discard.
- Run the suite under `dash` as well as `sh` (`/bin/sh` is bash 3.2 on macOS and dash on Linux), and run `shellcheck -s sh` on every script.

## After a substantive change

Have fresh reviewers look, because the author misses things: an adversarial pass on `sym`, which rewrites `~` (an independent review found a source-deleting bug here that its author did not), and a consistency pass on skills against AGENTS.md. Triage each claim against the files before applying it; one review claim here was wrong. When compressing a prompt, diff its backticked tokens against the old version so no decision is lost. Judge whether an auto-triggered skill earns its place with `skill-eval`, not by how well it reads. Leave commits to the owner and never push.

## Known gaps

A tab in a synced filename breaks sync. `sym -d` can remove an emptied target directory, which test 13 pins. The auto-triggered skills have not been run through `skill-eval`.

**Reply:** what changed, which checks ran, and any `OVERWRITE` or `DISCARD` you saw.
