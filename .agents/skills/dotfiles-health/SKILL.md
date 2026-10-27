---
name: dotfiles-health
description: "Apply when changing anything in dotfiles/ that configures AI agents (skills, subagent definitions, AGENTS.md, Claude or Codex settings and rules) or the sym installer, and before calling that work done. Also use to audit the setup. Skip changes outside the agent setup."
---

# Dotfiles Health

`~/usr` is the source of truth, and `make` makes the home directory match it.

The layout, the commands, and where each piece of agent configuration lives are in the repo `AGENTS.md`. This skill holds the invariants to check.

## Invariants

- **Global instructions:** `dotfiles/base/.codex/AGENTS.md` owns the shared contract. Each configured harness adapter, including Command Code's `~/.commandcode/AGENTS.md`, is a relative symlink to that file; `skills-campaign-test.py` checks the supported layouts. Update the adapter, setup reference, and check together when a harness changes its discovery path.
- **Skill frontmatter:** `name` equals the directory, and `description` exists. An explicit-only skill carries `disable-model-invocation: true`, an `agents/openai.yaml` with `allow_implicit_invocation: false`, and OpenCode `metadata.opencode/autoinvoke: "false"`, since those hosts do not consume each other's policy fields. `skills-check.sh` enforces this parity. It also fails an auto-triggered skill whose description has no `Skip` clause, and a router table (second column `Skill`) that names a skill that does not exist. It warns, without failing, on a skill over 8000 bytes (`orchestrate` gets 12000 for its per-harness routing table) or with no closing `**Report:**`. `ultrareview` alone is exempt from the length warning so its review lenses stay together.
- **Scripts pass their linters.** Shell is POSIX sh under `shellcheck -s sh` whatever its shebang. Every Python script, by `.py` or a python shebang (so `mdtool` and `skill-usage` count), passes `uvx ruff check` with the rules in `ruff.toml`, which ignores only the one-line-statement style. Run both on the files you changed, not the whole repo.
- **Descriptions and shape:** an auto-triggered description names its situations and a skip clause, because a broad one fires on every task. Skills stay dense: a thesis, bold rules, a closing `**The test:**`, and a `**Report:**`.
- **A rule has one owner.** The shim rules live in `dead-code-archaeology`, the Oracle Test in `test-audit`, task routing and completion in the canonical global contract and `do`, explicit-only loading in each skill's shared policy metadata, signal and crash policy and retry bounds in `lifecycle-concurrency`, the worktree and branch lifecycle in `orchestrate`, benchmark statistics in `benchmark-checklist`, junk-drawer modules in `deduplicate`, and the permission posture here. Other skills point to the owner; do not copy.
- **Model and effort live once.** Claude's are in `.claude/agents/*.md`, and Grok's are in `.grok/agents/*.md`. `orchestrate` names the agents without repeating them. Codex's sit in the `orchestrate` table and `config.toml`. Muse Code's sit in the `orchestrate` table, with the session default in `.config/muse/settings.json`. OpenCode has no pinned model in its config. The default model and effort in settings belong to the owner; do not change them unprompted.
- **Permission posture:** Claude uses `bypassPermissions` with sandboxing disabled; Codex uses `approval_policy = "never"`, `sandbox_mode = "danger-full-access"`, and an empty `rules/default.rules`; Muse uses `:unrestricted`; Grok uses yolo with sandbox profile `off`; OpenCode allows everything with a `permissions` allow-all rule; Command Code uses `permissions.defaultMode: yolo`. Preserve the owner's no-approval, no-sandbox preference wherever supported. Repository instructions still govern what work is appropriate.
- **Check tool behavior against current docs, not memory.** Established so far: Claude agent files take `model` and `effort` and hot-reload. Codex skills use `agents/openai.yaml`. Each posture value above disables approval and sandboxing in its harness; Grok's `yolo` enables always-approve and its sandbox profile `off` disables filesystem sandboxing.

## sym

- Properties the tests pin: every conflict is reported before anything is written; an existing link with the right text is already correct, but a dangling one is a conflict; a target path that passes through a symlinked directory is a conflict in both modes, so the source survives; delete mode never removes directories above the target; relative links are computed from physical paths; a `.sym-dir` directory links whole and respects Git ignores.
- Run the suite under `dash` as well as `sh` (`/bin/sh` is bash 3.2 on macOS and dash on Linux), and run `shellcheck -s sh` on the scripts you changed.

## After a substantive change

- For changes to `sym` that rewrite home paths, get a fresh adversarial review of source preservation. An independent review found a source-deleting bug here.
- **Choose proof by the mechanism changed:**
  - Wording with unchanged meaning: inspect the diff and relevant references; stop when checked.
  - Renames, removals, or heading and anchor changes: check the changed files and inbound references.
  - Local workflow composition: read the directly composed procedures and applicable global rules, then check the specific transitions and effects. A short instruction that composes workflows is a behavior change, not cosmetic wording.
  - Invocation metadata, discovery adapters, checkers, or fixture code: run the corresponding existing named structural tests and relevant metadata or link checks.
  - Broad shared policy, authority, or consequential uncertain behavior: get one focused independent consistency review and run the smallest behavioral scenario that can resolve the uncertainty.
- Check review claims against the files; a past claim here was wrong. Do not stack reviews that address the same uncertainty, repeat successful checks on unchanged relevant inputs, or create a process artifact just to report that checking is complete.
- When compressing a prompt, diff its backticked tokens against the old version so no decision is lost.
- Use `skill-eval` to judge whether an auto-triggered skill earns its place.
- Never push.

## Known gaps

A tab in a filename breaks linking. `sym -d` can remove an emptied target directory, which test 12 pins.

**The test:** `skills-check.sh` and the structural tests pass, no rule is stated outside its owner, and `make plan` shows no `CONFLICT`.

**Report:** what changed, which checks ran, and any `CONFLICT` you saw.
