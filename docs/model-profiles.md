# Instruction profiles

Load one user contract, not a normal contract plus model-specific corrections. Native harness prompts, project instructions, model/effort defaults, and permissions remain unchanged. Delegation follows the generated [routing policy](../tools/pi-subagent-bridge/README.md); instruction profile selection remains separate.

| Harness and reported model | Contract |
| --- | --- |
| Claude Code, exactly `claude-opus-5-5` | [Lean](../dotfiles/base/.agents/instructions/lean.md) |
| Codex, exactly `gpt-6.2-sol` | The same lean contract |
| Other or missing model IDs | [Normal](../dotfiles/base/.codex/AGENTS.md), unchanged |
| Copilot CLI pilot | Normal contract via `~/.copilot/copilot-instructions.md` |
| Other harnesses | Their existing normal-contract adapters, unchanged |

The lean version keeps owner preferences and boundaries rather than general coaching. It no longer requires loading `do` merely because a task is substantive. Requested workflows and useful task-specific skills still apply; `orchestrate` still governs every delegation. Performance, structured-data and renaming procedures are read only when relevant. The shared skill catalog and its invocation metadata have not changed, so this reduces the user contract, not all context a harness may load.

## Antigravity Neon guidance

Antigravity CLI retains its normal global contract and gains a small `always_on` native rule at `~/.gemini/config/rules/neon.md`. It scopes Neon to evidence-grounded tool use and bounded acceptance checks while Hydrogen implements delegated narrow slices. This is guidance, not an official model-card prompt template or a model-switching hook. The [Neon model card](https://deepmind.google/models/model-cards/gemini-4-neon/) reports a March 2026 knowledge cutoff and residual hallucination risk: validate post-cutoff facts and actual CLI models, not confidence alone.

See [Antigravity native tiers](antigravity-native.md) for the native model-selection limitation and runtime checks.

## Sol 6.2 model baseline

Reviewed November 17, 2026 against the [Sol 6.2 model card](https://developers.openai.com/api/docs/models/gpt-6.2-sol) and [Codex model documentation](https://learn.chatgpt.com/docs/models). The Codex default is `gpt-6.2-sol` at `medium` effort and `default` service tier. Scout, mechanic, worker, native expert, fallback, and memory assignments retain their existing roles and effort settings. Astra remains prohibited by the shared [model policy](../tools/pi-subagent-bridge/src/policy.ts), including its 6, 6.1, and 6.2 families and effort variants. The bridge rejects prohibited launches and persisted sessions; harness-native lanes follow the shared instruction contract.

Codex supplies the model's native instructions and capability metadata. Its default Sol 6.2 context is 500,000 tokens; the API card separately lists 1,050,000 total, 922,000 maximum input, and 128,000 maximum output tokens. Keep context and compaction settings unset so the native Codex catalog owns them. The API requires Responses for tool calling and rejects `none` reasoning; the existing `medium` setting remains supported.

The [GPT-6.2 migration guidance](https://developers.openai.com/api/docs/guides/latest-model#whats-new) also calls for preserving conversation prefixes to retain reasoning and cache reuse. The selector continues to load a contract at session or subagent startup, without per-turn rewriting or replacing Codex's built-in instructions. Start a fresh Sol 6.2 conversation when migrating, as described below.

## Loading

[Claude's `CLAUDE.md`](../dotfiles/base/.claude/CLAUDE.md) and [Codex's `AGENTS.override.md`](../dotfiles/base/.codex/AGENTS.override.md) are relative symlinks to the same short [bootstrap](../dotfiles/base/.agents/instructions/bootstrap.md). Codex reads the override instead of the adjacent normal `AGENTS.md`; keeping the latter in place preserves other harness adapters, evaluation fixtures, and the private sandbox layout.

The stateless [selector](../dotfiles/base/.local/bin/agent-instructions.py) emits exactly one complete contract from `SessionStart`. Codex also uses `SubagentStart`, selecting from the child's own reported model, never the parent's model or a tier name. Claude child hooks do not guarantee that model field, so they are not registered. The checked-in contract contains a generated routing block, but generation runs only during development. No renderer runs at session startup, and no per-prompt injection, model-switch reset notice, session database or launcher wrapper is needed.

The hook reads fixed tracked paths through its resolved source location, not paths supplied in the event. Input is limited to 1 MiB and a contract to 32 KiB. Invalid input and unreadable selected contracts report errors without echoing private payloads. Codex sets `additionalContextLimit = 0` only on these bounded handlers so the complete normal contract is not replaced by a spill-file notice. Python runs with `-I -S` and a five-second hook timeout.

If the hook is disabled, untrusted, unsupported, or fails, the bootstrap directs the agent to read the normal contract before working. That is a prompt-level fallback, not enforcement. No existing trust record is forged or bypassed. A missing normal contract must be reported.

## Activate and switch

After pulling, review `sh sync plan`, then run `sh sync`. This installs the new selector, profile files, and Codex override through existing link ownership, and removes previously owned overlay paths. An unmanaged pre-existing `AGENTS.override.md` is a conflict to resolve, not something to overwrite. No host sync is performed by the tests.

Review/trust the changed `SessionStart` and `SubagentStart` commands in Codex's `/hooks`, then start a fresh conversation on the intended model. Claude needs a fresh session after the settings change. The default Codex Sol 6.2 session selects the lean contract; Terra and Luna children continue to select the normal contract.

**Change profiles by starting a fresh conversation without inherited history.** In-session model changes do not replace the selected contract. Startup/resume/clear/compaction/fork events can reload according to the reported model, but hooks cannot erase earlier messages or summaries. Resuming, forking, switching models, or spawning a child with inherited context is therefore not proof that the old contract is absent. A hidden provider fallback is also not observable here. Do not use this mechanism as a security boundary.

Other harnesses retain their normal adapters. A harness that imports Claude hooks may additionally receive the normal contract if it reports a nonmatching model; the selector never guesses that an alias is Opus. `sbx` deliberately imports neither normal user hooks/settings nor the Codex override, so its private home retains the normal contract. Skills and project instructions can add their own context independently.

## Verify

Run `python3 -I -S dotfiles/instructions-test.py`. The scratch guard requires `.work/` in `.git/info/exclude` and rejects symlinked scratch paths. Tests cover exact selection, complete normal fallback, rebuild events, no per-prompt/switch output, child models, bounded malformed input, file errors, installed symlinks, actual registered commands, and the lean entry-point budget. The lean contract plus bootstrap must be less than half the normal contract's byte size; this is not a tokenizer measurement.

Also run the named `SkillCampaignTests.test_global_instruction_adapters_resolve_to_their_selected_entry_points`, `test_claude_skips_instruction_adapters_while_working_in_this_repo`, and `test_claude_finds_no_nested_skills_directory_in_this_repo` cases in `dotfiles/skills-campaign-test.py`, plus `DecideTests.test_all_coding_harnesses_share_one_routing_policy` in `tools/decide/tests/test_decide.py`.

Offline checks establish routing and context composition, not model compliance or a quality improvement. Compare representative work at the same model, effort, tools, and revision before attributing better results to a shorter contract. Missing preferences should be restored; generic coaching should earn its cost.

## Native contracts

Reviewed November 10, 2026: [Codex instruction precedence](https://learn.chatgpt.com/docs/agent-configuration/agents-md), [Codex hook context and trust](https://learn.chatgpt.com/docs/hooks), and [Claude startup hooks](https://code.claude.com/docs/en/hooks). `model_instructions_file` is intentionally not used: it replaces Codex's built-in instructions rather than selecting this user contract. The earlier additive overlays and their tests are removed, not retained as another compatibility layer.
