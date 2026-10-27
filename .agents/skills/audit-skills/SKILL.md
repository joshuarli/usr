---
name: audit-skills
description: "Use for /audit-skills: QA the global contract, skills, and agent definitions for contradictions, duplicated rules, bloat, and unclear wording; report ranked findings, then apply the approved ones in reviewed commits."
disable-model-invocation: true
metadata:
  opencode/slash: "true"
  opencode/autoinvoke: "false"
---

# Audit Skills

Instructions drift as they grow: two skills give opposite orders, a rule is restated in four places and edited in one, a harness loads the contract twice. This audit finds contradictions first, then rules without a single owner, then bloat and unclear wording, and fixes what the owner approves. `dotfiles-health` owns the structural invariants and the rule-owner list; this skill judges the prose against them. Whether a skill earns its place from real usage is `skill-eval`.

## Scope and cost

- **Everything an agent reads.** `dotfiles/base/.codex/AGENTS.md` and every adapter linking to it, the repo `AGENTS.md`, `SKILLS.md`, `docs/agent-setup.md`, `dotfiles/base/.claude/agents/` and `dotfiles/base/.grok/agents/`, and every `SKILL.md` and `references/` file under `dotfiles/base/.agents/skills/` and `.agents/skills/`.
- **Weight findings by load cost.** The global contract loads in every session, auto-skill descriptions in every session, and skill bodies only on use. A byte cut from the contract is worth more than a paragraph cut from an explicit skill.
- **Each harness loads the contract once.** List the adapter symlinks (`fd -H -t l '^(AGENTS|CLAUDE|GEMINI)\.md$' dotfiles`) against the paths in `docs/agent-setup.md`. A second adapter in one harness's directory doubles the contract in every session.

## Audit (read-only)

1. **Inventory.** Byte size of every file in scope; note the largest and those near the `skills-check.sh` length warning.
2. **Fan out by cluster** with [orchestrate](../../../dotfiles/base/.agents/skills/orchestrate/SKILL.md): one read-only lane each for the contract with its index and agent definitions, workflow and campaign skills, review, test, and performance skills, code-design skills, and language, writing, and repo skills. Rebalance clusters as skills are added. Each lane reads the global contract first, since anything a skill restates from it is redundant.
3. **Brief each lane with the priorities in order.**
   - Contradictions between files, quoted on both sides with `file:line`.
   - Rules without one owner: the same rule in several skills, or overlapping scopes that should merge or point. Check against the owner list in `dotfiles-health`.
   - Bloat: sentences that can be cut or halved with no lost decision.
   - Unclear wording: more than one reading, jargon where a plain word works, stacked qualifiers.
   - Descriptions that are vague or would fire too broadly; skills missing `**The test:**` or `**Report:**`.

   Each finding gives `file:line`, the quoted text, a proposed replacement or "delete", and a one-line reason.
4. **Check every claim against the files before reporting.** Lanes misread: a reference called dangling may exist, and a contradiction may already be resolved. Drop what does not survive.
5. **Report** ranked: contradictions, then ownership, then the largest cuts. Separate what needs the owner: behavior choices between conflicting rules, removing a slash command the owner types, and model or effort settings, which belong to the owner.

## Apply (after approval)

- **Lanes edit disjoint files and run no git writes.** Reuse the audit lanes, which already hold their findings. A fix that crosses into another lane's files is reported, not made.
- **Preserve every decision.** Per file, compare backticked tokens with `git show HEAD:<file> | rg -o '\`[^\`]+\`' | sort -u`; every token removed must be named as moved or deliberately dropped.
- **Find tests that pin instruction text before committing.** `rg -l 'SKILL\.md|AGENTS\.md|agents/skills' --glob '*test*'` lists them; run each. A lane once deleted a safety sentence that `tools/agent-memory/eval/test_live_recall.py` pins.
- **Review each lane's diff, then commit it alone** with a body naming the contradictions it resolves. New rule owners go into the list in `dotfiles-health` in the same change.
- **Run the shared checks once all lanes stop**, not while they edit: `sh dotfiles/skills-check.sh dotfiles/base/.agents/skills`, `sh dotfiles/skills-check.sh .agents/skills`, and `python3 -I dotfiles/skills-campaign-test.py`. Concurrent runs collide on fixtures and fail spuriously.
- **Expect modest savings.** Once contradictions and duplicates are gone, most remaining text is a specific rule. Stop there instead of compressing rules away.

**The test:** no two files give conflicting orders, each shared rule has one owner the others point to, the contract loads once per harness, every removed token is accounted for, and the checks and text-pinning tests pass on the final tree.

**Report:** findings ranked with `file:line`, owner decisions listed separately, and after applying, the commits, bytes before and after for the contract and in total, removed tokens, and checks run.
