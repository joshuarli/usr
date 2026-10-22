---
name: dotfiles-health
description: "Apply when changing anything in dotfiles/ that configures AI agents (skills, subagent definitions, AGENTS.md, Claude or Codex settings and rules) or the sym installer, and before calling that work done. Also use to audit the setup. Skip changes outside the agent setup."
---

# Dotfiles Health

`~/usr` is the source of truth, and `make` makes the home directory match it. Edit the repo, never `~`.

The layout, the commands, and where each piece of agent configuration lives are in the repo `AGENTS.md`. This skill holds the invariants to check.

## Invariants

- **Global instructions:** `dotfiles/base/.codex/AGENTS.md` owns the shared contract. Each configured harness adapter is a relative symlink to that file; `skills-campaign-test.py` checks the supported layouts. Update the adapter, setup reference, and check together when a harness changes its discovery path.
- **Skill frontmatter:** `name` equals the directory, and `description` exists. An explicit-only skill carries `disable-model-invocation: true`, an `agents/openai.yaml` with `allow_implicit_invocation: false`, and OpenCode `metadata.opencode/autoinvoke: "false"`, since those hosts do not consume each other's policy fields. `skills-check.sh` enforces this parity. It also fails an auto-triggered skill whose description has no `Skip` clause, and a router table (second column `Skill`) that names a skill that does not exist. It warns, without failing, on a skill over 8000 bytes (`orchestrate` gets 12000 for its per-harness routing table) or with no closing `**Report:**`. `ultrareview` alone is exempt from the length warning so its review lenses stay together.
- **Scripts pass their linters.** Shell is POSIX sh under `shellcheck -s sh` whatever its shebang. Every Python script, by `.py` or a python shebang (so `mdtool` and `skill-usage` count), passes `uvx ruff check` with the rules in `ruff.toml`, which ignores only the one-line-statement style. Run both on the files you changed, not the whole repo.
- **Descriptions and shape:** an auto-triggered description names its situations and a skip clause, because a broad one fires on every task. Skills stay dense: a thesis, bold rules, a closing `**The test:**`, and a `**Report:**`.
- **A rule has one owner.** The shim rules live in `dead-code-archaeology`, the Oracle Test in `test-audit`, task routing and completion in the canonical global contract and `do`, and explicit-only loading in each skill's shared policy metadata. Other skills point to the owner; do not copy.
- **Model and effort live once.** Claude's are in `.claude/agents/*.md`, and Grok's are in `.grok/agents/*.md`. `orchestrate` names the agents without repeating them. Codex's sit in the `orchestrate` table and `config.toml`. Muse Code's sit in the `orchestrate` table, with the session default in `.config/muse/settings.json`. OpenCode has no pinned model in its config. The default model and effort in settings belong to the owner; do not change them unprompted.
- **Permission posture:** Claude uses `bypassPermissions` with sandboxing disabled; Codex uses `approval_policy = "never"`, `sandbox_mode = "danger-full-access"`, and an empty `rules/default.rules`; Muse uses `:unrestricted`; Grok uses yolo with sandbox profile `off`; OpenCode allows everything with a `permissions` allow-all rule. Preserve the owner's no-approval, no-sandbox preference wherever supported. Repository instructions still govern what work is appropriate.
- **Check tool behavior against current docs, not memory.** Established so far: Claude agent files take `model` and `effort` and hot-reload, and its permission mode is `bypassPermissions`. Codex skills use `agents/openai.yaml`. Muse's `:unrestricted` profile disables approval and sandboxing. Grok's `yolo` enables always-approve and its sandbox profile `off` disables filesystem sandboxing. OpenCode accepts the global `permissions` allow-all rule.

## sym

- Never run `sym` without `-t <tmpdir>` while experimenting; the default target is `$HOME`.
- Fix a bug by adding a failing numbered test to `sym-test.sh` first, then the fix.
- Properties the tests pin: every conflict is reported before anything is written; an existing link with the right text is already correct, but a dangling one is a conflict; a target path that passes through a symlinked directory is a conflict in both modes, so the source survives; delete mode never removes directories above the target; relative links are computed from physical paths; a `.sym-dir` directory links whole and respects Git ignores.
- Run the suite under `dash` as well as `sh` (`/bin/sh` is bash 3.2 on macOS and dash on Linux), and run `shellcheck -s sh` on the scripts you changed.

## After a substantive change

Have fresh reviewers look, because the author misses things: an adversarial pass on `sym`, which rewrites `~` (an independent review found a source-deleting bug here that its author did not), and a consistency pass on skills against AGENTS.md. Triage each claim against the files before applying it; one review claim here was wrong. When compressing a prompt, diff its backticked tokens against the old version so no decision is lost. Judge whether an auto-triggered skill earns its place with `skill-eval`, not by how well it reads. Leave commits to the owner and never push.

## Known gaps

A tab in a filename breaks linking. `sym -d` can remove an emptied target directory, which test 12 pins. The auto-triggered skills have not been read with `skill-eval` against real sessions.

**Report:** what changed, which checks ran, and any `CONFLICT` you saw.
