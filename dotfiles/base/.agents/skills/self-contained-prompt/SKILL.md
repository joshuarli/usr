---
name: self-contained-prompt
description: "Draft copy-ready prompts for another agent that lacks the current conversation or repository context. Skip when the user wants the underlying work performed here."
disable-model-invocation: true
metadata:
  opencode/slash: "true"
  opencode/autoinvoke: "false"
---

# Self-Contained Prompt

Turn the user's request into a prompt another agent can follow without relying on this conversation or inaccessible files.

## Rules

- **Preserve intent and authority.** State the outcome, request mode, permitted actions, exclusions, and stopping condition. A research request does not authorize account access, inference, configuration changes, repository edits, or publication unless the user explicitly authorized them.
- **Carry the needed context.** Include relevant facts, observed output, constraints, decisions already made, and known unknowns. Do not say “as above” or refer to this conversation. Include file contents or excerpts only when the recipient needs them and can’t access them independently.
- **Keep it safe.** Omit credentials and unnecessary sensitive details. Use redacted observations. Do not turn assumptions into facts or invent environment access.
- **Make research verifiable.** For current or specialized facts, ask for current primary sources, direct citations, and a clear split between verified facts, inference, and unknowns. Say when browsing or account access is unavailable.
- **Define useful completion.** State the questions to answer, expected deliverable, and evidence needed to support a recommendation. Leave unresolved owner choices explicit.
- **Keep only useful detail.** Write the shortest prompt that still gives the recipient everything needed to act independently. Adapt its structure to the task; avoid generic boilerplate.
- **Return the prompt, not the work.** Put one copy-ready prompt in a fenced block. Briefly note only material assumptions or missing inputs. Do not perform the underlying task.

**The test:** an agent with only the prompt can understand the task, stay within its authority, and produce an answer that meets the stated acceptance criteria.

**Report:** the copy-ready prompt and any material assumptions or missing inputs.
