# skill-usage

Count how each skill is listed and loaded across real Claude, Codex, Muse, Grok, and Pi sessions (read-only). Session parsing reuses the transcript adapters of the installed `agent-memory` package (`agent_memory.transcripts` and `agent_memory.types`); the launcher runs this script with that environment's Python, `$AGENT_MEMORY_VENV/bin/python` (default `~/d/agent-memory/.venv`).

```sh
skill-usage
skill-usage --days 7
skill-usage --show do
skill-usage selftest
```

Installed on `PATH` as `skill-usage` via a shim in `dotfiles/base/.local/bin/skill-usage`.
