# decide

Ask a bounded advisory decision question using Cloudflare Workers AI. It does not deploy a Worker. Installed on `PATH` as `decide` via a shim in `dotfiles/base/.local/bin/decide`.

```sh
decide doctor
vault CLOUDFLARE_API_TOKEN CLOUDFLARE_ACCOUNT_ID -- decide <<'JSON'
{"state":"A sanitized brief","questions":{"tier":{"type":"choice","instructions":"Which tier fits?","criteria":{}}}}
JSON
decide eval cases.jsonl
```

Full setup (token permissions, `vault`, budgets) lives in `docs/agent-setup.md`.
