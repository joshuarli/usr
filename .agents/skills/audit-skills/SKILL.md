---
name: audit-skills
description: "Use for /audit-skills: QA the global contract, skills, and agent definitions for contradictions, duplicated rules, bloat, unclear wording, and procedures that belong in tooling; report ranked findings, then apply the approved ones in reviewed commits."
disable-model-invocation: true
metadata:
  opencode/slash: "true"
  opencode/autoinvoke: "false"
---

# Audit Skills

Instructions drift as they grow: two skills give opposite orders, a rule is restated in four places and edited in one, a harness loads the contract twice. This audit finds contradictions first, then rules without a single owner, then bloat and unclear wording, and fixes what the owner approves. `dotfiles-health` owns the structural invariants and the rule-owner list; this skill judges the prose against them. Whether a skill earns its place from real usage is `skill-eval`.

## Scope and cost

- **Everything an agent reads.** `dotfiles/base/.codex/AGENTS.md` and every adapter linking to it, the repo `AGENTS.md`, `SKILLS.md`, `docs/agent-setup.md`, `dotfiles/base/.claude/agents/`, and every `SKILL.md` and `references/` file under `dotfiles/base/.agents/skills/` and `.agents/skills/`.
- **Weight findings by load cost.** The global contract loads in every session, auto-skill descriptions in every session, and skill bodies only on use. A byte cut from the contract is worth more than a paragraph cut from an explicit skill.
- **Each harness loads the contract once.** List the adapter symlinks (`fd -H -t l '^(AGENTS|CLAUDE|GEMINI)\.md$' dotfiles`) against the paths in `docs/agent-setup.md`. A second adapter in one harness's directory doubles the contract in every session, and so does a stale link left in the home directory, which sync must then retire. Inside this repo, Claude Code also loads nested instruction files and `.claude/skills` directories beside files it reads; `.claude/settings.json` excludes the adapters and sync declares `~/.claude/skills` in code. When a finding is about load cost, prove it: run `claude -p --model claude-haiku-5-5 --allowedTools Read` asking it to read a file in the suspect directory and list every `Contents of` header, once with the fix and once without.

## Audit (read-only)

1. **Inventory.** Run `node tools/skills/skills.ts check` and `node tools/skills/skills.ts check --root .agents/skills` for current warnings. Rank every file in scope by bytes, and every skill by description length, since descriptions load in every session of every harness.
2. **Fan out by cluster** when the inventory shows work across many skills; a pass with a handful of findings is cheaper done directly. Use [orchestrate](../../../dotfiles/base/.agents/skills/orchestrate/SKILL.md) with one read-only lane each for the contract with its index and agent definitions, workflow and campaign skills, review, test, and performance skills, code-design skills, and language, writing, and repo skills. Rebalance clusters as skills are added. Each lane reads the global contract first, since anything a skill restates from it is redundant.
3. **Brief each lane with the priorities in order.**
   - Contradictions between files, quoted on both sides with `file:line`.
   - Rules without one owner: the same rule in several skills, or overlapping scopes that should merge or point. Check against the owner list in `dotfiles-health`.
   - Procedures that belong in tooling: a fixed sequence of commands or checks an agent must reproduce by hand (for example the git steps `worktree-retire` replaced). Propose a stdlib Python or TypeScript tool with tests, and leave the skill only the judgment the tool cannot make.
   - Restated enforcement: prose repeating what a schema, checker, hook, or test already enforces. Cut it to the judgment the enforcement leaves open.
   - Bloat: sentences that can be cut or halved with no lost decision, and facts pinned to a library version that will go stale.
   - Placement: material needed at one step only (one-time setup, lookup tables, verified facts) belongs in `references/`, linked at that step.
   - Unclear wording: more than one reading, jargon where a plain word works, stacked qualifiers.
   - Invocation precision: an auto-skill description must name the distinct tasks that require its body, not merely describe its topic. Test whether each description would trigger for a concrete user request and stay silent for an adjacent request; explicitly gated skills must remain manual-only.
   - Descriptions that are vague or would fire too broadly; skills missing `**The test:**` or `**Report:**`.

   Each finding gives `file:line`, the quoted text, a proposed replacement or "delete", and a one-line reason.
4. **Check every claim against the files before reporting.** Lanes misread: a reference called dangling may exist, and a contradiction may already be resolved. Drop what does not survive.
5. **Report** ranked: contradictions, then ownership, then the largest cuts. Separate what needs the owner: behavior choices between conflicting rules, removing a slash command the owner types, and model or effort settings, which belong to the owner.

## Apply (after approval)

- **Lanes edit disjoint files and run no git writes.** Reuse the audit lanes, which already hold their findings. A fix that crosses into another lane's files is reported, not made.
- **Preserve every decision.** Per file, compare backticked tokens with `git show HEAD:<file> | rg -o '\`[^\`]+\`' | sort -u`; every token removed must be named as moved or deliberately dropped.
- **Find tests that pin instruction text before committing.** `rg -l 'SKILL\.md|AGENTS\.md|agents/skills' --glob '*test*'` lists them; run each.
- **Review each lane's diff, then commit it alone** with a body naming the contradictions it resolves. New rule owners go into the list in `dotfiles-health` in the same change.
- **Run the shared checks once all lanes stop**, not while they edit: `node tools/skills/skills.ts check`, `node tools/skills/skills.ts check --root .agents/skills`, and `python3 -I dotfiles/skills-campaign-test.py`. Concurrent runs collide on fixtures and fail spuriously.
- **A new tool lands before the skill that points at it**, in its own commit with tests registered in `tools/sync/check.sh`. When a check fails, rerun it on the stashed tree to tell a pre-existing failure from a new one.
- **Expect modest savings.** Once contradictions and duplicates are gone, most remaining text is a specific rule. Stop there instead of compressing rules away.

**The test:** no two files give conflicting orders, each shared rule has one owner the others point to, the contract loads once per harness, every removed token is accounted for, and the checks and text-pinning tests pass on the final tree.

**Report:** findings ranked with `file:line`, owner decisions listed separately, and after applying, the commits, tools added and the prose they replaced, bytes before and after for the contract, descriptions, and total, removed tokens, and checks run.
