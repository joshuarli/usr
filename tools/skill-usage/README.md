# skill-usage

Count how each skill is listed and loaded across real Claude, Codex, Muse, Grok, and Pi sessions (read-only). Session parsing reuses the adapters in [`agent-memory`](../agent-memory/README.md).

```sh
skill-usage
skill-usage --days 7
skill-usage --show do
skill-usage selftest
```

Installed on `PATH` as `skill-usage` via a shim in `dotfiles/base/.local/bin/skill-usage`.
