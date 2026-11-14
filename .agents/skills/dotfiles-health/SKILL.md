---
name: dotfiles-health
description: "Apply when changing anything in dotfiles/ that configures AI agents (skills, subagent definitions, AGENTS.md, Claude or Codex settings and rules) or home link reconciliation, and before calling that work done. Also use to audit the setup. Skip changes outside agent setup and link reconciliation."
---

# Dotfiles Health

`~/usr` is the source of truth, and `sh sync` makes the home directory match it.

The layout, the commands, and where each piece of agent configuration lives are in the repo `AGENTS.md`. This skill holds the invariants to check.

## Invariants

- **Global instructions:** `dotfiles/base/.codex/AGENTS.md` owns the normal contract and remains the target of other harness adapters. Claude's `CLAUDE.md` and Codex's `AGENTS.override.md` link to the profile bootstrap; `agent-instructions.py` selects one complete contract at startup. Never append lean to normal, replace vendor system prompts, or rewrite shared files per session. `instructions-test.py` and the named adapter cases in `skills-campaign-test.py` check selection and discovery. Update the adapter, setup reference, and checks together when discovery changes.
- **Skill metadata:** `tools/skills/skills.ts` owns the structural rules (name and directory, description, the one authored invocation field and its generated Codex and OpenCode adapters, `Skip` clauses, resolvable references, size and `**Report:**` warnings). Run `node tools/skills/skills.ts generate` after changing invocation, then `check`; fix findings at the source rather than restating its rules here.
- **Scripts pass their linters.** Shell is POSIX sh whatever its shebang; Python passes `ruff.toml`. `sh sync check --changed` runs `shellcheck`, `ruff` and `ty` on exactly the files you changed.
- **Descriptions and shape:** an auto-triggered description names its situations and a skip clause, because a broad one fires on every task. Skills stay dense: a thesis, bold rules, a closing `**The test:**`, and a `**Report:**`.
- **A rule has one owner.** The shim rules live in `dead-code-archaeology`, the Oracle Test in `test-audit`, task routing and completion in the selected instruction contract and requested workflows, explicit-only loading in each skill's shared policy metadata, signal and crash policy and retry bounds in `lifecycle-concurrency`, the worktree and branch lifecycle in `orchestrate`, benchmark statistics in `benchmark-checklist`, junk-drawer modules in `deduplicate`, and the permission posture here. Other skills point to the owner; do not copy.
- **Model and effort ownership:** root routes and native exceptions live in `tools/pi-subagent-bridge/src/policy.ts`; nested Pi pins and ceilings live in `tools/pi-subagent-bridge/src/tier-policy.ts`. `make generate` derives policy tables, contract fragments and native profile fields; `make check-generated` rejects drift. `tier-profile.ts` validates installed profiles. Session defaults remain in each harness's tracked config and belong to the owner; do not change them unprompted.
- **Permission posture:** Claude uses `bypassPermissions` with sandboxing disabled; Codex uses `approval_policy = "never"`, `sandbox_mode = "danger-full-access"`, and an empty `rules/default.rules`; Muse uses `:unrestricted`; OpenCode allows everything with a `permissions` allow-all rule; Command Code uses `permissions.defaultMode: yolo`. Preserve the owner's no-approval, no-sandbox preference wherever supported. Repository instructions still govern what work is appropriate.
- **Check tool behavior against current docs, not memory.** Established so far: Claude agent files take `model` and `effort` and hot-reload. Codex skills use `agents/openai.yaml`. Each posture value above disables approval and sandboxing in its harness.

## Home link reconciliation

The Python link manager in `tools/sync/` owns `.sym-dir` discovery, preflight, ownership, and recovery. Follow the repository `AGENTS.md`, [sync reference](../../../docs/sync.md), and [development checks](../../../docs/development.md). The standalone `sym` command is retired.

## After a substantive change

- For link-reconciliation changes that rewrite home paths, get a fresh adversarial review of source preservation.
- **Choose proof by the mechanism changed:**
  - Wording with unchanged meaning: inspect the diff and relevant references; stop when checked.
  - Renames, removals, or heading and anchor changes: check the changed files and inbound references.
  - Local workflow composition: read the directly composed procedures and applicable global rules, then check the specific transitions and effects. A short instruction that composes workflows is a behavior change, not cosmetic wording.
  - Invocation metadata, discovery adapters, checkers, or fixture code: run the corresponding existing named structural tests and relevant metadata or link checks.
  - Broad shared policy, authority, or consequential uncertain behavior: get one focused independent consistency review and run the smallest behavioral scenario that can resolve the uncertainty.
- Check review claims against the files; a past claim here was wrong. Do not stack reviews that address the same uncertainty, repeat successful checks on unchanged relevant inputs, or create a process artifact just to report that checking is complete.
- When compressing a prompt, diff its backticked tokens against the old version so no decision is lost.
- Use `skill-eval` to judge whether an auto-triggered skill earns its place.

**The test:** `node tools/skills/skills.ts check` and the structural tests pass, no rule is stated outside its owner, and `sh sync plan` shows no `CONFLICT`.

**Report:** what changed, which checks ran, and any `CONFLICT` you saw.
