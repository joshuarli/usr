# Instruction profiles

Load one user contract, not a normal contract plus model-specific corrections. Native harness prompts, project instructions, model/effort defaults, and permissions remain unchanged. The shared bridge now pins new expert work to Hydrogen XHigh; instruction profile selection remains separate.

| Harness and reported model | Contract |
| --- | --- |
| Claude Code, exactly `claude-opus-5-5` | [Lean](../dotfiles/base/.agents/instructions/lean.md) |
| Codex, exactly `gpt-6.1-sol` | The same lean contract |
| Other or missing model IDs | [Normal](../dotfiles/base/.codex/AGENTS.md), unchanged |
| Other harnesses | Their existing normal-contract adapters, unchanged |

The lean version keeps owner preferences and boundaries rather than general coaching. It no longer requires loading `do` merely because a task is substantive. Requested workflows and useful task-specific skills still apply; `orchestrate` still governs every delegation. Performance and structured-data procedures are read only when relevant. The shared skill catalog and its invocation metadata have not changed, so this reduces the user contract, not all context a harness may load.

## Loading

[Claude's `CLAUDE.md`](../dotfiles/base/.claude/CLAUDE.md) and [Codex's `AGENTS.override.md`](../dotfiles/base/.codex/AGENTS.override.md) are relative symlinks to the same short [bootstrap](../dotfiles/base/.agents/instructions/bootstrap.md). Codex reads the override instead of the adjacent normal `AGENTS.md`; keeping the latter in place preserves other harness adapters, evaluation fixtures, and the private sandbox layout.

The stateless [selector](../dotfiles/base/.local/bin/agent-instructions.py) emits exactly one complete contract from `SessionStart`. Codex also uses `SubagentStart`, selecting from the child's own reported model, never the parent's model or a tier name. Claude child hooks do not guarantee that model field, so they are not registered. No per-prompt injection, model-switch reset notice, session database, launcher wrapper, or generated prompt file is needed.

The hook reads fixed tracked paths through its resolved source location, not paths supplied in the event. Input is limited to 1 MiB and a contract to 32 KiB. Invalid input and unreadable selected contracts report errors without echoing private payloads. Codex sets `additionalContextLimit = 0` only on these bounded handlers so the complete normal contract is not replaced by a spill-file notice. Python runs with `-I -S` and a five-second hook timeout.

If the hook is disabled, untrusted, unsupported, or fails, the bootstrap directs the agent to read the normal contract before working. That is a prompt-level fallback, not enforcement. No existing trust record is forged or bypassed. A missing normal contract must be reported.

## Activate and switch

After pulling, review `sh sync plan`, then run `sh sync`. This installs the new selector, profile files, and Codex override through existing link ownership, and removes previously owned overlay paths. An unmanaged pre-existing `AGENTS.override.md` is a conflict to resolve, not something to overwrite. No host sync is performed by the tests.

Review/trust the changed `SessionStart` and `SubagentStart` commands in Codex's `/hooks`, then start a fresh conversation on the intended model. Claude needs a fresh session after the settings change. Your default Codex Terra session continues to select the normal contract; selecting Sol does not require changing the default.

**Change profiles by starting a fresh conversation without inherited history.** In-session model changes do not replace the selected contract. Startup/resume/clear/compaction/fork events can reload according to the reported model, but hooks cannot erase earlier messages or summaries. Resuming, forking, switching models, or spawning a child with inherited context is therefore not proof that the old contract is absent. A hidden provider fallback is also not observable here. Do not use this mechanism as a security boundary.

Other harnesses retain their normal adapters. A harness that imports Claude hooks may additionally receive the normal contract if it reports a nonmatching model; the selector never guesses that an alias is Opus. `sbx` deliberately imports neither normal user hooks/settings nor the Codex override, so its private home retains the normal contract. Skills and project instructions can add their own context independently.

## Verify

Run `python3 -I -S dotfiles/instructions-test.py`. The scratch guard requires `.work/` in `.git/info/exclude` and rejects symlinked scratch paths. Tests cover exact selection, complete normal fallback, rebuild events, no per-prompt/switch output, child models, bounded malformed input, file errors, installed symlinks, actual registered commands, and the lean entry-point budget. The lean contract plus bootstrap must be less than half the normal contract's byte size; this is not a tokenizer measurement.

Also run the named `SkillCampaignTests.test_global_instruction_adapters_resolve_to_their_selected_entry_points`, `test_claude_skips_instruction_adapters_while_working_in_this_repo`, and `test_claude_finds_no_nested_skills_directory_in_this_repo` cases in `dotfiles/skills-campaign-test.py`, plus `DecideTests.test_all_coding_harnesses_share_one_routing_policy` in `tools/decide/tests/test_decide.py`.

Offline checks establish routing and context composition, not model compliance or a quality improvement. Compare representative work at the same model, effort, tools, and revision before attributing better results to a shorter contract. Missing preferences should be restored; generic coaching should earn its cost.

## Native contracts

Reviewed November 10, 2026: [Codex instruction precedence](https://learn.chatgpt.com/docs/agent-configuration/agents-md), [Codex hook context and trust](https://learn.chatgpt.com/docs/hooks), and [Claude startup hooks](https://code.claude.com/docs/en/hooks). `model_instructions_file` is intentionally not used: it replaces Codex's built-in instructions rather than selecting this user contract. The earlier additive overlays and their tests are removed, not retained as another compatibility layer.
