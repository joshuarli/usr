# USR-5: Push rules do not require user approval

Status: draft

Date: 2026-10-13

## Summary

The current Codex command rules and global Git hook do not establish user approval before every push. This RFC compares where to require that approval, and which approvals an agent cannot supply itself.

## Motivation

The Codex profile uses `approval_policy = "never"`, a prefix rule misses commands such as `git -C . push`, and the pre-push hook only checks whether stderr is a terminal. An agent's command runner can allocate a terminal, so that check does not separate the user from the agent. For Claude, the harness ask list is a prompt the user answers, which is a real boundary. Codex under `approval_policy = "never"` has none.

## Design

An approval counts only if the agent cannot produce it. A confirmation read from the controlling terminal does not meet that bar when the agent holds the terminal session, because a runner that can send input to a running command can answer the prompt itself.

Make the push credential require something only the user can do. Use a hardware-backed SSH key that requires a touch for every use (an `-sk` FIDO2 key), or a credential helper that requires biometric approval. Agent sessions then fail at the credential, and the user's own terminal pushes as before.

Keep Codex prefix rules and the pre-push hook as additional guards that make an accidental push fail early. They are not the boundary.

## Alternatives considered

- Rely on Codex prefix rules and set an approval policy that permits prompts. This still depends on matching every command form, and `approval_policy = "never"` is the setting that removes the prompt.
- Keep the terminal-presence check. This does not establish user intent.
- Confirm through `/dev/tty` in the pre-push hook. This is interactive but answerable by an agent that owns the terminal session.
- Keep push credentials out of agent sessions, for example a separate account or an SSH agent that is loaded only in the user's shell. This works without hardware, but depends on the harness not inheriting the environment.
- Require the user to perform every push outside the agent. This is simple but removes the ability to delegate an explicitly requested push.

## Open questions

- Is a touch-required key acceptable for every push, including scripted ones such as `setup-git-client.sh --push`?
- Should the Codex profile also leave `approval_policy = "never"` for sessions that have push credentials in scope?

## Decision

Pending owner decision. The recommended option is a user-presence credential for the push remote, with the prefix rules and the pre-push hook kept as early failures.
