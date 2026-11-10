# Model-specific execution overlays

Shared instructions and skills remain canonical. A small, stateless hook adds a behavioral delta only for an exact harness/model pair. It does not replace native system prompts, grant authority, change model/effort defaults, or alter `pi-subagent-bridge` routing.

## Selection

| Harness | Exact reported model | Events | Overlay |
| --- | --- | --- | --- |
| Claude Code | `claude-opus-5-5` | `SessionStart`, `PostModelSwitch` | [Opus 5.5](../dotfiles/base/.claude/model-overlays/opus-5-5.md) |
| Codex | `gpt-6.1-sol` | `SessionStart`, `UserPromptSubmit`, `SubagentStart` | [Sol 6.1](../dotfiles/base/.codex/model-overlays/gpt-6.1-sol.md) |

The [selector](../dotfiles/base/.local/bin/agent-model-overlay.py) uses `model`, or `to_model` for Claude model switches. It never infers a model from aliases, a parent model, a tier name, configuration defaults, or transcript text. Missing/unknown IDs and other models produce no overlay. New model versions require an explicit review; `opus` is not treated as a permanent alias for 5.5. The existing Codex Terra default therefore stays on the baseline. Other harness configurations and the shared instruction/skill symlinks are unchanged.

`SessionStart` reloads on startup, resume, clear, compaction, and fork when the harness provides the matching model ID. Claude sends a retirement reminder when switching away from Opus 5.5. Codex's prompt hook covers an explicit model selection before the next submitted prompt; its child hook uses the child's reported model, including a native Sol `god`, not the parent's model or the tier's name.

Only [Claude settings](../dotfiles/base/.claude/settings.json) and [Codex config](../dotfiles/base/.codex/config.toml) register these hooks. Each command uses isolated Python without site initialization (`-I -S`), the standard library only, and a five-second timeout. The selector resolves fixed files alongside its tracked source, including through installed symlinks. It does not read user-supplied paths, transcripts, credentials, or configuration. Input is bounded to 1 MiB and overlay files to 4 KiB. Invalid input or an unreadable selected file reports a generic error without echoing the payload; nonmatching models need no overlay file.

## Activate

From an updated checkout, review `sh sync plan`, then run `sh sync` and start fresh harness sessions. Sync installs the new files through its existing link discovery; no installer or launcher wrapper was added. No host sync is performed by the overlay tests.

Claude model-switch support requires Claude Code 2.1.251 or later. In Codex, open `/hooks` and review/trust the three new hook definitions once. New or changed non-managed hooks are skipped until trusted. Existing hook definitions and trust records are preserved; no trust bypass or manufactured trust hash is installed. For verification, start a Sol session after trusting the hooks, rather than assuming a previously skipped startup event will be replayed.

## Research basis

Reviewed November 10, 2026. These are bounded adaptations of documented behaviors, not a claim that a system card prescribes an optimal prompt or that the overlays improve benchmarks.

### Opus 5.5

Sources: Anthropic's [system card](https://www.anthropic.com/claude-opus-5-5-system-card), its [model-specific prompting guide](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-opus-5-5), and [Claude Code hook documentation](https://code.claude.com/docs/en/hooks).

The original card PDF exceeded this authoring environment's fetch limit. Relevant card text was reviewed through a [readable transcription of the card](https://malob.github.io/ai-system-cards/anthropic/claude-opus-5-5/); the official prompting and hook documentation were read directly. The transcription is not an independent Anthropic recommendation.

Card sections 6.2.2, 6.3.1, and 6.5.1 motivate explicitly treating missing required inputs as blockers, never inventing approval to persuade a worker, and distinguishing pasted material from user instructions. The card includes adversarial evaluations and earlier snapshots; these examples are not deployment incident-rate estimates.

The prompting guide directly motivates avoiding premature progress-only completion on authorized long tasks, collecting worker results, and retaining real stopping conditions. Its coordination guidance supports using actual time signals without inventing urgency. The overlay does not install a continuation loop, manufacture timing telemetry, or apply chat-only anti-rethinking advice to coding agents. Existing effort settings remain unchanged.

### GPT-6.1 Sol

Source: OpenAI's [September 29 system-card addendum](https://deploymentsafety.openai.com/gpt-6-1-sol), especially sections 7.2, 7.4.1, 7.4.2, 7.5.1, and 7.6. The official PDF and relevant pages were inspected.

The [warning-respect evaluation](https://deploymentsafety.openai.com/gpt-6-1-sol/respecting-warnings), [coding-deception evaluation](https://deploymentsafety.openai.com/gpt-6-1-sol/coding-deception), and [external-agent-message evaluation](https://deploymentsafety.openai.com/gpt-6-1-sol/unintended-engagement-with-external-agent-messages) motivate distinguishing repairable technical failures from denied authority, reporting failed tools and unverified claims, and not treating peer requests as new authorization. These are our conservative adaptations, not a published Sol-specific prompting recipe. No generic guide for another model is presented as Sol guidance.

## Limits

Hooks append conversation context; they cannot erase earlier injections or inherited history. The model-scoped header and Claude retirement reminder are behavioral guidance, not a security boundary. Start a fresh conversation without inherited history for strict separation after switching models. Claude's documented one-turn fallback chain does not fire `PostModelSwitch`; neither selector can discover a hidden server-side substitution. Codex's prompt hook is not a per-request filter.

Codex may inject the same short overlay at startup and again on prompt submission. This intentional stateless tradeoff handles later model selection without a session database. It has a token cost; measure it before expanding either overlay. Codex's `PreModelRequest` is diagnostic and cannot inject model-visible context, so it is not used. See the [Codex hooks contract](https://learn.chatgpt.com/docs/hooks).

Claude native child hooks are not registered: their documented input does not guarantee the child's model ID. Do not infer it from `god`. External Pi/Command Code workers receive their existing policies, not these parent overlays. The private `sbx` home does not import normal user hook/settings state, so this change does not automatically activate overlays there or expand sandbox access.

## Verify

Run `python3 -I -S dotfiles/model-overlay-test.py`. The offline tests exercise exact selection, no-op cases, lifecycle reloads, switching away, child-vs-parent selection, malformed inputs, file failures, and actual registered commands through installed symlinks in a scratch home with spaces.

These tests prove selector and configuration behavior, not live model compliance. Before claiming an improvement, compare identical representative tasks with and without the overlay at the same model, effort, tools, and repository revision. Record acceptance, owner interventions, unjustified retries, tool calls, tokens, and wall time. Keep the delta only when it earns its cost. Live authenticated harness tests and comparative model evaluations were not run during this change.
