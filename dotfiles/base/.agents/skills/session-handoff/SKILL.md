---
name: session-handoff
description: "Use for /session-handoff <agent> <session-id> or /session-handoff current: export a short redacted Markdown handoff that another coding agent can use. Skip normal session continuation and unrequested transcript export."
disable-model-invocation: true
metadata:
  opencode/slash: "true"
  opencode/autoinvoke: "false"
---

# Session Handoff

Export the current task or one explicitly named local coding-agent session as a portable Markdown brief. Do not resume execution, launch another harness, or publish the transcript. This skill produces a handoff; `resume-session` owns continuing work in the current agent.

## Recover the work

- For `/session-handoff <agent> <session-id>`, follow `resume-session`'s **Locate the exact session** procedure to resolve and inspect that session, including active branch ancestry. Read only the relevant events. Do not substitute another session or treat unverified summaries as facts. Stop and report if source evidence is unavailable.
- For `/session-handoff current`, use the active conversation and current repository. If its project or changes are inaccessible, label those fields unverified rather than guessing.
- Inspect the actual worktree when available (`git status`, HEAD, changed files, and focused tests). Reconcile session claims against live files and commits. A historical claim is not proof that a change landed.

## Export

Write the brief to a new `session-handoff-*.md` in `${TMPDIR:-/tmp}` with mode 0600, unless the user specifies an output path. Never overwrite a file or follow an output symlink. Keep it outside Git and don't copy entire transcripts, proprietary files, credentials, tokens, private user data, or irrelevant tool output. Redact sensitive snippets and omit details that aren't necessary to resume.

Use only these sections, deleting empty ones:

- **Goal and authority:** requested outcome, fixed constraints, permitted actions, and explicit non-goals.
- **Workspace:** project, repository, branch, HEAD, dirty paths, and the exact source session ID, with unknowns marked.
- **Decisions and evidence:** decisions already settled, primary sources, and paths to existing plans, issues, or artifacts rather than copied bodies.
- **Verified progress:** what actually landed, commands and results that were observed, and any limitations of those checks.
- **Next action:** the first unfinished step, acceptance test, blockers, and owner decisions still required.

Give the full output path and a short summary. If the content cannot be verified sufficiently, report the gap instead of producing a confident but misleading handoff.

**The test:** a fresh agent can resume from the brief without assuming completed work, leaking private data, or inheriting permissions from the source agent.

**Report:** the output path, recovered session and workspace, and any unverified fields.
