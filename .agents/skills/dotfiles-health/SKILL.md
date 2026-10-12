---
name: dotfiles-health
description: "Apply when changing anything in dotfiles/ that configures AI agents (skills, subagent definitions, AGENTS.md, Claude or Codex settings and rules) or the sym installer, and before calling that work done. Also use to audit the setup. Skip changes outside the agent setup."
---

# Dotfiles Health

`~/usr` is the source of truth, and `make` makes the home directory match it. Edit the repo, never `~`.

## Map

- **Instructions:** `dotfiles/base/.codex/AGENTS.md`, shared with Claude and pi by symlink.
- **Skills:** `dotfiles/base/.agents/skills/`, linked whole into `~/.agents/skills` by a `.sym-dir` marker. Claude and Codex both follow the link, which was tested. The directory's `.gitignore` tracks skill folders and nothing else, because the harnesses write into it.
- **Claude subagents:** `dotfiles/base/.claude/agents/`, linked and ignored the same way. They are the only place a child's model and effort are set.
- **Enforcement:** `dotfiles/base/.claude/settings.json` (deny rules) and `dotfiles/base/.codex/rules/default.rules` (prefix rules). Codex config is `dotfiles/base/.codex/config.toml`.
- **Installer:** `dotfiles/sym`, its tests `dotfiles/sym-test.sh`, and the skill invariants `dotfiles/skills-check.sh`. The Makefile applies `dotfiles/base` and then the layer for the OS (`darwin` or `linux`); a path in two layers is a conflict.

## Commands

`make check` runs the sym tests and the skill checks. `make plan` is a dry run. `make` syncs. Read the plan before syncing: a `CONFLICT` is a real file in the way, and `sym` writes nothing until every conflict is resolved. A file deleted from the repo leaves a dangling link in `~`, so remove it there too.

## Invariants

- **Skill frontmatter:** `name` equals the directory, and `description` exists. An explicit-only skill carries `disable-model-invocation: true` and an `agents/openai.yaml` with `allow_implicit_invocation: false`, since each harness ignores the other's flag. `skills-check.sh` enforces both. It also fails an auto-triggered skill whose description has no `Skip` clause, and a router table (second column `Skill`) that names a skill that does not exist. It warns, without failing, on a skill over 60 lines or with no closing `**Reply:**`.
- **Descriptions and shape:** an auto-triggered description names its situations and a skip clause, because a broad one fires on every task. Skills stay dense: a thesis, bold rules, a closing `**The test:**`, and a `**Reply:**`.
- **A rule has one owner.** The shim rules live in `dead-code-archaeology`, the Oracle Test in `test-audit`, and the skill-scope and explicit-only loading rules in the global AGENTS.md. Other skills point to the owner; do not copy.
- **Model and effort live once.** Claude's are in `agents/*.md`, and `orchestrate` names the agents without repeating them. Codex's sit in the `orchestrate` table and `config.toml`. The default model and effort in settings belong to the owner; do not change them unprompted.
- **A rule that must hold is enforced, not just written.** "No push" and "no formatters" in AGENTS.md are mirrored as deny rules and prefix rules. When you add such a rule, add its enforcement in the same change.
- **Test Codex rules** with `bash -c 'codex execpolicy check --rules FILE -- git push'`, because zsh will not split the command. A Codex prefix rule misses `git -C dir push`; the Claude deny list covers it.
- **Check tool behavior against current docs, not memory.** Established so far: Claude agent files take `model` and `effort` and hot-reload, deny rules beat allow even in `auto` mode, and the rule form is `Bash(cmd *)`. Codex skills use `agents/openai.yaml`, and Codex rules use `prefix_rule(..., decision = "forbidden")`.

## sym

- Never run `sym` without `-t <tmpdir>` while experimenting; the default target is `$HOME`.
- Fix a bug by adding a failing numbered test to `sym-test.sh` first, then the fix.
- Properties the tests pin: every conflict is reported before anything is written; an existing link with the right text is already correct, but a dangling one is a conflict; a target path that passes through a symlinked directory is a conflict in both modes, so the source survives; delete mode never removes directories above the target; relative links are computed from physical paths; a `.sym-dir` directory links whole and respects Git ignores.
- Run the suite under `dash` as well as `sh` (`/bin/sh` is bash 3.2 on macOS and dash on Linux), and run `shellcheck -s sh` on every script.

## After a substantive change

Have fresh reviewers look, because the author misses things: an adversarial pass on `sym`, which rewrites `~` (an independent review found a source-deleting bug here that its author did not), and a consistency pass on skills against AGENTS.md. Triage each claim against the files before applying it; one review claim here was wrong. When compressing a prompt, diff its backticked tokens against the old version so no decision is lost. Judge whether an auto-triggered skill earns its place with `skill-eval`, not by how well it reads. Leave commits to the owner and never push.

## Known gaps

A tab in a filename breaks linking. `sym -d` can remove an emptied target directory, which test 12 pins. The auto-triggered skills have not been run through `skill-eval`. The warnings `skills-check.sh` prints today are known: `orchestrate`, `ultrareview`, `campaign-preflight` (embedded templates), the three migration skills, and `test-audit` (a compression candidate) are long, and `orchestrate` and the migrations have no `**Reply:**`.

**Reply:** what changed, which checks ran, and any `CONFLICT` you saw.
